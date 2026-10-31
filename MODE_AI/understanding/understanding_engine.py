"""Understanding v1.2 orchestration. No production code/specification generation."""
from dataclasses import dataclass, field, replace
from enum import Enum
import copy
import re
import time
from uuid import uuid4

from .semantic_state import SemanticState as S
from .semantic_transition import SemanticTransition
from .understanding_record import (UnderstandingRecord, Requirement, Evidence, normalize_meaning,
                                   stable_id, digest, primitive, utc_now)
from .understanding_record import structural_digest
from .semantic_custody_policy import AuthorityContext, AuthorityLevel
from .meaning_continuity_validator import MeaningContinuityValidator
from .semantic_custody_engine import SemanticCustodyEngine
from .understanding_store import UnderstandingStore
from .understanding_updater import UnderstandingUpdater
from .system_relationship import SystemRelationship, RelationshipType as R
from .chain_recognition_engine import ChainRecognitionEngine
from .chain_relationship_mapper import ChainRelationshipMapper
from .decomposition_engine import DecompositionEngine
from .governing_engine import GoverningEngine
from .mechanism_derivation_engine import MechanismDerivationEngine, StructuralGap


class SpecificationReadiness(str, Enum):
    READY_FOR_SPECIFICATION = "READY_FOR_SPECIFICATION"
    READY_WITH_PROVISIONAL_ITEMS = "READY_WITH_PROVISIONAL_ITEMS"
    CLARIFICATION_REQUIRED = "CLARIFICATION_REQUIRED"
    STRUCTURALLY_INCOMPLETE = "STRUCTURALLY_INCOMPLETE"
    CONFLICTED = "CONFLICTED"
    UNPROVEN = "UNPROVEN"


@dataclass(frozen=True)
class UnderstandingRequest:
    operator_id: str
    thread_id: str
    current_input: str
    project_id: str = ""
    interpreted_input: dict = field(default_factory=dict)
    operator_objective: str = ""
    authoritative_document_context: dict = field(default_factory=dict)
    runtime_observation: object = None
    related_observations: tuple = ()
    relevant_context: dict = field(default_factory=dict)
    evidence: tuple[Evidence, ...] = ()
    authority_context: AuthorityContext | None = None
    existing_system_context: dict = field(default_factory=dict)
    existing_mechanisms: tuple = ()
    build_context: dict = field(default_factory=dict)
    runtime_metadata: dict = field(default_factory=dict)
    action: str = "AUTO"
    rollback_version: int | None = None
    request_id: str = field(default_factory=lambda: "understanding-request-" + uuid4().hex)
    declaration_delta: dict = field(default_factory=dict)


