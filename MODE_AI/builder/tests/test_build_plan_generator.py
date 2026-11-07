from __future__ import annotations

import copy
import json
import sys
from dataclasses import fields

import pytest

from builder.core.build_plan_generator import generate_build_plan
from builder.core.build_models import BuildPlan
from builder.core import build_entry
from builder.handoff.specification_receiver import receive_specification
from specs.handoff_gate import approve_builder_handoff
from specs.spec_engine import create_specification_object
from specs.spec_snapshot import create_spec_snapshot


def test_valid_handoff_generates_build_plan() -> None:
    build_plan = generate_build_plan(_valid_handoff_payload())

    assert build_plan.target_name == "Diagnostic Tool"


def test_build_id_generated_correctly() -> None:
    build_plan = generate_build_plan(_valid_handoff_payload())

    assert build_plan.build_id == f"build_{build_plan.spec_id}"


def test_spec_continuity_preserved() -> None:
    handoff = _valid_handoff_payload()
    build_plan = generate_build_plan(handoff)

    assert build_plan.spec_id == handoff["specification_object"]["spec_id"]
    assert build_plan.snapshot_hash == handoff["spec_hash"]


def test_required_files_and_directories_preserved() -> None:
    build_plan = generate_build_plan(_valid_handoff_payload())

    assert build_plan.required_files == ["reports/result.txt"]
    assert build_plan.required_directories == ["reports"]


def test_artifact_structure_required() -> None:
    handoff = _valid_handoff_payload()
    handoff["specification_object"].pop("artifact_structure")

    with pytest.raises(ValueError, match="missing artifact_structure"):
        generate_build_plan(handoff)


def test_invalid_handoff_payload_rejected() -> None:
    with pytest.raises(ValueError, match="invalid handoff payload"):
        generate_build_plan("not-a-dict")


def test_missing_specification_object_rejected() -> None:
    handoff = _valid_handoff_payload()
    handoff.pop("specification_object")

    with pytest.raises(ValueError, match="missing specification_object"):
        generate_build_plan(handoff)


def test_missing_snapshot_rejected() -> None:
    handoff = _valid_handoff_payload()
    handoff.pop("snapshot")

    with pytest.raises(ValueError, match="missing snapshot"):
        generate_build_plan(handoff)


def test_missing_structure_rejected() -> None:
    handoff = _valid_handoff_payload()
    handoff["specification_object"].pop("structure")

    with pytest.raises(ValueError, match="missing structure"):
        generate_build_plan(handoff)


def test_invalid_artifact_structure_rejected() -> None:
    handoff = _valid_handoff_payload()
    handoff["specification_object"]["artifact_structure"] = "invalid"

    with pytest.raises(ValueError, match="invalid artifact_structure"):
        generate_build_plan(handoff)


def test_fully_populated_specification_reaches_real_execution(monkeypatch, tmp_path) -> None:
    request = _valid_interpreted_build_request()
    contents = {"reports/result.py": "value = 'approved ✓'\n", "existing.txt": "modified\n"}
    request["artifact_structure"] = {
        "files": list(contents), "directories": ["reports"],
        "approved_files": contents, "existing_files": ["existing.txt"],
        "required_outputs": ["reports/result.py", "existing.txt"],
    }
    request["execution"] = {
        "repository_target": str(tmp_path),
        "authorized_read_scope": ["input.txt"],
        "authorized_write_scope": ["existing.txt"],
        "authorized_create_scope": ["reports/result.py"],
        "authorized_delete_scope": ["obsolete.txt"],
        "approved_commands": [[sys.executable, "-B", "-c", "assert 2 + 2 == 4"]],
    }
    request["validation"] = {
        "requirements": ["approved file contents match"],
        "commands": [[sys.executable, "-B", "-c",
                      "from pathlib import Path; "
                      f"expected = {contents!r}; "
                      "assert all(Path(p).read_text(encoding='utf-8') == s for p, s in expected.items())"]],
    }
    request["evidence"] = {"requirements": ["command results"]}
    request["completion"] = {"requirements": ["receipt written"]}
    original = copy.deepcopy(request)
    spec = create_specification_object(request)
    handoff = json.loads(json.dumps(approve_builder_handoff(spec, create_spec_snapshot(spec))))
    received = receive_specification(handoff)
    assert received.specification_object == spec
    for block in ("artifact_structure", "execution", "validation", "evidence", "completion"):
        assert spec[block] == original[block]

    # Explicit canonical transformations: source structure fields are nested;
    # artifact names gain required_ prefixes; build identity derives from spec.
    expected = {
        "build_id": f"build_{spec['spec_id']}", "spec_id": spec["spec_id"],
        "snapshot_hash": handoff["spec_hash"], "target_name": original["system_name"],
        "tool_type": original["tool_type"],
        "approved_components": original["approved_components"],
        "governance_constraints": original["governance_constraints"],
        "receipt_requirements": original["receipt_requirements"],
        "required_files": original["artifact_structure"]["files"],
        "required_directories": original["artifact_structure"]["directories"],
        "required_outputs": original["artifact_structure"]["required_outputs"],
        "approved_files": contents, "existing_files": ["existing.txt"],
        **original["execution"],
        "validation_commands": original["validation"]["commands"],
        "validation_requirements": original["validation"]["requirements"],
        "evidence_requirements": original["evidence"]["requirements"],
        "completion_requirements": original["completion"]["requirements"],
    }
    assert set(expected) == {field.name for field in fields(BuildPlan)}
    captured = []

    def capture(payload):
        plan = generate_build_plan(payload)
        captured.append(plan.to_dict())
        return plan

    monkeypatch.setattr(build_entry, "generate_build_plan", capture)
    (tmp_path / "existing.txt").write_text("original", encoding="utf-8")
    output = build_entry.run_builder_core(handoff, str(tmp_path))
    assert captured == [expected]
    # The prose constraint is preserved but has no executable proof contract.
    assert output.validation_status == "UNPROVEN"
    assert any(c.get('requirement') == 'no_raw_conversation' and c['state'] == 'UNPROVEN'
               for c in output.validation_results)
    for path, content in contents.items():
        assert (tmp_path / path).read_text(encoding="utf-8") == content
    assert request == original


