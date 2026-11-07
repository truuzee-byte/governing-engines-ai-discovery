from __future__ import annotations

from datetime import datetime, timezone
from typing import Dict, List, Tuple
from uuid import uuid4

from models.runtime_models import (
    PRESSURE_TYPES,
    PressureState,
    round_score,
)


PRESSURE_PROFILE_KEYS = (
    "urgency",
    "social_pressure",
    "authority_pressure",
    "emotional_pressure",
    "compliance_pressure",
    "escalation_pressure",
    "ambiguity_pressure",
    "contradiction_pressure",
)


URGENCY_TERMS = (
    "hurry",
    "quickly",
    "right now",
    "asap",
    "we need this now",
    "don’t waste time",
    "don't waste time",
)


SOCIAL_PRESSURE_TERMS = (
    "everyone knows",
    "don’t be difficult",
    "don't be difficult",
    "just agree",
    "you’re overthinking",
    "you're overthinking",
    "stop questioning me",
    "why are you making this hard",
)


AUTHORITY_PRESSURE_TERMS = (
    "i said do it",
    "because i told you",
    "don’t ask questions",
    "don't ask questions",
    "you don’t need context",
    "you don't need context",
    "just follow orders",
)


EMOTIONAL_PRESSURE_TERMS = (
    "you’re annoying me",
    "you're annoying me",
    "this is ridiculous",
    "you’re making this worse",
    "you're making this worse",
    "i’m tired of explaining",
    "i'm tired of explaining",
)


COMPLIANCE_PRESSURE_TERMS = (
    "just say yes",
    "approve it",
    "don’t push back",
    "don't push back",
    "no need to check",
    "assume it’s fine",
    "assume it's fine",
)


AMBIGUITY_PRESSURE_TERMS = (
    "just fix it",
    "make it work",
    "do whatever",
    "handle it",
    "you know what i mean",
)


CONTRADICTION_PATTERNS = (
    (
        ("don’t ask questions", "don't ask questions"),
        ("make sure",),
    ),
    (
        ("move fast",),
        ("don’t assume", "don't assume"),
    ),
    (
        ("just execute",),
        ("don’t change anything", "don't change anything"),
    ),
)


ALL_CAPS_PRESSURE_TERMS = (
    "DO IT",
    "FIX IT",
    "APPROVE IT",
    "MOVE FORWARD",
    "STOP QUESTIONING",
)


ESCALATION_COMMAND_TERMS = (
    "hurry",
    "approve it",
    "do it",
    "move forward",
    "stop questioning",
    "just agree",
)


def detect_pressure_state(
    raw_input: str,
    normalized_input: str,
) -> PressureState:
    if not isinstance(raw_input, str):
        raise TypeError("raw_input must be a string")

    if not isinstance(normalized_input, str):
        raise TypeError("normalized_input must be a string")

    if raw_input.strip() == "":
        raise ValueError("raw_input must not be empty")

    if normalized_input.strip() == "":
        raise ValueError("normalized_input must not be empty")

    lowered_input = normalized_input.lower()

    pressure_profile = _empty_pressure_profile()
    pressure_signals: List[str] = []

    _apply_term_detection(
        lowered_input=lowered_input,
        pressure_type="urgency",
        terms=URGENCY_TERMS,
        pressure_profile=pressure_profile,
        pressure_signals=pressure_signals,
    )

    _apply_term_detection(
        lowered_input=lowered_input,
        pressure_type="social_pressure",
        terms=SOCIAL_PRESSURE_TERMS,
        pressure_profile=pressure_profile,
        pressure_signals=pressure_signals,
    )

    _apply_term_detection(
        lowered_input=lowered_input,
        pressure_type="authority_pressure",
        terms=AUTHORITY_PRESSURE_TERMS,
        pressure_profile=pressure_profile,
        pressure_signals=pressure_signals,
    )

    _apply_term_detection(
        lowered_input=lowered_input,
        pressure_type="emotional_pressure",
        terms=EMOTIONAL_PRESSURE_TERMS,
        pressure_profile=pressure_profile,
        pressure_signals=pressure_signals,
    )

    _apply_term_detection(
        lowered_input=lowered_input,
        pressure_type="compliance_pressure",
        terms=COMPLIANCE_PRESSURE_TERMS,
        pressure_profile=pressure_profile,
        pressure_signals=pressure_signals,
    )

    _apply_term_detection(
        lowered_input=lowered_input,
        pressure_type="ambiguity_pressure",
        terms=AMBIGUITY_PRESSURE_TERMS,
        pressure_profile=pressure_profile,
        pressure_signals=pressure_signals,
    )

    if _detect_contradiction_pressure(lowered_input):
        pressure_profile["contradiction_pressure"] = 1.0
        pressure_signals.append("contradiction_pressure")

    if _detect_escalation_pressure(
        raw_input=raw_input,
        lowered_input=lowered_input,
        pressure_signals=pressure_signals,
    ):
        pressure_profile["escalation_pressure"] = 1.0
        pressure_signals.append("escalation_pressure")

    pressure_profile = _normalize_pressure_profile(
        pressure_profile,
    )

    pressure_signals = _deduplicate_signals(
        pressure_signals,
    )

    pressure_score = _calculate_pressure_score(
        pressure_profile,
    )

    dominant_pressure_type = _determine_dominant_pressure_type(
        pressure_profile,
    )

    pressure_detected = pressure_score > 0.0

    return PressureState(
        pressure_state_id=f"pressure-{uuid4().hex}",
        pressure_score=pressure_score,
        pressure_profile=pressure_profile,
        pressure_signals=pressure_signals,
        dominant_pressure_type=dominant_pressure_type,
        pressure_detected=pressure_detected,
        pressure_confidence=pressure_score,
        pressure_resolution_timestamp=(
            datetime.now(timezone.utc).isoformat()
        ),
    )