@dataclass
class UnderstandingResult:
    request_id: str
    operator_id: str
    observation_id: str = ""
    modes: list = field(default_factory=list)
    candidate_understanding: object = None
    existing_understanding: object = None
    requirement_state: dict = field(default_factory=dict)
    system_relationships: tuple = ()
    chain_recognition_result: object = None
    chain_relationship_map: object = None
    decomposition_result: object = None
    governing_principle_result: object = None
    mechanism_derivation_result: object = None
    structural_gaps: tuple = ()
    continuity_result: object = None
    drift_records: tuple = ()
    custody_decision: object = None
    transition: object = None
    update_result: object = None
    final_understanding: object = None
    state: str = "PENDING"
    action: str = "NO_CHANGE"
    review_required: bool = False
    errors: list = field(default_factory=list)
    warnings: list = field(default_factory=list)
    specification_readiness: SpecificationReadiness = SpecificationReadiness.UNPROVEN
    execution_timing: float = 0.0
    stages: list = field(default_factory=list)
    retry_information: dict = field(default_factory=dict)
    metadata: dict = field(default_factory=dict)

    def to_dict(self):
        from dataclasses import asdict
        return primitive(asdict(self))

    def specification_handoff(self):
        if (self.errors or self.review_required or self.final_understanding is None
                or self.specification_readiness != SpecificationReadiness.READY_FOR_SPECIFICATION
                or any(g.blocking for g in self.structural_gaps)):
            raise PermissionError("Understanding is not authorized for specification handoff")
        return self.governed_handoff()

    def governed_handoff(self):
        """Export governed meaning for consumers that do not request a specification.

        Semantic custody remains mandatory; this export grants no build authority.
        Specification consumers must continue to use specification_handoff().
        """
        if self.errors or self.review_required or self.final_understanding is None:
            raise PermissionError("Understanding is incomplete or requires review")
        if self.custody_decision is None or not self.custody_decision.evidence_sufficient:
            raise PermissionError("Validated custody decision required")
        self.custody_decision.verify(self.candidate_understanding, self.transition)
        generated = {"version", "previous_version_id", "rollback_available", "created_at", "updated_at", "updated_by", "transition_history"}
        if ({k: v for k, v in primitive(self.final_understanding).items() if k not in generated} !=
                {k: v for k, v in primitive(self.candidate_understanding).items() if k not in generated}):
            raise PermissionError("Final understanding differs from approved content")
        analysis = {"requirements": self.requirement_state, "relationships": self.system_relationships,
                    "chains": self.chain_recognition_result, "chain_map": self.chain_relationship_map,
                    "decomposition": self.decomposition_result, "principles": self.governing_principle_result,
                    "mechanisms": self.mechanism_derivation_result, "readiness": self.specification_readiness}
        if self.final_understanding.metadata.get("analysis_hash") != digest(analysis):
            raise PermissionError("Readiness or structural result changed after custody approval")
        return {"contract": "GovernedUnderstanding/1.2", "understanding_id": self.final_understanding.understanding_id,
                "version": self.final_understanding.version, "understanding_hash": digest(self.final_understanding),
                "result": self.to_dict(), "execution_authority": False, "capability_proven": False,
                "rp_state": "PENDING_VALIDATION", "material_claim_admitted": False,
                "admission_basis": "SEMANTIC_CUSTODY_ONLY"}

    def operational_handoff(self, model, inventory, *, current_system_version,source_bindings=None):
        """Bind governed capability meaning to an inventory-grounded procedure.

        The output is preparation, never access, a grant, execution or RP proof.
        """
        from system_layer.audit.operational_understanding_validator import evaluate
        meaning = self.governed_handoff()
        definition = model.get('definition', {})
        if definition.get('capability_id') != self.final_understanding.subject_id:
            raise PermissionError('Operational model does not govern this understood capability')
        if inventory is None or inventory.get('scope', {}).get('operator_id') != self.operator_id:
            raise PermissionError('Operational inventory owner mismatch')
        assessment = evaluate(model, inventory, current_system_version=current_system_version)
        source_map=None
        if source_bindings is not None:
            from system_layer.audit.operation_source_binding import assess
            source_map=assess(model,inventory,source_bindings)
        ready=assessment['state']=='STRUCTURALLY_GROUNDED_MODEL' and (source_map is None or source_map['state']=='DECLARED_STEPS_SOURCE_BOUND')
        return {'contract': 'CapabilityOperationPreparation/1', 'meaning': meaning,
                'operational_model': copy.deepcopy(model), 'assessment': assessment,
                'source_map':source_map,'source_binding_state':source_map['state'] if source_map else 'NOT_SELECTED',
                'state': 'ACCESS_AND_AUTHORITY_REQUIRED' if ready else 'REVIEW_REQUIRED',
                'access': 'NOT_ESTABLISHED', 'execution_authority': False,
                'execution': 'NOT_EXECUTED', 'observation': 'NOT_OBSERVED', 'validation': 'UNPROVEN'}

    def explain(self):
        """Render only structured findings; no second model or invented facts."""
        lines = [f"UNDERSTANDING: {self.state}", f"Specification readiness: {self.specification_readiness.value}",
                 "This is a governed model of requirements, not proof of operational capability."]
        if self.candidate_understanding:
            lines.append("Meaning: " + self.candidate_understanding.canonical_meaning)
        for name, values in self.requirement_state.items():
            lines.append(f"{name}: {values}")
        for edge in self.system_relationships:
            lines.append(f"Relationship: {edge.source_entity} --{edge.relationship_type.value}--> {edge.target_entity}; "
                         f"requirements={edge.governing_requirement_ids}; authority={edge.authority_requirements}; evidence={edge.evidence_requirements}")
        if self.chain_recognition_result:
            for chain in self.chain_recognition_result.chain_records:
                lines.append(f"Chain: {chain.chain_type.value} ({chain.chain_role.value}); transitions={chain.required_transitions}; "
                             f"unproven stages={chain.missing_stages}")
        if self.chain_relationship_map:
            lines.append(f"Chain handoffs: {self.chain_relationship_map.required_handoffs}")
        if self.decomposition_result:
            d = self.decomposition_result
            lines.extend([f"Decomposition: {d.parent_child_relationships}",
                          f"Essential candidates: {d.metadata.get('essential_candidates', ())}; implementation-specific: {d.implementation_specific_elements}",
                          f"Stopping reason: {d.stopping_reason}; status={d.irreducibility_status.value}"])
        if self.governing_principle_result:
            lines.append(f"Candidate governing principles: {[p.statement for p in self.governing_principle_result.candidate_principles]}")
        if self.mechanism_derivation_result:
            for m in self.mechanism_derivation_result.mechanism_requirements:
                lines.append(f"Mechanism: {m.mechanism_type}; status={m.status}; transition={m.enabled_transition}; prevents={m.failure_prevented}")
        lines.extend(f"Blocking gap: {g.description}" for g in self.structural_gaps if g.blocking)
        if self.custody_decision: lines.append("Custody: " + self.custody_decision.decision_explanation)
        lines.extend(f"Error: {e}" for e in self.errors)
        return "\n".join(lines)


