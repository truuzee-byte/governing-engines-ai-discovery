from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict

from builder.components.component_registry import get_component_definition
from builder.core.build_models import BuildPlan


@dataclass(frozen=True)
class ResolvedComponent:
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


def resolve_components(
    build_plan: BuildPlan,
) -> list[ResolvedComponent]:
    if not isinstance(build_plan, BuildPlan):
        raise ValueError("invalid build_plan")

    resolved_components: list[ResolvedComponent] = []

    for component_name in build_plan.approved_components:
        try:
            component_definition = get_component_definition(
                component_name,
            )

        except ValueError as exc:
            raise ValueError("unregistered component") from exc

        component_payload = component_definition.to_dict()

        if build_plan.tool_type not in component_payload["allowed_tool_types"]:
            raise ValueError("component not allowed for tool_type")

        resolved_components.append(
            ResolvedComponent(
                component_name=component_name,
                component_definition=component_payload,
            )
        )

    return resolved_components


def _require_non_empty_string(
    value: Any,
    field_name: str,
) -> None:
    if not isinstance(value, str):
        raise TypeError(f"{field_name} must be a string")

    if value.strip() == "":
        raise ValueError(f"{field_name} must not be empty")