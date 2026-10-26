from __future__ import annotations

import pytest

from builder.core.build_models import (
    BuildManifest,
    BuildPlan,
    BuildReceipt,
    BuilderOutputObject,
)


def test_build_plan_creation() -> None:
    build_plan = _build_plan()

    assert build_plan.build_id == "build_spec_diagnostic_tool_REQ-001"


def test_builder_output_object_creation() -> None:
    output = BuilderOutputObject(
        build_id="build_spec_diagnostic_tool_REQ-001",
        spec_id="spec_diagnostic_tool_REQ-001",
        artifact_root="artifacts/diagnostic",
        files_written=[],
        directories_created=[],
        validation_status="PASS",
        receipt_path="artifacts/diagnostic/build_receipt.json",
    )

    assert output.validation_status == "PASS"


def test_build_manifest_creation() -> None:
    manifest = _build_manifest()

    assert manifest.required_files == ["reports/result.txt"]


def test_build_receipt_creation() -> None:
    receipt = _build_receipt("PASS")

    assert receipt.final_status == "PASS"


def test_pass_fail_enforcement() -> None:
    BuildReceipt(
        intent_id="spec_diagnostic_tool_REQ-001",
        build_id="build_spec_diagnostic_tool_REQ-001",
        snapshot_hash="hash",
        stages_checked=[],
        drift_detected=False,
        final_status="FAIL",
    )

    with pytest.raises(ValueError):
        BuildReceipt(
            intent_id="spec_diagnostic_tool_REQ-001",
            build_id="build_spec_diagnostic_tool_REQ-001",
            snapshot_hash="hash",
            stages_checked=[],
            drift_detected=False,
            final_status="UNKNOWN",
        )


def test_deterministic_to_dict() -> None:
    build_plan = _build_plan()

    assert build_plan.to_dict() == {
        "build_id": "build_spec_diagnostic_tool_REQ-001",
        "spec_id": "spec_diagnostic_tool_REQ-001",
        "snapshot_hash": "snapshot_hash",
        "target_name": "Diagnostic Tool",
        "tool_type": "diagnostic_tool",
        "approved_components": ["validator", "reporter"],
        "required_files": ["reports/result.txt"],
        "required_directories": ["reports"],
        "required_outputs": [],
        "governance_constraints": ["no_raw_conversation"],
        "receipt_requirements": ["build_receipt"],
        "approved_commands": [],
        "approved_files": {},
        "authorized_create_scope": [],
        "authorized_delete_scope": [],
        "authorized_read_scope": [],
        "authorized_write_scope": [],
        "completion_requirements": [],
        "evidence_requirements": [],
        "existing_files": [],
        "repository_target": "",
        "validation_commands": [],
        "validation_requirements": [],
    }
    


def test_invalid_status_rejection() -> None:
    with pytest.raises(ValueError):
        BuilderOutputObject(
            build_id="build_spec_diagnostic_tool_REQ-001",
            spec_id="spec_diagnostic_tool_REQ-001",
            artifact_root="artifacts/diagnostic",
            files_written=[],
            directories_created=[],
            validation_status="INVALID",
            receipt_path="artifacts/diagnostic/build_receipt.json",
        )


def test_empty_required_string_rejection() -> None:
    with pytest.raises(ValueError):
        BuildPlan(
            build_id="",
            spec_id="spec_diagnostic_tool_REQ-001",
            snapshot_hash="snapshot_hash",
            target_name="Diagnostic Tool",
            tool_type="diagnostic_tool",
            approved_components=[],
            required_files=[],
            required_directories=[],
            required_outputs=[],
            governance_constraints=[],
            receipt_requirements=[],
        )


def _build_plan() -> BuildPlan:
    return BuildPlan(
        build_id="build_spec_diagnostic_tool_REQ-001",
        spec_id="spec_diagnostic_tool_REQ-001",
        snapshot_hash="snapshot_hash",
        target_name="Diagnostic Tool",
        tool_type="diagnostic_tool",
        approved_components=["validator", "reporter"],
        required_files=["reports/result.txt"],
        required_directories=["reports"],
        required_outputs=[],
        governance_constraints=["no_raw_conversation"],
        receipt_requirements=["build_receipt"],
    )


def _build_manifest() -> BuildManifest:
    return BuildManifest(
        build_id="build_spec_diagnostic_tool_REQ-001",
        spec_id="spec_diagnostic_tool_REQ-001",
        artifact_root="artifacts/diagnostic",
        required_files=["reports/result.txt"],
        required_directories=["reports"],
        required_outputs=[],
        actual_files=[],
        actual_directories=[],
    )


def _build_receipt(final_status: str) -> BuildReceipt:
    return BuildReceipt(
        intent_id="spec_diagnostic_tool_REQ-001",
        build_id="build_spec_diagnostic_tool_REQ-001",
        snapshot_hash="snapshot_hash",
        stages_checked=["build_plan_generated"],
        drift_detected=False,
        final_status=final_status,
    )