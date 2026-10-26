from __future__ import annotations

from models.runtime_models import DOMAINS, INTENT_TYPES, MODES


def resolve_mode(intent_type: str, detected_domain: str) -> str:
    """
    Resolves canonical Mode AI runtime mode for v1.2.
    """

    if not isinstance(intent_type, str):
        raise TypeError("intent_type must be a string")

    if not isinstance(detected_domain, str):
        raise TypeError("detected_domain must be a string")

    if intent_type not in INTENT_TYPES:
        raise ValueError(f"Invalid intent_type: {intent_type}")

    if detected_domain not in DOMAINS:
        raise ValueError(f"Invalid detected_domain: {detected_domain}")

    resolved_mode = _resolve_mode(intent_type, detected_domain)

    if resolved_mode not in MODES:
        raise ValueError(f"Resolved invalid mode: {resolved_mode}")

    return resolved_mode


def _resolve_mode(intent_type: str, detected_domain: str) -> str:
    if intent_type == "build" and detected_domain in {"software", "architecture", "mixed"}:
        return "Development"

    if intent_type == "audit":
        return "Canon Check"

    if intent_type == "preserve":
        return "Canon Check"

    if detected_domain == "creative":
        return "Creative Collaboration"

    return "Interpretation"