"""Provisional chain recognition contracts, never capability certificates."""
from dataclasses import dataclass, field
from enum import Enum


class ChainType(str, Enum):
    MEANING = "MEANING"
    IDENTITY = "IDENTITY"
    AUTHORITY = "AUTHORITY"
    EXECUTION = "EXECUTION"
    REALITY_EVIDENCE = "REALITY_EVIDENCE"
    CONTINUITY = "CONTINUITY"
    LEARNING = "LEARNING"
    CONSEQUENCE_CAUSALITY = "CONSEQUENCE_CAUSALITY"
    COORDINATION = "COORDINATION"


class ChainRole(str, Enum):
    PRIMARY = "PRIMARY"
    SUPPORTING = "SUPPORTING"
    CONSTRAINING = "CONSTRAINING"
    DEPENDENT = "DEPENDENT"
    NESTED = "NESTED"
    UNCERTAIN = "UNCERTAIN"
    MISSING = "MISSING"


@dataclass(frozen=True)
class SystemChain:
    chain_id: str
    chain_type: ChainType
    chain_role: ChainRole
    purpose: str
    primary_question: str
    entry_state: str
    required_stages: tuple[str, ...]
    required_transitions: tuple[tuple[str, str], ...]
    required_invariants: tuple[str, ...]
    required_authorities: tuple[str, ...]
    required_evidence: tuple[str, ...]
    relationship_ids: tuple[str, ...]
    source_references: tuple[str, ...]
    completion_condition: str
    completed_stages: tuple[str, ...] = ()
    missing_stages: tuple[str, ...] = ()
    broken_transitions: tuple = ()
    observed_mechanisms: tuple[str, ...] = ()
    missing_mechanisms: tuple[str, ...] = ()
    failure_conditions: tuple[str, ...] = ()
    confidence: float = 0.5
    validation_status: str = "PROVISIONAL"
    metadata: dict = field(default_factory=dict)


@dataclass(frozen=True)
class ChainRecognitionResult:
    chain_records: tuple[SystemChain, ...] = ()
    recognition_rationale: tuple[str, ...] = ()
    source_references: tuple[str, ...] = ()
    confidence: float = 0.0
    unresolved_questions: tuple[str, ...] = ()
    warnings: tuple[str, ...] = ()

    def by_role(self, role):
        return tuple(chain for chain in self.chain_records if chain.chain_role == ChainRole(role))
