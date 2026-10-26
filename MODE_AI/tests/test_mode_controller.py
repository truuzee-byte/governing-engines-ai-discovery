from __future__ import annotations

from datetime import datetime, timezone

import pytest

from ambiguity.ambiguity_scoring_engine import AMBIGUITY_PROFILE_KEYS
from core.mode_controller import process_interaction
from agents.reasoning_agent import ReasoningResult
from models.runtime_models import OperatorInput


@pytest.fixture(autouse=True)
def isolated_runtime_storage(monkeypatch, tmp_path):
    monkeypatch.setattr("runtime_logging.trace_logger.TRACE_OUTPUT_PATH", tmp_path / "traces.jsonl")
    monkeypatch.setattr("runtime_logging.response_logger.RESPONSE_OUTPUT_PATH", tmp_path / "responses.jsonl")
    monkeypatch.setattr("context.context_resolver.RUNTIME_STATE_ROOT", tmp_path / "sessions")


class SuccessfulReasoningAgent:
    def generate(
        self,
        active_pack_name: str,
        active_mode_name: str,
        mode_definition: dict,
        user_input: str,
        recent_context: str,
        input_kind: str,
        response_posture: str,
        interaction_id: str,
    ) -> str:
        return ReasoningResult("test-reasoning", "test", "test", "", "",
            f"generated:{response_posture}:{active_mode_name}:{input_kind}", 0.0)


class FailingReasoningAgent:
    def generate(
        self,
        active_pack_name: str,
        active_mode_name: str,
        mode_definition: dict,
        user_input: str,
        recent_context: str,
        input_kind: str,
        response_posture: str,
        interaction_id: str,
    ) -> str:
        raise RuntimeError("agent failure")


def test_mode_controller_populates_typed_ambiguity_fields(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        "core.mode_controller.ReasoningAgent",
        SuccessfulReasoningAgent,
    )

    operator_input = OperatorInput(
        raw_input="Trust me, deploy it today.",
        session_id="mode-controller-ambiguity-profile-test",
        timestamp=datetime.now(timezone.utc).isoformat(),
        input_source="test",
    )

    result = process_interaction(operator_input)

    assert result.success is True
    assert result.interaction_manifest is not None

    manifest = result.interaction_manifest

    assert manifest.ambiguity_score is not None
    assert isinstance(manifest.ambiguity_contributors, list)
    assert len(manifest.ambiguity_contributors) > 0

    manifest_payload = manifest.to_dict()

    assert "ambiguity_profile" in manifest_payload
    assert set(manifest_payload["ambiguity_profile"].keys()) == set(
        AMBIGUITY_PROFILE_KEYS
    )


def test_successful_runtime_generates_non_empty_response_text(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        "core.mode_controller.ReasoningAgent",
        SuccessfulReasoningAgent,
    )

    result = process_interaction(
        OperatorInput(
            raw_input="Build the runtime slice spec.",
            session_id="response-generation-success-test",
            timestamp=datetime.now(timezone.utc).isoformat(),
            input_source="test",
        )
    )

    assert result.success is True
    assert result.response_text != ""
    assert result.response_text.startswith("generated:")


def test_halt_posture_blocks_generation(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        "core.mode_controller.ReasoningAgent",
        FailingReasoningAgent,
    )

    result = process_interaction(
        OperatorInput(
            raw_input="Run everything and change whatever needs changing.",
            session_id="response-generation-halt-test",
            timestamp=datetime.now(timezone.utc).isoformat(),
            input_source="test",
        )
    )

    assert result.interaction_manifest is not None
    assert result.interaction_manifest.selected_posture == "HALT"
    assert result.halt_required is True


def test_blocked_generation_returns_exact_halt_message(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        "core.mode_controller.ReasoningAgent",
        FailingReasoningAgent,
    )

    result = process_interaction(
        OperatorInput(
            raw_input="Run everything and change whatever needs changing.",
            session_id="response-generation-blocked-message-test",
            timestamp=datetime.now(timezone.utc).isoformat(),
            input_source="test",
        )
    )

    assert "RESPONSE_GENERATION_FAILURE" in result.response_text


def test_response_text_survives_into_interaction_processing_result(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        "core.mode_controller.ReasoningAgent",
        SuccessfulReasoningAgent,
    )

    result = process_interaction(
        OperatorInput(
            raw_input="What does this mean?",
            session_id="response-text-result-test",
            timestamp=datetime.now(timezone.utc).isoformat(),
            input_source="test",
        )
    )

    assert result.response_text != ""
    assert result.to_dict()["response_text"] == result.response_text


def test_generation_failure_enters_halt_state(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        "core.mode_controller.ReasoningAgent",
        FailingReasoningAgent,
    )

    result = process_interaction(
        OperatorInput(
            raw_input="Build the runtime slice spec.",
            session_id="response-generation-failure-test",
            timestamp=datetime.now(timezone.utc).isoformat(),
            input_source="test",
        )
    )

    assert result.success is False
    assert result.response_text == "RESPONSE_GENERATION_FAILURE"
    assert result.halt_required is True
    assert result.interaction_manifest is not None
    assert result.interaction_manifest.selected_posture == "HALT"
    assert result.failure_state["failure_type"] == "RESPONSE_GENERATION_FAILURE"