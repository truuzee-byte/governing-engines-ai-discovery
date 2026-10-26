from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Optional
from uuid import uuid4


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


@dataclass(frozen=True)
class OperatorIdentity:
    operator_id: str
    session_id: str
    authenticated_at: str = field(default_factory=utc_now)

    @staticmethod
    def create(operator_id: Optional[str] = None) -> "OperatorIdentity":
        return OperatorIdentity(
            operator_id=operator_id or f"operator-{uuid4().hex}",
            session_id=f"session-{uuid4().hex}",
        )

    def validate_profile_match(self, profile_operator_id: str) -> bool:
        return self.operator_id == profile_operator_id

    def require_profile_match(self, profile_operator_id: str) -> None:
        if not self.validate_profile_match(profile_operator_id):
            raise PermissionError(
                "Operator identity mismatch. Profile crossover blocked."
            )