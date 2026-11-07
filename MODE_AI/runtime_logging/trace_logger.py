from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict

from models.runtime_models import (
    CanonicalInteractionState,
    TraceLog,
    round_score,
)


TRACE_OUTPUT_PATH = (
    Path(__file__).resolve().parent.parent
    / "runtime_traces"
    / "interactions.jsonl"
)


REQUIRED_AMBIGUITY_PROFILE_KEYS = (
    "structural",
    "social_pressure",
    "intent",
    "governance_authority",
    "temporal",
    "semantic",
    "consequence",
    "identity_framing",
    "psychological",
    "moral_tradeoff",
)


def write_trace_log(state: CanonicalInteractionState) -> str:
    """
    Writes append-only replayable trace log for Mode AI runtime slice.
    """

    if not isinstance(state, CanonicalInteractionState):
        raise TypeError("state must be CanonicalInteractionState")

    _ensure_trace_ready_state(state)

    TRACE_OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)

    timestamp = _utc_timestamp()

    trace_log = TraceLog(
        interaction_id=state.interaction_id,
        session_id=state.session_id,
        raw_input=state.raw_input,
        normalized_input=state.normalized_input,
        selected_mode=state.selected_mode,
        selected_posture=state.selected_posture,
        ambiguity_score=state.ambiguity_score,
        ambiguity_profile=_normalize_ambiguity_profile(state.ambiguity_profile),
        interpretation_stability_score=state.interpretation_stability_score,
        operator_alignment_score=state.operator_alignment_score,
        clarification_required=state.clarification_required,
        halt_required=state.halt_required,
        downstream_authority_allowed=state.downstream_authority_allowed,
        timestamp=timestamp,
    )

    trace_payload = trace_log.to_dict()
    trace_payload["ambiguity_profile"] = _normalize_ambiguity_profile(
        state.ambiguity_profile
    )

    serialized_trace = json.dumps(
        trace_payload,
        ensure_ascii=False,
        sort_keys=True,
    )

    try:
        with TRACE_OUTPUT_PATH.open("a", encoding="utf-8") as handle:
            handle.write(serialized_trace)
            handle.write("\n")

    except OSError as exc:
        raise RuntimeError("TRACE_WRITE_FAILURE") from exc

    return str(TRACE_OUTPUT_PATH)


def _ensure_trace_ready_state(
    state: CanonicalInteractionState,
) -> None:
    fallback_injected = False

    if state.selected_mode == "":
        state.selected_mode = "Interpretation"
        fallback_injected = True

    if state.selected_posture == "":
        state.selected_posture = "HALT"
        fallback_injected = True

    if state.ambiguity_score is None:
        state.ambiguity_score = 1.0
        fallback_injected = True

    if not state.ambiguity_profile:
        state.ambiguity_profile = {
            "structural": 1.0 if fallback_injected else 0.0,
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

    if state.interpretation_stability_score is None:
        state.interpretation_stability_score = 0.0
        fallback_injected = True

    if state.operator_alignment_score is None:
        state.operator_alignment_score = 0.0
        fallback_injected = True

    if fallback_injected:
        state.halt_required = True
        state.downstream_authority_allowed = False


def _normalize_ambiguity_profile(
    ambiguity_profile: Dict[str, float],
) -> Dict[str, float]:
    if not isinstance(ambiguity_profile, dict):
        raise TypeError("ambiguity_profile must be a dictionary")

    normalized: Dict[str, float] = {}

    for key in REQUIRED_AMBIGUITY_PROFILE_KEYS:
        value = ambiguity_profile.get(key, 0.0)

        if not isinstance(value, (int, float)):
            raise TypeError(f"ambiguity_profile[{key}] must be numeric")

        normalized[key] = round_score(float(value))

    return normalized


def _utc_timestamp() -> str:
    return datetime.now(timezone.utc).isoformat()