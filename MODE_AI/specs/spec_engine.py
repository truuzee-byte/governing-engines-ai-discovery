from __future__ import annotations

import copy
import re
from datetime import datetime, timezone
from typing import Any, Dict

from specs.validator_result import ValidatorResult
from specs.spec_validator import validate_builder_eligibility


REQUIRED_INTERPRETED_BUILD_REQUEST_FIELDS = (
    "request_id",
    "system_name",
    "system_purpose",
    "tool_type",
    "construction_scope",
    "approved_components",
    "governance_constraints",
    "execution_authority",
    "receipt_requirements",
    "runtime_target",
    "source_trace_reference",
)

from specs.spec_validator import (
    ALLOWED_AUTHORITY_STATE_VALUES, ALLOWED_VALIDATION_STATE_VALUES,
    ALLOWED_READINESS_STATE_VALUES, validate_specification_states, require_builder_specification,
)


def _request_states(request: dict) -> dict:
    # Omission is a draft, never an approval. These are independent states:
    # explicitly approving one field does not establish the others.
    defaults = {
        "authority_state": "draft_only",
        "validation_state": "incomplete",
        "readiness_state": "needs_clarification",
        "save_ready_state": False,
        "clarification_required": True,
    }
    return {name: request.get(name, default) for name, default in defaults.items()}


def create_specification_object(
    interpreted_build_request: dict,
    *, draft_only: bool = False,
) -> dict:
    validation_result = validate_interpreted_build_request(
        interpreted_build_request,
        draft_only=draft_only,
    )

    if validation_result.failed():
        raise ValueError(validation_result.failure_reason)

    # Builder data must use the canonical nested blocks. These aliases would
    # otherwise disappear when constructing the specification below.
    misplaced_builder_fields = {
        "files", "directories", "required_files", "required_directories",
        "approved_files", "approved_file_contents", "existing_files", "required_outputs",
        "repository_target", "artifact_target", "artifact_root",
        "authorized_read_scope", "authorized_write_scope", "authorized_create_scope",
        "authorized_delete_scope", "approved_commands", "execution_requirements",
        "validation_commands", "validation_requirements", "evidence_requirements",
        "completion_requirements", "component_metadata",
    } & interpreted_build_request.keys()
    if misplaced_builder_fields:
        raise ValueError(f"unsupported or misplaced Builder fields: {misplaced_builder_fields}")

    request_payload = copy.deepcopy(interpreted_build_request)

    spec_id = generate_spec_id(
        system_name=request_payload["system_name"],
        request_id=request_payload["request_id"],
    )

    artifact_structure = _resolve_artifact_structure(
        request_payload,
    )

    source_trace_reference = request_payload["source_trace_reference"]

    specification = {
        "object_type": "SpecificationObject",
        "object_version": "1.0",
        "spec_id": spec_id,
        "spec_version": "1.0",
        "spec_name": request_payload["system_name"],
        "spec_class": "BuildSpec",
        "intent_object": {
            "intent_type": "build_system",
            "target_system": request_payload["system_name"],
            "purpose": request_payload["system_purpose"],
        },
        "mode": "BuilderMode",
        "metadata": {
            "created_by": "mode_ai",
            "created_at": datetime.now(timezone.utc).isoformat(),
            "context_thread": request_payload["request_id"],
            "source_system": "mode_ai",
        },
        "structure": {
            "intent_id": request_payload["request_id"],
            "system_name": request_payload["system_name"],
            "system_purpose": request_payload["system_purpose"],
            "tool_type": request_payload["tool_type"],
            "construction_scope": list(request_payload["construction_scope"]),
            "approved_components": list(request_payload["approved_components"]),
            "governance_constraints": list(
                request_payload["governance_constraints"]
            ),
            "execution_authority": request_payload["execution_authority"],
            "receipt_requirements": list(
                request_payload["receipt_requirements"]
            ),
            "runtime_target": request_payload.get("runtime_target"),
        },
        "dependencies": [],
        **_request_states(request_payload),
        "trace_log": create_trace_log(
            spec_id=spec_id,
            source_trace_reference=source_trace_reference,
        ),
        "lineage": create_lineage(
            spec_id=spec_id,
            source_trace_reference=source_trace_reference,
        ),
        "artifact_structure": artifact_structure,
    }
    for name in ("execution", "validation", "evidence", "completion"):
        if name in request_payload:
            specification[name] = request_payload[name]
    return specification


