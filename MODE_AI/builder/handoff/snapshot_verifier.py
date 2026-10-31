from __future__ import annotations

from builder.handoff.specification_receiver import ReceivedSpecification
from specs.spec_snapshot import hash_specification_object


def verify_snapshot_continuity(
    received_specification: ReceivedSpecification,
) -> bool:
    if not isinstance(received_specification, ReceivedSpecification):
        return False

    snapshot = received_specification.snapshot
    specification_object = received_specification.specification_object

    if not isinstance(snapshot, dict):
        return False

    if not isinstance(specification_object, dict):
        return False

    snapshot_payload = snapshot.get("spec_payload")

    if not isinstance(snapshot_payload, dict):
        return False

    if snapshot_payload != specification_object:
        return False

    snapshot_spec_id = snapshot.get("spec_id")
    specification_spec_id = specification_object.get("spec_id")

    if not isinstance(snapshot_spec_id, str):
        return False

    if not isinstance(specification_spec_id, str):
        return False

    if snapshot_spec_id != specification_spec_id:
        return False

    snapshot_hash = snapshot.get("spec_hash")

    if not isinstance(snapshot_hash, str):
        return False

    expected_hash = hash_specification_object(
        specification_object,
    )

    if snapshot_hash != expected_hash:
        return False

    return True