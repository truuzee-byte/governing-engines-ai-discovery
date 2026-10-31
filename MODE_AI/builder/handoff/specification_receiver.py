from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict

from specs.spec_validator import require_builder_specification
from specs.handoff_gate import validate_handoff


@dataclass(frozen=True)
class ReceivedSpecification:
    specification_object: Dict[str, Any]
    snapshot: Dict[str, Any]
    spec_reference: str
    spec_hash: str
    builder_target: str
    authority_state: str
    handoff_trace_reference: str

    def __post_init__(self) -> None:
        if not isinstance(self.specification_object, dict):
            raise TypeError("specification_object must be a dictionary")

        if not isinstance(self.snapshot, dict):
            raise TypeError("snapshot must be a dictionary")

        _require_non_empty_string(self.spec_reference, "spec_reference")
        _require_non_empty_string(self.spec_hash, "spec_hash")
        _require_non_empty_string(self.builder_target, "builder_target")
        _require_non_empty_string(self.authority_state, "authority_state")
        _require_non_empty_string(
            self.handoff_trace_reference,
            "handoff_trace_reference",
        )

    def to_dict(self) -> Dict[str, Any]:
        return {
            "specification_object": dict(self.specification_object),
            "snapshot": dict(self.snapshot),
            "spec_reference": self.spec_reference,
            "spec_hash": self.spec_hash,
            "builder_target": self.builder_target,
            "authority_state": self.authority_state,
            "handoff_trace_reference": self.handoff_trace_reference,
        }


def receive_specification(
    handoff_payload: dict,
) -> ReceivedSpecification:
    if not isinstance(handoff_payload, dict):
        raise ValueError("invalid handoff payload")

    if handoff_payload.get("handoff_status") != "APPROVED":
        raise ValueError("handoff not approved")

    if handoff_payload.get("handoff_type") != "builder_execution":
        raise ValueError("handoff not approved")

    specification_object = _get_required_dict(
        payload=handoff_payload,
        field_name="specification_object",
        failure_reason="missing specification_object",
    )

    snapshot = _get_required_dict(
        payload=handoff_payload,
        field_name="snapshot",
        failure_reason="missing snapshot",
    )

    spec_reference = _get_required_string(
        payload=handoff_payload,
        field_name="spec_reference",
        failure_reason="missing spec_reference",
    )

    spec_hash = _get_required_string(
        payload=handoff_payload,
        field_name="spec_hash",
        failure_reason="missing spec_hash",
    )

    builder_target = _get_required_string(
        payload=handoff_payload,
        field_name="builder_target",
        failure_reason="missing builder_target",
    )

    authority_state = _get_required_string(
        payload=handoff_payload,
        field_name="authority_state",
        failure_reason="missing authority_state",
    )

    handoff_trace_reference = _get_required_string(
        payload=handoff_payload,
        field_name="handoff_trace_reference",
        failure_reason="missing handoff_trace_reference",
    )

    canonical_authority = require_builder_specification(specification_object)
    if type(authority_state) is not str or authority_state != canonical_authority:
        raise ValueError("authority_state does not match canonical specification")
    validation = validate_handoff(specification_object, snapshot)
    if validation.failed():
        raise ValueError(f"invalid handoff snapshot: {validation.failure_reason}")
    if spec_reference != specification_object["spec_id"] or spec_hash != snapshot["spec_hash"]:
        raise ValueError("handoff specification reference or hash mismatch")

    return ReceivedSpecification(
        specification_object=specification_object,
        snapshot=snapshot,
        spec_reference=spec_reference,
        spec_hash=spec_hash,
        builder_target=builder_target,
        authority_state=authority_state,
        handoff_trace_reference=handoff_trace_reference,
    )


def _get_required_dict(
    payload: Dict[str, Any],
    field_name: str,
    failure_reason: str,
) -> Dict[str, Any]:
    if field_name not in payload:
        raise ValueError(failure_reason)

    value = payload[field_name]

    if not isinstance(value, dict):
        raise ValueError(failure_reason)

    return value


def _get_required_string(
    payload: Dict[str, Any],
    field_name: str,
    failure_reason: str,
) -> str:
    if field_name not in payload:
        raise ValueError(failure_reason)

    value = payload[field_name]

    if not _is_non_empty_string(value):
        raise ValueError(failure_reason)

    return value


def _require_non_empty_string(
    value: Any,
    field_name: str,
) -> None:
    if not isinstance(value, str):
        raise TypeError(f"{field_name} must be a string")

    if value.strip() == "":
        raise ValueError(f"{field_name} must not be empty")


def _is_non_empty_string(
    value: Any,
) -> bool:
    return isinstance(value, str) and value.strip() != ""
