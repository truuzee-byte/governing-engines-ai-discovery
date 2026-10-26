"""Explicit inter-chain handoffs and dependency analysis, with no invented precedence."""
from dataclasses import dataclass
from .system_relationship import RelationshipType as R


@dataclass(frozen=True)
class ChainRelationshipMap:
    chain_ids: tuple = ()
    relationships: tuple = ()
    precedence_rules: tuple = ()
    dependency_order: tuple = ()
    blocking_relationships: tuple = ()
    circular_dependencies: tuple = ()
    unresolved_conflicts: tuple = ()
    required_handoffs: tuple = ()
    evidence_handoffs: tuple = ()
    authority_handoffs: tuple = ()
    confidence: float = 0.0
    explanation: str = ""


class ChainRelationshipMapper:
    def map(self, recognition, relationships):
        chains = recognition.chain_records
        links, authority, evidence, blocks, conflicts, precedence = [], [], [], [], [], []
        for edge in relationships:
            left = [c for c in chains if edge.source_entity in c.required_stages]
            right = [c for c in chains if edge.target_entity in c.required_stages]
            for source in left:
                for target in right:
                    if source.chain_id == target.chain_id: continue
                    link = (source.chain_id, edge.relationship_type.value, target.chain_id, edge.relationship_id)
                    if link not in links: links.append(link)
                    if edge.relationship_type == R.AUTHORIZES: authority.append(link)
                    if edge.relationship_type in {R.VALIDATES, R.PROVES}: evidence.append(link)
                    if edge.relationship_type == R.BLOCKS: blocks.append(link)
                    if edge.relationship_type == R.DEPENDS_ON:
                        if edge.authority_requirements:
                            precedence.append((target.chain_id, source.chain_id, edge.relationship_id))
                        else:
                            conflicts.append(f"No authority for precedence of {edge.relationship_id}")
        # Topological layers preserve incomparability. Cycles are reported, not sorted away.
        remaining = {c.chain_id: set() for c in chains}
        for before, after, _ in precedence:
            remaining[after].add(before)
        layers = []
        while remaining:
            ready = tuple(sorted(k for k, deps in remaining.items() if not deps))
            if not ready: break
            layers.append(ready)
            for k in ready: remaining.pop(k)
            for deps in remaining.values(): deps.difference_update(ready)
        cycles = tuple(sorted(remaining))
        if cycles: conflicts.append("Circular or cycle-dependent precedence; no total order authorized.")
        return ChainRelationshipMap(tuple(c.chain_id for c in chains), tuple(links), tuple(precedence),
            tuple(layers), tuple(blocks), cycles, tuple(dict.fromkeys(conflicts)), tuple(links),
            tuple(dict.fromkeys(evidence)), tuple(dict.fromkeys(authority)), 0.6,
            "Handoffs follow shared entities and source relationships; independent chains remain unordered.")
