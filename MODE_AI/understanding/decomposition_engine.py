"""Recursive composition analysis with bounded traversal and explicit stopping evidence."""
from dataclasses import dataclass, field
from enum import Enum
from .understanding_record import stable_id


class IrreducibilityStatus(str, Enum):
    NOT_EVALUATED = "NOT_EVALUATED"
    DECOMPOSABLE = "DECOMPOSABLE"
    PARTIALLY_DECOMPOSED = "PARTIALLY_DECOMPOSED"
    PROVISIONALLY_IRREDUCIBLE = "PROVISIONALLY_IRREDUCIBLE"
    EVIDENCE_REQUIRED = "EVIDENCE_REQUIRED"
    CONFLICTED = "CONFLICTED"
    UNRESOLVED = "UNRESOLVED"


@dataclass(frozen=True)
class DecompositionResult:
    decomposition_id: str
    target_id: str
    target_type: str
    root_structure: str
    component_elements: tuple = ()
    nested_elements: tuple = ()
    parent_child_relationships: tuple = ()
    governing_relationships: tuple = ()
    essential_elements: tuple = ()
    conditional_elements: tuple = ()
    derivative_elements: tuple = ()
    implementation_specific_elements: tuple = ()
    invariant_elements: tuple = ()
    removable_candidates: tuple = ()
    substitution_candidates: tuple = ()
    decomposition_depth: int = 0
    stopping_reason: str = ""
    irreducibility_status: IrreducibilityStatus = IrreducibilityStatus.NOT_EVALUATED
    unresolved_questions: tuple = ()
    counterexample_requirements: tuple = ()
    evidence_references: tuple = ()
    confidence: float = 0.0
    validation_state: str = "PROVISIONAL"
    metadata: dict = field(default_factory=dict)


class DecompositionEngine:
    def decompose(self, target_id, relationships=(), composition=None, *, target_type="SYSTEM", max_depth=12):
        composition = composition or {}
        elements, links, questions, evidence = {}, [], [], set()
        depth = 0
        def visit(node, level, ancestors):
            nonlocal depth
            depth = max(depth, level)
            if node in ancestors:
                questions.append(f"Composition cycle at {node}"); return
            if level >= max_depth:
                questions.append(f"Depth boundary at {node}"); return
            info = composition.get(node, {})
            children = info.get("children", [])
            classification = info.get("classification", "ESSENTIAL_CANDIDATE")
            if classification not in {"ESSENTIAL", "ESSENTIAL_CANDIDATE", "CONDITIONAL", "DERIVATIVE", "IMPLEMENTATION_SPECIFIC", "INVARIANT", "REMOVABLE", "SUBSTITUTABLE"}:
                raise ValueError("unknown decomposition classification")
            # Essential/irreducible claims require actual removal/variation evidence.
            tested = info.get("removal_invalidates_relationship") is True and bool(info.get("validated_evidence"))
            if classification == "ESSENTIAL" and not tested:
                classification = "ESSENTIAL_CANDIDATE"
            elements[node] = {"id": node, "classification": classification, "removal_tested": tested}
            evidence.update(info.get("validated_evidence", []))
            if not children:
                questions.append(f"{node}: further subdivision/removal/substitution evidence unavailable")
            for child in children:
                links.append((node, child)); visit(child, level + 1, ancestors | {node})
        visit(target_id, 0, set())
        # Explicit graph constituents remain visible even without a supplied composition tree.
        for edge in relationships:
            for node in (edge.source_entity, edge.target_entity):
                if node not in elements:
                    elements[node] = {"id": node, "classification": "ESSENTIAL_CANDIDATE", "removal_tested": False}
                    links.append((target_id, node))
        def group(kind): return tuple(k for k, v in elements.items() if v["classification"] == kind)
        cycle = any("cycle" in q for q in questions)
        all_tested = bool(elements) and all(v["removal_tested"] for v in elements.values())
        status = (IrreducibilityStatus.CONFLICTED if cycle else IrreducibilityStatus.PROVISIONALLY_IRREDUCIBLE
                  if all_tested else IrreducibilityStatus.PARTIALLY_DECOMPOSED if links else IrreducibilityStatus.EVIDENCE_REQUIRED)
        return DecompositionResult(stable_id("decomposition", target_id, links), target_id, target_type, target_id,
            tuple(elements.values()), tuple(k for k in elements if k != target_id), tuple(links),
            tuple(e.relationship_id for e in relationships), group("ESSENTIAL"), group("CONDITIONAL"), group("DERIVATIVE"),
            group("IMPLEMENTATION_SPECIFIC"), group("INVARIANT"), group("REMOVABLE"), group("SUBSTITUTABLE"), depth,
            "Cycle boundary" if cycle else "Scoped removal evidence" if all_tested else "Available composition exhausted; further structural evidence required",
            status, tuple(questions), ("Test removal/substitution without violating the authority boundary.",),
            tuple(sorted(evidence)), 0.8 if all_tested else 0.4, metadata={"essential_candidates": group("ESSENTIAL_CANDIDATE")})
