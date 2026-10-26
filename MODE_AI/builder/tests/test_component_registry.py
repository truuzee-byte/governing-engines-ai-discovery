from __future__ import annotations

import pytest

from builder.components.component_registry import (
    ComponentDefinition,
    get_component_definition,
    is_registered_component,
)


def test_all_required_components_registered() -> None:
    for component_name in (
        "validator",
        "reporter",
        "receipt_writer",
        "manifest_validator",
        "workspace_manager",
        "file_writer",
        "command_runner",
    ):
        assert is_registered_component(component_name) is True


def test_get_component_definition_works() -> None:
    definition = get_component_definition("validator")

    assert definition.component_name == "validator"


def test_unregistered_component_rejected() -> None:
    with pytest.raises(ValueError, match="unregistered component"):
        get_component_definition("missing_component")


def test_is_registered_component_true_false_behavior() -> None:
    assert is_registered_component("validator") is True
    assert is_registered_component("missing_component") is False


def test_invalid_artifact_types_rejected() -> None:
    with pytest.raises(TypeError):
        ComponentDefinition(
            component_name="bad",
            component_type="bad",
            allowed_tool_types="not-a-list",
            required_files=[],
            required_directories=[],
            governance_constraints=[],
        )