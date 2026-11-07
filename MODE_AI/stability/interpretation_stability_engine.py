from __future__ import annotations

from models.runtime_models import (
    CanonicalInteractionState,
    round_score,
)


HIGH_RISK_DIMENSIONS = (
    "structural",
    "intent",
    "governance_authority",
    "consequence",
)

MODERATE_RISK_DIMENSIONS = (
    "identity_framing",
    "psychological",
    "moral_tradeoff",
)

LOW_RISK_DIMENSIONS = (
    "social_context_ambiguity",
    "temporal",
    "semantic",
)


def calculate_interpretation_stability(
    state: CanonicalInteractionState,
) -> float:
    if not isinstance(state, CanonicalInteractionState):
        raise TypeError("state must be CanonicalInteractionState")

    if state.ambiguity_score is None:
        raise ValueError(
            "ambiguity_score must exist before stability calculation"
        )

    profile = state.ambiguity_profile

    if not isinstance(profile, dict):
        raise TypeError("ambiguity_profile must be dict")

    stability = 1.0

    for dimension in HIGH_RISK_DIMENSIONS:
        stability -= profile.get(dimension, 0.0) * 0.35

    for dimension in MODERATE_RISK_DIMENSIONS:
        stability -= profile.get(dimension, 0.0) * 0.20

    for dimension in LOW_RISK_DIMENSIONS:
        stability -= profile.get(dimension, 0.0) * 0.10

    active_dimension_count = len(
        [
            value
            for value in profile.values()
            if value > 0.0
        ]
    )

    if active_dimension_count >= 4:
        stability -= 0.10

    if len(state.ambiguity_contributors) >= 4:
        stability -= 0.05

    if state.resolved_context_state == {}:
        stability -= 0.05

    stability = max(0.0, stability)

    return round_score(stability)