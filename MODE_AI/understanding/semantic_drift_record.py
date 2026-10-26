"""Records differences; never authorizes or resolves them."""
from dataclasses import dataclass, field, asdict
from enum import Enum
from datetime import datetime, timezone
from uuid import uuid4


class DriftType(str, Enum):
    LEXICAL_DRIFT = "LEXICAL_DRIFT"
    MEANING_EXPANSION = "MEANING_EXPANSION"
    MEANING_REDUCTION = "MEANING_REDUCTION"
    MEANING_REVERSAL = "MEANING_REVERSAL"
    AUTHORITY_DRIFT = "AUTHORITY_DRIFT"
    CONTEXT_DRIFT = "CONTEXT_DRIFT"
    TEMPORAL_DRIFT = "TEMPORAL_DRIFT"
    CONFIDENCE_DRIFT = "CONFIDENCE_DRIFT"
    SOURCE_DRIFT = "SOURCE_DRIFT"
    POLICY_DRIFT = "POLICY_DRIFT"
    UNRESOLVED_DRIFT = "UNRESOLVED_DRIFT"


class DriftSeverity(str, Enum):
    NONE = "NONE"
    LOW = "LOW"
    MODERATE = "MODERATE"
    HIGH = "HIGH"
    CRITICAL = "CRITICAL"


@dataclass(frozen=True)
class SemanticDriftRecord:
    understanding_id: str
    operator_id: str
    previous_meaning: str
    proposed_meaning: str
    drift_type: DriftType
    drift_severity: DriftSeverity
    affected_fields: tuple[str, ...] = ()
    evidence_references: tuple[str, ...] = ()
    triggering_observation_ids: tuple[str, ...] = ()
    authority_difference: str = ""
    context_difference: str = ""
    temporal_difference: str = ""
    contradiction_detected: bool = False
    continuity_preserved: bool = False
    resolution_status: str = "UNRESOLVED"
    resolution_lineage: tuple[str, ...] = ()
    resolved_at: str | None = None
    resolved_by: str | None = None
    resolution_reason: str = ""
    drift_id: str = field(default_factory=lambda: "drift-" + uuid4().hex)
    created_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())

    def to_dict(self):
        return asdict(self)
