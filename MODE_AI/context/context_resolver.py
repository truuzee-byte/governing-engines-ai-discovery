from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict


RUNTIME_STATE_ROOT = (
    Path(__file__).resolve().parent.parent
    / "runtime_state"
    / "session_context"
)


def resolve_context_state(session_id: str) -> Dict[str, Any]:
    """
    Resolves append-only session context state for Mode AI runtime slice v1.2.

    Rules:
    - return session_id
    - return prior interaction count if available
    - return empty state if no prior state exists
    - no failure if session is new
    """

    if not isinstance(session_id, str):
        raise TypeError("session_id must be a string")

    normalized_session_id = session_id.strip()

    if normalized_session_id == "":
        raise ValueError("session_id must not be empty")

    RUNTIME_STATE_ROOT.mkdir(parents=True, exist_ok=True)

    session_path = _session_path(normalized_session_id)

    if not session_path.exists():
        return {
            "session_id": normalized_session_id,
            "prior_interaction_count": 0,
            "prior_interactions": [],
            "session_exists": False,
        }

    try:
        with session_path.open("r", encoding="utf-8") as handle:
            payload = json.load(handle)

    except json.JSONDecodeError as exc:
        raise ValueError(
            f"Invalid session context JSON for session_id={normalized_session_id}"
        ) from exc

    if not isinstance(payload, dict):
        raise ValueError("Session context payload must be a dictionary")

    prior_interactions = payload.get("prior_interactions", [])

    if not isinstance(prior_interactions, list):
        raise ValueError("prior_interactions must be a list")

    return {
        "session_id": normalized_session_id,
        "prior_interaction_count": len(prior_interactions),
        "prior_interactions": prior_interactions,
        "session_exists": True,
    }


def append_interaction_context(
    session_id: str,
    interaction_record: Dict[str, Any],
) -> str:
    """
    Append-only session interaction persistence.
    """

    if not isinstance(interaction_record, dict):
        raise TypeError("interaction_record must be a dictionary")

    normalized_session_id = session_id.strip()

    if normalized_session_id == "":
        raise ValueError("session_id must not be empty")

    RUNTIME_STATE_ROOT.mkdir(parents=True, exist_ok=True)

    session_path = _session_path(normalized_session_id)

    if session_path.exists():
        with session_path.open("r", encoding="utf-8") as handle:
            payload = json.load(handle)

    else:
        payload = {
            "session_id": normalized_session_id,
            "prior_interactions": [],
        }

    prior_interactions = payload.setdefault("prior_interactions", [])

    if not isinstance(prior_interactions, list):
        raise ValueError("prior_interactions must be a list")

    prior_interactions.append(interaction_record)

    with session_path.open("w", encoding="utf-8") as handle:
        json.dump(payload, handle, indent=2, ensure_ascii=False)

    return str(session_path)


def _session_path(session_id: str) -> Path:
    safe_session_id = "".join(
        character
        for character in session_id
        if character.isalnum() or character in {"-", "_"}
    )

    if safe_session_id == "":
        raise ValueError("session_id produced invalid storage identifier")

    return RUNTIME_STATE_ROOT / f"{safe_session_id}.json"