from __future__ import annotations

from typing import Any, Dict

from specs.validator_result import ValidatorResult


REQUIRED_SPECIFICATION_OBJECT_FIELDS = (
    "object_type",
    "object_version",
    "spec_id",
    "spec_class",
    "metadata",
    "structure",
    "dependencies",
    "authority_state",
    "validation_state",
    "readiness_state",
    "save_ready_state",
    "clarification_required",
    "trace_log",
    "lineage",
)

ALLOWED_SPEC_CLASS_VALUES = {
    "BuildSpec",
}

ALLOWED_AUTHORITY_STATE_VALUES = {
    "draft_only",
    "pending_save",
    "save_confirmed",
    "handoff_approved",
    "authority_granted",
}

BUILDER_AUTHORITY_STATE_VALUES = {
    "handoff_approved",
    "authority_granted",
}

REQUIRED_TRACE_LOG_FIELDS = (
    "trace_id",
    "source_system",
    "interpretation_trace_reference",
    "validation_trace_reference",
    "handoff_trace_reference",
)

REQUIRED_LINEAGE_FIELDS = (
    "lineage_id",
    "parent_refs",
    "source_refs",
    "revision_history",
    "created_from",
    "current_version",
)

REQUIRED_BUILDSPEC_STRUCTURE_FIELDS = (
    "intent_id",
    "system_name",
    "tool_type",
    "construction_scope",
    "approved_components",
    "governance_constraints",
    "execution_authority",
    "receipt_requirements",
)


def validate_specification_object(
    specification_object: dict,
) -> ValidatorResult:
    if not isinstance(specification_object, dict):
        return ValidatorResult.fail_result(
            failure_reason="specification_object must be a dictionary",
            source_stage="spec_validator",
        )

    for field_name in REQUIRED_SPECIFICATION_OBJECT_FIELDS:
        if field_name not in specification_object:
            return ValidatorResult.fail_result(
                failure_reason="missing required SpecificationObject field",
                failing_field=field_name,
                source_stage="spec_validator",
            )

    if specification_object["object_type"] != "SpecificationObject":
        return ValidatorResult.fail_result(
            failure_reason="invalid object_type",
            failing_field="object_type",
            source_stage="spec_validator",
        )

    if specification_object["spec_class"] not in ALLOWED_SPEC_CLASS_VALUES:
        return ValidatorResult.fail_result(
            failure_reason="unsupported spec_class",
            failing_field="spec_class",
            source_stage="spec_validator",
        )

    if specification_object["authority_state"] not in ALLOWED_AUTHORITY_STATE_VALUES:
        return ValidatorResult.fail_result(
            failure_reason="invalid authority_state",
            failing_field="authority_state",
            source_stage="spec_validator",
        )

    if not isinstance(specification_object["metadata"], dict):
        return ValidatorResult.fail_result(
            failure_reason="metadata must be a dictionary",
            failing_field="metadata",
            source_stage="spec_validator",
        )

    if not isinstance(specification_object["dependencies"], list):
        return ValidatorResult.fail_result(
            failure_reason="dependencies must be a list",
            failing_field="dependencies",
            source_stage="spec_validator",
        )

    trace_result = validate_trace_log(
        specification_object["trace_log"],
    )

    if trace_result.failed():
        return trace_result

    lineage_result = validate_lineage(
        specification_object["lineage"],
    )

    if lineage_result.failed():
        return lineage_result

    structure_result = validate_buildspec_structure(
        specification_object["structure"],
    )

    if structure_result.failed():
        return structure_result

    return ValidatorResult.pass_result(
        source_stage="spec_validator",
    )


