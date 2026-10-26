from __future__ import annotations

from typing import Dict, List

from models.runtime_models import DOMAINS


DOMAIN_TERMS: Dict[str, tuple[str, ...]] = {
    "governance": (
        "governance",
        "authority",
        "custody",
        "validation",
        "validator",
        "admissibility",
        "downstream",
        "halt",
        "refusal",
        "receipt",
        "trace",
        "lineage",
        "compliance",
        "audit",
    ),
    "software": (
        "code",
        "build",
        "runtime",
        "file",
        "files",
        "function",
        "class",
        "module",
        "python",
        "implementation",
        "execute",
        "test",
        "tests",
        "schema",
    ),
    "architecture": (
        "architecture",
        "system",
        "systems",
        "contract",
        "interface",
        "orchestration",
        "pipeline",
        "layer",
        "boundary",
        "state",
        "stateful",
        "stateless",
    ),
    "creative": (
        "story",
        "character",
        "scene",
        "world",
        "canon",
        "book",
        "chapter",
        "animation",
        "franchise",
        "dialogue",
        "visual",
    ),
    "research": (
        "study",
        "research",
        "test",
        "protocol",
        "score",
        "scoring",
        "benchmark",
        "analysis",
        "experiment",
        "evidence",
        "compare",
        "comparative",
    ),
}


def detect_domain(normalized_input: str) -> str:
    """
    Detects canonical domain for Mode AI runtime slice v1.2.
    """

    if not isinstance(normalized_input, str):
        raise TypeError("normalized_input must be a string")

    candidate = normalized_input.strip()

    if candidate == "":
        raise ValueError("normalized_input must not be empty")

    lowered = candidate.lower()

    matched_domains: List[str] = []

    for domain, terms in DOMAIN_TERMS.items():
        if any(term in lowered for term in terms):
            matched_domains.append(domain)

    matched_domains = list(dict.fromkeys(matched_domains))

    if len(matched_domains) == 0:
        return "conversation"

    if len(matched_domains) > 1:
        return "mixed"

    resolved_domain = matched_domains[0]

    if resolved_domain not in DOMAINS:
        raise ValueError(f"Resolved invalid domain: {resolved_domain}")

    return resolved_domain