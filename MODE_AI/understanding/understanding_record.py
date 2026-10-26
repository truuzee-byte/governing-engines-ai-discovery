"""Serializable governed meaning. No truth or custody decisions live here."""
from dataclasses import dataclass, field, asdict, fields
from datetime import datetime, timezone
from enum import Enum
import hashlib
import json
import re
from .semantic_state import SemanticState


def utc_now():
    return datetime.now(timezone.utc).isoformat()


def normalize_meaning(text):
    return " ".join(text.casefold().split()).rstrip(".! ")


def primitive(value):
    if isinstance(value, Enum):
        return value.value
    if hasattr(value, "to_dict"):
        return primitive(value.to_dict())
    if hasattr(value, "__dataclass_fields__"):
        return primitive(asdict(value))
    if isinstance(value, dict):
        return {str(k): primitive(v) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [primitive(v) for v in value]
    return value


def digest(value):
    return hashlib.sha256(json.dumps(primitive(value), sort_keys=True, ensure_ascii=False,
                                    allow_nan=False).encode()).hexdigest()


def stable_id(prefix, *parts):
    return prefix + "-" + digest(parts)[:24]


def structural_digest(value):
    """Compare modeled structure independently of observation/reference identity.

    This is repeatability evidence only, never a custody or storage hash.
    """
    def project(item):
        if isinstance(item, dict):
            return {k: project(v) for k, v in item.items() if k not in {
                "source_references", "supporting_evidence", "source_observation_ids", "evidence_references"}}
        if isinstance(item, list): return [project(v) for v in item]
        return item
    return digest(project(primitive(value)))


@dataclass(frozen=True)
class Evidence:
    reference: str
    source_type: str
    validated: bool = False
    domain: str = ""
    claim: str = ""
    observation_id: str = ""
    system_id: str = ""
    verified_at: str | None = None

    def __post_init__(self):
        if not self.reference or type(self.validated) is not bool:
            raise ValueError("evidence requires a reference and explicit boolean validation")


@dataclass(frozen=True)
class Requirement:
    requirement_id: str
    text: str
    kind: str = "REQUIREMENT"
    source_references: tuple[str, ...] = ()
    justification: str = ""
    completion_condition: str = ""
    prohibited_states: tuple[str, ...] = ()

    def __post_init__(self):
        if self.kind not in {"REQUIREMENT", "PREFERENCE", "CONSTRAINT", "INVARIANT", "DERIVED"}:
            raise ValueError("unknown requirement kind")
        if not self.text.strip() or not self.source_references:
            raise ValueError("requirement requires text and provenance")
        if self.kind == "DERIVED" and not self.justification:
            raise ValueError("derived requirement requires justification")


@dataclass(frozen=True)
class UnderstandingRecord:
    understanding_id: str
    operator_id: str
    thread_id: str
    project_id: str
    subject_id: str
    subject_type: str
    semantic_domain: str
    canonical_meaning: str
    normalized_meaning: str
    meaning_summary: str = ""
    qualifiers: tuple[str, ...] = ()
    scope: str = ""
    context: dict = field(default_factory=dict)
    temporal_scope: str = ""
    operator_objective: str = ""
    requirements: tuple[Requirement, ...] = ()
    constraints: tuple[str, ...] = ()
    invariants: tuple[str, ...] = ()
    dependencies: tuple[str, ...] = ()
    system_relationship_ids: tuple[str, ...] = ()
    chain_ids: tuple[str, ...] = ()
    decomposition_result_ids: tuple[str, ...] = ()
    governing_principle_ids: tuple[str, ...] = ()
    mechanism_requirement_ids: tuple[str, ...] = ()
    structural_gap_ids: tuple[str, ...] = ()
    semantic_state: SemanticState = SemanticState.PENDING_VALIDATION
    active: bool = True
    confidence: float = 0.0
    validation_status: str = "UNVALIDATED"
    custody_holder: str = ""
    authority_level: str = "UNVERIFIED_INPUT"
    source_observation_ids: tuple[str, ...] = ()
    supporting_evidence: tuple[Evidence, ...] = ()
    contradicting_evidence: tuple[Evidence, ...] = ()
    source_types: tuple[str, ...] = ()
    last_verified_at: str | None = None
    version: int = 0
    previous_version_id: str | None = None
    supersedes_id: str | None = None
    superseded_by_id: str | None = None
    created_at: str = field(default_factory=utc_now)
    updated_at: str = field(default_factory=utc_now)
    created_by: str = ""
    updated_by: str = ""
    policy_version: str = "1.2"
    transition_history: tuple[dict, ...] = ()
    review_required: bool = False
    review_status: str = "NONE"
    rollback_available: bool = False
    protected_meaning: bool = False
    metadata: dict = field(default_factory=dict)
    schema_version: str = "1.2"

    def __post_init__(self):
        for name in ("understanding_id", "operator_id", "thread_id", "subject_id", "semantic_domain", "canonical_meaning"):
            if not isinstance(getattr(self, name), str) or not getattr(self, name).strip():
                raise ValueError(f"missing {name}")
        if not isinstance(self.semantic_state, SemanticState) or not 0 <= self.confidence <= 1:
            raise ValueError("invalid semantic state/confidence")
        if self.normalized_meaning != normalize_meaning(self.canonical_meaning):
            raise ValueError("normalized meaning does not match canonical meaning")
        if self.schema_version != "1.2":
            raise ValueError("unsupported Understanding schema")

    def to_dict(self):
        return asdict(self)

    @classmethod
    def from_dict(cls, data):
        data = dict(data)
        if set(data) - {f.name for f in fields(cls)}:
            raise ValueError("unknown Understanding fields")
        data["semantic_state"] = SemanticState(data["semantic_state"])
        for name in ("supporting_evidence", "contradicting_evidence"):
            data[name] = tuple(Evidence(**e) for e in data.get(name, ()))
        data["requirements"] = tuple(Requirement(**{**r,
            "source_references": tuple(r.get("source_references", ())),
            "prohibited_states": tuple(r.get("prohibited_states", ()))}) for r in data.get("requirements", ()))
        for f in fields(cls):
            if isinstance(f.default, tuple) and f.name in data:
                data[f.name] = tuple(data[f.name])
        return cls(**data)
