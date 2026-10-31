from __future__ import annotations
from tests.local_controller_fixture import local_controller

from datetime import datetime, timezone

from core.mode_controller import process_interaction
from models.runtime_models import OperatorInput


def test_manifest_generation_simple_interpretation() -> None:
    operator_input = OperatorInput(
        raw_input="What does this mean?",
        session_id="test-session-001",
        timestamp=datetime.now(timezone.utc).isoformat(),
        input_source="test",
    )

    result = process_interaction(operator_input)

    assert result.success is True
    assert result.interaction_manifest is not None

    manifest = result.interaction_manifest

    assert manifest.selected_mode == "Interpretation"
    assert manifest.selected_posture in {
        "DIRECT_RESPONSE",
        "INTERPRET",
    }

    assert manifest.ambiguity_score <= 0.50
    assert manifest.clarification_required is False
    assert manifest.downstream_authority_allowed is False


def test_manifest_generation_build_request() -> None:
    operator_input = OperatorInput(
        raw_input="Build the runtime slice spec.",
        session_id="test-session-002",
        timestamp=datetime.now(timezone.utc).isoformat(),
        input_source="test",
    )

    result = process_interaction(operator_input)

    assert result.success is True
    assert result.interaction_manifest is not None

    manifest = result.interaction_manifest

    assert manifest.selected_mode == "Development"
    assert manifest.selected_posture == "DEVELOPMENT_ANALYSIS"
    assert manifest.downstream_authority_allowed is False


def test_manifest_generation_document_review() -> None:
    operator_input = OperatorInput(
        raw_input="DOCUMENT: MODE AI — IMPLEMENTATION DOCUMENT",
        session_id="test-session-003",
        timestamp=datetime.now(timezone.utc).isoformat(),
        input_source="test",
    )

    result = process_interaction(operator_input)

    assert result.success is True
    assert result.interaction_manifest is not None

    manifest = result.interaction_manifest

    assert manifest.selected_mode == "Canon Check"
    assert manifest.selected_posture == "CANON_VALIDATION"
    assert manifest.downstream_authority_allowed is False
