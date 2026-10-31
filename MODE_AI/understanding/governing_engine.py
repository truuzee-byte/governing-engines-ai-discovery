"""Scoped principle candidates; recurrence never confers governing authority."""
from dataclasses import dataclass
from .understanding_record import stable_id


@dataclass(frozen=True)
class GoverningPrincipleCandidate:
    principle_id: str
    statement: str
    candidate_type: str
    source_relationship_ids: tuple
    source_chain_ids: tuple
    source_decomposition_ids: tuple
    invariant_claim: str
    scope: str
    boundary_conditions: tuple
    supporting_observation_ids: tuple
    supporting_system_ids: tuple
    supporting_mechanism_ids: tuple
    counterexamples_tested: tuple
    known_counterexamples: tuple
    falsification_conditions: tuple
    confidence: float
    validation_state: str = "CANDIDATE"
    authority_status: str = "UNPROMOTED"


@dataclass(frozen=True)
class GoverningPrincipleResult:
    candidate_principles: tuple = ()
    rejected_candidates: tuple = ()
    unresolved_candidates: tuple = ()
    supporting_chains: tuple = ()
    supporting_relationships: tuple = ()
    evidence_domains: tuple = ()
    counterexamples: tuple = ()
    scope_boundaries: tuple = ()
    confidence: float = 0.0
    validation_state: str = "NOT_EVALUATED"
    review_required: bool = False


class GoverningEngine:
    def evaluate(self, decomposition, recognition, relationships, comparisons=()):
        if not decomposition.component_elements or not decomposition.parent_child_relationships:
            return GoverningPrincipleResult(unresolved_candidates=("Structural decomposition required.",))
        groups = {}
        allowed_invariants = {v for edge in relationships for v in edge.invariants}
        for item in comparisons:
            if (item.get("validated") is True and item.get("observation_id") and item.get("system_id")
                    and item.get("evidence_reference") and item.get("invariant") in allowed_invariants
                    and item.get("scope") and item.get("boundary_conditions") and item.get("falsification_conditions")):
                groups.setdefault((item["invariant"], item["scope"]), []).append(item)
        candidates, rejected, unresolved = [], [], []
        for (invariant, scope), items in sorted(groups.items()):
            systems = {i["system_id"] for i in items}
            observations = {i["observation_id"] for i in items}
            if len(systems) < 2 or len(observations) < 2:
                unresolved.append(f"{invariant}: independent cross-system recurrence missing"); continue
            counterexamples = tuple(i["observation_id"] for i in items if i.get("counterexample") is True)
            if counterexamples:
                rejected.append({"invariant": invariant, "scope": scope, "counterexamples": counterexamples}); continue
            searched = all(i.get("counterexample_search_completed") is True for i in items)
            candidates.append(GoverningPrincipleCandidate(
                stable_id("principle", invariant, scope), f"Within {scope}, observed structures preserve {invariant}.",
                "RECURRING_PRINCIPLE", tuple(e.relationship_id for e in relationships if invariant in e.invariants),
                tuple(c.chain_id for c in recognition.chain_records if invariant in c.required_invariants),
                (decomposition.decomposition_id,), invariant, scope,
                tuple(sorted({b for i in items for b in i["boundary_conditions"]})),
                tuple(sorted(observations)), tuple(sorted(systems)),
                tuple(sorted({m for i in items for m in i.get("mechanism_ids", [])})),
                tuple(i["evidence_reference"] for i in items if i.get("counterexample_search_completed") is True), (),
                tuple(sorted({f for i in items for f in i["falsification_conditions"]})),
                0.65 if searched else 0.4, "PROVISIONAL" if searched else "CANDIDATE"))
            if not searched: unresolved.append(f"{invariant}: counterexample search unavailable/incomplete")
        return GoverningPrincipleResult(tuple(candidates), tuple(rejected), tuple(unresolved),
            tuple(c.chain_id for c in recognition.chain_records), tuple(e.relationship_id for e in relationships),
            scope_boundaries=tuple(c.scope for c in candidates), confidence=0.5 if candidates else 0.0,
            validation_state="CANDIDATE" if candidates else "UNPROVEN", review_required=bool(candidates or unresolved))
