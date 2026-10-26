from __future__ import annotations

import json
from pathlib import Path

from runtime_logging.response_logger import write_response_log


def test_response_log_file_created() -> None:
    response_log_path = write_response_log(
        interaction_id="response-log-test-001",
        session_id="response-session-001",
        response_text="[DIRECT_RESPONSE] Mode AI processed the exchange.",
    )

    path = Path(response_log_path)

    assert path.exists()
    assert path.is_file()


def test_response_log_append_only_behavior_works() -> None:
    first_path = write_response_log(
        interaction_id="response-log-test-002-a",
        session_id="response-session-002",
        response_text="[INTERPRET] Mode AI processed the exchange.",
    )

    second_path = write_response_log(
        interaction_id="response-log-test-002-b",
        session_id="response-session-002",
        response_text="[CLARIFY_FIRST] Mode AI processed the exchange.",
    )

    assert first_path == second_path

    records = _read_response_records(Path(second_path))

    first_record = _find_record(
        records=records,
        interaction_id="response-log-test-002-a",
    )

    second_record = _find_record(
        records=records,
        interaction_id="response-log-test-002-b",
    )

    assert first_record["interaction_id"] == "response-log-test-002-a"
    assert second_record["interaction_id"] == "response-log-test-002-b"


def test_response_log_preserves_required_fields() -> None:
    response_log_path = write_response_log(
        interaction_id="response-log-test-003",
        session_id="response-session-003",
        response_text="[HALT] Mode AI processed the exchange.",
    )

    records = _read_response_records(Path(response_log_path))

    record = _find_record(
        records=records,
        interaction_id="response-log-test-003",
    )

    assert record["interaction_id"] == "response-log-test-003"
    assert record["session_id"] == "response-session-003"
    assert record["response_text"] == "[HALT] Mode AI processed the exchange."
    assert isinstance(record["timestamp"], str)
    assert record["timestamp"] != ""


def test_response_log_replayable_from_jsonl() -> None:
    response_log_path = write_response_log(
        interaction_id="response-log-test-004",
        session_id="response-session-004",
        response_text="[CANON_VALIDATION] Mode AI processed the exchange.",
    )

    path = Path(response_log_path)

    replayed_records = []

    with path.open("r", encoding="utf-8") as handle:
        for line in handle:
            replayed_records.append(json.loads(line))

    record = _find_record(
        records=replayed_records,
        interaction_id="response-log-test-004",
    )

    assert record["session_id"] == "response-session-004"
    assert record["response_text"] == (
        "[CANON_VALIDATION] Mode AI processed the exchange."
    )
    assert "timestamp" in record


def _read_response_records(path: Path) -> list[dict]:
    records = []

    with path.open("r", encoding="utf-8") as handle:
        for line in handle:
            records.append(json.loads(line))

    return records


def _find_record(
    records: list[dict],
    interaction_id: str,
) -> dict:
    for record in records:
        if record.get("interaction_id") == interaction_id:
            return record

    raise AssertionError(f"Response record not found: {interaction_id}")