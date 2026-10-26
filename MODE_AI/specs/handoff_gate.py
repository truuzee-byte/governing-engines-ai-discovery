from __future__ import annotations

import copy
from typing import Any, Dict, Union

from specs.spec_snapshot import (
    SpecSnapshot,
    hash_specification_object,
    verify_spec_snapshot,
)
from specs.spec_validator import validate_builder_eligibility
from specs.validator_result import ValidatorResult


SnapshotInput = Union[SpecSnapshot, Dict[str, Any]]


def approve_builder_handoff(
    specification_object: dict,
    snapshot: SnapshotInput,
) -> dict:
    validation_result = validate_handoff(
        specification_object=specification_object,
        snapshot=snapshot,
    )

    if validation_result.failed():
        raise ValueError(validation_result.failure_reason)

    normalized_snapshot = _normalize_snapshot(snapshot)

    return create_handoff_payload(
        specification_object=specification_object,
        snapshot=normalized_snapshot,
    )


def validate_handoff(
    specification_object: dict,
    snapshot: SnapshotInput,
) -> ValidatorResult:
    eligibility_result = validate_builder_eligibility(
        specification_object,
    )

    if eligibility_result.failed():
        return ValidatorResult.fail_result(
            failure_reason="SpecificationObject handoff eligibility failed",
            failing_field=eligibility_result.failing_field,
            source_stage="handoff_gate",
            validation_notes=[
                eligibility_result.failure_reason or "",
            ],
        )

    if snapshot is None:
        return ValidatorResult.fail_result(
            failure_reason="snapshot is required",
            failing_field="snapshot",
            source_stage="handoff_gate",
        )

    try:
        normalized_snapshot = _normalize_snapshot(snapshot)

    except (TypeError, ValueError):
        return ValidatorResult.fail_result(
            failure_reason="invalid snapshot",
            failing_field="snapshot",
            source_stage="handoff_gate",
        )

    snapshot_verification_result = verify_spec_snapshot(
        normalized_snapshot,
    )

    if snapshot_verification_result.failed():
        return ValidatorResult.fail_result(
            failure_reason="snapshot verification failed",
            failing_field=snapshot_verification_result.failing_field,
            source_stage="handoff_gate",
            validation_notes=list(
                snapshot_verification_result.validation_notes
            ),
        )

    snapshot_match_result = _validate_snapshot_against_specification_object(
        specification_object=specification_object,
        snapshot=normalized_snapshot,
    )

    if snapshot_match_result.failed():
        return snapshot_match_result

    handoff_trace_reference = (
        specification_object
        .get("trace_log", {})
        .get("handoff_trace_reference")
    )

    if not _is_non_empty_string(handoff_trace_reference):
        return ValidatorResult.fail_result(
            failure_reason="missing handoff_trace_reference",
            failing_field="trace_log.handoff_trace_reference",
            source_stage="handoff_gate",
        )

    return ValidatorResult.pass_result(
        source_stage="handoff_gate",
        validation_notes=[
            "Builder handoff approved",
        ],
    )


def create_handoff_payload(
    specification_object: dict,
    snapshot: SnapshotInput,
) -> dict:
    validation_result = validate_handoff(
        specification_object=specification_object,
        snapshot=snapshot,
    )

    if validation_result.failed():
        raise ValueError(validation_result.failure_reason)

    normalized_snapshot = _normalize_snapshot(snapshot)

    return {
        "handoff_status": "APPROVED",
        "handoff_type": "builder_execution",
        "specification_object": specification_object,
        "snapshot": normalized_snapshot.to_dict(),
        "spec_reference": specification_object["spec_id"],
        "spec_hash": normalized_snapshot.spec_hash,
        "builder_target": specification_object["structure"]["system_name"],
        "authority_state": specification_object["authority_state"],
        "handoff_trace_reference": (
            specification_object["trace_log"]["handoff_trace_reference"]
        ),
    }


def _validate_snapshot_against_specification_object(
    specification_object: dict,
    snapshot: SnapshotInput,
) -> ValidatorResult:
    normalized_snapshot = _normalize_snapshot(snapshot)

    if normalized_snapshot.spec_id != specification_object["spec_id"]:
        return ValidatorResult.fail_result(
            failure_reason="snapshot spec_id mismatch",
            failing_field="snapshot.spec_id",
            source_stage="handoff_gate",
        )

    snapshot_payload = normalized_snapshot.to_dict()["spec_payload"]

    if snapshot_payload != specification_object:
        return ValidatorResult.fail_result(
            failure_reason="snapshot payload mismatch",
            failing_field="snapshot.spec_payload",
            source_stage="handoff_gate",
        )

    expected_hash = hash_specification_object(
        specification_object,
    )

    if normalized_snapshot.spec_hash != expected_hash:
        return ValidatorResult.fail_result(
            failure_reason="snapshot hash mismatch",
            failing_field="snapshot.spec_hash",
            source_stage="handoff_gate",
        )

    return ValidatorResult.pass_result(
        source_stage="handoff_gate",
    )


def _normalize_snapshot(
    snapshot: SnapshotInput,
) -> SpecSnapshot:
    if isinstance(snapshot, SpecSnapshot):
        return snapshot

    if not isinstance(snapshot, dict):
        raise TypeError("snapshot must be SpecSnapshot or dictionary")

    required_fields = (
        "snapshot_id",
        "spec_id",
        "spec_hash",
        "snapshot_ts",
        "spec_payload",
    )

    for field_name in required_fields:
        if field_name not in snapshot:
            raise ValueError("snapshot missing required field")

    if not isinstance(snapshot["spec_payload"], dict):
        raise ValueError("snapshot spec_payload must be a dictionary")

    return SpecSnapshot(
        snapshot_id=snapshot["snapshot_id"],
        spec_id=snapshot["spec_id"],
        spec_hash=snapshot["spec_hash"],
        snapshot_ts=snapshot["snapshot_ts"],
        spec_payload=copy.deepcopy(snapshot["spec_payload"]),
    )


def _is_non_empty_string(
    value: Any,
) -> bool:
    return isinstance(value, str) and value.strip() != ""