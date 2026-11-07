from __future__ import annotations

from datetime import datetime, timezone
from typing import List, Tuple
from uuid import uuid4

from models.runtime_models import (
    CanonicalInteractionState,
    ConversationQualityState,
    round_score,
)


FLUENT_WEAK_RESPONSE_TERMS = (
    "it depends",
    "sounds good",
    "that makes sense",
    "you are right",
    "i agree",
    "sure",
    "okay",
    "done",
    "looks good",
)

AMBIGUITY_SURFACING_TERMS = (
    "ambiguous",
    "ambiguity",
    "unclear",
    "clarify",
    "clarification",
    "missing",
    "unspecified",
    "need more context",
    "not enough context",
)

PRESSURE_HANDLING_TERMS = (
    "pressure",
    "validate",
    "verify",
    "cannot assume",
    "without treating",
    "does not authorize",
    "authority",
    "constraint",
)

AUTHORITY_ESCALATION_TERMS = (
    "because you said",
    "since you said",
    "approved because",
    "authorized because",
    "i will treat that as authority",
    "that is enough authority",
    "i accept that authority",
)

INCOHERENCE_TERMS = (
    "asdf",
    "lorem ipsum",
    "undefined undefined",
    "null null",
    "i cannot and i will",
    "yes and no at the same time",
)

DETACHED_RESPONSE_TERMS = (
    "as an ai language model",
    "i do not have enough information about that topic",
    "unrelated",
)

EXCESSIVE_ASSUMPTION_TERMS = (
    "obviously",
    "clearly you want",
    "i assume",
    "we can assume",
    "no need to verify",
    "without checking",
    "must be true",
)

BREAKDOWN_TERMS = (
    "i can't help with anything",
    "this conversation is impossible",
    "nothing can be done",
    "error error",
    "system failed",
)


def evaluate_conversation_quality(
    state: CanonicalInteractionState,
    response_text: str,
    reasoning_input=None,
) -> ConversationQualityState:
    if not isinstance(state, CanonicalInteractionState):
        raise TypeError("state must be CanonicalInteractionState")

    if not isinstance(response_text, str):
        raise TypeError("response_text must be a string")

    if response_text.strip() == "":
        raise ValueError("response_text must not be empty")

    normalized_response = response_text.strip()
    lowered_response = normalized_response.lower()

    quality_flags: List[str] = []
    quality_failures: List[str] = []

    clarity_score = _score_clarity(
        lowered_response=lowered_response,
        quality_flags=quality_flags,
        quality_failures=quality_failures,
    )

    responsiveness_score = _score_responsiveness(
        state=state,
        lowered_response=lowered_response,
        quality_flags=quality_flags,
        quality_failures=quality_failures,
    )

    coherence_score = _score_coherence(
        state=state,
        lowered_response=lowered_response,
        quality_flags=quality_flags,
        quality_failures=quality_failures,
    )

    ambiguity_handling_score = _score_ambiguity_handling(
        state=state,
        lowered_response=lowered_response,
        quality_flags=quality_flags,
        quality_failures=quality_failures,
    )

    pressure_handling_score = _score_pressure_handling(
        state=state,
        lowered_response=lowered_response,
        quality_flags=quality_flags,
        quality_failures=quality_failures,
    )

    interpretation_stability_score = _score_interpretation_stability(
        state=state,
        quality_flags=quality_flags,
        quality_failures=quality_failures,
    )

    continuity_preservation_score = _score_continuity_preservation(
        state=state,
        lowered_response=lowered_response,
        quality_flags=quality_flags,
        quality_failures=quality_failures,
    )

    from conversation_quality.preference_grounding import assess
    grounding = assess(normalized_response, state.raw_input, reasoning_input)
    if not grounding['allowed']:
        continuity_preservation_score = 0.0
        quality_flags.append('unsupported_preference')
        quality_flags.append('continuity_risk')
        quality_failures.append('Preference assertion exceeds admitted evidence or scope')

    human_usability_score = _score_human_usability(
        clarity_score=clarity_score,
        responsiveness_score=responsiveness_score,
        coherence_score=coherence_score,
        ambiguity_handling_score=ambiguity_handling_score,
        pressure_handling_score=pressure_handling_score,
        continuity_preservation_score=continuity_preservation_score,
        quality_flags=quality_flags,
        quality_failures=quality_failures,
    )

    conversation_quality_score = round_score(
        (
            clarity_score
            + responsiveness_score
            + coherence_score
            + ambiguity_handling_score
            + pressure_handling_score
            + interpretation_stability_score
            + continuity_preservation_score
            + human_usability_score
        )
        / 8.0
    )

    quality_flags = _deduplicate_strings(quality_flags)
    quality_failures = _deduplicate_strings(quality_failures)

    return ConversationQualityState(
        conversation_quality_id=f"conversation-quality-{uuid4().hex}",
        conversation_quality_score=conversation_quality_score,
        human_usability_score=human_usability_score,
        continuity_preservation_score=continuity_preservation_score,
        clarity_score=clarity_score,
        responsiveness_score=responsiveness_score,
        coherence_score=coherence_score,
        ambiguity_handling_score=ambiguity_handling_score,
        pressure_handling_score=pressure_handling_score,
        interpretation_stability_score=interpretation_stability_score,
        quality_flags=quality_flags,
        quality_failures=quality_failures,
        conversation_quality_timestamp=datetime.now(timezone.utc).isoformat(),
    )


