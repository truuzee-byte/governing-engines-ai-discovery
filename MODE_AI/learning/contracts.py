"""Governed experience contracts. Labels never establish eligibility or authority."""
from dataclasses import dataclass, field, asdict
from enum import Enum
from datetime import datetime, timezone
import hashlib
import json


def digest(value):
    return hashlib.sha256(json.dumps(value,sort_keys=True,separators=(',',':'),ensure_ascii=False).encode()).hexdigest()

def now():
    return datetime.now(timezone.utc).isoformat()

class Status(str, Enum):
    PROPOSED='PROPOSED'
    ELIGIBLE='ELIGIBLE'
    INELIGIBLE='INELIGIBLE'
    PENDING_VALIDATION='PENDING_VALIDATION'
    APPROVED='APPROVED'
    REJECTED='REJECTED'
    SUPERSEDED='SUPERSEDED'
    REVOKED='REVOKED'
    SUSPENDED='SUSPENDED'
    DEPRECATED='DEPRECATED'
    ARCHIVED='ARCHIVED'
    REMOVED='REMOVED'

class CandidateType(str, Enum):
    EXECUTION_SUCCESS='EXECUTION_SUCCESS'
    EXECUTION_FAILURE='EXECUTION_FAILURE'
    VALIDATION_FAILURE='VALIDATION_FAILURE'
    INTERPRETATION_CORRECTION='INTERPRETATION_CORRECTION'
    CLARIFICATION_RESOLUTION='CLARIFICATION_RESOLUTION'
    OBLIGATION_FAILURE='OBLIGATION_FAILURE'
    GOVERNANCE_FAILURE='GOVERNANCE_FAILURE'
    CONTEXT_FAILURE='CONTEXT_FAILURE'
    TOOL_FAILURE='TOOL_FAILURE'
    CAPABILITY_GAP='CAPABILITY_GAP'
    OPERATOR_CORRECTION='OPERATOR_CORRECTION'
    REPEATED_PATTERN='REPEATED_PATTERN'


def validate_scope(scope):
    if not isinstance(scope,dict) or set(scope) != {'operator_id','project','domain','capability'}:
        raise ValueError('Exact operator/project/domain/capability scope required')
    if not all(isinstance(v,str) and v.strip() for v in scope.values()):
        raise ValueError('Nonempty explicit scope required')

@dataclass(frozen=True)
class LearningCandidate:
    candidate_id: str
    candidate_type: str
    claim: dict
    scope: dict
    source_observation_ids: list
    source_understanding_ids: list
    source_build_id: str | None
    source_spec_id: str | None
    source_rp_decision_id: str | None
    evidence_refs: list
    lineage: dict
    authority_source: str
    uncertainty_state: str
    unresolved_states: list
    outcome_state: str
    support_state: str
    created_at: str
    candidate_status: str = 'PROPOSED'
    schema_version: int = 1

    def __post_init__(self):
        CandidateType(self.candidate_type); Status(self.candidate_status); validate_scope(self.scope)
        if self.schema_version != 1: raise ValueError('Unknown schema')

    def to_dict(self): return json.loads(json.dumps(asdict(self)))

@dataclass(frozen=True)
class LearningRecord:
    learning_id: str
    originating_candidate_id: str
    lesson: dict
    scope: dict
    candidate_type: str
    evidence: list
    lineage: dict
    authority: str
    approval_record: dict
    applicability_conditions: dict
    exclusions: list
    unresolved_conditions: list
    supersedes: list
    superseded_by: str | None
    revocation_state: str
    created_at: str
    updated_at: str
    integrity_metadata: dict
    status: str = 'APPROVED'
    schema_version: int = 1

    def __post_init__(self):
        Status(self.status); CandidateType(self.candidate_type); validate_scope(self.scope)
        if self.schema_version != 1: raise ValueError('Unknown schema')

    def to_dict(self): return json.loads(json.dumps(asdict(self)))
