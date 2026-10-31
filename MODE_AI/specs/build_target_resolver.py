from __future__ import annotations

from typing import Any, Dict, Optional

from specs.validator_result import ValidatorResult


SUPPORTED_TOOL_TYPES = {
    "audit_tool",
    "diagnostic_tool",
    "validation_tool",
    "workflow_tool",
    "pipeline_tool",
    "governance_tool",
    "analysis_tool",
}


def resolve_build_target(
    specification_object: dict,
) -> dict:
    validation_result = validate_build_target(
        specification_object,
    )

    if validation_result.failed():
        raise ValueError(validation_result.failure_reason)

    structure = specification_object["structure"]

    runtime_target: Optional[str] = structure.get("runtime_target")

    if runtime_target is not None and not isinstance(runtime_target, str):
        runtime_target = None

    return {
        "target_name": structure["system_name"],
        "tool_type": structure["tool_type"],
        "system_name": structure["system_name"],
        "runtime_target": runtime_target,
        "spec_id": specification_object["spec_id"],
        "spec_reference": specification_object["spec_id"],
        "authority_state": specification_object["authority_state"],
    }


def validate_build_target(
    specification_object: dict,
) -> ValidatorResult:
    if not isinstance(specification_object, dict):
        return ValidatorResult.fail_result(
            failure_reason="specification_object must be a dictionary",
            source_stage="build_target_resolver",
        )

    if specification_object.get("object_type") != "SpecificationObject":
        return ValidatorResult.fail_result(
            failure_reason="invalid object_type",
            failing_field="object_type",
            source_stage="build_target_resolver",
        )

    if specification_object.get("spec_class") != "BuildSpec":
        return ValidatorResult.fail_result(
            failure_reason="unsupported spec_class",
            failing_field="spec_class",
            source_stage="build_target_resolver",
        )

    structure = specification_object.get("structure")

    if not isinstance(structure, dict):
        return ValidatorResult.fail_result(
            failure_reason="structure must be a dictionary",
            failing_field="structure",
            source_stage="build_target_resolver",
        )

    if "system_name" not in structure:
        return ValidatorResult.fail_result(
            failure_reason="missing system_name",
            failing_field="structure.system_name",
            source_stage="build_target_resolver",
        )

    if not _is_non_empty_string(structure["system_name"]):
        return ValidatorResult.fail_result(
            failure_reason="invalid system_name",
            failing_field="structure.system_name",
            source_stage="build_target_resolver",
        )

    if "tool_type" not in structure:
        return ValidatorResult.fail_result(
            failure_reason="missing tool_type",
            failing_field="structure.tool_type",
            source_stage="build_target_resolver",
        )

    if not _is_non_empty_string(structure["tool_type"]):
        return ValidatorResult.fail_result(
            failure_reason="invalid tool_type",
            failing_field="structure.tool_type",
            source_stage="build_target_resolver",
        )

    if not is_supported_tool_type(structure["tool_type"]):
        return ValidatorResult.fail_result(
            failure_reason="unsupported tool_type",
            failing_field="structure.tool_type",
            source_stage="build_target_resolver",
        )

    if "spec_id" not in specification_object:
        return ValidatorResult.fail_result(
            failure_reason="missing spec_id",
            failing_field="spec_id",
            source_stage="build_target_resolver",
        )

    if not _is_non_empty_string(specification_object["spec_id"]):
        return ValidatorResult.fail_result(
            failure_reason="invalid spec_id",
            failing_field="spec_id",
            source_stage="build_target_resolver",
        )

    if "authority_state" not in specification_object:
        return ValidatorResult.fail_result(
            failure_reason="missing authority_state",
            failing_field="authority_state",
            source_stage="build_target_resolver",
        )

    if not _is_non_empty_string(specification_object["authority_state"]):
        return ValidatorResult.fail_result(
            failure_reason="invalid authority_state",
            failing_field="authority_state",
            source_stage="build_target_resolver",
        )

    return ValidatorResult.pass_result(
        source_stage="build_target_resolver",
        validation_notes=[
            "build target resolved",
        ],
    )


def is_supported_tool_type(
    tool_type: str,
) -> bool:
    if not isinstance(tool_type, str):
        return False

    return tool_type.strip() in SUPPORTED_TOOL_TYPES


def _is_non_empty_string(
    value: Any,
) -> bool:
    return isinstance(value, str) and value.strip() != ""