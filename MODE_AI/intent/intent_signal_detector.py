from __future__ import annotations

from typing import List


SIGNAL_PRIORITY_ORDER = (
    "clarification_signal",
    "audit_signal",
    "build_signal",
    "preservation_signal",
    "analysis_signal",
)


BUILD_TERMS = (
    "build",
    "make",
    "create",
    "implement",
    "generate",
    "construct",
    "write",
    "develop",
    "runtime slice",
    "file structure",
    "spec",
)


ANALYSIS_TERMS = (
    "analyze",
    "analysis",
    "interpret",
    "meaning",
    "understand",
    "explain",
    "evaluate",
    "review",
    "thoughts",
)


AUDIT_TERMS = (
    "audit",
    "validate",
    "verify",
    "check",
    "canon",
    "compliance",
    "governance",
    "failure",
    "drift",
)


CLARIFICATION_TERMS = (
    "clarify",
    "what do you mean",
    "before",
    "earlier",
    "which one",
    "can you explain",
    "do you mean",
)


PRESERVATION_TERMS = (
    "preserve",
    "remember",
    "save",
    "lock",
    "canonize",
    "store",
    "retain",
)


def detect_intent_signals(normalized_input: str) -> List[str]:
    """
    Detects deterministic intent signals for Mode AI runtime slice v1.2.
    """

    if not isinstance(normalized_input, str):
        raise TypeError("normalized_input must be a string")

    candidate = normalized_input.strip()

    if candidate == "":
        raise ValueError("normalized_input must not be empty")

    lowered = candidate.lower()

    detected_signals: List[str] = []

    if _contains_any(lowered, CLARIFICATION_TERMS):
        detected_signals.append("clarification_signal")

    if _contains_any(lowered, AUDIT_TERMS):
        detected_signals.append("audit_signal")

    if _contains_any(lowered, BUILD_TERMS):
        detected_signals.append("build_signal")

    if _contains_any(lowered, PRESERVATION_TERMS):
        detected_signals.append("preservation_signal")

    if _contains_any(lowered, ANALYSIS_TERMS):
        detected_signals.append("analysis_signal")

    return _deduplicate_and_order(detected_signals)


def _contains_any(candidate: str, terms: tuple[str, ...]) -> bool:
    return any(term in candidate for term in terms)


def _deduplicate_and_order(signals: List[str]) -> List[str]:
    unique_signals = list(dict.fromkeys(signals))

    return [
        signal
        for signal in SIGNAL_PRIORITY_ORDER
        if signal in unique_signals
    ]