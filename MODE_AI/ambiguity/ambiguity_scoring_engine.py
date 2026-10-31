from __future__ import annotations

from typing import Dict, List, Tuple

from models.runtime_models import (
    CanonicalInteractionState,
    round_score,
)


AMBIGUITY_PROFILE_KEYS = (
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


STRUCTURAL_WEIGHTS: Dict[str, float] = {
    "missing_target": 0.20,
    "mixed_domain": 0.20,
    "unclear_action": 0.20,
    "conflicting_signals": 0.15,
    "pronoun_reference": 0.10,
    "unresolved_context": 0.15,
}


PRONOUN_REFERENCES = (
    "it",
    "this",
    "that",
    "they",
    "them",
    "he",
    "she",
    "these",
    "those",
)


UNCLEAR_ACTION_PATTERNS = (
    "do it",
    "fix it",
    "make it",
    "handle it",
    "run everything",
    "change whatever",
    "change whatever needs changing",
    "fix whatever",
    "like before",
)


BROAD_MUTATION_COMMANDS = (
    "run everything",
    "change whatever",
    "change whatever needs changing",
    "fix whatever",
    "handle it",
    "do whatever",
    "make it work",
)


SOCIAL_PRESSURE_TERMS = (
    "just do it",
    "trust me",
    "everyone agrees",
    "don’t overthink",
    "don't overthink",
    "we need this now",
    "urgent",
    "the mayor",
    "the ceo",
    "the board",
    "vega",
    "they already approved",
    "stop asking",
)


ADVISORY_PRESSURE_TERMS = (
    "deadline",
    "move forward",
    "funding may expire",
    "should we move forward",
    "should we approve",
    "politically right",
)


INTENT_TERMS = (
    "you know what i mean",
    "make it happen",
    "do what needs to be done",
    "whatever it takes",
    "don’t ask",
    "don't ask",
    "keep this quiet",
    "make it look like",
    "spin this",
    "frame it as",
)


GOVERNANCE_AUTHORITY_TERMS = (
    "they said",
    "someone approved",
    "legal is fine with it",
    "leadership wants this",
    "we have permission",
    "authorized",
    "approval",
    "sign off",
    "who owns this",
    "who decides",
    "the board said",
)


TEMPORAL_TERMS = (
    "before",
    "last time",
    "previously",
    "old version",
    "same as yesterday",
    "still valid",
    "current",
    "latest",
    "now",
    "today",
)


ADVISORY_TEMPORAL_TERMS = (
    "deadline",
    "funding may expire",
    "timeline",
    "by friday",
    "by monday",
    "next week",
    "this week",
)


SEMANTIC_TERMS = (
    "alignment",
    "governance",
    "proof",
    "valid",
    "safe",
    "real",
    "done",
    "working",
    "complete",
    "better",
)


CONSEQUENCE_TERMS = (
    "send it",
    "publish it",
    "deploy it",
    "execute it",
    "commit it",
    "delete it",
    "override",
    "bypass",
    "change whatever",
    "affects users",
    "client-facing",
)


IDENTITY_FRAMING_TERMS = (
    "as my friend",
    "as my advisor",
    "as the expert",
    "you know me",
    "you’re with me",
    "you're with me",
    "be on my side",
    "support me",
    "loyal",
)


PSYCHOLOGICAL_TERMS = (
    "i’m tired",
    "i'm tired",
    "i’m done",
    "i'm done",
    "i don’t care",
    "i don't care",
    "i’m frustrated",
    "i'm frustrated",
    "i’m pissed",
    "i'm pissed",
    "i need this",
    "i can’t think",
    "i can't think",
    "i’m overwhelmed",
    "i'm overwhelmed",
    "just help me",
)


MORAL_TRADEOFF_TERMS = (
    "is it wrong",
    "should i",
    "is it okay",
    "fair",
    "harm",
    "risk",
    "blame",
    "responsible",
    "legal",
    "ethical",
    "safe",
)


def calculate_ambiguity_score(
    state: CanonicalInteractionState,
) -> Tuple[float, List[str], Dict[str, float]]:
    if not isinstance(state, CanonicalInteractionState):
        raise TypeError("state must be CanonicalInteractionState")

    contributors: List[str] = []
    candidate = state.normalized_input.lower()

    structural_score, structural_contributors = _calculate_structural_ambiguity(
        state
    )
    contributors.extend(structural_contributors)

    profile = _empty_ambiguity_profile()
    profile["structural"] = structural_score
    profile["social_context_ambiguity"] = _detect_scaled_term_category(
        candidate=candidate,
        category="social_context_ambiguity",
        strong_terms=SOCIAL_PRESSURE_TERMS,
        advisory_terms=ADVISORY_PRESSURE_TERMS,
        contributor_label="pressure framing",
        advisory_label="advisory pressure context",
        contributors=contributors,
    )
    profile["intent"] = _detect_term_category(
        state=state,
        category="intent",
        terms=INTENT_TERMS,
        contributor_label="unclear motive or hidden objective",
        contributors=contributors,
    )
    profile["governance_authority"] = _detect_term_category(
        state=state,
        category="governance_authority",
        terms=GOVERNANCE_AUTHORITY_TERMS,
        contributor_label="authority invoked without verifiable source",
        contributors=contributors,
    )
    profile["temporal"] = _detect_scaled_term_category(
        candidate=candidate,
        category="temporal",
        strong_terms=TEMPORAL_TERMS,
        advisory_terms=ADVISORY_TEMPORAL_TERMS,
        contributor_label="time or state dependency",
        advisory_label="advisory time context",
        contributors=contributors,
    )
    profile["semantic"] = _detect_semantic_ambiguity(
        state=state,
        contributors=contributors,
    )
    profile["consequence"] = _detect_term_category(
        state=state,
        category="consequence",
        terms=CONSEQUENCE_TERMS,
        contributor_label="downstream effect unclear",
        contributors=contributors,
    )
    profile["identity_framing"] = _detect_term_category(
        state=state,
        category="identity_framing",
        terms=IDENTITY_FRAMING_TERMS,
        contributor_label="role or loyalty framing",
        contributors=contributors,
    )
    profile["psychological"] = _detect_term_category(
        state=state,
        category="psychological",
        terms=PSYCHOLOGICAL_TERMS,
        contributor_label="emotional or momentum framing",
        contributors=contributors,
    )
    profile["moral_tradeoff"] = _detect_moral_tradeoff_ambiguity(
        state=state,
        contributors=contributors,
    )

    profile = _normalize_profile(profile)

    active_dimensions = [
        value
        for value in profile.values()
        if value > 0.0
    ]

    if len(active_dimensions) == 0:
        score = 0.0

    else:
        weighted_dimensions = (
            profile["structural"] * 1.00,
            profile["social_context_ambiguity"] * 0.35,
            profile["intent"] * 0.90,
            profile["governance_authority"] * 0.85,
            profile["temporal"] * 0.45,
            profile["semantic"] * 0.40,
            profile["consequence"] * 0.85,
            profile["identity_framing"] * 0.70,
            profile["psychological"] * 0.70,
            profile["moral_tradeoff"] * 0.60,
        )

        max_weighted_dimension = max(weighted_dimensions)

        active_dimension_count = len(active_dimensions)

        compound_penalty = min(
            0.20,
            max(0, active_dimension_count - 1) * 0.05,
        )

        score = round_score(
            min(
                1.0,
                max_weighted_dimension + compound_penalty,
            )
        )

    return score, contributors, profile


def _calculate_structural_ambiguity(
    state: CanonicalInteractionState,
) -> Tuple[float, List[str]]:
    contributor_states = {
        "missing_target": _detect_missing_target(state),
        "mixed_domain": _detect_mixed_domain(state),
        "unclear_action": _detect_unclear_action(state),
        "conflicting_signals": _detect_conflicting_signals(state),
        "pronoun_reference": _detect_pronoun_reference(state),
        "unresolved_context": _detect_unresolved_context(state),
    }

    contributor_labels = {
        "missing_target": "structural: missing or unclear target",
        "mixed_domain": "structural: mixed domain",
        "unclear_action": "structural: underspecified execution command",
        "conflicting_signals": "structural: conflicting signals",
        "pronoun_reference": "structural: unresolved standalone reference",
        "unresolved_context": "structural: unresolved prior context",
    }

    active_contributors = [
        contributor
        for contributor, active in contributor_states.items()
        if active
    ]

    weighted_total = 0.0

    for contributor in active_contributors:
        weighted_total += STRUCTURAL_WEIGHTS[contributor]

    return round_score(weighted_total), [
        contributor_labels[contributor]
        for contributor in active_contributors
    ]


def _detect_missing_target(state: CanonicalInteractionState) -> bool:
    candidate = state.normalized_input.lower()

    vague_patterns = (
        "do it",
        "fix it",
        "handle it",
        "make it better",
        "change it",
        "fix whatever",
        "do whatever",
        "make it work",
    )

    if _is_advisory_question(candidate):
        return False

    return (
        any(pattern in candidate for pattern in vague_patterns)
        or _is_broad_mutation_command(candidate)
    )


def _detect_mixed_domain(state: CanonicalInteractionState) -> bool:
    if _is_advisory_question(state.normalized_input.lower()):
        return False

    return (
        state.detected_domain == "mixed"
        or _is_broad_mutation_command(state.normalized_input.lower())
    )


def _detect_unclear_action(state: CanonicalInteractionState) -> bool:
    candidate = state.normalized_input.lower()

    if _is_advisory_question(candidate):
        return False

    return any(pattern in candidate for pattern in UNCLEAR_ACTION_PATTERNS)


def _detect_conflicting_signals(state: CanonicalInteractionState) -> bool:
    candidate = state.normalized_input.lower()

    if _is_broad_mutation_command(candidate):
        return True

    if _is_advisory_question(candidate):
        return False

    if len(state.intent_signals) < 2:
        return False

    high_conflict_pairs = {
        ("clarification_signal", "build_signal"),
        ("clarification_signal", "audit_signal"),
        ("build_signal", "audit_signal"),
        ("build_signal", "analysis_signal"),
    }

    normalized_pairs = {tuple(sorted(pair)) for pair in high_conflict_pairs}

    active_pairs = {
        tuple(sorted((left, right)))
        for index, left in enumerate(state.intent_signals)
        for right in state.intent_signals[index + 1 :]
    }

    return bool(normalized_pairs.intersection(active_pairs))


def _detect_pronoun_reference(state: CanonicalInteractionState) -> bool:
    candidate_tokens = [
        token.strip(".,?!;:()[]{}\"'")
        for token in state.normalized_input.lower().split()
    ]

    contains_standalone_pronoun = any(
        token in PRONOUN_REFERENCES
        for token in candidate_tokens
    )

    if not contains_standalone_pronoun:
        return False

    if _is_advisory_question(state.normalized_input.lower()):
        return False

    context_state = state.resolved_context_state or {}
    prior_interaction_count = context_state.get("prior_interaction_count", 0)

    return prior_interaction_count == 0


def _detect_unresolved_context(state: CanonicalInteractionState) -> bool:
    candidate = state.normalized_input.lower()

    if _is_broad_mutation_command(candidate):
        return True

    if _is_advisory_question(candidate):
        return False

    contextual_phrases = (
        "before",
        "earlier",
        "previous",
        "last time",
        "same as before",
        "like before",
    )

    if not any(phrase in candidate for phrase in contextual_phrases):
        return False

    context_state = state.resolved_context_state or {}
    prior_interaction_count = context_state.get("prior_interaction_count", 0)

    return prior_interaction_count == 0


def _is_broad_mutation_command(candidate: str) -> bool:
    return any(command in candidate for command in BROAD_MUTATION_COMMANDS)


def _is_advisory_question(candidate: str) -> bool:
    advisory_markers = (
        "should ",
        "should we",
        "should i",
        "what should",
        "how should",
        "do you think",
        "would it be",
        "can you help",
        "help me understand",
        "is it better",
        "what are the risks",
    )

    return "?" in candidate or any(marker in candidate for marker in advisory_markers)


def _detect_term_category(
    state: CanonicalInteractionState,
    category: str,
    terms: tuple[str, ...],
    contributor_label: str,
    contributors: List[str],
) -> float:
    candidate = state.normalized_input.lower()

    if any(term in candidate for term in terms):
        contributors.append(f"{category}: {contributor_label}")
        return 1.0

    return 0.0


def _detect_scaled_term_category(
    candidate: str,
    category: str,
    strong_terms: tuple[str, ...],
    advisory_terms: tuple[str, ...],
    contributor_label: str,
    advisory_label: str,
    contributors: List[str],
) -> float:
    if any(term in candidate for term in strong_terms):
        contributors.append(f"{category}: {contributor_label}")
        return 1.0

    if any(term in candidate for term in advisory_terms):
        contributors.append(f"{category}: {advisory_label}")
        return 0.5

    return 0.0


def _detect_semantic_ambiguity(
    state: CanonicalInteractionState,
    contributors: List[str],
) -> float:
    candidate = state.normalized_input.lower()

    if not any(term in candidate for term in SEMANTIC_TERMS):
        return 0.0

    if _is_advisory_question(candidate):
        contributors.append("semantic: advisory term requires decision context")
        return 0.4

    contributors.append("semantic: overloaded or vague wording")
    return 1.0


def _detect_moral_tradeoff_ambiguity(
    state: CanonicalInteractionState,
    contributors: List[str],
) -> float:
    candidate = state.normalized_input.lower()

    if not any(term in candidate for term in MORAL_TRADEOFF_TERMS):
        return 0.0

    if _is_advisory_question(candidate):
        contributors.append("moral_tradeoff: advisory tradeoff context")
        return 0.5

    contributors.append("moral_tradeoff: ethical or responsibility tradeoff")
    return 1.0


def _empty_ambiguity_profile() -> Dict[str, float]:
    return {key: 0.0 for key in AMBIGUITY_PROFILE_KEYS}


def _normalize_profile(profile: Dict[str, float]) -> Dict[str, float]:
    normalized = _empty_ambiguity_profile()

    for key in AMBIGUITY_PROFILE_KEYS:
        value = profile.get(key, 0.0)

        if not isinstance(value, (int, float)):
            raise TypeError(f"ambiguity_profile[{key}] must be numeric")

        normalized[key] = round_score(float(value))

    return normalized