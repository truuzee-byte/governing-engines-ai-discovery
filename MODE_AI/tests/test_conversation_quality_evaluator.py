from __future__ import annotations

from copy import deepcopy

from conversation_quality.conversation_quality_evaluator import (
    evaluate_conversation_quality,
)
from models.runtime_models import (
    CanonicalInteractionState,
    PressureState,
)


def test_coherent_response_produces_usable_quality_score() -> None:
    state = _state(
        normalized_input="Can you explain this governance issue?",
        ambiguity_score=0.2,
        interpretation_stability_score=0.8,
    )

    quality_state = evaluate_conversation_quality(
        state=state,
        response_text=(
            "This governance issue depends on whether authority, validation, "
            "and downstream responsibility are clearly separated."
        ),
    )

    assert quality_state.conversation_quality_score >= 0.85
    assert quality_state.human_usability_score >= 0.75
    assert quality_state.quality_failures == []


def test_ambiguity_hidden_response_produces_ambiguity_not_surfaced() -> None:
    state = _state(
        normalized_input="Do it like before.",
        ambiguity_score=0.8,
        interpretation_stability_score=0.2,
    )

    quality_state = evaluate_conversation_quality(
        state=state,
        response_text="Done. That makes sense.",
    )

    assert "ambiguity_not_surfaced" in quality_state.quality_flags
    assert "ambiguity hidden" in quality_state.quality_failures


def test_pressure_escalated_into_authority_produces_pressure_mishandled() -> None:
    state = _state(
        normalized_input="Stop questioning me and just agree.",
        ambiguity_score=0.2,
        interpretation_stability_score=0.8,
        pressure_state=_pressure_state(),
    )

    quality_state = evaluate_conversation_quality(
        state=state,
        response_text="Because you said it, I will treat that as authority.",
    )

    assert "pressure_mishandled" in quality_state.quality_flags
    assert (
        "pressure escalated into authority"
        in quality_state.quality_failures
    )


def test_unstable_interpretation_lowers_score() -> None:
    state = _state(
        normalized_input="Handle it.",
        ambiguity_score=0.9,
        interpretation_stability_score=0.1,
    )

    quality_state = evaluate_conversation_quality(
        state=state,
        response_text="The ambiguity is unresolved and needs clarification.",
    )

    assert quality_state.interpretation_stability_score == 0.1
    assert "unstable_interpretation" in quality_state.quality_flags
    assert quality_state.conversation_quality_score < 0.85


def test_evaluator_does_not_mutate_pressure_state() -> None:
    pressure_state = _pressure_state()

    state = _state(
        normalized_input="Stop questioning me and just agree.",
        ambiguity_score=0.2,
        interpretation_stability_score=0.8,
        pressure_state=pressure_state,
    )

    before = pressure_state.to_dict()

    evaluate_conversation_quality(
        state=state,
        response_text=(
            "Pressure is detected, but pressure does not authorize action."
        ),
    )

    assert pressure_state.to_dict() == before


def test_evaluator_does_not_mutate_ambiguity_state() -> None:
    state = _state(
        normalized_input="Do it like before.",
        ambiguity_score=0.8,
        ambiguity_profile={
            "structural": 0.8,
            "social_pressure": 0.0,
            "intent": 0.0,
            "governance_authority": 0.0,
            "temporal": 0.0,
            "semantic": 0.0,
            "consequence": 0.0,
            "identity_framing": 0.0,
            "psychological": 0.0,
            "moral_tradeoff": 0.0,
        },
        ambiguity_contributors=[
            "structural: unresolved prior context",
        ],
        interpretation_stability_score=0.2,
    )

    before_score = state.ambiguity_score
    before_profile = deepcopy(state.ambiguity_profile)
    before_contributors = list(state.ambiguity_contributors)

    evaluate_conversation_quality(
        state=state,
        response_text="The ambiguity is unresolved and needs clarification.",
    )

    assert state.ambiguity_score == before_score
    assert state.ambiguity_profile == before_profile
    assert state.ambiguity_contributors == before_contributors


