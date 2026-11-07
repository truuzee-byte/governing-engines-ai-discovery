from __future__ import annotations

import pytest

from builder.components.component_resolver import ResolvedComponent, resolve_components
from builder.core.build_models import BuildPlan


def test_valid_components_resolve() -> None:
    resolved = resolve_components(_build_plan())

    assert len(resolved) == 2
    assert all(isinstance(item, ResolvedComponent) for item in resolved)


def test_resolved_components_preserve_definitions() -> None:
    resolved = resolve_components(_build_plan())

    assert resolved[0].component_definition["component_name"] == "validator"


def test_unregistered_component_rejected() -> None:
    plan = _build_plan(approved_components=["missing_component"])

    with pytest.raises(ValueError, match="unregistered component"):
        resolve_components(plan)


def test_invalid_build_plan_rejected() -> None:
    with pytest.raises(ValueError, match="invalid build_plan"):
        resolve_components("not-a-build-plan")


def test_unsupported_tool_type_rejected() -> None:
    plan = _build_plan(tool_type="unsupported_tool")

    with pytest.raises(ValueError, match="component not allowed for tool_type"):
        resolve_components(plan)


def test_component_not_allowed_for_tool_type_rejected(monkeypatch) -> None:
    from builder.components import component_resolver

    class FakeDefinition:
        def to_dict(self):
            return {
                "component_name": "validator",
                "component_type": "validation",
                "allowed_tool_types": ["other_tool"],
                "required_files": [],
                "required_directories": [],
                "governance_constraints": [],
            }

    monkeypatch.setattr(
        component_resolver,
        "get_component_definition",
        lambda component_name: FakeDefinition(),
    )

    with pytest.raises(ValueError, match="component not allowed for tool_type"):
        resolve_components(_build_plan())


def _build_plan(
    approved_components: list | None = None,
    tool_type: str = "diagnostic_tool",
) -> BuildPlan:
    return BuildPlan(
        build_id="build_001",
        spec_id="spec_001",
        snapshot_hash="hash",
        target_name="Diagnostic Tool",
        tool_type=tool_type,
        approved_components=approved_components or ["validator", "reporter"],
        required_files=[],
        required_directories=[],
        required_outputs=[],
        governance_constraints=[],
        receipt_requirements=[],
    )