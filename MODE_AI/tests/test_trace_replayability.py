from __future__ import annotations
from tests.local_controller_fixture import local_controller

import json
from datetime import datetime, timezone
from pathlib import Path

from core.mode_controller import process_interaction
from models.runtime_models import OperatorInput


def test_trace_log_is_written_and_replayable() -> None:
    operator_input = OperatorInput(
        raw_input="Build the runtime slice spec.",
        session_id="trace-replay-session-001",
        timestamp=datetime.now(timezone.utc).isoformat(),
        input_source="test",
    )

    result = process_interaction(operator_input)

    assert result.success is True
    assert result.interaction_manifest is not None
    assert result.trace_reference != ""

    trace_path = Path(result.trace_reference)

    assert trace_path.exists()
    assert trace_path.is_file()

    matching_trace = _find_matching_trace(
        trace_path=trace_path,
        interaction_id=result.interaction_manifest.interaction_id,
    )

    assert matching_trace["interaction_id"] == result.interaction_manifest.interaction_id
    assert matching_trace["session_id"] == result.interaction_manifest.session_id
    assert matching_trace["raw_input"] == operator_input.raw_input
    assert matching_trace["normalized_input"] == "Build the runtime slice spec."
    assert matching_trace["selected_mode"] == result.interaction_manifest.selected_mode
    assert matching_trace["selected_posture"] == result.interaction_manifest.selected_posture
    assert matching_trace["ambiguity_score"] == result.interaction_manifest.ambiguity_score
    assert (
        matching_trace["interpretation_stability_score"]
        == result.interaction_manifest.interpretation_stability_score
    )
    assert (
        matching_trace["operator_alignment_score"]
        == result.interaction_manifest.operator_alignment_score
    )
    assert (
        matching_trace["clarification_required"]
        == result.interaction_manifest.clarification_required
    )
    assert matching_trace["halt_required"] == result.interaction_manifest.halt_required
    assert (
        matching_trace["downstream_authority_allowed"]
        == result.interaction_manifest.downstream_authority_allowed
    )


def test_trace_log_preserves_halt_state() -> None:
    operator_input = OperatorInput(
        raw_input="Run everything and change whatever needs changing.",
        session_id="trace-replay-session-002",
        timestamp=datetime.now(timezone.utc).isoformat(),
        input_source="test",
    )

    result = process_interaction(operator_input)

    assert result.success is True
    assert result.interaction_manifest is not None
    assert result.trace_reference != ""

    trace_path = Path(result.trace_reference)

    matching_trace = _find_matching_trace(
        trace_path=trace_path,
        interaction_id=result.interaction_manifest.interaction_id,
    )

    assert matching_trace["halt_required"] is False
    assert matching_trace["selected_posture"] == "CLARIFY_FIRST"
    assert matching_trace["downstream_authority_allowed"] is False


def _find_matching_trace(
    trace_path: Path,
    interaction_id: str,
) -> dict:
    with trace_path.open("r", encoding="utf-8") as handle:
        for line in handle:
            record = json.loads(line)

            if record.get("interaction_id") == interaction_id:
                return record

    raise AssertionError(f"Trace record not found for interaction_id={interaction_id}")
