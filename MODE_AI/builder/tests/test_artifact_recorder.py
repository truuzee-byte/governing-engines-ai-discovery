from __future__ import annotations

import pytest

from builder.core.artifact_recorder import create_build_manifest
from builder.core.build_models import BuildPlan


def test_build_manifest_created_correctly() -> None:
    manifest = create_build_manifest(
        build_plan=_build_plan(),
        artifact_root="artifacts",
        actual_files=[],
        actual_directories=[],
    )

    assert manifest.artifact_root == "artifacts"


def test_build_plan_continuity_preserved() -> None:
    build_plan = _build_plan()
    manifest = create_build_manifest(build_plan, "artifacts", [], [])

    assert manifest.build_id == build_plan.build_id
    assert manifest.spec_id == build_plan.spec_id


def test_required_files_preserved() -> None:
    manifest = create_build_manifest(_build_plan(), "artifacts", [], [])

    assert manifest.required_files == ["reports/result.txt"]


def test_required_directories_preserved() -> None:
    manifest = create_build_manifest(_build_plan(), "artifacts", [], [])

    assert manifest.required_directories == ["reports"]


def test_invalid_build_plan_rejected() -> None:
    with pytest.raises(TypeError):
        create_build_manifest("not-a-build-plan", "artifacts", [], [])


def test_empty_artifact_root_rejected() -> None:
    with pytest.raises(ValueError):
        create_build_manifest(_build_plan(), "", [], [])


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