def validate_builder_eligibility(
    specification_object: dict,
) -> ValidatorResult:
    shape_result = validate_specification_object(
        specification_object,
    )

    if shape_result.failed():
        return shape_result

    if specification_object["object_type"] != "SpecificationObject":
        return ValidatorResult.fail_result(
            failure_reason="Builder eligibility rejected",
            failing_field="object_type",
            source_stage="spec_validator",
            validation_notes=[
                "invalid object_type",
            ],
        )

    if specification_object["spec_class"] != "BuildSpec":
        return ValidatorResult.fail_result(
            failure_reason="Builder eligibility rejected",
            failing_field="spec_class",
            source_stage="spec_validator",
            validation_notes=[
                "unsupported spec_class",
            ],
        )

    if specification_object["validation_state"] != "valid":
        return ValidatorResult.fail_result(
            failure_reason="invalid validation_state",
            failing_field="validation_state",
            source_stage="spec_validator",
        )

    if specification_object["readiness_state"] != "ready_for_build":
        return ValidatorResult.fail_result(
            failure_reason="invalid readiness_state",
            failing_field="readiness_state",
            source_stage="spec_validator",
        )

    if specification_object["save_ready_state"] is not True:
        return ValidatorResult.fail_result(
            failure_reason="save_ready_state must be true",
            failing_field="save_ready_state",
            source_stage="spec_validator",
        )

    if specification_object["clarification_required"] is not False:
        return ValidatorResult.fail_result(
            failure_reason="clarification_required must be false",
            failing_field="clarification_required",
            source_stage="spec_validator",
        )

    if specification_object["authority_state"] not in BUILDER_AUTHORITY_STATE_VALUES:
        return ValidatorResult.fail_result(
            failure_reason="invalid authority_state",
            failing_field="authority_state",
            source_stage="spec_validator",
        )

    trace_result = validate_trace_log(
        specification_object["trace_log"],
    )

    if trace_result.failed():
        return trace_result

    lineage_result = validate_lineage(
        specification_object["lineage"],
    )

    if lineage_result.failed():
        return lineage_result

    structure_result = validate_buildspec_structure(
        specification_object["structure"],
    )

    if structure_result.failed():
        return structure_result

    return ValidatorResult.pass_result(
        source_stage="spec_validator",
    )


def validate_trace_log(
    trace_log: dict,
) -> ValidatorResult:
    if not isinstance(trace_log, dict):
        return ValidatorResult.fail_result(
            failure_reason="trace_log must be a dictionary",
            failing_field="trace_log",
            source_stage="spec_validator",
        )

    for field_name in REQUIRED_TRACE_LOG_FIELDS:
        if field_name not in trace_log:
            return ValidatorResult.fail_result(
                failure_reason="trace_log missing required field",
                failing_field=field_name,
                source_stage="spec_validator",
            )

    for field_name in REQUIRED_TRACE_LOG_FIELDS:
        if not isinstance(trace_log[field_name], str):
            return ValidatorResult.fail_result(
                failure_reason="trace_log missing required field",
                failing_field=field_name,
                source_stage="spec_validator",
            )

        if trace_log[field_name].strip() == "":
            return ValidatorResult.fail_result(
                failure_reason="trace_log missing required field",
                failing_field=field_name,
                source_stage="spec_validator",
            )

    if trace_log["source_system"] != "mode_ai":
        return ValidatorResult.fail_result(
            failure_reason="invalid trace_log source_system",
            failing_field="source_system",
            source_stage="spec_validator",
        )

    return ValidatorResult.pass_result(
        source_stage="spec_validator",
    )


def validate_lineage(
    lineage: dict,
) -> ValidatorResult:
    if not isinstance(lineage, dict):
        return ValidatorResult.fail_result(
            failure_reason="lineage must be a dictionary",
            failing_field="lineage",
            source_stage="spec_validator",
        )

    for field_name in REQUIRED_LINEAGE_FIELDS:
        if field_name not in lineage:
            return ValidatorResult.fail_result(
                failure_reason="lineage missing required field",
                failing_field=field_name,
                source_stage="spec_validator",
            )

    if not _is_non_empty_string(lineage["lineage_id"]):
        return ValidatorResult.fail_result(
            failure_reason="lineage missing required field",
            failing_field="lineage_id",
            source_stage="spec_validator",
        )

    if not isinstance(lineage["parent_refs"], list):
        return ValidatorResult.fail_result(
            failure_reason="lineage missing required field",
            failing_field="parent_refs",
            source_stage="spec_validator",
        )

    if not isinstance(lineage["source_refs"], list):
        return ValidatorResult.fail_result(
            failure_reason="lineage missing required field",
            failing_field="source_refs",
            source_stage="spec_validator",
        )

    if not isinstance(lineage["revision_history"], list):
        return ValidatorResult.fail_result(
            failure_reason="lineage missing required field",
            failing_field="revision_history",
            source_stage="spec_validator",
        )

    if lineage["created_from"] != "mode_ai":
        return ValidatorResult.fail_result(
            failure_reason="invalid lineage created_from",
            failing_field="created_from",
            source_stage="spec_validator",
        )

    if not _is_non_empty_string(lineage["current_version"]):
        return ValidatorResult.fail_result(
            failure_reason="lineage missing required field",
            failing_field="current_version",
            source_stage="spec_validator",
        )

    return ValidatorResult.pass_result(
        source_stage="spec_validator",
    )