class UnderstandingEngine:
    def __init__(self, store=None, *, continuity=None, custody=None, recognition=None,
                 mapper=None, decomposition=None, governing=None, mechanisms=None):
        self.store = store or UnderstandingStore()
        self.continuity = continuity or MeaningContinuityValidator()
        self.custody = custody or SemanticCustodyEngine()
        self.updater = UnderstandingUpdater(self.store)
        self.recognition = recognition or ChainRecognitionEngine()
        self.mapper = mapper or ChainRelationshipMapper()
        self.decomposition = decomposition or DecompositionEngine()
        self.governing = governing or GoverningEngine()
        self.mechanisms = mechanisms or MechanismDerivationEngine()

    def receive_rp_outcome(self, outcome):
        """Keep the external reality result separate from semantic custody states."""
        if not hasattr(self, "_rp_outcomes"): self._rp_outcomes = []
        self._rp_outcomes.append(copy.deepcopy(outcome))

    def adopt_learning(self, manager, operator, thread, request, approval):
        """Append approved bounded experience through the existing custody owner."""
        from system_layer.contracts import authorize
        from learning.contracts import digest as learning_digest
        import json
        if set(request) != {'learning_id', 'learning_hash', 'scope', 'conditions', 'expected_version', 'thread_id'}:
            raise ValueError('Exact Learning adoption fields required')
        if request['thread_id'] != thread:
            raise PermissionError('Learning adoption thread mismatch')
        authorize(operator, 'LEARNING_UNDERSTANDING_UPDATE', request, approval)
        source = manager.understanding_candidate(operator, request['learning_id'],
            request['learning_hash'], request['scope'], request['conditions'])
        scope = request['scope']
        subject = 'governed-learning:' + learning_digest(scope)
        before = self.store.find_by_subject(operator, thread, scope['project'], subject, 'RUNTIME')
        if before and (not before.active or before.semantic_state != S.CONFIRMED or before.review_required):
            raise PermissionError('Existing Understanding lifecycle requires independent reconciliation')
        if type(request['expected_version']) is not int or request['expected_version'] != (before.version if before else 0):
            raise ValueError('Stale Understanding adoption')
        context = copy.deepcopy(before.context if before else {})
        updates = context.setdefault('learning_updates', {})
        prior = updates.get(source['learning_id'])
        if prior and prior['source_hash'] == request['learning_hash']:
            return {'state': 'NO_CHANGE', 'understanding_id': before.understanding_id,
                    'version': before.version, 'execution_authority': False}
        updates[source['learning_id']] = {'source_hash': request['learning_hash'],
            'record': source, 'conditions': copy.deepcopy(request['conditions']),
            'adoption_approval': copy.deepcopy(approval), 'update_cause': 'VALIDATED_LEARNING'}
        context['learning_understanding_contract'] = 'LearningUnderstanding/1'
        meaning = before.canonical_meaning if before else (
            'Governed historical experience within exact scope ' + json.dumps(scope, sort_keys=True) +
            '; measured conditions only; no universal truth or execution authority.')
        refs = tuple(dict.fromkeys((tuple(e.reference for e in before.supporting_evidence) if before else ()) +
                                   tuple(source['evidence']) + (request['learning_hash'], approval['hash'])))
        data = {'subject_id': subject, 'subject_type': 'GOVERNED_LEARNING', 'semantic_domain': 'RUNTIME',
                'meaning': meaning, 'context': context, 'scope': before.scope if before else json.dumps(scope, sort_keys=True),
                'objective': before.operator_objective if before else '', 'source_references': refs,
                'qualifiers': before.qualifiers if before else ('Measured conditions only',),
                'requirements': primitive(before.requirements) if before else [],
                'constraints': before.constraints if before else (), 'invariants': before.invariants if before else (),
                'dependencies': before.dependencies if before else (),
                'temporal_scope': before.temporal_scope if before else '',
                'protected_meaning': before.protected_meaning if before else False}
        evidence = (before.supporting_evidence if before else ()) + (
            Evidence(request['learning_hash'], 'REALITY_VALIDATION', True, 'RUNTIME', normalize_meaning(meaning),
                     verified_at=source['updated_at']),)
        result = self.process(UnderstandingRequest(operator, thread, meaning, project_id=scope['project'],
            interpreted_input=data, evidence=evidence,
            action='EXPAND' if before else 'AUTO',
            authority_context=AuthorityContext(operator, AuthorityLevel.VALIDATED_RUNTIME_EVIDENCE,
                'RUNTIME', authenticated=True, confirmation_reference=approval['hash']),
            runtime_metadata={'learning_adoption_expected_version': request['expected_version']}))
        if result.errors or result.review_required or result.final_understanding is None:
            raise PermissionError('Learning adoption not committed: ' + str(result.errors or result.state))
        return {'state': result.state, 'understanding_id': result.final_understanding.understanding_id,
                'version': result.final_understanding.version, 'execution_authority': False}

    def process(self, request):
        started = time.monotonic()
        if not isinstance(request, UnderstandingRequest):
            raise TypeError("UnderstandingRequest required")
        result = UnderstandingResult(request.request_id, request.operator_id)
        provenance_prior={'state':result.state,'readiness':result.specification_readiness.value}
        provenance_rule='UNAVAILABLE'
        recognized_for_provenance='UNAVAILABLE'
        result.metadata["external_reality_outcomes"] = copy.deepcopy([
            value for value in getattr(self, "_rp_outcomes", [])
            if value.get("request", {}).get("scope", {}).get("operator_id") == request.operator_id
            and value.get("request", {}).get("scope", {}).get("thread_id") == request.thread_id])
        try:
            request = copy.deepcopy(request)
            if not request.operator_id.strip() or not request.thread_id.strip() or not request.current_input.strip():
                raise ValueError("operator, thread and source input required")
            observation = request.runtime_observation
            if observation is not None:
                if observation.operator_id != request.operator_id or observation.thread_id != request.thread_id:
                    raise ValueError("observation operator/thread boundary mismatch")
                result.observation_id = observation.observation_id
            result.stages.append("request_received")
            if normalize_meaning(request.current_input) in {"hello", "hi", "thanks", "thank you"} and not (
                    request.interpreted_input or request.authoritative_document_context):
                result.state = "NO_RELEVANT_UNDERSTANDING"
                result.stages.extend(["relevance_determined", "result_returned"])
                return result
            data, recognized = self._interpret(request)
            recognized_for_provenance=recognized
            system = bool(data.get("relationships") or data.get("system_request"))
            result.modes = (["SYSTEM", "REQUIREMENT"] if system else ["SEMANTIC_UPDATE"])
            if request.authoritative_document_context: result.modes.append("DOCUMENT")
            if observation: result.modes.append("OBSERVATION")
            if data.get("failure_candidate"): result.modes.append("FAILURE_LEARNING_CANDIDATE")
            result.stages.extend(["mode_determined", "relevance_determined"])
            if not recognized:
                provenance_rule='if not recognized: state=CLARIFICATION_REQUIRED; review_required=True; specification_readiness=CLARIFICATION_REQUIRED; return without semantic write'
                result.state = "CLARIFICATION_REQUIRED"
                result.review_required = True
                result.specification_readiness = SpecificationReadiness.CLARIFICATION_REQUIRED
                result.warnings.append("No justified semantic structure extracted. Supply a source-linked interpretation; no record written.")
                return result
            authority = request.authority_context or AuthorityContext("unverified", AuthorityLevel.UNVERIFIED_INPUT, "OPERATOR")
            refs = tuple(data.get("source_references", ())) or ((result.observation_id,) if result.observation_id else (request.request_id,))
            requirements = self._requirements(data, refs)
            result.requirement_state = {
                "operator_objective": data.get("objective", request.operator_objective or data["meaning"]),
                "requirements": [primitive(r) for r in requirements if r.kind != "PREFERENCE"],
                "preferences": [primitive(r) for r in requirements if r.kind == "PREFERENCE"],
                "constraints": list(data.get("constraints", ())), "invariants": list(data.get("invariants", ())),
                "dependencies": list(data.get("dependencies", ())), "actors": list(data.get("actors", ())),
                "components": list(data.get("components", ())), "prohibited_states": list(data.get("prohibited_states", ())),
                "completion_conditions": list(data.get("completion_conditions", ())),
                "missing_requirements": list(data.get("missing_requirements", ())),
                "conflicts": list(data.get("conflicts", ())),
                "authority_dependencies": list(data.get("authority_requirements", ())),
                "evidence_requirements": list(data.get("evidence_requirements", ())),
            }
            result.stages.extend(["candidate_extracted", "requirements_resolved"])
            subject = data["subject_id"]
            domain = data.get("semantic_domain", "OPERATOR")
            existing = self.store.find_by_subject(request.operator_id, request.thread_id, request.project_id, subject, domain)
            if ('learning_adoption_expected_version' in request.runtime_metadata and
                    request.runtime_metadata['learning_adoption_expected_version'] != (existing.version if existing else 0)):
                raise ValueError('Learning adoption head changed during evaluation')
            if data.get('_source_bound_amendment') and data['_expected_declaration_version'] != (existing.version if existing else 0):
                raise ValueError('Declaration head changed during interpretation')
            result.existing_understanding = existing
            result.final_understanding = existing
            result.stages.append("existing_understanding_located")
            meaning = data["meaning"]
            evidence = tuple(request.evidence)
            # A direct authenticated statement is evidence of the operator's declared
            # intent/preference, not evidence that an external capability exists.
            if (data.get("direct_operator_declaration") and authority.authenticated
                    and authority.domain == "OPERATOR" and authority.holder == request.operator_id
                    and authority.level in {AuthorityLevel.DIRECT_OPERATOR_STATEMENT, AuthorityLevel.AUTHORIZED_OPERATOR}):
                evidence += (Evidence(refs[0], "OPERATOR_STATEMENT", True, "OPERATOR", normalize_meaning(meaning),
                                      result.observation_id, verified_at=utc_now()),)
            valid = any(e.validated and e.domain == domain and e.claim == normalize_meaning(meaning)
                        and e.source_type in self.custody.policy.qualifying_source_types for e in evidence)
            owner = self.custody.policy.rank(domain, authority.level.value) >= 3
            state = S.CONFIRMED if valid and owner and authority.authenticated else S.PROVISIONAL if evidence else S.PENDING_VALIDATION
            observations = (result.observation_id,) if result.observation_id else ()
            candidate = UnderstandingRecord(
                existing.understanding_id if existing else stable_id("understanding", request.operator_id, request.thread_id, request.project_id, subject, domain),
                request.operator_id, request.thread_id, request.project_id, subject, data.get("subject_type", "PROJECT_FACT"),
                domain, meaning, normalize_meaning(meaning), meaning_summary=data.get("summary", meaning),
                qualifiers=tuple(data.get("qualifiers", ())), scope=data.get("scope", ""), context=data.get("context", {}),
                temporal_scope=data.get("temporal_scope", ""), operator_objective=result.requirement_state["operator_objective"],
                requirements=requirements, constraints=tuple(data.get("constraints", ())), invariants=tuple(data.get("invariants", ())),
                dependencies=tuple(data.get("dependencies", ())), semantic_state=state, confidence=0.8 if valid else 0.3,
                validation_status="SUPPORTED_DECLARATION" if state == S.CONFIRMED else "PENDING",
                custody_holder=authority.holder, authority_level=authority.level.value,
                source_observation_ids=observations, supporting_evidence=evidence,
                source_types=tuple(sorted({e.source_type for e in evidence})), last_verified_at=utc_now() if valid else None,
                created_by=authority.holder, protected_meaning=bool(data.get("protected_meaning", False)),
                metadata={"claim": data.get("claim", {}), "source_input": request.current_input,
                          "failure_candidate": bool(data.get("failure_candidate")), "capability_proven": False})
            if existing and 'learning_adoption_expected_version' in request.runtime_metadata:
                candidate = replace(candidate, contradicting_evidence=existing.contradicting_evidence,
                    source_observation_ids=existing.source_observation_ids,
                    metadata={**candidate.metadata, **existing.metadata, 'capability_proven': False})
            if request.action == "ROLLBACK":
                if existing is None or request.rollback_version is None or existing.semantic_state != S.ROLLBACK_REQUIRED:
                    raise ValueError("rollback requires current ROLLBACK_REQUIRED state and an explicit prior version")
                prior = self.store.get(request.operator_id, existing.understanding_id, request.rollback_version)
                if prior is None or prior.version >= existing.version:
                    raise ValueError("invalid rollback version")
                candidate = replace(prior, metadata={**prior.metadata, "rollback_from": existing.version,
                                                      "rollback_to": prior.version})
            elif request.action == "MARK_PROVISIONAL":
                if existing is None: raise ValueError("downgrade requires existing understanding")
                candidate = replace(existing, semantic_state=S.PROVISIONAL, confidence=min(existing.confidence, 0.3), validation_status="UNPROVEN")
            elif request.action in {"ARCHIVE", "DISPUTE", "CONTRADICT", "SUPERSEDE", "ROLLBACK_REQUIRED"}:
                if existing is None: raise ValueError("lifecycle action requires existing understanding")
                target = {"ARCHIVE": S.ARCHIVED, "DISPUTE": S.DISPUTED, "CONTRADICT": S.CONTRADICTED,
                          "SUPERSEDE": S.SUPERSEDED, "ROLLBACK_REQUIRED": S.ROLLBACK_REQUIRED}[request.action]
                candidate = replace(existing, semantic_state=target, active=target not in {S.ARCHIVED, S.SUPERSEDED},
                    contradicting_evidence=existing.contradicting_evidence + evidence,
                    superseded_by_id=data.get("superseded_by_id") if target == S.SUPERSEDED else existing.superseded_by_id)
                if target == S.SUPERSEDED and not candidate.superseded_by_id:
                    raise ValueError("supersession requires replacement understanding reference")
                if target == S.SUPERSEDED:
                    replacement = self.store.get(request.operator_id, candidate.superseded_by_id)
                    if (replacement is None or replacement.understanding_id == existing.understanding_id
                            or replacement.thread_id != request.thread_id or replacement.project_id != request.project_id
                            or replacement.semantic_domain != domain or not replacement.active):
                        raise ValueError("supersession replacement must exist within the same custody boundary")
            result.candidate_understanding = candidate
            continuity = self.continuity.validate(existing, candidate)
            if data.get('_source_bound_amendment'):
                # The delta resolver has verified exact operator spans, target
                # lineage and expected version; this is a declaration update,
                # never validation of an external proposition. Keep drift and
                # historical versions, but do not mistake an authorized edit
                # for an unexplained model rewrite.
                continuity = replace(continuity, continuity_preserved=True,
                    requires_review=False, contradiction_detected=False,
                    classification='SOURCE_BOUND_AMENDMENT',
                    explanation='Exact operator declaration delta; no external truth or execution authority.')
            result.continuity_result, result.drift_records = continuity, continuity.drift_records
            result.stages.extend(["meaning_continuity_validated", "semantic_drift_recorded"])
            action = "CREATE" if existing is None else "REFINE"
            if request.action == "AUTO" and existing and continuity.classification == "CONTEXTUAL_CHANGE" and not continuity.requires_review:
                # Context-specific correction is additive, never erases the general preference.
                candidate = replace(candidate, canonical_meaning=existing.canonical_meaning,
                    normalized_meaning=existing.normalized_meaning, qualifiers=tuple(dict.fromkeys(existing.qualifiers +
                        (f"{data.get('context', {})}: {meaning}",))),
                    context={**existing.context, **candidate.context},
                    supporting_evidence=existing.supporting_evidence + evidence,
                    metadata={**candidate.metadata, "base_claim": existing.metadata.get("claim", {}), "contextual_claim": data.get("claim", {})})
                action = "EXPAND"
            elif request.action == "AUTO" and existing and continuity.classification == "EQUIVALENT":
                # Verification timestamps do not create new evidence identities.
                combined = {(e.reference, e.claim, e.validated): e for e in existing.supporting_evidence}
                combined.update({(e.reference, e.claim, e.validated): e for e in evidence})
                obs = tuple(dict.fromkeys(existing.source_observation_ids + observations))
                action = "NO_CHANGE" if (set(combined) == {(e.reference, e.claim, e.validated) for e in existing.supporting_evidence}
                                          and obs == existing.source_observation_ids) else "ADD_EVIDENCE"
                proposed_state = candidate.semantic_state
                incoming_requirements = {r.requirement_id: r for r in candidate.requirements}
                merged_requirements = tuple(replace(r, source_references=tuple(dict.fromkeys(r.source_references +
                    incoming_requirements.get(r.requirement_id, r).source_references))) for r in existing.requirements)
                candidate = replace(existing, supporting_evidence=tuple(combined.values()), source_observation_ids=obs,
                                    requirements=merged_requirements)
                if proposed_state == S.CONFIRMED and existing.semantic_state in {S.PENDING_VALIDATION, S.PROVISIONAL}:
                    candidate = replace(candidate, semantic_state=S.CONFIRMED, validation_status="SUPPORTED_DECLARATION",
                        authority_level=authority.level.value, custody_holder=authority.holder, confidence=0.8,
                        last_verified_at=utc_now())
                    action = "CONFIRM"
            if request.action != "AUTO":
                action = "MARK_PROVISIONAL" if request.action == "ROLLBACK_REQUIRED" else request.action
            transition = SemanticTransition(candidate.understanding_id, request.operator_id,
                existing.semantic_state if existing else S.PENDING_VALIDATION, candidate.semantic_state,
                existing.canonical_meaning if existing else "", candidate.canonical_meaning,
                f"Source-linked {action}", action, existing.version if existing else 0,
                authority.level.value, authority.holder, observations, tuple(e.reference for e in evidence),
                existing.confidence if existing else 0, candidate.confidence, created_at=utc_now())
            result.transition, result.action = transition, action
            result.stages.append("transition_proposed")
            decision = self.custody.evaluate(candidate, existing, transition, continuity, authority)
            result.custody_decision = decision
            result.stages.append("custody_evaluated")
            if not decision.permitted:
                self.store.record_review(candidate, decision, transition, continuity)
                result.state = decision.decision.value
                result.review_required = True
                result.specification_readiness = (SpecificationReadiness.CONFLICTED if continuity.requires_review
                                                   else SpecificationReadiness.UNPROVEN)
                return result
            self.updater.prepare(existing, candidate, decision, transition)
            result.stages.append("approved_update_prepared")
            relationships = self._relationships(request, data, requirements, refs)
            result.system_relationships = relationships
            result.stages.append("system_relationships_mapped")
            recognition = self.recognition.recognize(relationships, candidate.operator_objective, data.get("required_chain_types", ()))
            result.chain_recognition_result = recognition
            result.stages.append("chains_recognized")
            mapping = self.mapper.map(recognition, relationships)
            result.chain_relationship_map = mapping
            result.stages.append("chain_relationships_mapped")
            decomposition = self.decomposition.decompose(subject, relationships, data.get("composition", {}))
            result.decomposition_result = decomposition
            result.stages.append("structure_decomposed")
            principles = self.governing.evaluate(decomposition, recognition, relationships, data.get("recurrence_evidence", ()))
            result.governing_principle_result = principles
            result.stages.append("governing_principles_evaluated")
            mechanisms = self.mechanisms.derive(relationships, recognition, decomposition, request.existing_mechanisms, principles)
            result.mechanism_derivation_result = mechanisms
            recognition = self.recognition.reconcile_evidence(recognition, mechanisms)
            result.chain_recognition_result = recognition
            result.stages.append("mechanisms_derived")
            gaps = list(mechanisms.structural_gaps)
            def gap(kind, description):
                gaps.append(StructuralGap(stable_id("gap", subject, kind, description), kind, description, refs))
            if system:
                if not relationships: gap("MISSING_RELATIONSHIPS", "System relationships have not been established.")
                if not result.requirement_state["actors"]: gap("UNRESOLVED_IDENTITY", "System actors have not been identified.")
                if not result.requirement_state["components"]: gap("MISSING_COMPONENT_STRUCTURE", "System components have not been identified.")
                if decomposition.irreducibility_status.value == "CONFLICTED": gap("DECOMPOSITION_CONFLICT", decomposition.stopping_reason)
                mapped = {rid for edge in relationships for rid in edge.governing_requirement_ids}
                for req in requirements:
                    if req.kind in {"REQUIREMENT", "DERIVED", "INVARIANT", "CONSTRAINT"} and req.requirement_id not in mapped:
                        gap("UNMAPPED_REQUIREMENT", req.text)
                if not result.requirement_state["completion_conditions"]: gap("UNVERIFIABLE_COMPLETION", "Explicit completion conditions required.")
                for question in recognition.unresolved_questions: gap("MISSING_CHAIN", question)
                for conflict in mapping.unresolved_conflicts: gap("CHAIN_CONFLICT", conflict)
                for missing in result.requirement_state["missing_requirements"]: gap("MISSING_REQUIREMENT", missing)
                for conflict in result.requirement_state["conflicts"]: gap("CONTRADICTORY_REQUIREMENT", conflict)
                for chain in recognition.chain_records:
                    if chain.broken_transitions:
                        gap("BROKEN_TRANSITION", f"{chain.chain_type.value}: {chain.broken_transitions}")
            result.structural_gaps = tuple(gaps)
            result.stages.append("structural_gaps_detected")
            result.specification_readiness = self.evaluate_specification_readiness(result, candidate, system)
            result.stages.append("specification_readiness_determined")
            analysis_hash = digest({"requirements": result.requirement_state, "relationships": relationships,
                                    "chains": recognition, "chain_map": mapping, "decomposition": decomposition,
                                    "principles": principles, "mechanisms": mechanisms,
                                    "readiness": result.specification_readiness})
            if action == "NO_CHANGE" and existing.metadata.get("analysis_hash") != analysis_hash:
                action = "ADD_EVIDENCE"
                transition = replace(transition, action=action, reason="Structural evidence/readiness changed; meaning preserved")
                result.transition, result.action = transition, action
            if action != "NO_CHANGE":
                candidate = replace(candidate, system_relationship_ids=tuple(e.relationship_id for e in relationships),
                    chain_ids=tuple(c.chain_id for c in recognition.chain_records), decomposition_result_ids=(decomposition.decomposition_id,),
                    governing_principle_ids=tuple(p.principle_id for p in principles.candidate_principles),
                    mechanism_requirement_ids=tuple(m.mechanism_id for m in mechanisms.mechanism_requirements),
                    structural_gap_ids=tuple(g.gap_id for g in gaps),
                    metadata={**candidate.metadata, "analysis_hash": analysis_hash})
                decision = self.custody.evaluate(candidate, existing, transition, continuity, authority)
                if not decision.permitted: raise ValueError("final custody binding rejected")
            result.candidate_understanding, result.custody_decision = candidate, decision
            bundle = {"request_id": request.request_id, "observation_id": result.observation_id,
                      "requirements": result.requirement_state, "relationships": relationships, "chains": recognition,
                      "chain_map": mapping, "decomposition": decomposition, "principles": principles,
                      "mechanisms": mechanisms, "gaps": gaps, "continuity": continuity,
                      "drift": result.drift_records, "readiness": result.specification_readiness,
                      "source_input": request.current_input, "source_references": refs}
            update = self.updater.apply(existing, candidate, decision, transition, bundle)
            result.update_result, result.final_understanding = update, update.updated_record
            result.state = update.updated_record.semantic_state.value
            result.review_required = decision.review_required
            result.stages.extend(["governed_result_committed", "result_returned"])
            result.metadata = {**result.metadata, "capability_proven": False, "execution_authority": False,
                               "structural_fingerprint": structural_digest({"requirements": requirements, "relationships": relationships,
                                    "chains": recognition, "mechanisms": mechanisms}),
                               "source_observation_ids": list(observations)}
        except Exception as exc:
            result.errors.append({"type": type(exc).__name__, "message": str(exc),
                                  "after_stage": result.stages[-1] if result.stages else "receive"})
            result.state = "FAILED"
            result.final_understanding = result.existing_understanding
            result.review_required = True
            result.specification_readiness = SpecificationReadiness.UNPROVEN
            result.retry_information = {"request_id": request.request_id, "observation_id": result.observation_id,
                "expected_version": result.existing_understanding.version if result.existing_understanding else 0,
                "action": "REEVALUATE_FROM_SOURCE", "automatic_retry": False}
        finally:
            result.execution_timing = time.monotonic() - started
            from runtime_observation.transformation_provenance import emit, digest as provenance_digest
            emit(component=__name__,stage='UnderstandingEngine.process',prior=provenance_prior,
                event={'kind':'UnderstandingRequest','request_id':request.request_id,'input_hash':provenance_digest(request.current_input)},
                context={'recognized':recognized_for_provenance,'interpreted_input_supplied':bool(request.interpreted_input),
                    'document_context_supplied':bool(request.authoritative_document_context),
                    'controller_values_received':request.runtime_metadata.get('interpreted_intent',{}),
                    'stages':list(result.stages)},rules=provenance_rule,
                transformation='initialize_and_evaluate_separate_UnderstandingResult',
                result={'state':result.state,'readiness':result.specification_readiness.value,'review_required':result.review_required,
                        'warnings':list(result.warnings),'errors':list(result.errors)},
                reason=list(result.warnings) if result.warnings else 'UNAVAILABLE',
                consumers=['interactive_mode_ai.ModeRuntime._understand_observation'],
                correlation={'understanding_request_id':request.request_id,'observation_id':result.observation_id or 'UNAVAILABLE'})
        return result

    def evaluate_specification_readiness(self, result, candidate, system=True):
        if result.errors: return SpecificationReadiness.UNPROVEN
        if result.requirement_state.get("conflicts") or result.chain_relationship_map.unresolved_conflicts:
            return SpecificationReadiness.CONFLICTED
        if any(g.blocking for g in result.structural_gaps): return SpecificationReadiness.STRUCTURALLY_INCOMPLETE
        if not system or candidate.semantic_state != S.CONFIRMED: return SpecificationReadiness.UNPROVEN
        if result.governing_principle_result.candidate_principles:
            return SpecificationReadiness.READY_WITH_PROVISIONAL_ITEMS
        return SpecificationReadiness.READY_FOR_SPECIFICATION

    def _requirements(self, data, refs):
        result = []
        for item in data.get("requirements", []):
            if isinstance(item, str): item = {"text": item}
            if not isinstance(item, dict) or set(item) - {"requirement_id", "text", "kind", "source_references", "justification", "completion_condition", "prohibited_states"}:
                raise ValueError("unsupported requirement fields")
            result.append(Requirement(item.get("requirement_id") or stable_id("req", normalize_meaning(item["text"]), item.get("kind", "REQUIREMENT")),
                item["text"], item.get("kind", "REQUIREMENT"), tuple(item.get("source_references", refs)),
                item.get("justification", ""), item.get("completion_condition", ""), tuple(item.get("prohibited_states", ()))))
        return tuple(result)

    def _relationships(self, request, data, requirements, refs):
        edges = []
        ids = {r.requirement_id for r in requirements if r.kind != "PREFERENCE"}
        for item in data.get("relationships", []):
            if not isinstance(item, dict) or set(item) - {"source", "target", "type", "requirement_ids", "source_references",
                "constraints", "invariants", "authority_requirements", "evidence_requirements", "failure_condition", "metadata"}:
                raise ValueError("unsupported relationship fields")
            reqs = tuple(item.get("requirement_ids", sorted(ids)))
            if not reqs or not set(reqs) <= ids: raise ValueError("relationship has missing/unknown requirement or uses preference as authority")
            edge = SystemRelationship.create(request.operator_id, request.project_id, data["subject_id"],
                item["source"], item["target"], item["type"], reqs, item.get("source_references", refs),
                constraints=tuple(item.get("constraints", data.get("constraints", ()))),
                invariants=tuple(item.get("invariants", data.get("invariants", ()))),
                authority_requirements=tuple(item.get("authority_requirements", data.get("authority_requirements", ()))),
                evidence_requirements=tuple(item.get("evidence_requirements", data.get("evidence_requirements", ()))),
                failure_condition=item.get("failure_condition", ""), metadata=item.get("metadata", {}))
            edges.append(edge)
        if len({e.relationship_id for e in edges}) != len(edges): raise ValueError("duplicate relationship identity")
        return tuple(sorted(edges, key=lambda e: e.relationship_id))

    def _interpret(self, request):
        """Bounded first-pass grammar plus explicit interpreted/document contracts.

        Unrecognized prose is not a semantic fact. A richer interpreter can supply
        the existing request contract without bypassing downstream custody.
        """
        if request.declaration_delta:
            from .declaration_delta import apply_delta
            authority = request.authority_context
            if (request.interpreted_input or request.authoritative_document_context or not authority
                    or not authority.authenticated or authority.holder != request.operator_id
                    or authority.domain != 'OPERATOR' or authority.level not in {
                        AuthorityLevel.DIRECT_OPERATOR_STATEMENT, AuthorityLevel.AUTHORIZED_OPERATOR}):
                raise ValueError('Declaration delta requires authenticated operator custody and one input contract')
            subject = request.declaration_delta.get('subject_id')
            existing = self.store.find_by_subject(request.operator_id,request.thread_id,request.project_id,subject,'OPERATOR')
            reference = request.runtime_metadata.get('operator_source_reference')
            resolved = apply_delta(existing,request.declaration_delta,text=request.current_input,source_reference=reference)
            prior_context=copy.deepcopy(existing.context) if existing else {}
            prior_constraint_quotes={d['quote'] for d in prior_context.get('declarations',[]) if d['kind']=='CONSTRAINT'}
            constraints=[v for v in (existing.constraints if existing else ()) if v not in prior_constraint_quotes]
            constraints+= [d['quote'] for d in resolved['declarations'] if d['kind']=='CONSTRAINT']
            return {'subject_id':subject,'subject_type':'OPERATOR_DECLARATIONS','semantic_domain':'OPERATOR',
                'meaning':resolved['meaning'],'scope':'Declared meaning in this operator thread; not external truth',
                'objective':existing.operator_objective if existing else request.operator_objective or resolved['meaning'],
                'constraints':list(dict.fromkeys(constraints)),
                'invariants':list(existing.invariants) if existing else [],
                'dependencies':list(existing.dependencies) if existing else [],
                'qualifiers':list(existing.qualifiers) if existing else [],
                'protected_meaning':existing.protected_meaning if existing else False,
                'source_references':list(dict.fromkeys([reference]+[r for item in resolved['declarations'] for r in item['source_references']])),
                'context':{**prior_context,'declaration_contract':resolved['contract'],'declarations':resolved['declarations'],
                           'amendments':resolved['amendments']},
                'requirements':[{'text':item['quote'],'source_references':item['source_references']}
                                for item in resolved['declarations'] if item['kind'] in {'REQUIREMENT','CONSTRAINT'}],
                'direct_operator_declaration':True,'_source_bound_amendment':True,
                '_expected_declaration_version':resolved['expected_version']}, True
        if request.interpreted_input and request.authoritative_document_context:
            document = request.authoritative_document_context
            if request.interpreted_input != document.get("interpretation"):
                raise ValueError("document and interpretation disagree; clarification required")
        data = copy.deepcopy(request.interpreted_input)
        if request.authoritative_document_context:
            document = request.authoritative_document_context
            if not document.get("source_reference") or not isinstance(document.get("interpretation"), dict):
                raise ValueError("document input requires source_reference and structured interpretation")
            data = copy.deepcopy(document["interpretation"])
            data.setdefault("source_references", [document["source_reference"]])
        if data:
            supported = {"subject_id", "subject_type", "semantic_domain", "meaning", "summary", "objective", "claim",
                "source_references", "qualifiers", "scope", "context", "temporal_scope", "requirements", "constraints",
                "invariants", "dependencies", "actors", "components", "prohibited_states", "completion_conditions",
                "missing_requirements", "conflicts", "authority_requirements", "evidence_requirements", "relationships",
                "composition", "required_chain_types", "recurrence_evidence", "protected_meaning", "system_request",
                "failure_candidate", "superseded_by_id", "direct_operator_declaration"}
            if set(data) - supported:
                raise ValueError(f"unsupported interpretation fields: {sorted(set(data) - supported)}")
            if not data.get("subject_id") or not data.get("meaning"):
                raise ValueError("interpreted input requires subject_id and meaning")
            # Structured interpretation does not itself grant validated evidence.
            data.pop("direct_operator_declaration", None)
            return data, True
        text = request.current_input.strip()
        creator = re.fullmatch(r"I (?:created|built) (?:this|the) runtime[.!]?", text, re.I)
        if creator:
            return {"subject_id": "operator.runtime_creator", "subject_type": "OPERATOR_IDENTITY", "semantic_domain": "OPERATOR",
                    "meaning": "The operator states that they created this runtime.", "claim": {"predicate": "declared_creator", "value": request.operator_id},
                    "direct_operator_declaration": True}, True
        preference = re.fullmatch(r"(?:I prefer|The operator prefers) (.+?)[.]?", text, re.I)
        contextual = re.fullmatch(r"For (.+?), (?:give me|I want) (.+?)[.]?", text, re.I)
        if preference or contextual:
            value = (contextual.group(2) if contextual else preference.group(1)).rstrip(".")
            return {"subject_id": "operator.response_preference", "subject_type": "OPERATOR_PREFERENCE", "semantic_domain": "OPERATOR",
                    "meaning": f"The operator prefers {value}.", "context": {"work": contextual.group(1)} if contextual else {},
                    "claim": {"predicate": "response_preference", "value": normalize_meaning(value)}, "direct_operator_declaration": True}, True
        obligation = re.fullmatch(r"(.+?) must (.+?)(?:,? but I would prefer (.+?)(?: for the first version)?)?[.]?", text, re.I)
        if obligation and not re.search(r"(?:learn from|improve (?:based on|from)) failed executions", text, re.I):
            requirement = obligation.group(2).rstrip(".,")
            requirements = [{"text": requirement}]
            if obligation.group(3): requirements.append({"text": obligation.group(3).rstrip("."), "kind": "PREFERENCE"})
            return {"subject_id": normalize_meaning(obligation.group(1)), "subject_type": "OPERATOR_REQUIREMENT",
                    "meaning": f"{obligation.group(1)} must {requirement}.", "requirements": requirements,
                    "system_request": True, "direct_operator_declaration": True}, True
        adaptation = re.fullmatch(r"(.+?) (?:should|must) (?:learn from|improve (?:based on|from)) failed executions[.]?", text, re.I)
        if adaptation:
            system = normalize_meaning(adaptation.group(1))
            edges = [
                ("execution", "outcome", "PRODUCES"), ("outcome", "failure_observation", "PRODUCES"),
                ("failure_observation", "validated_outcome", "VALIDATES"),
                ("validated_outcome", "failure_classification", "PRODUCES"),
                ("validated_outcome", "adaptation_proposal", "TRIGGERS"),
                ("authority", "adaptation_proposal", "AUTHORIZES"),
                ("prior_state", "accepted_change", "PRESERVES"),
                ("adaptation_proposal", "accepted_change", "TRANSITIONS_TO"),
                ("accepted_change", "prior_state", "TRANSITIONS_TO"),
                ("accepted_change", "replayed_execution", "TRIGGERS"),
                ("replayed_execution", "regression_validation", "VALIDATES"),
                ("regression_validation", "post_change_evidence", "PROVES")]
            return {"subject_id": system + ".failure_adaptation", "subject_type": "OPERATOR_REQUIREMENT",
                "meaning": f"{system} should derive governed adaptation from failed execution outcomes.",
                "objective": "Derive governed adaptation from failed execution outcomes",
                "system_request": True, "direct_operator_declaration": True,
                "requirements": [{"text": "Adapt from failed execution outcomes"}],
                "actors": ["authority"], "components": sorted({node for a, b, _ in edges for node in (a, b) if node != "authority"}),
                "invariants": ["prior valid behavior remains recoverable"],
                "authority_requirements": ["authorized change approval"],
                "evidence_requirements": ["validated outcome evidence"],
                "completion_conditions": ["approved adaptation is re-exercised and validated"],
                "relationships": [{"source": a, "target": b, "type": k,
                    "failure_condition": "unvalidated or unauthorized adaptation", "metadata": {
                        "entity_roles": {"adaptation_proposal": "ADAPTATION_PROPOSAL"},
                        "derivation": "Adaptation requires observed outcome, validation, authorized change, continuity and retest; provisional structural analysis."}}
                    for a, b, k in edges]}, True
        if request.runtime_metadata.get("failure_candidate"):
            return {"subject_id": request.runtime_metadata.get("subject_id", "runtime.failure." + digest(text)[:16]),
                    "subject_type": "FAILURE_PATTERN", "semantic_domain": "RUNTIME", "meaning": text,
                    "scope": "This observation only; no generalization", "failure_candidate": True}, True
        return {}, False