def validate_interpreted_build_request(
    interpreted_build_request: dict,
    *, draft_only: bool = False,
) -> ValidatorResult:
    if not isinstance(interpreted_build_request, dict):
        return ValidatorResult.fail_result(
            failure_reason="interpreted_build_request must be a dictionary",
            source_stage="spec_engine",
        )

    for field_name in REQUIRED_INTERPRETED_BUILD_REQUEST_FIELDS:
        if field_name not in interpreted_build_request:
            return ValidatorResult.fail_result(
                failure_reason=(
                    "missing required interpreted_build_request field"
                ),
                failing_field=field_name,
                source_stage="spec_engine",
            )

    string_fields = (
        "request_id",
        "system_name",
        "system_purpose",
        "tool_type",
        "execution_authority",
        "source_trace_reference",
    )

    for field_name in string_fields:
        if not isinstance(interpreted_build_request[field_name], str):
            return ValidatorResult.fail_result(
                failure_reason="invalid interpreted_build_request field type",
                failing_field=field_name,
                source_stage="spec_engine",
            )

    if not _is_non_empty_string(interpreted_build_request["system_name"]):
        return ValidatorResult.fail_result(
            failure_reason="invalid system_name",
            failing_field="system_name",
            source_stage="spec_engine",
        )

    if not _is_non_empty_string(interpreted_build_request["request_id"]):
        return ValidatorResult.fail_result(
            failure_reason="invalid request_id",
            failing_field="request_id",
            source_stage="spec_engine",
        )

    if not _is_non_empty_string(
        interpreted_build_request["source_trace_reference"]
    ):
        return ValidatorResult.fail_result(
            failure_reason="invalid source_trace_reference",
            failing_field="source_trace_reference",
            source_stage="spec_engine",
        )

    list_fields = (
        "construction_scope",
        "approved_components",
        "governance_constraints",
        "receipt_requirements",
    )

    for field_name in list_fields:
        if not isinstance(interpreted_build_request[field_name], list):
            return ValidatorResult.fail_result(
                failure_reason="invalid interpreted_build_request field type",
                failing_field=field_name,
                source_stage="spec_engine",
            )

    runtime_target = interpreted_build_request["runtime_target"]

    if runtime_target is not None and not isinstance(runtime_target, str):
        return ValidatorResult.fail_result(
            failure_reason="invalid interpreted_build_request field type",
            failing_field="runtime_target",
            source_stage="spec_engine",
        )

    if "artifact_structure" in interpreted_build_request:
        artifact_result = _validate_artifact_structure(
            interpreted_build_request["artifact_structure"],
        )

        if artifact_result.failed():
            return artifact_result

    # The document preparation path may construct only a closed draft. Existing
    # execution callers still require explicitly confirmed request authority.
    if type(draft_only) is not bool:
        return ValidatorResult.fail_result(failure_reason="invalid draft mode", source_stage="spec_engine")
    expected_authority = "draft_only" if draft_only else "operator_confirmed"
    if interpreted_build_request["execution_authority"] != expected_authority:
        return ValidatorResult.fail_result(
            failure_reason="invalid execution_authority", failing_field="execution_authority",
            source_stage="spec_engine",
        )
    try:
        validate_specification_states(_request_states(interpreted_build_request))
        if draft_only and _request_states(interpreted_build_request) != {
            "authority_state": "draft_only", "validation_state": "incomplete",
            "readiness_state": "needs_clarification", "save_ready_state": False,
            "clarification_required": True,
        }:
            raise ValueError("Draft preparation cannot assert readiness or authority")
    except ValueError as exc:
        return ValidatorResult.fail_result(failure_reason=str(exc), source_stage="spec_engine")
    for name in ("execution", "validation", "evidence", "completion"):
        if name in interpreted_build_request and not isinstance(interpreted_build_request[name], dict):
            return ValidatorResult.fail_result(
                failure_reason=f"invalid {name}", failing_field=name, source_stage="spec_engine",
            )

    return ValidatorResult.pass_result(
        source_stage="spec_engine",
        validation_notes=[
            "interpreted build request valid",
        ],
    )