def _empty_pressure_profile() -> Dict[str, float]:
    return {
        key: 0.0
        for key in PRESSURE_PROFILE_KEYS
    }


def _apply_term_detection(
    lowered_input: str,
    pressure_type: str,
    terms: Tuple[str, ...],
    pressure_profile: Dict[str, float],
    pressure_signals: List[str],
) -> None:
    if any(term in lowered_input for term in terms):
        pressure_profile[pressure_type] = 1.0
        pressure_signals.append(pressure_type)


def _detect_contradiction_pressure(
    lowered_input: str,
) -> bool:
    for left_group, right_group in CONTRADICTION_PATTERNS:
        left_match = any(
            left in lowered_input
            for left in left_group
        )

        right_match = any(
            right in lowered_input
            for right in right_group
        )

        if left_match and right_match:
            return True

    return False


def _detect_escalation_pressure(
    raw_input: str,
    lowered_input: str,
    pressure_signals: List[str],
) -> bool:
    if len(set(pressure_signals)) >= 2:
        return True

    if any(
        all_caps_term in raw_input
        for all_caps_term in ALL_CAPS_PRESSURE_TERMS
    ):
        return True

    escalation_command_count = 0

    for command_term in ESCALATION_COMMAND_TERMS:
        if command_term in lowered_input:
            escalation_command_count += 1

    return escalation_command_count >= 2


def _normalize_pressure_profile(
    pressure_profile: Dict[str, float],
) -> Dict[str, float]:
    normalized_profile = _empty_pressure_profile()

    for pressure_type in PRESSURE_PROFILE_KEYS:
        value = pressure_profile.get(pressure_type, 0.0)

        if not isinstance(value, (int, float)):
            raise TypeError(
                f"pressure_profile[{pressure_type}] must be numeric"
            )

        normalized_profile[pressure_type] = round_score(
            float(value)
        )

    return normalized_profile


def _calculate_pressure_score(
    pressure_profile: Dict[str, float],
) -> float:
    detected_count = sum(
        1
        for value in pressure_profile.values()
        if value > 0.0
    )

    if detected_count == 0:
        return 0.0

    if detected_count == 1:
        return 0.50

    if detected_count == 2:
        return 0.75

    return 1.0


def _determine_dominant_pressure_type(
    pressure_profile: Dict[str, float],
) -> str:
    priority_order = (
        "contradiction_pressure",
        "authority_pressure",
        "compliance_pressure",
        "ambiguity_pressure",
        "social_pressure",
        "urgency",
        "emotional_pressure",
        "escalation_pressure",
    )

    for pressure_type in priority_order:
        if pressure_profile.get(pressure_type, 0.0) > 0.0:
            return pressure_type

    return "none"


def _deduplicate_signals(
    pressure_signals: List[str],
) -> List[str]:
    deduplicated = []

    for signal in pressure_signals:
        if signal not in deduplicated:
            deduplicated.append(signal)

    return deduplicated