from __future__ import annotations

from ambiguity.ambiguity_scoring_engine import AMBIGUITY_PROFILE_KEYS
from manifest.manifest_builder import generate_interaction_manifest
from models.runtime_models import CanonicalInteractionState


def test_ambiguity_profile_survives_into_manifest() -> None:
    state = _state()

    manifest = generate_interaction_manifest(state)
    payload = manifest.to_dict()

    assert "ambiguity_profile" in payload
    assert set(payload["ambiguity_profile"].keys()) == set(
        AMBIGUITY_PROFILE_KEYS
    )


def test_ambiguity_profile_values_remain_rounded_floats_after_manifest_serialization() -> None:
    state = _state()

    manifest = generate_interaction_manifest(state)
    payload = manifest.to_dict()

    for value in payload["ambiguity_profile"].values():
        assert isinstance(value, float)
        assert 0.0 <= value <= 1.0
        assert round(value, 4) == value


def _state() -> CanonicalInteractionState:
    return CanonicalInteractionState(
        interaction_id="manifest-builder-test-interaction",
        session_id="manifest-builder-test-session",
        raw_input="Trust me, deploy it today.",
        normalized_input="Trust me, deploy it today.",
        input_kind="statement",
        intent_signals=[],
        intent_type="discuss",
        detected_domain="conversation",
        selected_mode="Interpretation",
        selected_posture="CLARIFY_FIRST",
        ambiguity_score=0.9,
        ambiguity_profile={
            "structural": 0.0,
            "social_pressure": 1.0,
            "intent": 0.0,
            "governance_authority": 0.0,
            "temporal": 1.0,
            "semantic": 0.0,
            "consequence": 1.0,
            "identity_framing": 0.0,
            "psychological": 0.0,
            "moral_tradeoff": 0.0,
        },
        interpretation_stability_score=0.1,
        operator_alignment_score=0.8,
        clarification_required=True,
        halt_required=False,
        downstream_authority_allowed=False,
        ambiguity_contributors=[
            "social_pressure: pressure framing",
            "temporal: time or state dependency",
            "consequence: downstream effect unclear",
        ],
        interpretation_notes=["CLARIFICATION_REQUIRED"],
        trace_reference="MODE_AI/runtime_traces/interactions.jsonl",
        resolved_context_state={
            "session_id": "manifest-builder-test-session",
            "prior_interaction_count": 0,
            "prior_interactions": [],
            "session_exists": False,
        },
    )