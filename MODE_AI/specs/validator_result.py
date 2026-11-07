from __future__ import annotations

from dataclasses import dataclass, field
from typing import List, Optional


VALID_RESULTS = {
    "PASS",
    "FAIL",
}


@dataclass
class ValidatorResult:
    result: str
    failure_reason: Optional[str] = None
    failing_field: Optional[str] = None
    trace_reference: Optional[str] = None
    source_stage: Optional[str] = None
    validation_notes: List[str] = field(default_factory=list)

    def __post_init__(self) -> None:
        if not isinstance(self.result, str):
            raise TypeError("result must be a string")

        self.result = self.result.strip().upper()

        if self.result not in VALID_RESULTS:
            raise ValueError(
                f"result must be one of {sorted(VALID_RESULTS)}"
            )

        if self.result == "FAIL":
            if self.failure_reason is None:
                raise ValueError(
                    "failure result must include failure_reason"
                )

            if not isinstance(self.failure_reason, str):
                raise TypeError("failure_reason must be a string")

            if self.failure_reason.strip() == "":
                raise ValueError(
                    "failure result must include failure_reason"
                )

        if self.failure_reason is not None:
            self.failure_reason = _normalize_optional_string(
                self.failure_reason,
                "failure_reason",
            )

        if self.failing_field is not None:
            self.failing_field = _normalize_optional_string(
                self.failing_field,
                "failing_field",
            )

        if self.trace_reference is not None:
            self.trace_reference = _normalize_optional_string(
                self.trace_reference,
                "trace_reference",
            )

        if self.source_stage is not None:
            self.source_stage = _normalize_optional_string(
                self.source_stage,
                "source_stage",
            )

        if not isinstance(self.validation_notes, list):
            raise TypeError("validation_notes must be a list")

        normalized_notes = []

        for note in self.validation_notes:
            if not isinstance(note, str):
                raise TypeError("validation_notes must contain only strings")

            normalized_notes.append(note)

        self.validation_notes = normalized_notes

    def passed(self) -> bool:
        return self.result == "PASS"

    def failed(self) -> bool:
        return self.result == "FAIL"

    def to_dict(self) -> dict:
        return {
            "result": self.result,
            "failure_reason": self.failure_reason,
            "failing_field": self.failing_field,
            "trace_reference": self.trace_reference,
            "source_stage": self.source_stage,
            "validation_notes": list(self.validation_notes),
        }

    @classmethod
    def pass_result(
        cls,
        trace_reference: Optional[str] = None,
        source_stage: Optional[str] = None,
        validation_notes: Optional[List[str]] = None,
    ) -> ValidatorResult:
        return cls(
            result="PASS",
            failure_reason=None,
            failing_field=None,
            trace_reference=trace_reference,
            source_stage=source_stage,
            validation_notes=(
                list(validation_notes)
                if validation_notes is not None
                else []
            ),
        )

    @classmethod
    def fail_result(
        cls,
        failure_reason: str,
        failing_field: Optional[str] = None,
        trace_reference: Optional[str] = None,
        source_stage: Optional[str] = None,
        validation_notes: Optional[List[str]] = None,
    ) -> ValidatorResult:
        return cls(
            result="FAIL",
            failure_reason=failure_reason,
            failing_field=failing_field,
            trace_reference=trace_reference,
            source_stage=source_stage,
            validation_notes=(
                list(validation_notes)
                if validation_notes is not None
                else []
            ),
        )


def _normalize_optional_string(
    value: str,
    field_name: str,
) -> str:
    if not isinstance(value, str):
        raise TypeError(f"{field_name} must be a string")

    normalized_value = value.strip()

    if normalized_value == "":
        raise ValueError(f"{field_name} must not be empty")

    return normalized_value