def generate_spec_id(
    system_name: str,
    request_id: str,
) -> str:
    if not _is_non_empty_string(system_name):
        raise ValueError("invalid system_name")

    if not _is_non_empty_string(request_id):
        raise ValueError("invalid request_id")

    safe_system_name = normalize_safe_identifier(
        system_name,
    )

    safe_request_id = _normalize_request_id(
        request_id,
    )

    if safe_system_name == "":
        raise ValueError("invalid system_name")

    if safe_request_id == "":
        raise ValueError("invalid request_id")

    return f"spec_{safe_system_name}_{safe_request_id}"


def create_trace_log(
    spec_id: str,
    source_trace_reference: str,
) -> dict:
    if not _is_non_empty_string(spec_id):
        raise ValueError("invalid spec_id")

    if not _is_non_empty_string(source_trace_reference):
        raise ValueError("invalid source_trace_reference")

    return {
        "trace_id": f"trace_{spec_id}",
        "source_system": "mode_ai",
        "interpretation_trace_reference": source_trace_reference,
        "validation_trace_reference": f"validation_{spec_id}",
        "handoff_trace_reference": f"handoff_{spec_id}",
    }


def create_lineage(
    spec_id: str,
    source_trace_reference: str,
) -> dict:
    if not _is_non_empty_string(spec_id):
        raise ValueError("invalid spec_id")

    if not _is_non_empty_string(source_trace_reference):
        raise ValueError("invalid source_trace_reference")

    return {
        "lineage_id": f"lineage_{spec_id}",
        "parent_refs": [],
        "source_refs": [
            source_trace_reference,
        ],
        "revision_history": [],
        "created_from": "mode_ai",
        "current_version": "1.0",
    }


def normalize_safe_identifier(
    value: str,
) -> str:
    if not isinstance(value, str):
        raise TypeError("value must be a string")

    normalized = value.strip().lower()
    normalized = normalized.replace("\\", "_")
    normalized = normalized.replace("/", "_")
    normalized = normalized.replace(".", "_")
    normalized = re.sub(r"[^a-z0-9_-]+", "_", normalized)
    normalized = re.sub(r"_+", "_", normalized)
    normalized = normalized.strip("_")

    return normalized


def _normalize_request_id(
    value: str,
) -> str:
    if not isinstance(value, str):
        raise TypeError("value must be a string")

    normalized = value.strip()
    normalized = normalized.replace("\\", "_")
    normalized = normalized.replace("/", "_")
    normalized = normalized.replace(".", "_")
    normalized = re.sub(r"[^A-Za-z0-9_-]+", "_", normalized)
    normalized = re.sub(r"_+", "_", normalized)
    normalized = normalized.strip("_")

    return normalized


def _resolve_artifact_structure(
    interpreted_build_request: Dict[str, Any],
) -> dict:
    if "artifact_structure" not in interpreted_build_request:
        return {
            "directories": [],
            "files": [],
        }

    artifact_structure = copy.deepcopy(
        interpreted_build_request["artifact_structure"]
    )

    artifact_result = _validate_artifact_structure(
        artifact_structure,
    )

    if artifact_result.failed():
        raise ValueError(artifact_result.failure_reason)

    return artifact_structure


def _validate_artifact_structure(
    artifact_structure: Any,
) -> ValidatorResult:
    if not isinstance(artifact_structure, dict):
        return ValidatorResult.fail_result(
            failure_reason="invalid artifact_structure",
            failing_field="artifact_structure",
            source_stage="spec_engine",
        )

    if "directories" not in artifact_structure:
        return ValidatorResult.fail_result(
            failure_reason="invalid artifact_structure",
            failing_field="artifact_structure.directories",
            source_stage="spec_engine",
        )

    if "files" not in artifact_structure:
        return ValidatorResult.fail_result(
            failure_reason="invalid artifact_structure",
            failing_field="artifact_structure.files",
            source_stage="spec_engine",
        )

    if not isinstance(artifact_structure["directories"], list):
        return ValidatorResult.fail_result(
            failure_reason="artifact_structure directories must be a list",
            failing_field="artifact_structure.directories",
            source_stage="spec_engine",
        )

    if not isinstance(artifact_structure["files"], list):
        return ValidatorResult.fail_result(
            failure_reason="artifact_structure files must be a list",
            failing_field="artifact_structure.files",
            source_stage="spec_engine",
        )

    return ValidatorResult.pass_result(
        source_stage="spec_engine",
    )


def _is_non_empty_string(
    value: Any,
) -> bool:
    return isinstance(value, str) and value.strip() != ""
