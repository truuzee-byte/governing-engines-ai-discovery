from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict

from builder.components.component_resolver import ResolvedComponent


@dataclass(frozen=True)
class LoadedComponent:
    component_name: str
    component_definition: Dict[str, Any]

    def __post_init__(self) -> None:
        _require_non_empty_string(self.component_name, "component_name")

        if not isinstance(self.component_definition, dict):
            raise TypeError("component_definition must be a dictionary")

    def to_dict(self) -> Dict[str, Any]:
        return {
            "component_name": self.component_name,
            "component_definition": dict(self.component_definition),
        }


def load_components(
    resolved_components: list,
) -> list[LoadedComponent]:
    if not isinstance(resolved_components, list):
        raise ValueError("resolved_components must be a list")

    loaded_components: list[LoadedComponent] = []

    for resolved_component in resolved_components:
        if not isinstance(resolved_component, ResolvedComponent):
            raise ValueError("invalid resolved component")

        component_definition = resolved_component.component_definition

        if not isinstance(component_definition, dict):
            raise ValueError("missing component_definition")

        if len(component_definition) == 0:
            raise ValueError("missing component_definition")

        loaded_components.append(
            LoadedComponent(
                component_name=resolved_component.component_name,
                component_definition=dict(component_definition),
            )
        )

    return loaded_components


def _require_non_empty_string(
    value: Any,
    field_name: str,
) -> None:
    if not isinstance(value, str):
        raise TypeError(f"{field_name} must be a string")

    if value.strip() == "":
        raise ValueError(f"{field_name} must not be empty")