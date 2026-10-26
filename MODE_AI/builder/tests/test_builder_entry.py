from __future__ import annotations

import hashlib
import json
from pathlib import Path
import subprocess
import sys

import pytest

from builder.core.builder_entry import run_builder_core
from builder.core.build_models import BuilderOutputObject
from specs.handoff_gate import approve_builder_handoff
from specs.spec_engine import create_specification_object
from specs.spec_snapshot import create_spec_snapshot
from builder.kernel.kernel_client import BootstrapKernelClient

def test_run_builder_core_returns_builder_output_object(tmp_path) -> None:
    output = run_builder_core(_valid_handoff_payload(root=tmp_path), str(tmp_path))

    assert isinstance(output, BuilderOutputObject)


def test_receipt_file_generated(tmp_path) -> None:
    output = run_builder_core(_valid_handoff_payload(root=tmp_path), str(tmp_path))

    assert (tmp_path / ".builder_metadata" / "build_receipt.json").exists()
    assert output.receipt_path.endswith("build_receipt.json")


def test_validation_status_pass_on_valid_build(tmp_path) -> None:
    output = run_builder_core(_valid_handoff_payload(root=tmp_path), str(tmp_path))

    assert output.validation_status == "PASS"


def test_invalid_build_plan_rejected(tmp_path) -> None:
    handoff = _valid_handoff_payload(root=tmp_path)
    handoff["specification_object"]["artifact_structure"] = "invalid"

    with pytest.raises(ValueError):
        run_builder_core(handoff, str(tmp_path))


def test_invalid_build_manifest_rejected(monkeypatch, tmp_path) -> None:
    monkeypatch.setattr(
        "builder.core.build_entry.validate_manifest_integrity",
        lambda build_manifest: False,
    )

    output = run_builder_core(
        _valid_handoff_payload(root=tmp_path),
        str(tmp_path),
    )

    assert output.validation_status == "FAIL"
    assert "manifest_failed" in json.loads(Path(output.receipt_path).read_text())["stages_checked"]

def test_receipt_path_generated_correctly(tmp_path) -> None:
    output = run_builder_core(_valid_handoff_payload(root=tmp_path), str(tmp_path))

    assert output.receipt_path == str(tmp_path / ".builder_metadata" / "build_receipt.json")


def _valid_handoff_payload(*, root, files=None, commands=None, requirements=None) -> dict:
    if files is None:
        files = {"reports/result.txt": "validated output"}
    if commands is None:
        commands = [[sys.executable, "-B", "-c",
                     "from pathlib import Path; assert Path('reports/result.txt').read_text() == 'validated output'"]]
    spec = create_specification_object(
        {
            "request_id": "REQ-001",
            "authority_state": "handoff_approved",
            "validation_state": "valid",
            "readiness_state": "ready_for_build",
            "save_ready_state": True,
            "clarification_required": False,
            "system_name": "Diagnostic Tool",
            "system_purpose": "Validate runtime construction behavior",
            "tool_type": "diagnostic_tool",
            "construction_scope": ["create_files", "validate_outputs"],
            "approved_components": ["validator", "reporter"],
            "governance_constraints": [],
            "execution_authority": "operator_confirmed",
            "receipt_requirements": ["build_receipt"],
            "runtime_target": None,
            "source_trace_reference": "trace_source_REQ-001",
            "artifact_structure": {
                "directories": ["reports"],
                "files": list(files),
            },
        }
    )
    # Supply current Builder fields before hashing; the legacy spec factory
    # intentionally does not preserve these extension fields.
    spec["artifact_structure"]["approved_files"] = files
    spec["execution"] = {"repository_target": str(root), "authorized_create_scope": list(files), "approved_commands": []}
    spec["validation"] = {
        "commands": commands,
        "requirements": requirements if requirements is not None else ["required_validation_must_execute"],
    }
    snapshot = create_spec_snapshot(spec)
    return approve_builder_handoff(spec, snapshot)


def _assert_evidence(output, expected_status):
    receipt = json.loads(Path(output.receipt_path).read_text())
    evidence = json.loads(Path(output.evidence_references[0]).read_text())
    assert output.validation_status == receipt["final_status"] == evidence["validation_status"] == expected_status
    assert output.validation_results == receipt["validation_results"] == evidence["validation_results"]
    assert output.command_results == receipt["commands_executed"] == evidence["command_results"]
    return evidence


