from __future__ import annotations

from typing import List

from models.runtime_models import INPUT_KINDS


QUESTION_PREFIXES = (
    "who",
    "what",
    "when",
    "where",
    "why",
    "how",
    "which",
    "whose",
    "whom",
    "should",
    "do",
    "does",
    "did",
    "can",
    "could",
    "would",
    "will",
    "is",
    "are",
    "am",
    "was",
    "were",
    "has",
    "have",
    "had",
)

BUILD_TERMS = (
    "build",
    "make",
    "create",
    "implement",
    "document",
    "spec",
)

CLARIFICATION_PREFIXES = (
    "yes",
    "no",
)

CLARIFICATION_REFERENCES = (
    "that",
    "this",
    "before",
    "earlier",
    "previous",
    "you said",
    "like before",
)

DOCUMENT_MARKER = "DOCUMENT:"


def detect_input_kind(normalized_input: str) -> str:
    """
    Detects canonical input kind for Mode AI runtime slice v1.2.
    """

    if not isinstance(normalized_input, str):
        raise TypeError("normalized_input must be a string")

    candidate = normalized_input.strip()

    if candidate == "":
        raise ValueError("normalized_input must not be empty")

    lowered = candidate.lower()

    detected_signals: List[str] = []

    if _is_document_review(candidate):
        detected_signals.append("document_review")

    if _is_question(candidate, lowered):
        detected_signals.append("question")

    if _is_build_request(lowered):
        detected_signals.append("build_request")

    if _is_clarification_response(lowered):
        detected_signals.append("clarification_response")

    resolved_kind = _resolve_input_kind(detected_signals)

    if resolved_kind not in INPUT_KINDS:
        raise ValueError(f"Resolved invalid input kind: {resolved_kind}")

    return resolved_kind


def _is_question(candidate: str, lowered: str) -> bool:
    if candidate.endswith("?"):
        return True

    return lowered.startswith(QUESTION_PREFIXES)


def _is_build_request(lowered: str) -> bool:
    return any(term in lowered for term in BUILD_TERMS)


def _is_clarification_response(lowered: str) -> bool:
    if lowered.startswith(CLARIFICATION_PREFIXES):
        return True

    return any(reference in lowered for reference in CLARIFICATION_REFERENCES)


def _is_document_review(candidate: str) -> bool:
    return DOCUMENT_MARKER in candidate


def _resolve_input_kind(detected_signals: List[str]) -> str:
    unique_signals = list(dict.fromkeys(detected_signals))

    if len(unique_signals) == 0:
        return "statement"

    if len(unique_signals) == 1:
        return unique_signals[0]

    if "document_review" in unique_signals:
        return "document_review"

    conflicting_pairs = {
        ("question", "build_request"),
        ("question", "clarification_response"),
        ("build_request", "clarification_response"),
    }

    normalized_pairs = {
        tuple(sorted(pair))
        for pair in conflicting_pairs
    }

    active_pairs = {
        tuple(sorted((left, right)))
        for index, left in enumerate(unique_signals)
        for right in unique_signals[index + 1 :]
    }

    if normalized_pairs.intersection(active_pairs):
        return "mixed_input"

    priority_order = (
        "clarification_response",
        "build_request",
        "question",
    )

    for kind in priority_order:
        if kind in unique_signals:
            return kind

    return "statement"