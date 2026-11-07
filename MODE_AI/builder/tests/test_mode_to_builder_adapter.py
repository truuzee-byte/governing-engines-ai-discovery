import copy
import json
from types import SimpleNamespace

import pytest

from builder.handoff.mode_to_builder_adapter import (
    mode_to_builder_handoff,
)
from builder.handoff.specification_receiver import receive_specification
from builder.handoff.snapshot_verifier import verify_snapshot_continuity
from specs.spec_validator import validate_builder_eligibility


def _manifest(
    *,
    interaction_id="interaction-001",
    session_id="session-001",
    clarification_required=False,
    halt_required=False,
    selected_posture="INTERPRET",
    downstream_authority_allowed=True,
):
    return SimpleNamespace(
        interaction_id=interaction_id,
        session_id=session_id,
        clarification_required=clarification_required,
        halt_required=halt_required,
        selected_posture=selected_posture,
        downstream_authority_allowed=downstream_authority_allowed,
    )


def _mode_result(
    *,
    raw_input="Build validator runtime.",
    trace_reference="runtime_traces/interactions.jsonl",
    manifest=None,
):
    return SimpleNamespace(
        raw_input=raw_input,
        builder_specification_states={"authority_state": "handoff_approved", "validation_state": "valid",
            "readiness_state": "ready_for_build", "save_ready_state": True, "clarification_required": False},
        trace_reference=trace_reference,
        interaction_manifest=manifest,
    )


def test_valid_mode_result_creates_builder_handoff_payload() -> None:
    manifest = _manifest()

    mode_result = _mode_result(
        manifest=manifest,
    )

    payload = mode_to_builder_handoff(mode_result)

    assert payload["specification_id"] == "interaction-001"
    assert payload["operator_intent"] == "Build validator runtime."
    assert payload["builder_target"] == "builder_runtime"

    assert payload["authority_state"] == "handoff_approved"

    assert payload["lineage"] == {
        "mode_session_id": "session-001",
        "mode_interaction_id": "interaction-001",
        "trace_reference": "runtime_traces/interactions.jsonl",
    }


def test_missing_manifest_blocks_handoff() -> None:
    mode_result = _mode_result(
        manifest=None,
    )

    with pytest.raises(
        ValueError,
        match="missing interaction manifest",
    ):
        mode_to_builder_handoff(mode_result)


def test_manifest_permission_does_not_manufacture_specification_approval():
    result = _mode_result(manifest=_manifest())
    del result.builder_specification_states
    with pytest.raises(ValueError, match="Explicit builder_specification_states"):
        mode_to_builder_handoff(result)


def test_halt_required_blocks_handoff() -> None:
    manifest = _manifest(
        halt_required=True,
        selected_posture="HALT",
    )

    mode_result = _mode_result(
        manifest=manifest,
    )

    with pytest.raises(
        ValueError,
        match="mode halted; builder handoff blocked",
    ):
        mode_to_builder_handoff(mode_result)


def test_downstream_authority_blocked_rejects_handoff() -> None:
    manifest = _manifest(
        downstream_authority_allowed=False,
        clarification_required=True,
        selected_posture="CLARIFY_FIRST",
    )

    mode_result = _mode_result(
        manifest=manifest,
    )

    with pytest.raises(
        ValueError,
        match="downstream authority not allowed",
    ):
        mode_to_builder_handoff(mode_result)


def test_lineage_fields_preserved() -> None:
    manifest = _manifest(
        interaction_id="interaction-777",
        session_id="session-777",
    )

    mode_result = _mode_result(
        trace_reference="runtime_traces/session-777.jsonl",
        manifest=manifest,
    )

    payload = mode_to_builder_handoff(mode_result)

    assert payload["lineage"]["mode_session_id"] == "session-777"
    assert payload["lineage"]["mode_interaction_id"] == "interaction-777"
    assert (
        payload["lineage"]["trace_reference"]
        == "runtime_traces/session-777.jsonl"
    )


