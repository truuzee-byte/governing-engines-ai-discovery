from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, Optional

from models.runtime_models import ConversationQualityState, PressureState


RESPONSE_OUTPUT_PATH = (
    Path(__file__).resolve().parent.parent
    / "runtime_responses"
    / "responses.jsonl"
)


def write_response_log(
    interaction_id: str,
    session_id: str,
    response_text: str,
    pressure_state: Optional[PressureState] = None,
    conversation_quality_state: Optional[ConversationQualityState] = None,
) -> str:
    if not isinstance(interaction_id, str):
        raise TypeError("interaction_id must be a string")

    if not isinstance(session_id, str):
        raise TypeError("session_id must be a string")

    if not isinstance(response_text, str):
        raise TypeError("response_text must be a string")

    if pressure_state is not None:
        if not isinstance(pressure_state, PressureState):
            raise TypeError(
                "pressure_state must be PressureState or None"
            )

    if conversation_quality_state is not None:
        if not isinstance(
            conversation_quality_state,
            ConversationQualityState,
        ):
            raise TypeError(
                "conversation_quality_state must be "
                "ConversationQualityState or None"
            )

    if interaction_id.strip() == "":
        raise ValueError("interaction_id must not be empty")

    if session_id.strip() == "":
        raise ValueError("session_id must not be empty")

    if response_text.strip() == "":
        raise ValueError("response_text must not be empty")

    RESPONSE_OUTPUT_PATH.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    record: Dict[str, object] = {
        "interaction_id": interaction_id,
        "session_id": session_id,
        "response_text": response_text,
        "pressure_state": (
            pressure_state.to_dict()
            if pressure_state is not None
            else {}
        ),
        "conversation_quality_state": (
            conversation_quality_state.to_dict()
            if conversation_quality_state is not None
            else {}
        ),
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }

    serialized_record = json.dumps(
        record,
        ensure_ascii=False,
        sort_keys=True,
    )

    try:
        with RESPONSE_OUTPUT_PATH.open(
            "a",
            encoding="utf-8",
        ) as handle:
            handle.write(serialized_record)
            handle.write("\n")

    except OSError as exc:
        raise RuntimeError(
            "RESPONSE_LOG_WRITE_FAILURE"
        ) from exc

    return str(RESPONSE_OUTPUT_PATH)