def validate_buildspec_structure(
    structure: dict,
) -> ValidatorResult:
    if not isinstance(structure, dict):
        return ValidatorResult.fail_result(
            failure_reason="structure must be a dictionary",
            failing_field="structure",
            source_stage="spec_validator",
        )

    for field_name in REQUIRED_BUILDSPEC_STRUCTURE_FIELDS:
        if field_name not in structure:
            return ValidatorResult.fail_result(
                failure_reason="structure missing required field",
                failing_field=field_name,
                source_stage="spec_validator",
            )

    string_fields = (
        "intent_id",
        "system_name",
        "tool_type",
        "execution_authority",
    )

    for field_name in string_fields:
        if not _is_non_empty_string(structure[field_name]):
            return ValidatorResult.fail_result(
                failure_reason="invalid structure field type",
                failing_field=field_name,
                source_stage="spec_validator",
            )

    list_fields = (
        "construction_scope",
        "approved_components",
        "governance_constraints",
        "receipt_requirements",
    )

    for field_name in list_fields:
        if not isinstance(structure[field_name], list):
            return ValidatorResult.fail_result(
                failure_reason="invalid structure field type",
                failing_field=field_name,
                source_stage="spec_validator",
            )

    return ValidatorResult.pass_result(
        source_stage="spec_validator",
    )


def is_builder_eligible(
    specification_object: dict,
) -> bool:
    return validate_builder_eligibility(
        specification_object,
    ).passed()


def _is_non_empty_string(
    value: Any,
) -> bool:
    return isinstance(value, str) and value.strip() != ""

# Canonical consumer contract; producer and Builder share these exact checks.
ALLOWED_AUTHORITY_STATE_VALUES = {
    "draft_only",
    "pending_save",
    "save_confirmed",
    "handoff_approved",
    "authority_granted",
}

ALLOWED_VALIDATION_STATE_VALUES = {
    "valid",
    "invalid",
    "incomplete",
}

ALLOWED_READINESS_STATE_VALUES = {
    "ready_for_build",
    "needs_clarification",
    "invalid_spec",
}


def validate_specification_states(specification_object: dict) -> None:
    """Validate canonical states exactly; never normalize authority values."""
    for name, allowed in (
        ("authority_state", ALLOWED_AUTHORITY_STATE_VALUES),
        ("validation_state", ALLOWED_VALIDATION_STATE_VALUES),
        ("readiness_state", ALLOWED_READINESS_STATE_VALUES),
    ):
        value = specification_object.get(name)
        if type(value) is not str or value not in allowed:
            raise ValueError(f"invalid or missing {name}")
    for name in ("save_ready_state", "clarification_required"):
        if type(specification_object.get(name)) is not bool:
            raise ValueError(f"invalid or missing {name}")


def require_builder_specification(specification_object: dict) -> str:
    """Return unchanged canonical authority only for an eligible BuildSpec.

    handoff_approved / authority_granted -> APPROVED builder_execution.
    All other canonical states are ineligible; unknown states are invalid.
    """
    if not isinstance(specification_object, dict):
        raise ValueError("specification_object must be a dictionary")
    validate_specification_states(specification_object)
    if not _is_non_empty_string(specification_object.get("spec_id")):
        raise ValueError("invalid or missing spec_id")
    if type(specification_object.get("spec_class")) is not str:
        raise ValueError("invalid spec_class")
    eligibility = validate_builder_eligibility(specification_object)
    if eligibility.failed():
        raise ValueError(f"ineligible specification: {eligibility.failing_field}: {eligibility.failure_reason}")
    return specification_object["authority_state"]


