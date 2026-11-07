from __future__ import annotations

import pytest

from specs.validator_result import ValidatorResult


def test_pass_result_serializes_deterministically() -> None:
    result = ValidatorResult.pass_result(
        trace_reference="trace-001",
        source_stage="spec_validator",
        validation_notes=["ok"],
    )

    assert result.to_dict() == {
        "result": "PASS",
        "failure_reason": None,
        "failing_field": None,
        "trace_reference": "trace-001",
        "source_stage": "spec_validator",
        "validation_notes": ["ok"],
    }


def test_fail_result_serializes_deterministically() -> None:
    result = ValidatorResult.fail_result(
        failure_reason="invalid object_type",
        failing_field="object_type",
        trace_reference="trace-002",
        source_stage="spec_validator",
        validation_notes=["rejected"],
    )

    assert result.to_dict() == {
        "result": "FAIL",
        "failure_reason": "invalid object_type",
        "failing_field": "object_type",
        "trace_reference": "trace-002",
        "source_stage": "spec_validator",
        "validation_notes": ["rejected"],
    }


def test_result_normalizes_to_uppercase() -> None:
    result = ValidatorResult(result="pass")

    assert result.result == "PASS"


def test_invalid_result_raises_value_error() -> None:
    with pytest.raises(ValueError):
        ValidatorResult(result="UNKNOWN")


def test_fail_without_failure_reason_raises_value_error() -> None:
    with pytest.raises(ValueError):
        ValidatorResult(result="FAIL")


def test_failure_reason_preserved() -> None:
    result = ValidatorResult.fail_result(
        failure_reason="missing required SpecificationObject field",
    )

    assert result.failure_reason == "missing required SpecificationObject field"


def test_failing_field_preserved() -> None:
    result = ValidatorResult.fail_result(
        failure_reason="missing required SpecificationObject field",
        failing_field="spec_id",
    )

    assert result.failing_field == "spec_id"


def test_trace_reference_preserved() -> None:
    result = ValidatorResult.pass_result(
        trace_reference="trace-003",
    )

    assert result.trace_reference == "trace-003"


def test_source_stage_preserved() -> None:
    result = ValidatorResult.pass_result(
        source_stage="handoff_gate",
    )

    assert result.source_stage == "handoff_gate"


def test_validation_notes_preserved_as_list() -> None:
    result = ValidatorResult.pass_result(
        validation_notes=["note-a", "note-b"],
    )

    assert isinstance(result.validation_notes, list)
    assert result.validation_notes == ["note-a", "note-b"]


def test_passed_returns_true_for_pass() -> None:
    result = ValidatorResult.pass_result()

    assert result.passed() is True
    assert result.failed() is False


def test_failed_returns_true_for_fail() -> None:
    result = ValidatorResult.fail_result(
        failure_reason="invalid spec",
    )

    assert result.failed() is True
    assert result.passed() is False