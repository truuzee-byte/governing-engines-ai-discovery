"""Explicit legal transitions and auditable transition proposals."""
from dataclasses import dataclass, field, asdict
from enum import Enum
from uuid import uuid4
from .semantic_state import SemanticState as S


class SemanticTransitionDecision(str, Enum):
    APPROVE = "APPROVE"
    REJECT = "REJECT"
    DEFER = "DEFER"
    REQUIRE_EVIDENCE = "REQUIRE_EVIDENCE"
    REQUIRE_HUMAN_REVIEW = "REQUIRE_HUMAN_REVIEW"
    REQUIRE_AUTHORITY_CONFIRMATION = "REQUIRE_AUTHORITY_CONFIRMATION"
    ROLLBACK = "ROLLBACK"
    NO_CHANGE = "NO_CHANGE"


LEGAL_TRANSITIONS = {
    S.UNOBSERVED: frozenset({S.OBSERVED}),
    S.OBSERVED: frozenset({S.INTERPRETED, S.REJECTED}),
    S.INTERPRETED: frozenset({S.PENDING_VALIDATION, S.REJECTED}),
    S.PENDING_VALIDATION: frozenset({S.PROVISIONAL, S.CONFIRMED, S.REJECTED,
        S.HUMAN_REVIEW_REQUIRED, S.AUTHORITY_CONFIRMATION_REQUIRED, S.ARCHIVED}),
    S.PROVISIONAL: frozenset({S.CONFIRMED, S.DISPUTED, S.PENDING_VALIDATION,
        S.REJECTED, S.ARCHIVED, S.SUPERSEDED}),
    S.CONFIRMED: frozenset({S.DISPUTED, S.SUPERSEDED, S.ROLLBACK_REQUIRED,
        S.PROVISIONAL, S.ARCHIVED}),
    S.DISPUTED: frozenset({S.CONFIRMED, S.CONTRADICTED, S.HUMAN_REVIEW_REQUIRED, S.ARCHIVED}),
    S.CONTRADICTED: frozenset({S.SUPERSEDED, S.ARCHIVED, S.ROLLBACK_REQUIRED}),
    S.HUMAN_REVIEW_REQUIRED: frozenset({S.PENDING_VALIDATION, S.REJECTED}),
    S.AUTHORITY_CONFIRMATION_REQUIRED: frozenset({S.PENDING_VALIDATION, S.REJECTED}),
    S.ROLLBACK_REQUIRED: frozenset({S.CONFIRMED, S.PROVISIONAL, S.PENDING_VALIDATION}),
    S.SUPERSEDED: frozenset(), S.REJECTED: frozenset(), S.ARCHIVED: frozenset(),
}


def is_transition_allowed(previous, proposed):
    return S(proposed) in LEGAL_TRANSITIONS[S(previous)]


@dataclass(frozen=True)
class SemanticTransition:
    understanding_id: str
    operator_id: str
    previous_state: S
    proposed_state: S
    previous_meaning: str
    proposed_meaning: str
    reason: str
    action: str
    expected_version: int
    authority_source: str
    requested_by: str
    triggering_observation_ids: tuple[str, ...] = ()
    evidence_references: tuple[str, ...] = ()
    confidence_before: float = 0.0
    confidence_after: float = 0.0
    approved_state: S | None = None
    approved_by: str | None = None
    policy_result: str = "PENDING"
    continuity_result: str = ""
    rollback_reference: str | None = None
    transition_id: str = field(default_factory=lambda: "transition-" + uuid4().hex)
    created_at: str = ""
    completed_at: str | None = None

    def validate(self):
        same = self.previous_state == self.proposed_state
        if same and self.action in {"NO_CHANGE", "ADD_EVIDENCE", "REFINE", "EXPAND", "REDUCE", "CREATE"}:
            return
        if not is_transition_allowed(self.previous_state, self.proposed_state):
            raise ValueError(f"illegal semantic transition: {self.previous_state} -> {self.proposed_state}")

    def to_dict(self):
        return asdict(self)
