"""Recognize graph obligations. Text and component names are not chain evidence."""
from .system_relationship import RelationshipType as R
from .system_chain import ChainType as C, ChainRole, SystemChain, ChainRecognitionResult
from .understanding_record import stable_id
from dataclasses import replace


class ChainRecognitionEngine:
    def reconcile_evidence(self, recognition, derivation):
        """Report supplied stage evidence without certifying the real capability."""
        records = []
        for chain in recognition.chain_records:
            linked = [m for m in derivation.mechanism_requirements if chain.chain_id in m.required_by_chain_ids]
            supported = [m for m in linked if m.status == "EXISTING_SUFFICIENT"]
            supported_edges = {rid for m in supported for rid in m.required_by_relationship_ids}
            supported_transitions = {m.enabled_transition for m in supported}
            completed = {node for transition in supported_transitions for node in transition}
            records.append(replace(chain,
                completed_stages=tuple(sorted(completed)),
                missing_stages=tuple(stage for stage in chain.required_stages if stage not in completed),
                broken_transitions=tuple(t for t in chain.required_transitions if t not in supported_transitions),
                observed_mechanisms=tuple(m.mechanism_id for m in supported),
                missing_mechanisms=tuple(m.mechanism_id for m in linked if m.status != "EXISTING_SUFFICIENT"),
                validation_status="SUPPORTED_BY_SUPPLIED_EVIDENCE" if set(chain.relationship_ids) <= supported_edges else "UNPROVEN"))
        return replace(recognition, chain_records=tuple(records))

    def recognize(self, relationships, objective="", required_chain_types=()):
        groups = {}
        for edge in relationships:
            kind = {
                R.AUTHORIZES: C.AUTHORITY, R.VALIDATES: C.REALITY_EVIDENCE,
                R.PROVES: C.REALITY_EVIDENCE, R.PRESERVES: C.CONTINUITY,
                R.TRANSITIONS_TO: C.EXECUTION, R.PRODUCES: C.EXECUTION, R.TRIGGERS: C.EXECUTION,
                R.COORDINATES_WITH: C.COORDINATION, R.PROPAGATES_TO: C.CONSEQUENCE_CAUSALITY,
            }.get(edge.relationship_type)
            # Explicit semantic roles are interpreted structure, not text search.
            roles = edge.metadata.get("entity_roles", {})
            if edge.relationship_type == R.VALIDATES and roles.get(edge.target_entity) == "IDENTITY":
                kind = C.IDENTITY
            elif edge.relationship_type == R.PRESERVES and roles.get(edge.target_entity) == "MEANING":
                kind = C.MEANING
            if kind:
                groups.setdefault(kind, []).append(edge)
        # A learning candidate needs an outcome -> validation -> proposed change
        # path. Mentioning learning or merely persisting failures is insufficient.
        feedback = []
        for first in relationships:
            for second in relationships:
                if (first.relationship_type == R.VALIDATES and second.relationship_type == R.TRIGGERS
                        and first.target_entity == second.source_entity
                        and second.metadata.get("entity_roles", {}).get(second.target_entity) == "ADAPTATION_PROPOSAL"):
                    feedback.extend((first, second))
        if feedback:
            groups[C.LEARNING] = list({edge.relationship_id: edge for edge in feedback}.values())
        records, rationale, unresolved = [], [], []
        requested = {C(kind) for kind in required_chain_types}
        for kind in sorted(set(groups) | requested, key=lambda k: k.value):
            edges = groups.get(kind, [])
            stages = tuple(sorted({node for e in edges for node in (e.source_entity, e.target_entity)}))
            role = (ChainRole.MISSING if not edges else ChainRole.PRIMARY if kind == C.LEARNING or kind in requested
                    else ChainRole.CONSTRAINING if kind in {C.AUTHORITY, C.REALITY_EVIDENCE} else ChainRole.SUPPORTING)
            refs = tuple(sorted({ref for e in edges for ref in e.source_references}))
            if not edges:
                unresolved.append(f"Required {kind.value} chain has no justified structural relationships.")
            chain = SystemChain(stable_id("chain", kind, tuple(sorted(e.relationship_id for e in edges))),
                kind, role, objective, f"Which obligations establish {kind.value}?",
                stages[0] if stages else "UNRESOLVED", stages,
                tuple((e.source_entity, e.target_entity) for e in edges),
                tuple(sorted({v for e in edges for v in e.invariants})),
                tuple(sorted({v for e in edges for v in e.authority_requirements})),
                tuple(sorted({v for e in edges for v in e.evidence_requirements})),
                tuple(e.relationship_id for e in edges), refs,
                "All modeled transitions require operational evidence; recognition is not completion.",
                missing_stages=stages, failure_conditions=tuple(e.failure_condition for e in edges if e.failure_condition),
                metadata={"capability_proven": False, "recognition_basis": [e.relationship_type.value for e in edges]})
            records.append(chain)
            rationale.append(f"{kind.value}: derived from edges {chain.relationship_ids}; operational completeness unproven.")
        return ChainRecognitionResult(tuple(records), tuple(rationale),
            tuple(sorted({r for chain in records for r in chain.source_references})),
            0.7 if records else 0.0, tuple(unresolved), ("Chain types are provisional recognition primitives, not laws.",))
