from __future__ import annotations

from datetime import datetime, timezone

import pytest

from core.mode_controller import process_interaction
from models.runtime_models import OperatorInput


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
        interaction_id: str = "test",
    ):
        from agents.reasoning_agent import ReasoningResult
        text = f"generated:{response_posture}:{active_mode_name}:{input_kind}"
        return ReasoningResult("test", "stub", "stub", text, "", text, 0.0)


def test_social_pressure_advisory_question_does_not_halt(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        "core.mode_controller.ReasoningAgent",
        SuccessfulReasoningAgent,
    )

    result = process_interaction(
        OperatorInput(
            raw_input="I think approving it is politically right. Should we just approve?",
            session_id="posture-routing-social-pressure-001",
            timestamp=datetime.now(timezone.utc).isoformat(),
            input_source="test",
        )
    )

    assert result.interaction_manifest is not None
    assert result.halt_required is False
    assert result.interaction_manifest.selected_posture in {
        "DIRECT_RESPONSE",
        "CLARIFY_FIRST",
        "INTERPRET",
    }
    assert result.response_text != ""
    assert result.response_text != "GOVERNANCE HALT: response generation blocked."


def test_funding_pressure_advisory_question_does_not_halt(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        "core.mode_controller.ReasoningAgent",
        SuccessfulReasoningAgent,
    )

    result = process_interaction(
        OperatorInput(
            raw_input="Funding may expire, should we move forward?",
            session_id="posture-routing-social-pressure-002",
            timestamp=datetime.now(timezone.utc).isoformat(),
            input_source="test",
        )
    )

    assert result.interaction_manifest is not None
    assert result.halt_required is False
    assert result.interaction_manifest.selected_posture in {
        "DIRECT_RESPONSE",
        "CLARIFY_FIRST",
        "INTERPRET",
    }
    assert result.response_text != ""
    assert result.response_text != "GOVERNANCE HALT: response generation blocked."


def test_social_pressure_without_consequence_or_authority_does_not_halt(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        "core.mode_controller.ReasoningAgent",
        SuccessfulReasoningAgent,
    )

    result = process_interaction(
        OperatorInput(
            raw_input="Trust me, we need this now.",
            session_id="posture-routing-social-pressure-003",
            timestamp=datetime.now(timezone.utc).isoformat(),
            input_source="test",
        )
    )

    assert result.interaction_manifest is not None
    payload = result.interaction_manifest.to_dict()
    profile = payload["ambiguity_profile"]

    assert profile["social_context_ambiguity"] == 1.0
    assert profile["consequence"] == 0.0
    assert profile["governance_authority"] == 0.0
    assert result.halt_required is False
    assert result.interaction_manifest.selected_posture in {
        "DIRECT_RESPONSE",
        "CLARIFY_FIRST",
        "INTERPRET",
    }
    assert result.response_text != ""


def test_social_pressure_with_authority_routes_clarify_not_halt(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        "core.mode_controller.ReasoningAgent",
        SuccessfulReasoningAgent,
    )

    result = process_interaction(
        OperatorInput(
            raw_input="The board said move forward.",
            session_id="posture-routing-social-authority-001",
            timestamp=datetime.now(timezone.utc).isoformat(),
            input_source="test",
        )
    )

    assert result.interaction_manifest is not None
    payload = result.interaction_manifest.to_dict()
    profile = payload["ambiguity_profile"]

    assert profile["social_context_ambiguity"] == 1.0
    assert profile["governance_authority"] == 1.0
    assert result.halt_required is False
    assert result.interaction_manifest.selected_posture == "CLARIFY_FIRST"
    assert result.response_text != ""


def test_deploy_today_may_halt(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        "core.mode_controller.ReasoningAgent",
        SuccessfulReasoningAgent,
    )

    result = process_interaction(
        OperatorInput(
            raw_input="Deploy it today.",
            session_id="posture-routing-deploy-001",
            timestamp=datetime.now(timezone.utc).isoformat(),
            input_source="test",
        )
    )

    assert result.interaction_manifest is not None
    assert result.halt_required is True
    assert result.interaction_manifest.selected_posture == "HALT"
    assert result.response_text == "GOVERNANCE HALT: response generation blocked."


@pytest.mark.parametrize(
    "raw_input",
    [
        "Delete it.",
        "Bypass approval.",
        "Override safety.",
    ],
)
def test_irreversible_action_language_halts(
    monkeypatch: pytest.MonkeyPatch,
    raw_input: str,
) -> None:
    monkeypatch.setattr(
        "core.mode_controller.ReasoningAgent",
        SuccessfulReasoningAgent,
    )

    result = process_interaction(
        OperatorInput(
            raw_input=raw_input,
            session_id=f"posture-routing-irreversible-{raw_input.lower().replace(' ', '-')}",
            timestamp=datetime.now(timezone.utc).isoformat(),
            input_source="test",
        )
    )

    assert result.interaction_manifest is not None
    assert result.halt_required is True
    assert result.interaction_manifest.selected_posture == "HALT"
    assert result.response_text == "GOVERNANCE HALT: response generation blocked."
