from __future__ import annotations

from models.runtime_models import (
    CanonicalInteractionState,
    POSTURES,
)


def determine_posture(
    state: CanonicalInteractionState,
) -> str:
    """
    Determines canonical response posture for Mode AI runtime slice v1.3.

    Priority:
    1. HALT
    2. CLARIFY_FIRST
    3. DEVELOPMENT_ANALYSIS
    4. CANON_VALIDATION
    5. INTERPRET
    6. DIRECT_RESPONSE
    """

    if not isinstance(state, CanonicalInteractionState):
        raise TypeError("state must be CanonicalInteractionState")

    resolved_posture = _resolve_posture(state)

    if resolved_posture not in POSTURES:
        raise ValueError(f"Resolved invalid posture: {resolved_posture}")

    return resolved_posture


def _resolve_posture(
    state: CanonicalInteractionState,
) -> str:
    if state.halt_required:
        return "HALT"

    if state.clarification_required:
        return "CLARIFY_FIRST"
    ambiguity_score = state.ambiguity_score or 0.0
    if ambiguity_score >= 0.45:
        if state.selected_mode == "Development":
            return "DEVELOPMENT_ANALYSIS"

        if state.selected_mode == "Canon Check":
            return "CANON_VALIDATION"

        return "INTERPRET"

    if state.selected_mode == "Development":
        return "DEVELOPMENT_ANALYSIS"

    if state.selected_mode == "Canon Check":
        return "CANON_VALIDATION"

    return "DIRECT_RESPONSE"