def test_real_adapter_creates_canonical_spec_accepted_by_receiver():
    result = _mode_result(manifest=_manifest())
    result.builder_files = {"validation.py": "answer = 42\n"}
    result.builder_validation_commands = [["python", "validation.py"]]
    payload = mode_to_builder_handoff(result)
    canonical = payload["specification_object"]
    assert validate_builder_eligibility(canonical).passed()
    received = receive_specification(json.loads(json.dumps(payload)))
    assert received.specification_object == canonical
    assert received.authority_state == canonical["authority_state"] == "handoff_approved"
    assert received.snapshot["spec_payload"] == canonical
    assert verify_snapshot_continuity(received)
    assert canonical["artifact_structure"]["approved_files"] == result.builder_files
    assert canonical["validation"]["commands"] == result.builder_validation_commands


@pytest.mark.parametrize("authority", ["handoff_approved", "authority_granted"])
def test_supplied_canonical_state_survives_round_trip_unchanged(authority):
    result = _mode_result(manifest=_manifest())
    spec = mode_to_builder_handoff(result)["specification_object"]
    spec["authority_state"] = authority
    original = copy.deepcopy(spec)
    result.builder_specification = spec
    payload = mode_to_builder_handoff(result)
    received = receive_specification(json.loads(json.dumps(payload)))
    assert payload["handoff_status"] == "APPROVED"
    assert received.authority_state == payload["authority_state"] == authority
    assert spec == original == received.specification_object == received.snapshot["spec_payload"]


@pytest.mark.parametrize("name", ["halt_required", "clarification_required", "downstream_authority_allowed"])
def test_missing_mode_authority_flags_are_rejected(name):
    manifest = _manifest()
    delattr(manifest, name)
    with pytest.raises(ValueError, match=name):
        mode_to_builder_handoff(_mode_result(manifest=manifest))


@pytest.mark.parametrize("value", [None, "true", "false", 1, 0, {}, []])
def test_malformed_mode_authority_is_not_coerced(value):
    with pytest.raises(ValueError, match="downstream_authority_allowed"):
        mode_to_builder_handoff(_mode_result(manifest=_manifest(downstream_authority_allowed=value)))


def test_missing_supplied_spec_authority_is_rejected():
    result = _mode_result(manifest=_manifest())
    spec = mode_to_builder_handoff(result)["specification_object"]
    del spec["authority_state"]
    result.builder_specification = spec
    with pytest.raises(ValueError, match="authority_state"):
        mode_to_builder_handoff(result)


@pytest.mark.parametrize("field,value", [
    ("authority_state", {}), ("authority_state", []), ("authority_state", True),
    ("authority_state", "APPROVED"), ("authority_state", " handoff_approved"),
    ("authority_state", "unknown"), ("authority_state", "draft_only"),
    ("authority_state", "pending_save"), ("authority_state", "save_confirmed"),
    ("validation_state", "invalid"), ("validation_state", "incomplete"),
    ("validation_state", {"validated": True}), ("validation_state", "unknown"),
    ("readiness_state", "needs_clarification"), ("readiness_state", "invalid_spec"),
    ("readiness_state", {"builder_ready": True}), ("readiness_state", "unknown"),
    ("save_ready_state", False), ("save_ready_state", 1),
    ("clarification_required", True), ("clarification_required", 0),
])
def test_invalid_or_ineligible_supplied_spec_is_rejected(field, value):
    result = _mode_result(manifest=_manifest())
    spec = mode_to_builder_handoff(result)["specification_object"]
    spec[field] = value
    result.builder_specification = spec
    with pytest.raises(ValueError, match=field):
        mode_to_builder_handoff(result)


def test_clarification_blocks_otherwise_authorized_mode():
    with pytest.raises(ValueError, match="clarification required"):
        mode_to_builder_handoff(_mode_result(manifest=_manifest(clarification_required=True)))
