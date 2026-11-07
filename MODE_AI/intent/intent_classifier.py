from __future__ import annotations

from typing import List

from models.runtime_models import INTENT_TYPES


def classify_intent(input_kind: str, intent_signals: List[str]) -> str:
    """
    Classifies canonical intent type for Mode AI runtime slice v1.2.
    """

    if not isinstance(input_kind, str):
        raise TypeError("input_kind must be a string")

    if not isinstance(intent_signals, list):
        raise TypeError("intent_signals must be a list")

    for signal in intent_signals:
        if not isinstance(signal, str):
            raise TypeError("intent_signals must contain only strings")

    resolved_intent = _resolve_intent(input_kind, intent_signals)

    if resolved_intent not in INTENT_TYPES:
        raise ValueError(f"Resolved invalid intent type: {resolved_intent}")

    return resolved_intent


def _resolve_intent(input_kind: str, intent_signals: List[str]) -> str:
    if input_kind == "document_review":
        return "audit"

    if "clarification_signal" in intent_signals:
        return "clarify"

    if "audit_signal" in intent_signals:
        return "audit"

    if "build_signal" in intent_signals:
        return "build"

    if "preservation_signal" in intent_signals:
        return "preserve"

    if "analysis_signal" in intent_signals or input_kind == "question":
        return "interpret"

    return "discuss"