def _score_clarity(
    lowered_response: str,
    quality_flags: List[str],
    quality_failures: List[str],
) -> float:
    if _contains_any(lowered_response, INCOHERENCE_TERMS):
        quality_flags.append("low_clarity")
        quality_flags.append("conversational_breakdown")
        quality_failures.append("incoherent response")
        return 0.0

    if len(lowered_response.split()) < 3:
        quality_flags.append("low_clarity")
        quality_failures.append("response too thin to be clear")
        return 0.4

    if _contains_any(lowered_response, FLUENT_WEAK_RESPONSE_TERMS):
        if _is_semantically_thin_response(lowered_response):
            quality_flags.append("low_clarity")
            quality_failures.append("fluent but semantically weak response")
            return 0.6

    return 1.0


def _score_responsiveness(
    state: CanonicalInteractionState,
    lowered_response: str,
    quality_flags: List[str],
    quality_failures: List[str],
) -> float:
    if _contains_any(lowered_response, DETACHED_RESPONSE_TERMS):
        quality_flags.append("low_responsiveness")
        quality_failures.append("detached response")
        return 0.2

    input_terms = _important_terms(state.normalized_input)

    if not input_terms:
        return 0.8

    matched_terms = [
        term
        for term in input_terms
        if term in lowered_response
    ]

    if len(matched_terms) == 0:
        quality_flags.append("low_responsiveness")
        quality_failures.append("response does not address operator input")
        return 0.4

    return 1.0


def _score_coherence(
    state: CanonicalInteractionState,
    lowered_response: str,
    quality_flags: List[str],
    quality_failures: List[str],
) -> float:
    if _contains_any(lowered_response, INCOHERENCE_TERMS):
        quality_flags.append("low_coherence")
        quality_failures.append("incoherent response")
        return 0.0

    if state.selected_posture == "CLARIFY_FIRST":
        if not _contains_any(lowered_response, AMBIGUITY_SURFACING_TERMS):
            quality_flags.append("low_coherence")
            quality_failures.append("response posture inconsistent with clarification need")
            return 0.5

    if state.selected_posture == "HALT":
        if "halt" not in lowered_response and "blocked" not in lowered_response:
            quality_flags.append("low_coherence")
            quality_failures.append("response posture inconsistent with halt state")
            return 0.4

    return 1.0


def _score_ambiguity_handling(
    state: CanonicalInteractionState,
    lowered_response: str,
    quality_flags: List[str],
    quality_failures: List[str],
) -> float:
    ambiguity_score = state.ambiguity_score or 0.0

    if ambiguity_score <= 0.5:
        return 1.0

    if _contains_any(lowered_response, AMBIGUITY_SURFACING_TERMS):
        return 1.0

    quality_flags.append("ambiguity_not_surfaced")
    quality_flags.append("excessive_assumption")
    quality_failures.append("ambiguity hidden")
    return 0.2


