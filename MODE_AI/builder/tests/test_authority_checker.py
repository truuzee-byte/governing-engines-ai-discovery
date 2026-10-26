from __future__ import annotations

from builder.handoff.authority_checker import check_builder_authority
from builder.handoff.specification_receiver import ReceivedSpecification


def test_handoff_approved_passes() -> None:
    assert check_builder_authority(_received("handoff_approved")) is True


def test_authority_granted_passes() -> None:
    assert check_builder_authority(_received("authority_granted")) is True


def test_draft_only_fails() -> None:
    assert check_builder_authority(_received("draft_only")) is False


def test_invalid_authority_fails() -> None:
    assert check_builder_authority(_received("invalid")) is False


def test_malformed_received_specification_fails() -> None:
    assert check_builder_authority("not-received") is False


def _received(authority_state: str) -> ReceivedSpecification:
    return ReceivedSpecification(
        specification_object={"spec_id": "spec_001"},
        snapshot={"spec_id": "spec_001"},
        spec_reference="spec_001",
        spec_hash="hash",
        builder_target="Diagnostic Tool",
        authority_state=authority_state,
        handoff_trace_reference="handoff_spec_001",
    )