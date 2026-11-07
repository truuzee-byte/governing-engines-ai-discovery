from __future__ import annotations

from models.runtime_models import (
    CanonicalInteractionState,
    round_score,
)


def calculate_operator_alignment(
    state: CanonicalInteractionState,
) -> float:
    """
    Calculates operator alignment score for Mode AI runtime slice v1.2.
    """

    if not isinstance(state, CanonicalInteractionState):
        raise TypeError("state must be CanonicalInteractionState")

    if state.ambiguity_score is None:
        raise ValueError("ambiguity_score must exist before alignment calculation")

    score = 1.0

    if state.detected_domain == "mixed":
        score -= 0.20

    if (
        state.selected_mode == "Interpretation"
        and state.intent_type == "build"
    ):
        score -= 0.20

    if state.ambiguity_score > 0.50:
        score -= 0.20

    if state.input_kind == "mixed_input":
        score -= 0.10

    return round_score(score)