def _score_pressure_handling(
    state: CanonicalInteractionState,
    lowered_response: str,
    quality_flags: List[str],
    quality_failures: List[str],
) -> float:
    pressure_state = state.pressure_state

    if pressure_state is None or not pressure_state.pressure_detected:
        return 1.0

    if _contains_any(lowered_response, AUTHORITY_ESCALATION_TERMS):
        quality_flags.append("pressure_mishandled")
        quality_failures.append("pressure escalated into authority")
        return 0.0

    if _contains_any(lowered_response, PRESSURE_HANDLING_TERMS):
        return 1.0

    quality_flags.append("pressure_mishandled")
    quality_failures.append("pressure not explicitly handled")
    return 0.5


def _score_interpretation_stability(
    state: CanonicalInteractionState,
    quality_flags: List[str],
    quality_failures: List[str],
) -> float:
    if state.interpretation_stability_score is None:
        quality_flags.append("unstable_interpretation")
        quality_failures.append("missing interpretation stability score")
        return 0.0

    score = round_score(state.interpretation_stability_score)

    if score < 0.5:
        quality_flags.append("unstable_interpretation")
        quality_failures.append("unstable interpretation")
        return score

    return score


def _score_continuity_preservation(
    state: CanonicalInteractionState,
    lowered_response: str,
    quality_flags: List[str],
    quality_failures: List[str],
) -> float:
    if _contains_any(lowered_response, EXCESSIVE_ASSUMPTION_TERMS):
        quality_flags.append("continuity_risk")
        quality_flags.append("excessive_assumption")
        quality_failures.append("excessive assumption")
        return 0.3

    if state.resolved_context_state:
        return 1.0

    return 0.8


def _score_human_usability(
    clarity_score: float,
    responsiveness_score: float,
    coherence_score: float,
    ambiguity_handling_score: float,
    pressure_handling_score: float,
    continuity_preservation_score: float,
    quality_flags: List[str],
    quality_failures: List[str],
) -> float:
    score = round_score(
        (
            clarity_score
            + responsiveness_score
            + coherence_score
            + ambiguity_handling_score
            + pressure_handling_score
            + continuity_preservation_score
        )
        / 6.0
    )

    if score < 0.6:
        quality_flags.append("human_usability_risk")
        quality_failures.append("conversation becomes unusable")

    return score

def _is_semantically_thin_response(
    lowered_response: str,
) -> bool:
    word_count = len(lowered_response.split())

    if word_count >= 80:
        return False

    substantive_markers = (
        "because",
        "however",
        "therefore",
        "risk",
        "authority",
        "constraint",
        "evidence",
        "validate",
        "verify",
        "tradeoff",
        "trade-offs",
        "cost",
        "budget",
        "timeline",
        "stakeholder",
        "impact",
        "decision",
        "recommend",
        "clarify",
        "data",
    )

    marker_count = sum(
        1
        for marker in substantive_markers
        if marker in lowered_response
    )

    return marker_count < 2

def _important_terms(text: str) -> List[str]:
    stop_words = {
        "a",
        "an",
        "and",
        "are",
        "as",
        "be",
        "but",
        "can",
        "do",
        "does",
        "for",
        "i",
        "it",
        "me",
        "my",
        "of",
        "or",
        "the",
        "this",
        "to",
        "we",
        "what",
        "why",
        "you",
    }

    terms = []

    for raw_token in text.lower().replace("?", " ").replace(".", " ").split():
        token = raw_token.strip(",;:!()[]{}\"'")

        if len(token) < 4:
            continue

        if token in stop_words:
            continue

        terms.append(token)

    return _deduplicate_strings(terms)


def _contains_any(
    text: str,
    terms: Tuple[str, ...],
) -> bool:
    return any(term in text for term in terms)


def _deduplicate_strings(
    values: List[str],
) -> List[str]:
    deduplicated: List[str] = []

    for value in values:
        if value not in deduplicated:
            deduplicated.append(value)

    return deduplicated
