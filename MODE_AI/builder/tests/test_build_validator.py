from __future__ import annotations

from builder.core.build_models import BuildManifest, BuildPlan
from dataclasses import replace

import pytest

from builder.core.build_validator import (
    evaluate_validation_results, validate_build_manifest, validate_build_plan,
)


def test_valid_build_plan_passes() -> None:
    assert validate_build_plan(_build_plan()) is True


def test_invalid_build_plan_fails() -> None:
    assert validate_build_plan("not-a-build-plan") is False


def test_build_command_completion_is_not_validation():
    command = ["build"]
    plan = replace(_build_plan(), approved_commands=[command])
    assert evaluate_validation_results(plan, [{"command": command, "returncode": 0}], []) == "UNPROVEN"


def test_every_required_command_needs_evidence():
    plan = replace(_build_plan(), validation_commands=[["first"], ["second"]])
    completed = {"command": ["first"], "returncode": 0, "state": "PASSED"}
    assert evaluate_validation_results(plan, [completed], [completed]) == "UNPROVEN"


def test_python_compile_evidence_is_required():
    plan = replace(_build_plan(), required_files=["validation.py"], validation_commands=[["validate"]])
    completed = {"command": ["validate"], "returncode": 0, "state": "PASSED"}
    assert evaluate_validation_results(plan, [completed], [completed]) == "UNPROVEN"


@pytest.mark.parametrize("results", [
    [{"state": "NOT_EXECUTED"}, {"state": "FAILED"}],
    [{"state": "FAILED"}, {"state": "NOT_EXECUTED"}],
])
def test_failure_takes_precedence_over_missing_evidence(results):
    assert evaluate_validation_results(_build_plan(), [], results) == "FAIL"


def test_unknown_validation_state_cannot_pass():
    plan = replace(_build_plan(), validation_commands=[["validate"]])
    command = {"command": ["validate"], "returncode": 0}
    assert evaluate_validation_results(plan, [command], [{**command, "state": "UNKNOWN"}]) == "UNPROVEN"


def test_valid_build_manifest_passes(tmp_path) -> None:
    artifact_root = tmp_path / "artifacts"
    reports_dir = artifact_root / "reports"
    reports_dir.mkdir(parents=True)

    result_file = reports_dir / "result.txt"
    result_file.write_text("validated output", encoding="utf-8")

    manifest = BuildManifest(
        build_id="build_001",
        spec_id="spec_001",
        artifact_root=str(artifact_root),
        required_files=["reports/result.txt"],
        required_directories=["reports"],
        required_outputs=[],
        actual_files=["reports/result.txt"],
        actual_directories=["reports"],
    )

    assert validate_build_manifest(manifest) is True


def test_invalid_build_manifest_fails() -> None:
    assert validate_build_manifest("not-a-build-manifest") is False


def test_malformed_lists_rejected() -> None:
    build_plan = BuildPlan(
        build_id="build_001",
        spec_id="spec_001",
        snapshot_hash="hash",
        target_name="Diagnostic Tool",
        tool_type="diagnostic_tool",
        approved_components=[],
        required_files=[],
        required_directories=[],
        required_outputs=[],
        governance_constraints=[],
        receipt_requirements=[],
    )

    object.__setattr__(build_plan, "approved_components", "not-a-list")

    assert validate_build_plan(build_plan) is False


def _build_plan() -> BuildPlan:
    return BuildPlan(
        build_id="build_001",
        spec_id="spec_001",
        snapshot_hash="hash",
        target_name="Diagnostic Tool",
        tool_type="diagnostic_tool",
        approved_components=["validator"],
        required_files=["reports/result.txt"],
        required_directories=["reports"],
        required_outputs=[],
        governance_constraints=["no_raw_conversation"],
        receipt_requirements=["build_receipt"],
    )


def _build_manifest() -> BuildManifest:
    return BuildManifest(
        build_id="build_001",
        spec_id="spec_001",
        artifact_root="artifacts",
        required_files=["reports/result.txt"],
        required_directories=["reports"],
        required_outputs=[],
        actual_files=["reports/result.txt"],
        actual_directories=["reports"],
    )
