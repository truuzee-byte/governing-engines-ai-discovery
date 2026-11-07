from __future__ import annotations

import re


_WHITESPACE_PATTERN = re.compile(r"\s+")


def normalize_input(raw_input: str) -> str:
    """
    Canonical normalization layer for Mode AI v1.2 runtime slice.

    Rules enforced:
    - trim outer whitespace
    - preserve operator wording
    - preserve ambiguity
    - do not summarize
    - do not reinterpret
    """

    if not isinstance(raw_input, str):
        raise TypeError("raw_input must be a string")

    normalized = raw_input.strip()

    if normalized == "":
        raise ValueError("raw_input must not normalize to empty string")

    normalized = normalized.replace("\r\n", "\n")
    normalized = normalized.replace("\r", "\n")

    normalized_lines = []

    for line in normalized.split("\n"):
        collapsed = _WHITESPACE_PATTERN.sub(" ", line).strip()
        normalized_lines.append(collapsed)

    return "\n".join(normalized_lines)