from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Optional
from uuid import uuid4


@dataclass
class ProviderRequestTelemetry:
    telemetry_id: str
    interaction_id: str
    reasoning_id: str
    stage: str

    provider: str
    model: str
    provider_response_id: Optional[str]

    started_at_utc: str
    completed_at_utc: str
    duration_seconds: float

    input_tokens: Optional[int]
    cached_input_tokens: Optional[int]
    output_tokens: Optional[int]
    reasoning_tokens: Optional[int]
    total_tokens: Optional[int]

    status: str = "COMPLETE"
    error_type: Optional[str] = None
    error_message: Optional[str] = None

    @classmethod
    def create(
        cls,
        *,
        interaction_id: str,
        reasoning_id: str,
        stage: str,
        provider: str,
        model: str,
        provider_response_id: Optional[str],
        started_at_utc: str,
        completed_at_utc: str,
        duration_seconds: float,
        input_tokens: Optional[int],
        cached_input_tokens: Optional[int],
        output_tokens: Optional[int],
        reasoning_tokens: Optional[int],
        total_tokens: Optional[int],
        status: str = "COMPLETE",
        error_type: Optional[str] = None,
        error_message: Optional[str] = None,
    ) -> "ProviderRequestTelemetry":
        return cls(
            telemetry_id=f"provider-telemetry-{uuid4().hex}",
            interaction_id=interaction_id,
            reasoning_id=reasoning_id,
            stage=stage,
            provider=provider,
            model=model,
            provider_response_id=provider_response_id,
            started_at_utc=started_at_utc,
            completed_at_utc=completed_at_utc,
            duration_seconds=duration_seconds,
            input_tokens=input_tokens,
            cached_input_tokens=cached_input_tokens,
            output_tokens=output_tokens,
            reasoning_tokens=reasoning_tokens,
            total_tokens=total_tokens,
            status=status,
            error_type=error_type,
            error_message=error_message,
        )

    def to_dict(self) -> dict:
        return asdict(self)