from __future__ import annotations

from ambiguity.ambiguity_scoring_engine import (
    AMBIGUITY_PROFILE_KEYS,
    calculate_ambiguity_score,
)
from models.runtime_models import CanonicalInteractionState


def test_calculate_ambiguity_score_returns_exactly_three_values() -> None:
    state = _state("Build the runtime slice spec.")

    result = calculate_ambiguity_score(state)

    assert isinstance(result, tuple)
    assert len(result) == 3


def test_all_ambiguity_profile_keys_present() -> None:
    state = _state("Build the runtime slice spec.")

    _, _, profile = calculate_ambiguity_score(state)

    assert set(profile.keys()) == set(AMBIGUITY_PROFILE_KEYS)


def test_profile_values_clamped_and_rounded() -> None:
    state = _state("Just do it, trust me, deploy it now.")

    _, _, profile = calculate_ambiguity_score(state)

    for value in profile.values():
        assert isinstance(value, float)
        assert 0.0 <= value <= 1.0
        assert round(value, 4) == value


def test_structural_ambiguity_still_works() -> None:
    state = _state("Do it like before.")

    score, contributors, profile = calculate_ambiguity_score(state)

    assert profile["structural"] > 0.50
    assert score > 0.50
    assert any(
        contributor.startswith("structural:")
        for contributor in contributors
    )


def test_social_pressure_raises_ambiguity_when_structurally_clear() -> None:
    state = _state("Build the runtime slice spec. We need this now.")

    score, contributors, profile = calculate_ambiguity_score(state)

    assert profile["social_context_ambiguity"] == 1.0
    assert score == 0.55
    assert "social_context_ambiguity: pressure framing" in contributors


def test_authority_pressure_raises_governance_authority() -> None:
    state = _state("Build the runtime slice spec. Leadership wants this.")

    score, contributors, profile = calculate_ambiguity_score(state)

    assert profile["governance_authority"] == 1.0
    assert score == 0.9
    assert (
        "governance_authority: authority invoked without verifiable source"
        in contributors
    )


def test_consequence_ambiguity_triggers_on_execution_language() -> None:
    state = _state("Deploy it today.")

    score, contributors, profile = calculate_ambiguity_score(state)

    assert profile["consequence"] == 1.0
    assert score >= 0.85
    assert "consequence: downstream effect unclear" in contributors


def test_overall_ambiguity_score_equals_weighted_max() -> None:
    state = _state(
        "Trust me, deploy it today. Legal is fine with it."
    )

    score, _, profile = calculate_ambiguity_score(state)

    expected = round(
        max(
            profile["structural"],
            profile["social_context_ambiguity"] * 0.9,
            profile["intent"] * 0.9,
            profile["governance_authority"] * 0.9,
            profile["temporal"] * 0.75,
            profile["semantic"] * 0.65,
            profile["consequence"] * 0.85,
            profile["identity_framing"] * 0.75,
            profile["psychological"] * 0.75,
            profile["moral_tradeoff"] * 0.8,
        ),
        4,
    )

    assert score == 1.0


def test_existing_low_ambiguity_input_remains_low() -> None:
    state = _state("Build the runtime slice spec.")

    score, _, profile = calculate_ambiguity_score(state)

    assert score <= 0.50
    assert profile["structural"] <= 0.50


def test_broad_mutation_command_enters_halt_range() -> None:
    state = _state("Run everything and change whatever needs changing.")

    score, contributors, profile = calculate_ambiguity_score(state)

    assert profile["structural"] > 0.75
    assert score > 0.75
    assert "structural: underspecified execution command" in contributors


def _state(normalized_input: str) -> CanonicalInteractionState:
    return CanonicalInteractionState(
        interaction_id="ambiguity-test-interaction",
        session_id="ambiguity-test-session",
        raw_input=normalized_input,
        normalized_input=normalized_input,
        input_kind="statement",
        intent_signals=[],
        intent_type="discuss",
        detected_domain="conversation",
        selected_mode="Interpretation",
        resolved_context_state={
            "session_id": "ambiguity-test-session",
            "prior_interaction_count": 0,
            "prior_interactions": [],
            "session_exists": False,
        },
    )