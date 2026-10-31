from dataclasses import dataclass, asdict, field
from datetime import datetime, timezone
from typing import Any, Dict, Optional


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


@dataclass
class OnboardingState:
    operator_id: str
    onboarding_required: bool
    onboarding_complete: bool = False
    initial_thread_id: Optional[str] = None
    temporal_initialized: bool = False
    created_at: str = field(default_factory=utc_now)
    updated_at: str = field(default_factory=utc_now)

    def mark_complete(self, initial_thread_id: str) -> None:
        self.onboarding_required = False
        self.onboarding_complete = True
        self.initial_thread_id = initial_thread_id
        self.temporal_initialized = True
        self.updated_at = utc_now()

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

    @staticmethod
    def from_dict(data: Dict[str, Any]) -> "OnboardingState":
        return OnboardingState(
            operator_id=data["operator_id"],
            onboarding_required=data.get("onboarding_required", True),
            onboarding_complete=data.get("onboarding_complete", False),
            initial_thread_id=data.get("initial_thread_id"),
            temporal_initialized=data.get("temporal_initialized", False),
            created_at=data.get("created_at", utc_now()),
            updated_at=data.get("updated_at", utc_now()),
        )