"""Conservative semantic comparison. Unknown equivalence is not approval."""
from dataclasses import dataclass, field
from .semantic_drift_record import SemanticDriftRecord, DriftType as D, DriftSeverity as V
from .understanding_record import normalize_meaning, primitive, structural_digest


@dataclass(frozen=True)
class MeaningContinuityResult:
    continuity_preserved: bool
    exact_match: bool = False
    meaning_changed: bool = False
    contradiction_detected: bool = False
    requires_review: bool = False
    explanation: str = ""
    compared_fields: tuple[str, ...] = ()
    drift_records: tuple[SemanticDriftRecord, ...] = ()
    classification: str = "NEW"
    confidence: float = 0.0


class MeaningContinuityValidator:
    def validate(self, existing, proposed):
        if existing is None:
            return MeaningContinuityResult(True, explanation="No previous meaning; evidence and custody still required.")
        compared = ("subject_id", "semantic_domain", "canonical_meaning", "scope", "qualifiers",
                    "context", "temporal_scope", "authority_level", "custody_holder", "confidence",
                    "supporting_evidence", "policy_version", "protected_meaning", "requirements", "constraints", "invariants", "dependencies")
        changed = tuple(name for name in compared if primitive(getattr(existing, name)) != primitive(getattr(proposed, name)))
        equivalent = existing.normalized_meaning == proposed.normalized_meaning
        context_changed = existing.context != proposed.context or existing.temporal_scope != proposed.temporal_scope
        old_claim = existing.metadata.get("claim", {})
        new_claim = proposed.metadata.get("claim", {})
        contradiction = (not context_changed and bool(old_claim) and bool(new_claim)
                         and old_claim.get("predicate") == new_claim.get("predicate")
                         and old_claim.get("value") != new_claim.get("value"))
        if not equivalent and not context_changed and not (old_claim and new_claim):
            contradiction = (normalize_meaning(existing.canonical_meaning.replace(" not ", " ")) ==
                             normalize_meaning(proposed.canonical_meaning.replace(" not ", " ")))
        drifts = []
        def add(kind, severity, names, preserved=True):
            drifts.append(SemanticDriftRecord(
                existing.understanding_id, existing.operator_id, existing.canonical_meaning,
                proposed.canonical_meaning, kind, severity, tuple(names),
                tuple(e.reference for e in proposed.supporting_evidence), proposed.source_observation_ids,
                authority_difference=f"{existing.authority_level} -> {proposed.authority_level}",
                context_difference=str(proposed.context) if context_changed else "",
                temporal_difference=proposed.temporal_scope,
                contradiction_detected=contradiction, continuity_preserved=preserved))
        classification = "EQUIVALENT"
        if contradiction:
            add(D.MEANING_REVERSAL, V.HIGH, ("canonical_meaning",), False)
            classification = "CONTRADICTION"
        elif context_changed:
            add(D.CONTEXT_DRIFT, V.MODERATE, ("context", "canonical_meaning"))
            classification = "CONTEXTUAL_CHANGE"
        elif not equivalent:
            old_scope, new_scope = set(existing.qualifiers), set(proposed.qualifiers)
            if existing.normalized_meaning in proposed.normalized_meaning:
                add(D.MEANING_EXPANSION, V.MODERATE, ("canonical_meaning",))
                classification = "EXPANSION"
            elif proposed.normalized_meaning in existing.normalized_meaning:
                add(D.MEANING_REDUCTION, V.MODERATE, ("canonical_meaning",))
                classification = "REDUCTION"
            else:
                add(D.UNRESOLVED_DRIFT, V.HIGH, ("canonical_meaning",), False)
                classification = "AMBIGUITY"
        elif "canonical_meaning" in changed:
            add(D.LEXICAL_DRIFT, V.LOW, ("canonical_meaning",))
        for field_name, kind in (("scope", D.CONTEXT_DRIFT), ("qualifiers", D.CONTEXT_DRIFT),
            ("temporal_scope", D.TEMPORAL_DRIFT), ("authority_level", D.AUTHORITY_DRIFT),
            ("custody_holder", D.AUTHORITY_DRIFT), ("confidence", D.CONFIDENCE_DRIFT),
            ("supporting_evidence", D.SOURCE_DRIFT), ("policy_version", D.POLICY_DRIFT), ("protected_meaning", D.POLICY_DRIFT)):
            if field_name in changed:
                add(kind, V.MODERATE, (field_name,))
        structural_changed = any(name in changed for name in ("constraints", "invariants", "dependencies")) or (
            structural_digest(existing.requirements) != structural_digest(proposed.requirements))
        if structural_changed:
            add(D.UNRESOLVED_DRIFT, V.HIGH, ("requirements", "constraints", "invariants", "dependencies"), False)
            classification = "REPLACEMENT"
        identity_changed = existing.subject_id != proposed.subject_id or existing.semantic_domain != proposed.semantic_domain
        if identity_changed:
            add(D.UNRESOLVED_DRIFT, V.CRITICAL, ("subject_id", "semantic_domain"), False)
        review = contradiction or classification in {"AMBIGUITY", "REPLACEMENT"} or identity_changed
        material_change = any(name in changed for name in ("scope", "qualifiers", "context", "temporal_scope", "protected_meaning"))
        return MeaningContinuityResult(not review, not changed, not equivalent or structural_changed or material_change,
            contradiction, review, "Compared explicit claims and boundaries; unrecognized changes require review.",
            compared, tuple(drifts), classification, 1.0 if equivalent or contradiction else 0.5)
