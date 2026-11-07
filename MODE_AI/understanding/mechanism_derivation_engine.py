"""Derive obligations from graph edges, without selecting implementation technology."""
from dataclasses import dataclass
from .system_relationship import RelationshipType as R
from .understanding_record import stable_id


@dataclass(frozen=True)
class MechanismRequirement:
    mechanism_id: str
    mechanism_type: str
    description: str
    required_by_requirement_ids: tuple
    required_by_relationship_ids: tuple
    required_by_chain_ids: tuple
    required_stage: str
    enabled_transition: tuple
    invariant_protected: tuple
    authority_requirement: tuple
    failure_prevented: str
    evidence_required: tuple
    current_implementation_reference: str | None
    status: str
    confidence: float
    source_references: tuple
    decomposition_reference: str


@dataclass(frozen=True)
class StructuralGap:
    gap_id: str
    gap_type: str
    description: str
    source_references: tuple = ()
    relationship_ids: tuple = ()
    mechanism_ids: tuple = ()
    blocking: bool = True


@dataclass(frozen=True)
class MechanismDerivationResult:
    mechanism_requirements: tuple = ()
    existing_sufficient_mechanisms: tuple = ()
    missing_mechanisms: tuple = ()
    mechanism_relationships: tuple = ()
    protected_invariants: tuple = ()
    enabled_transitions: tuple = ()
    failure_prevention_map: tuple = ()
    evidence_requirements: tuple = ()
    unresolved_mechanisms: tuple = ()
    structural_gaps: tuple = ()
    confidence: float = 0.0
    warnings: tuple = ()


class MechanismDerivationEngine:
    def derive(self, relationships, recognition, decomposition, existing_mechanisms=(), principles=None):
        requirements, sufficient, missing, unresolved, gaps = [], [], [], [], []
        kinds = {R.PRESERVES: "PRIOR_STATE_PRESERVATION", R.AUTHORIZES: "AUTHORITY_GATE",
                 R.VALIDATES: "EVIDENCE_VALIDATION", R.PROVES: "EXECUTION_PROOF",
                 R.PRODUCES: "OUTCOME_CAPTURE", R.TRANSITIONS_TO: "STATE_TRANSITION",
                 R.TRIGGERS: "GOVERNED_TRIGGER", R.BLOCKS: "EXECUTION_GATE",
                 R.COORDINATES_WITH: "COORDINATION", R.PROPAGATES_TO: "CONSEQUENCE_TRACKING",
                 R.SUPERSEDES: "VERSIONED_REPLACEMENT"}
        for edge in relationships:
            chain_ids = tuple(c.chain_id for c in recognition.chain_records if edge.relationship_id in c.relationship_ids)
            if edge.relationship_type not in kinds:
                continue
            kind = kinds[edge.relationship_type]
            mid = stable_id("mechanism", edge.relationship_id, kind)
            candidates = [m for m in existing_mechanisms if edge.relationship_id in m.get("relationship_ids", [])]
            valid = [m for m in candidates if m.get("validated") is True and m.get("operational") is True
                     and m.get("implementation_reference") and m.get("evidence_references")
                     and set(edge.invariants) <= set(m.get("preserved_invariants", []))
                     and set(edge.authority_requirements) <= set(m.get("enforced_authorities", []))
                     and set(edge.evidence_requirements) <= set(m.get("satisfied_evidence_requirements", []))
                     and [edge.source_entity, edge.target_entity] in m.get("enabled_transitions", [])]
            status = "EXISTING_SUFFICIENT" if valid else "UNPROVEN" if candidates else "MISSING"
            mechanism = MechanismRequirement(mid, kind, f"Enable {edge.description}",
                edge.governing_requirement_ids, (edge.relationship_id,), chain_ids, edge.target_entity,
                (edge.source_entity, edge.target_entity), edge.invariants, edge.authority_requirements,
                edge.failure_condition, edge.evidence_requirements,
                valid[0]["implementation_reference"] if valid else None, status,
                0.8 if valid else 0.5, edge.source_references, decomposition.decomposition_id)
            requirements.append(mechanism)
            (sufficient if valid else unresolved if candidates else missing).append(mid)
            absent = []
            if not chain_ids: absent.append("chain justification")
            if not edge.invariants: absent.append("invariant")
            if not edge.authority_requirements: absent.append("authority")
            if not edge.evidence_requirements: absent.append("evidence requirement")
            if not edge.failure_condition: absent.append("failure condition")
            if absent:
                gaps.append(StructuralGap(stable_id("gap", mid, absent), "UNRESOLVED_JUSTIFICATION",
                    "Missing " + ", ".join(absent), edge.source_references, (edge.relationship_id,), (mid,)))
            if not valid:
                gaps.append(StructuralGap(stable_id("gap", mid, status), status + "_MECHANISM",
                    f"{kind} lacks sufficient operational evidence", edge.source_references, (edge.relationship_id,), (mid,)))
        return MechanismDerivationResult(tuple(requirements), tuple(sufficient), tuple(missing),
            tuple((m.mechanism_id, m.required_by_relationship_ids) for m in requirements),
            tuple(sorted({v for m in requirements for v in m.invariant_protected})),
            tuple(m.enabled_transition for m in requirements),
            tuple((m.mechanism_id, m.failure_prevented) for m in requirements),
            tuple(sorted({v for m in requirements for v in m.evidence_required})),
            tuple(unresolved), tuple(gaps), 0.6 if requirements else 0.0,
            ("Mechanism requirements and supplied evidence assessments are not independent execution proof.",))
