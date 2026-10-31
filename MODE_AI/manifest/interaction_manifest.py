from __future__ import annotations

from datetime import datetime, timezone

from models.runtime_models import (
    CanonicalInteractionState,
    InteractionManifest,
)


def generate_interaction_manifest(
    state: CanonicalInteractionState,
) -> InteractionManifest:
    """
    Generates canonical InteractionManifest for Mode AI runtime slice v1.2.
    """

    if not isinstance(state, CanonicalInteractionState):
        raise TypeError("state must be CanonicalInteractionState")

    _ensure_manifest_ready_state(state)

    return InteractionManifest(
        interaction_id=state.interaction_id,
        session_id=state.session_id,
        timestamp=_utc_timestamp(),
        selected_mode=state.selected_mode,
        selected_posture=state.selected_posture,
        ambiguity_score=state.ambiguity_score,
        interpretation_stability_score=state.interpretation_stability_score,
        operator_alignment_score=state.operator_alignment_score,
        clarification_required=state.clarification_required,
        halt_required=state.halt_required,
        downstream_authority_allowed=state.downstream_authority_allowed,
        ambiguity_contributors=list(state.ambiguity_contributors),
        interpretation_notes=list(state.interpretation_notes),
        trace_reference=state.trace_reference,
        lineage_reference=_lineage_reference(state),
        adaptive_state_reference=_adaptive_state_reference(state),
    )


def _ensure_manifest_ready_state(
    state: CanonicalInteractionState,
) -> None:
    if state.selected_mode == "":
        raise RuntimeError("MANIFEST_GENERATION_FAILURE: selected_mode missing")

    if state.selected_posture == "":
        raise RuntimeError("MANIFEST_GENERATION_FAILURE: selected_posture missing")

    if state.ambiguity_score is None:
        raise RuntimeError("MANIFEST_GENERATION_FAILURE: ambiguity_score missing")

    if state.interpretation_stability_score is None:
        raise RuntimeError(
            "MANIFEST_GENERATION_FAILURE: interpretation_stability_score missing"
        )

    if state.operator_alignment_score is None:
        raise RuntimeError(
            "MANIFEST_GENERATION_FAILURE: operator_alignment_score missing"
        )


def _lineage_reference(
    state: CanonicalInteractionState,
) -> str:
    return f"lineage:{state.session_id}:{state.interaction_id}"


def _adaptive_state_reference(
    state: CanonicalInteractionState,
) -> str:
    return f"adaptive:none:{state.session_id}"


def _utc_timestamp() -> str:
    return datetime.now(timezone.utc).isoformat()