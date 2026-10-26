from __future__ import annotations

import copy
import hashlib
import json
from dataclasses import dataclass
from datetime import datetime, timezone
from types import MappingProxyType
from typing import Any, Dict, Mapping

from specs.validator_result import ValidatorResult


SNAPSHOT_ID_PREFIX = "spec_snapshot"


@dataclass(frozen=True)
class SpecSnapshot:
    snapshot_id: str
    spec_id: str
    spec_hash: str
    snapshot_ts: str
    spec_payload: Mapping[str, Any]

    def __post_init__(self) -> None:
        _require_non_empty_string(
            self.snapshot_id,
            "snapshot_id",
        )
        _require_non_empty_string(
            self.spec_id,
            "spec_id",
        )
        _require_non_empty_string(
            self.spec_hash,
            "spec_hash",
        )
        _require_non_empty_string(
            self.snapshot_ts,
            "snapshot_ts",
        )

        if not isinstance(self.spec_payload, Mapping):
            raise TypeError("spec_payload must be a mapping")

        frozen_payload = _freeze_payload(
            copy.deepcopy(dict(self.spec_payload))
        )

        object.__setattr__(
            self,
            "spec_payload",
            frozen_payload,
        )

    def to_dict(self) -> Dict[str, Any]:
        return {
            "snapshot_id": self.snapshot_id,
            "spec_id": self.spec_id,
            "spec_hash": self.spec_hash,
            "snapshot_ts": self.snapshot_ts,
            "spec_payload": _thaw_payload(self.spec_payload),
        }


def create_spec_snapshot(
    specification_object: Dict[str, Any],
) -> SpecSnapshot:
    if not isinstance(specification_object, dict):
        raise TypeError("specification_object must be a dictionary")

    spec_id = specification_object.get("spec_id")

    _require_non_empty_string(
        spec_id,
        "spec_id",
    )

    canonical_payload = copy.deepcopy(specification_object)
    spec_hash = hash_specification_object(canonical_payload)

    return SpecSnapshot(
        snapshot_id=_generate_snapshot_id(
            spec_id=spec_id,
            spec_hash=spec_hash,
        ),
        spec_id=spec_id,
        spec_hash=spec_hash,
        snapshot_ts=datetime.now(timezone.utc).isoformat(),
        spec_payload=canonical_payload,
    )


def hash_specification_object(
    specification_object: Dict[str, Any],
) -> str:
    if not isinstance(specification_object, dict):
        raise TypeError("specification_object must be a dictionary")

    canonical_serialized = canonical_serialize(
        specification_object,
    )

    return hashlib.sha256(
        canonical_serialized.encode("utf-8")
    ).hexdigest()


def canonical_serialize(
    payload: Dict[str, Any],
) -> str:
    if not isinstance(payload, dict):
        raise TypeError("payload must be a dictionary")

    return json.dumps(
        payload,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    )


def verify_spec_snapshot(
    snapshot: SpecSnapshot,
) -> ValidatorResult:
    if not isinstance(snapshot, SpecSnapshot):
        raise TypeError("snapshot must be SpecSnapshot")

    snapshot_payload = snapshot.to_dict()
    required_fields = (
        "snapshot_id",
        "spec_id",
        "spec_hash",
        "snapshot_ts",
        "spec_payload",
    )

    for field_name in required_fields:
        if field_name not in snapshot_payload:
            return ValidatorResult.fail_result(
                failure_reason="snapshot missing required field",
                failing_field=field_name,
                source_stage="spec_snapshot",
            )

    expected_hash = hash_specification_object(
        snapshot_payload["spec_payload"]
    )

    if snapshot.spec_hash != expected_hash:
        return ValidatorResult.fail_result(
            failure_reason="snapshot hash mismatch",
            failing_field="spec_hash",
            source_stage="spec_snapshot",
            validation_notes=[
                "SPEC_DRIFT_DETECTED",
            ],
        )

    payload_spec_id = snapshot_payload["spec_payload"].get("spec_id")

    if payload_spec_id != snapshot.spec_id:
        return ValidatorResult.fail_result(
            failure_reason="snapshot spec_id mismatch",
            failing_field="spec_id",
            source_stage="spec_snapshot",
            validation_notes=[
                "SPEC_DRIFT_DETECTED",
            ],
        )

    return ValidatorResult.pass_result(
        source_stage="spec_snapshot",
        validation_notes=[
            "snapshot verified",
        ],
    )


def snapshot_to_dict(
    snapshot: SpecSnapshot,
) -> Dict[str, Any]:
    if not isinstance(snapshot, SpecSnapshot):
        raise TypeError("snapshot must be SpecSnapshot")

    return snapshot.to_dict()


def _generate_snapshot_id(
    spec_id: str,
    spec_hash: str,
) -> str:
    return f"{SNAPSHOT_ID_PREFIX}:{spec_id}:{spec_hash[:16]}"


def _freeze_payload(
    value: Any,
) -> Any:
    if isinstance(value, dict):
        return MappingProxyType(
            {
                key: _freeze_payload(nested_value)
                for key, nested_value in value.items()
            }
        )

    if isinstance(value, list):
        return tuple(
            _freeze_payload(item)
            for item in value
        )

    return value


def _thaw_payload(
    value: Any,
) -> Any:
    if isinstance(value, Mapping):
        return {
            key: _thaw_payload(nested_value)
            for key, nested_value in value.items()
        }

    if isinstance(value, tuple):
        return [
            _thaw_payload(item)
            for item in value
        ]

    return value


def _require_non_empty_string(
    value: Any,
    field_name: str,
) -> None:
    if not isinstance(value, str):
        raise TypeError(f"{field_name} must be a string")

    if value.strip() == "":
        raise ValueError(f"{field_name} must not be empty")