@pytest.mark.parametrize("block,field,value", [
    ("execution", "repository_target", None),
    ("execution", "authorized_create_scope", "file.py"),
    ("execution", "approved_commands", ["python test.py"]),
    ("execution", "approved_commands", [["python", 1]]),
    ("execution", "approved_commands", [[]]),
    ("validation", "commands", "python test.py"),
    ("validation", "requirements", "must validate"),
    ("evidence", "requirements", {"required": True}),
    ("completion", "requirements", [None]),
    ("artifact_structure", "approved_files", {"file.py": 123}),
    ("artifact_structure", "approved_files", {1: "value"}),
    ("artifact_structure", "existing_files", "file.py"),
    ("artifact_structure", "required_outputs", "file.py"),
    ("execution", "requirements", ["unsupported operation"]),
    ("execution", "artifact_root", "unrepresentable target"),
    ("artifact_structure", "component_metadata", {"custom": True}),
])
def test_malformed_or_unrepresentable_fields_fail_closed(block, field, value) -> None:
    request = _valid_interpreted_build_request()
    request.setdefault(block, {})[field] = value
    spec = create_specification_object(request)
    handoff = approve_builder_handoff(spec, create_spec_snapshot(spec))
    with pytest.raises(ValueError):
        generate_build_plan(handoff)


@pytest.mark.parametrize("block", ["evidence", "completion"])
def test_malformed_requirement_block_is_not_discarded(block) -> None:
    handoff = _valid_handoff_payload()
    handoff["specification_object"][block] = ["must not disappear"]
    with pytest.raises(ValueError, match=f"invalid {block}"):
        generate_build_plan(handoff)


@pytest.mark.parametrize("block,field", [
    ("structure", "tool_type"), ("structure", "approved_components"),
    ("structure", "governance_constraints"), ("structure", "receipt_requirements"),
    ("artifact_structure", "files"), ("artifact_structure", "directories"),
])
def test_missing_canonical_fields_are_not_defaulted(block, field) -> None:
    handoff = _valid_handoff_payload()
    handoff["specification_object"][block].pop(field)
    with pytest.raises(ValueError):
        generate_build_plan(handoff)


@pytest.mark.parametrize("field", [
    "files", "directories", "approved_files", "repository_target", "artifact_root",
    "authorized_create_scope", "authorized_write_scope", "execution_requirements",
    "validation_commands", "validation_requirements", "evidence_requirements",
    "component_metadata",
])
def test_misplaced_builder_fields_cannot_disappear_in_factory(field) -> None:
    request = _valid_interpreted_build_request()
    request[field] = ["required"]
    with pytest.raises(ValueError, match="unsupported or misplaced Builder fields"):
        create_specification_object(request)


def _valid_handoff_payload() -> dict:
    spec = create_specification_object(_valid_interpreted_build_request())
    snapshot = create_spec_snapshot(spec)

    return copy.deepcopy(approve_builder_handoff(spec, snapshot))


def _valid_interpreted_build_request() -> dict:
    return {
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
        "governance_constraints": ["no_raw_conversation"],
        "execution_authority": "operator_confirmed",
        "receipt_requirements": ["build_receipt"],
        "runtime_target": None,
        "source_trace_reference": "trace_source_REQ-001",
        "artifact_structure": {
            "directories": ["reports"],
            "files": ["reports/result.txt"],
        },
    }