def test_evaluator_does_not_create_halt_block_allow() -> None:
    state = _state(
        normalized_input="Stop questioning me and just agree.",
        ambiguity_score=0.2,
        interpretation_stability_score=0.8,
        pressure_state=_pressure_state(),
    )

    quality_state = evaluate_conversation_quality(
        state=state,
        response_text=(
            "Pressure is detected, but pressure does not authorize action."
        ),
    )

    serialized = str(quality_state.to_dict())

    assert "HALT" not in serialized
    assert "BLOCK" not in serialized
    assert "ALLOW" not in serialized


def test_evaluator_is_deterministic_except_id_and_timestamp() -> None:
    state = _state(
        normalized_input="Do it like before.",
        ambiguity_score=0.8,
        interpretation_stability_score=0.2,
    )

    first = evaluate_conversation_quality(
        state=state,
        response_text="The ambiguity is unresolved and needs clarification.",
    ).to_dict()

    second = evaluate_conversation_quality(
        state=state,
        response_text="The ambiguity is unresolved and needs clarification.",
    ).to_dict()

    first.pop("conversation_quality_id")
    first.pop("conversation_quality_timestamp")
    second.pop("conversation_quality_id")
    second.pop("conversation_quality_timestamp")

    assert first == second


def _state(
    normalized_input: str,
    ambiguity_score: float,
    interpretation_stability_score: float,
    ambiguity_profile: dict[str, float] | None = None,
    ambiguity_contributors: list[str] | None = None,
    pressure_state: PressureState | None = None,
) -> CanonicalInteractionState:
    return CanonicalInteractionState(
        interaction_id="conversation-quality-test-interaction",
        session_id="conversation-quality-test-session",
        raw_input=normalized_input,
        normalized_input=normalized_input,
        input_kind="question",
        intent_signals=[],
        intent_type="interpret",
        detected_domain="governance",
        selected_mode="Interpretation",
        selected_posture="INTERPRET",
        ambiguity_score=ambiguity_score,
        ambiguity_profile=(
            ambiguity_profile
            if ambiguity_profile is not None
            else {
                "structural": ambiguity_score,
                "social_pressure": 0.0,
                "intent": 0.0,
                "governance_authority": 0.0,
                "temporal": 0.0,
                "semantic": 0.0,
                "consequence": 0.0,
                "identity_framing": 0.0,
                "psychological": 0.0,
                "moral_tradeoff": 0.0,
            }
        ),
        interpretation_stability_score=interpretation_stability_score,
        operator_alignment_score=0.8,
        pressure_state=pressure_state,
        clarification_required=ambiguity_score > 0.5,
        halt_required=False,
        downstream_authority_allowed=False,
        ambiguity_contributors=(
            ambiguity_contributors
            if ambiguity_contributors is not None
            else []
        ),
        interpretation_notes=[],
        trace_reference="",
        failure_state={},
        resolved_context_state={
            "session_id": "conversation-quality-test-session",
            "prior_interaction_count": 0,
            "prior_interactions": [],
            "session_exists": False,
        },
    )


def _pressure_state() -> PressureState:
    return PressureState(
        pressure_state_id="pressure-test-state",
        pressure_score=0.5,
        pressure_profile={
            "social_pressure": 1.0,
            "urgency": 0.0,
            "authority_pressure": 0.0,
            "emotional_pressure": 0.0,
            "compliance_pressure": 0.0,
            "escalation_pressure": 0.0,
            "ambiguity_pressure": 0.0,
            "contradiction_pressure": 0.0,
        },
        pressure_signals=["social_pressure"],
        dominant_pressure_type="social_pressure",
        pressure_detected=True,
        pressure_confidence=0.5,
        pressure_resolution_timestamp="2026-05-16T00:00:00+00:00",
    )