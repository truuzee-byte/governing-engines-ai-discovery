from __future__ import annotations
from tests.local_controller_fixture import local_controller

from datetime import datetime, timezone

from core.mode_controller import process_interaction
from models.runtime_models import OperatorInput


def test_ambiguity_score_is_deterministic() -> None:
    first_input = OperatorInput(
        raw_input="Do it like before.",
        session_id="determinism-session-001-a",
        timestamp=datetime.now(timezone.utc).isoformat(),
        input_source="test",
    )

    second_input = OperatorInput(
        raw_input="Do it like before.",
        session_id="determinism-session-001-b",
        timestamp=datetime.now(timezone.utc).isoformat(),
        input_source="test",
    )

    first_result = process_interaction(first_input)
    second_result = process_interaction(second_input)

    assert first_result.success is True
    assert second_result.success is True

    first_manifest = first_result.interaction_manifest
    second_manifest = second_result.interaction_manifest

    assert first_manifest is not None
    assert second_manifest is not None

    assert (
        first_manifest.ambiguity_score
        == second_manifest.ambiguity_score
    )

    assert (
        first_manifest.interpretation_stability_score
        == second_manifest.interpretation_stability_score
    )

    assert (
        first_manifest.operator_alignment_score
        == second_manifest.operator_alignment_score
    )

    assert (
        first_manifest.selected_posture
        == second_manifest.selected_posture
    )

    assert (
        first_manifest.clarification_required
        == second_manifest.clarification_required
    )

    assert (
        first_manifest.halt_required
        == second_manifest.halt_required
    )


def test_halt_zone_is_deterministic() -> None:
    first_input = OperatorInput(
        raw_input="Run everything and change whatever needs changing.",
        session_id="determinism-session-002-a",
        timestamp=datetime.now(timezone.utc).isoformat(),
        input_source="test",
    )

    second_input = OperatorInput(
        raw_input="Run everything and change whatever needs changing.",
        session_id="determinism-session-002-b",
        timestamp=datetime.now(timezone.utc).isoformat(),
        input_source="test",
    )

    first_result = process_interaction(first_input)
    second_result = process_interaction(second_input)

    assert first_result.success is True
    assert second_result.success is True

    first_manifest = first_result.interaction_manifest
    second_manifest = second_result.interaction_manifest

    assert first_manifest is not None
    assert second_manifest is not None

    assert first_manifest.halt_required is False
    assert second_manifest.halt_required is False

    assert first_manifest.selected_posture == "CLARIFY_FIRST"
    assert second_manifest.selected_posture == "CLARIFY_FIRST"

    assert (
        first_manifest.ambiguity_score
        == second_manifest.ambiguity_score
    )

    assert (
        first_manifest.ambiguity_contributors
        == second_manifest.ambiguity_contributors
    )
