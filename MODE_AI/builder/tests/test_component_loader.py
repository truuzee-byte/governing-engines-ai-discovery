from __future__ import annotations

import pytest

from builder.components.component_loader import LoadedComponent, load_components
from builder.components.component_resolver import ResolvedComponent


def test_valid_resolved_component_loads() -> None:
    loaded = load_components([_resolved_component()])

    assert len(loaded) == 1
    assert isinstance(loaded[0], LoadedComponent)


def test_invalid_resolved_component_rejected() -> None:
    with pytest.raises(ValueError, match="invalid resolved component"):
        load_components(["not-a-resolved-component"])


def test_missing_component_definition_rejected() -> None:
    resolved = ResolvedComponent(
        component_name="validator",
        component_definition={},
    )

    with pytest.raises(ValueError, match="missing component_definition"):
        load_components([resolved])


def test_invalid_resolved_components_input_rejected() -> None:
    with pytest.raises(ValueError, match="resolved_components must be a list"):
        load_components("not-a-list")


def _resolved_component() -> ResolvedComponent:
    return ResolvedComponent(
        component_name="validator",
        component_definition={
            "component_name": "validator",
            "component_type": "validation",
            "allowed_tool_types": ["diagnostic_tool"],
            "required_files": [],
            "required_directories": [],
            "governance_constraints": [],
        },
    )