def test_valid_python_passes_only_after_declared_validation(tmp_path):
    command = [sys.executable, "-B", "-c",
               "import runpy; assert runpy.run_path('validation.py')['answer'] == 42"]
    output = run_builder_core(_valid_handoff_payload(root=tmp_path,
        files={"validation.py": "answer = 42\n"}, commands=[command]), str(tmp_path))
    evidence = _assert_evidence(output, "PASS")
    assert output.command_results[0]["command"] == command
    assert output.command_results[0]["returncode"] == 0
    check = next(r for r in output.validation_results if r.get("validation_type") == "python_compile")
    assert check["state"] == "PASSED"
    assert check["executed"] is True
    assert check["sha256"] == evidence["file_hashes"]["validation.py"]
    assert not list(tmp_path.rglob("*.pyc"))


def test_historical_truncated_python_cannot_pass(tmp_path):
    broken = (Path(__file__).parents[1] / "outputs" / "builds" /
              "spec_interaction-004559b1f0894095bd78267595740b15" / "validation.py").read_text()
    assert broken.rstrip().endswith("class")
    command = [sys.executable, "-B", "-c",
               "from pathlib import Path; assert Path('validation.py').read_text().rstrip().endswith('class')"]
    output = run_builder_core(_valid_handoff_payload(root=tmp_path,
        files={"validation.py": broken}, commands=[command]), str(tmp_path))
    _assert_evidence(output, "FAIL")
    assert output.command_results[0]["returncode"] == 0
    check = next(r for r in output.validation_results if r.get("validation_type") == "python_compile")
    assert check["state"] == "FAILED"
    assert check["error_type"] == "SyntaxError"


@pytest.mark.parametrize("requirements", [[], ["required_validation_must_execute"]])
def test_no_executable_validation_is_unproven(tmp_path, requirements):
    output = run_builder_core(_valid_handoff_payload(root=tmp_path,
        files={"validation.py": "answer = 42\n"}, commands=[], requirements=requirements), str(tmp_path))
    _assert_evidence(output, "UNPROVEN")
    assert any(r.get("validation_type") == "python_compile" and r["state"] == "PASSED"
               for r in output.validation_results)
    assert any(r["state"] == "UNPROVEN" and r["executed"] is False for r in output.validation_results)


def test_validation_command_failure_reaches_receipt(tmp_path):
    commands = [[sys.executable, "-B", "-c", "raise SystemExit(7)"],
                [sys.executable, "-B", "-c", "print('second validation ran')"]]
    output = run_builder_core(_valid_handoff_payload(root=tmp_path,
        files={"validation.py": "answer = 42\n"}, commands=commands), str(tmp_path))
    _assert_evidence(output, "FAIL")
    assert [r["returncode"] for r in output.command_results] == [7, 0]
    assert "second validation ran" in output.command_results[1]["stdout"]


def test_compile_checks_final_bytes_after_commands(tmp_path):
    command = [sys.executable, "-B", "-c",
               "from pathlib import Path; Path('validation.py').write_text('class')"]
    output = run_builder_core(_valid_handoff_payload(root=tmp_path,
        files={"validation.py": "answer = 42\n"}, commands=[command]), str(tmp_path))
    evidence = _assert_evidence(output, "FAIL")
    assert evidence["file_hashes"]["validation.py"] == hashlib.sha256(b"class").hexdigest()


@pytest.mark.parametrize("error", [OSError("cannot launch"), subprocess.TimeoutExpired(["validate"], 1)])
def test_command_execution_error_is_recorded(tmp_path, monkeypatch, error):
    def fail_command(self, commands, approved_commands):
        raise error
    monkeypatch.setattr(BootstrapKernelClient, "run_commands", fail_command)
    output = run_builder_core(_valid_handoff_payload(root=tmp_path), str(tmp_path))
    _assert_evidence(output, "FAIL")
    assert output.command_results[0]["error_type"] == type(error).__name__


def test_missing_command_result_is_unproven(tmp_path, monkeypatch):
    monkeypatch.setattr(BootstrapKernelClient, "run_commands", lambda *args: [])
    output = run_builder_core(_valid_handoff_payload(root=tmp_path), str(tmp_path))
    _assert_evidence(output, "UNPROVEN")
    assert any(r["state"] == "NOT_EXECUTED" for r in output.validation_results)
