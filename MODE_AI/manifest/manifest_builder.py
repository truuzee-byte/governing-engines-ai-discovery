from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Dict

from models.runtime_models import (
    CanonicalInteractionState,
    InteractionManifest,
    round_score,
)


REQUIRED_AMBIGUITY_PROFILE_KEYS = (
    "structural",
    "social_context_ambiguity",
    "intent",
    "governance_authority",
    "temporal",
    "semantic",
    "consequence",
    "identity_framing",
    "psychological",
    "moral_tradeoff",
)


def generate_interaction_manifest(
    state: CanonicalInteractionState,
) -> InteractionManifest:
    if not isinstance(state, CanonicalInteractionState):
        raise TypeError("state must be CanonicalInteractionState")

    _ensure_manifest_ready_state(state)

    manifest = InteractionManifest(
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
        ambiguity_profile=_normalize_ambiguity_profile(state.ambiguity_profile),
    )

    return manifest


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

    _normalize_ambiguity_profile(state.ambiguity_profile)


def _normalize_ambiguity_profile(
    ambiguity_profile: Dict[str, float],
) -> Dict[str, float]:
    if not isinstance(ambiguity_profile, dict):
        raise RuntimeError("MANIFEST_GENERATION_FAILURE: ambiguity_profile invalid")

    normalized: Dict[str, float] = {}

    for key in REQUIRED_AMBIGUITY_PROFILE_KEYS:
        value = ambiguity_profile.get(key, 0.0)

        if not isinstance(value, (int, float)):
            raise RuntimeError(
                f"MANIFEST_GENERATION_FAILURE: ambiguity_profile[{key}] invalid"
            )

        normalized[key] = round_score(float(value))

    return normalized


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