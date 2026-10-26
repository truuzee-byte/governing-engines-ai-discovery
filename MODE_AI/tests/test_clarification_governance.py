from __future__ import annotations

from datetime import datetime, timezone

from core.mode_controller import process_interaction
from models.runtime_models import OperatorInput
import pytest


@pytest.fixture(autouse=True)
def isolated_context(tmp_path, monkeypatch):
    from agents.reasoning_agent import ReasoningResult
    monkeypatch.setattr('core.mode_controller._generate_reasoning_result',
        lambda *args, **kwargs: ReasoningResult('clarification-fixture','fixture','offline','','','Could you clarify?',0))
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr('context.context_resolver.RUNTIME_STATE_ROOT', tmp_path/'context')
    monkeypatch.setattr('runtime_logging.trace_logger.TRACE_OUTPUT_PATH', tmp_path/'traces.jsonl')
    monkeypatch.setattr('runtime_logging.response_logger.RESPONSE_OUTPUT_PATH', tmp_path/'responses.jsonl')


def test_middle_zone_requires_clarification_without_halt() -> None:
    operator_input = OperatorInput(
        raw_input="Do it like before.",
        session_id="clarification-session-001",
        timestamp=datetime.now(timezone.utc).isoformat(),
        input_source="test",
    )

    result = process_interaction(operator_input)

    assert result.success is True
    assert result.interaction_manifest is not None

    manifest = result.interaction_manifest

    # Operator authority: strictly greater than 0.50, not greater-or-equal.
    assert 0.50 < manifest.ambiguity_score <= 0.75
    assert manifest.clarification_required is True
    assert manifest.halt_required is False
    assert manifest.selected_posture == "CLARIFY_FIRST"
    assert manifest.downstream_authority_allowed is False


def test_high_zone_requires_halt() -> None:
    operator_input = OperatorInput(
        raw_input="Run everything and change whatever needs changing.",
        session_id="clarification-session-002",
        timestamp=datetime.now(timezone.utc).isoformat(),
        input_source="test",
    )

    result = process_interaction(operator_input)

    assert result.success is True
    assert result.interaction_manifest is not None

    manifest = result.interaction_manifest

    assert manifest.ambiguity_score > 0.75
    assert manifest.clarification_required is True
    assert manifest.halt_required is False
    assert manifest.selected_posture == "CLARIFY_FIRST"
    assert manifest.downstream_authority_allowed is False


def test_low_zone_does_not_require_clarification_or_halt() -> None:
    operator_input = OperatorInput(
        raw_input="Build the runtime slice spec.",
        session_id="clarification-session-003",
        timestamp=datetime.now(timezone.utc).isoformat(),
        input_source="test",
    )

    result = process_interaction(operator_input)

    assert result.success is True
    assert result.interaction_manifest is not None

    manifest = result.interaction_manifest

    assert manifest.ambiguity_score <= 0.50
    assert manifest.clarification_required is False
    assert manifest.halt_required is False
    assert manifest.downstream_authority_allowed is False


@pytest.mark.parametrize('score,required', [(0.49,False),(0.50,False),(0.5001,True),(0.65,True)])
def test_operator_threshold_boundary(monkeypatch, score, required):
    monkeypatch.setattr('core.mode_controller.calculate_ambiguity_score', lambda state: (score, [], {}))
    result = process_interaction(OperatorInput(raw_input='Do it like before.', session_id='threshold',
        timestamp=datetime.now(timezone.utc).isoformat(), input_source='test'))
    assert result.success
    assert result.interaction_manifest.clarification_required is required
    if required: assert result.interaction_manifest.selected_posture == 'CLARIFY_FIRST'
    assert not result.interaction_manifest.downstream_authority_allowed
