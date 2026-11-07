"""Bounded execution spine: explicit operator contract, existing engines, no RP decisions.

/build accepts JSON containing request, understanding and authorization. It is
not a document parser. Missing fields return clarification rather than defaults.
"""
from copy import deepcopy
from dataclasses import asdict
from pathlib import Path
import hashlib
import json
import re
import threading
from uuid import uuid4

from core.mode_controller import (normalize_input, detect_input_kind, detect_intent_signals,
    classify_intent, detect_domain, resolve_mode, detect_pressure_state, calculate_ambiguity_score,
    calculate_interpretation_stability, calculate_operator_alignment, evaluate_clarification_state,
    determine_posture)
from models.runtime_models import CanonicalInteractionState
from understanding import UnderstandingRequest, AuthorityContext, AuthorityLevel
from understanding.understanding_record import Evidence, normalize_meaning
from specs.spec_engine import create_specification_object
from specs.spec_engine import REQUIRED_INTERPRETED_BUILD_REQUEST_FIELDS
from specs.spec_snapshot import create_spec_snapshot
from specs.handoff_gate import approve_builder_handoff
from integration.mode_generation import ModeGenerationProvider, GenerationFailure
from integration.strict_json import load_payload


def digest(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode()).hexdigest()


def interpret(text, request_id, thread_id):
    state = CanonicalInteractionState(request_id, thread_id, text)
    state.normalized_input = normalize_input(text)
    state.pressure_state = detect_pressure_state(text, state.normalized_input)
    state.input_kind = detect_input_kind(state.normalized_input)
    state.intent_signals = detect_intent_signals(state.normalized_input)
    state.intent_type = classify_intent(state.input_kind, state.intent_signals)
    state.detected_domain = detect_domain(state.normalized_input)
    state.selected_mode = resolve_mode(state.intent_type, state.detected_domain)
    state.ambiguity_score, state.ambiguity_contributors, state.ambiguity_profile = calculate_ambiguity_score(state)
    state.interpretation_stability_score = calculate_interpretation_stability(state)
    state.operator_alignment_score = calculate_operator_alignment(state)
    evaluate_clarification_state(state)
    state.selected_posture = determine_posture(state)
    return state


class BuildRuntime:
    def __init__(self, runtime, provider=None, builder=None):
        self.runtime = runtime
        self.provider = provider or ModeGenerationProvider()
        self.builder = builder
        self._lock = threading.Lock()
        self._used = set()

    def route(self, text):
        if text.startswith('/build clarify '):
            pending = getattr(self.runtime.context, 'build_clarification', None)
            if not pending or pending['thread_id'] != self.runtime.context.active_thread.thread_id:
                return self._clarify(text, {}, ['No build clarification is active in this thread.'])
            try:
                patch = load_payload(text[len('/build clarify '):])
                if not isinstance(patch, dict) or set(patch) - {'request', 'understanding', 'authorization'}:
                    raise ValueError('Clarification must contain request, understanding or authorization fields')
                envelope = deepcopy(pending['envelope'])
                for key, value in patch.items():
                    if not isinstance(value, dict):
                        raise ValueError('Clarification sections must be objects')
                    envelope.setdefault(key, {}).update(value)
                return self._route_envelope(envelope, pending['operator_input'])
            except (ValueError, TypeError) as exc:
                return self._clarify(pending['operator_input'], pending['envelope'], [str(exc)])
        if text.startswith("/build "):
            try:
                return self._route_envelope(load_payload(text[7:]), text)
            except (ValueError, TypeError) as exc:
                result = {"state": "SPECIFICATION_NOT_READY", "reasons": [str(exc)],
                          "request_id": 'rejected:' + uuid4().hex, "observation_ids": []}
                self._publish_rejection(result)
                return result
        # Imperative construction without the required contract requests detail.
        if re.match(r"^(?:please\s+)?(?:build|implement|construct|create)\b", text.strip(), re.I):
            routing = interpret(text, "build-routing", self.runtime.context.active_thread.thread_id)
            if routing.detected_domain == "creative" or routing.intent_type != "build":
                return None
            return self._clarify(text, {}, [
                'What exact behavior should the artifact provide, where should its files be created or modified, and what checks will demonstrate completion?'])
        return None

    def _route_envelope(self, envelope, original):
        if not isinstance(envelope, dict):
            raise ValueError('Build request must be an object')
        missing = []
        for section in ('request', 'understanding', 'authorization'):
            if not isinstance(envelope.get(section), dict):
                missing.append(section)
        request = envelope.get('request', {})
        if isinstance(request, dict):
            required = set(REQUIRED_INTERPRETED_BUILD_REQUEST_FIELDS) | {
                'operator_input', 'artifact_structure', 'execution', 'validation', 'evidence',
                'completion', 'authority_state', 'validation_state', 'readiness_state',
                'save_ready_state', 'clarification_required'}
            missing.extend('request.' + name for name in sorted(required - request.keys()))
        if missing:
            return self._clarify(original, envelope, ['Missing explicit build fields: ' + ', '.join(missing)], missing)
        result = self.execute(envelope)
        if result['state'] != 'SPECIFICATION_NOT_READY':
            self.runtime.context.build_clarification = None
        return result

    def _clarify(self, original, envelope, questions, missing=None):
        """Collect explicit fields without converting conversation into approval.

        Partial amendments use the existing canonical envelope. Its exact hash
        must still be authorized when complete; no approval or evidence is inferred.
        Unrelated subsequent conversation does not answer or execute this draft.
        """
        pending = {'thread_id': self.runtime.context.active_thread.thread_id,
                   'operator_input': original, 'envelope': deepcopy(envelope)}
        self.runtime.context.build_clarification = pending
        from specs.conversation_specification import synchronize_pending, require_current
        if not envelope:
            synchronize_pending(self.runtime)
        current_draft=None
        if pending.get('conversation_specification_reference'):
            current_draft=require_current(self.runtime,pending['conversation_specification_reference'])
        result = {'state': 'SPECIFICATION_NOT_READY', 'clarification_required': True,
                  'request_id': 'clarification:' + uuid4().hex, 'observation_ids': [],
                  'execution_attempted': False, 'reasons': questions,
                  'missing_fields': missing or (current_draft['missing_fields'] if current_draft else ['behavior', 'artifact_target', 'completion_checks']),
                  'resume': '/build clarify with explicit canonical request/understanding/authorization fields',
                  'operator_input': original}
        if current_draft:
            result['specification_candidate']=current_draft
        self._publish_rejection(result)
        return result

    def _publish_rejection(self,result):
        with self._lock:
            self._observation_custody_failed = False
            self._observe(result,result['state'])
            self._publish_result(result)

    def _publish_result(self,result):
        self.runtime.context.build_result=deepcopy(result)
        from interactive_mode_ai import RuntimeState
        state=getattr(self.runtime.context.runtime_state,'value',self.runtime.context.runtime_state)
        if result['state']=='SPECIFICATION_NOT_READY' and state not in {'HALTED','ERROR','BUILDING','VALIDATING'}:
            self.runtime._set_state(RuntimeState.CLARIFYING)

    def execute(self, envelope, *, capability_guard=None):
        with self._lock:
            self._observation_custody_failed = False
            self._active_capability_guard = capability_guard
            try:
                result = self._execute(deepcopy(envelope))
            finally:
                self._active_capability_guard = None
                self.provider.learning_advisory_loader = None
            if not result['observation_ids']:
                self._observe(result, result['state'])
            self._publish_result(result)
            return result

    def _execute(self, envelope):
        runtime = self.runtime
        operator = runtime.context.identity.operator_id
        thread = runtime.context.active_thread.thread_id
        result = {"state": "SPECIFICATION_NOT_READY", "reasons": [], "observation_ids": [],
                  "request_id": 'attempt:' + uuid4().hex, "execution_attempted": False,
                  "attempt_id": 'build-attempt:' + uuid4().hex,
                  "operator_request": deepcopy(envelope) if isinstance(envelope, dict) else {}}
        try:
            if set(envelope) != {"request", "understanding", "authorization"}:
                raise ValueError("Expected request, understanding and authorization")
            request, data, authorization = envelope["request"], envelope["understanding"], envelope["authorization"]
            supported = set(REQUIRED_INTERPRETED_BUILD_REQUEST_FIELDS) | {
                "operator_input", "artifact_structure", "execution", "validation", "evidence", "completion",
                "authority_state", "validation_state", "readiness_state", "save_ready_state", "clarification_required"}
            if set(request) - supported:
                raise ValueError("Unsupported request fields: " + str(sorted(set(request) - supported)))
            missing = supported - set(request)
            if missing:
                raise ValueError("Missing explicit canonical request fields: " + str(sorted(missing)))
            rid = request["request_id"]
            if rid in self._used:
                raise ValueError("Request already attempted; a new explicit authorization is required")
            corrective_authority = authorization.get("corrective")
            base_authorization = {k: v for k, v in authorization.items() if k != "corrective"}
            if base_authorization != {"operator_id": operator, "thread_id": thread, "decision": "APPROVE",
                                 "request_hash": digest({"request": request, "understanding": data})}:
                raise ValueError("Missing or mismatched explicit operator authorization")
            data=deepcopy(data)
            declared_reference=data.pop('conversation_specification_reference',None)
            if declared_reference is not None:
                from specs.conversation_specification import require_current
                declared=require_current(runtime,declared_reference)
                supplied={item.get('text') for item in data.get('requirements',[]) if isinstance(item,dict)}
                if not {item['quote'] for item in declared['requirement_inventory']} <= supplied:
                    raise ValueError('Current conversation requirements lost before Builder handoff')
            self._execution_allowed()
            state = interpret(request["operator_input"], rid, thread)
            result["interpretation"] = state.to_dict()
            if (state.intent_type != "build" or state.selected_mode != "Development" or state.halt_required
                    or state.clarification_required):
                raise ValueError("Build intent, ambiguity or clarification gate blocked execution")
            state.downstream_authority_allowed = True
            result["interpretation"] = state.to_dict()
            if (not request["artifact_structure"]["files"] or not request["validation"]["commands"]
                    or not request["validation"]["requirements"]):
                raise ValueError("Explicit artifact files and executable validation required")
            if request["artifact_structure"].get("approved_files"):
                raise ValueError("This Mode generation path requires proposals, not pre-supplied contents")
            for block in ("execution", "validation", "evidence", "completion"):
                if block not in request: raise ValueError(f"Missing {block}")
            if data.get("objective") != request["system_purpose"] or data.get("semantic_domain") != "OPERATOR":
                raise ValueError("Understanding must express the same operator objective")
            if data.get("missing_requirements") or data.get("conflicts"):
                raise ValueError("Unresolved operator requirements")
            from mode_operator.operator_requirement_engine import OperatorRequirementEngine
            from mode_operator.operator_requirement_models import OperatorRequirementDomain
            from mode_operator.operator_profile import OperatorProfile
            # Exact fields supplied by the operator satisfy session requirements;
            # this path neither reads nor creates persistent personal records.
            requirements = OperatorRequirementEngine(None).evaluate(
                operator_profile=getattr(runtime.context, "profile", OperatorProfile(operator)),
                thread_id=thread, input_text=request["operator_input"], domain=OperatorRequirementDomain.ENGINEERING,
                session_answers={"system_type": request["tool_type"],
                                 "constraints": json.dumps(request["governance_constraints"]),
                                 "environment": request["runtime_target"]}, persistent_memories=[])
            result["operator_requirements"] = requirements.to_dict()
            if not requirements.can_continue():
                raise ValueError("Missing operator requirements: " + str(requirements.missing_required_fields()))
            understanding = runtime.understanding_engine.process(UnderstandingRequest(
                operator, thread, request["operator_input"], request_id=rid,
                interpreted_input=data, operator_objective=request["system_purpose"],
                authority_context=AuthorityContext(operator, AuthorityLevel.AUTHORIZED_OPERATOR, "OPERATOR", authenticated=True),
                evidence=(Evidence("operator-request:" + digest(envelope), "OPERATOR_STATEMENT", True,
                                   "OPERATOR", normalize_meaning(data["meaning"])),)))
            result['understanding_attempt'] = understanding.to_dict()
            governed = understanding.specification_handoff()
            result["understanding"] = governed
            canonical = deepcopy(request)
            del canonical["operator_input"]
            specification = create_specification_object(canonical)
            specification["metadata"]["governed_understanding"] = governed
            specification["metadata"]["operator_authorization"] = authorization
            # Preserve structural requirements without reconstructing them from file names.
            specification["structure"]["understanding_requirements"] = deepcopy(understanding.requirement_state)
            specification["structure"]["system_relationships"] = governed["result"]["system_relationships"]
            specification["structure"]["mechanism_requirements"] = governed["result"]["mechanism_derivation_result"]
            handoff = approve_builder_handoff(specification, create_spec_snapshot(specification))
            result["specification"] = specification
            root = Path(request["execution"]["repository_target"])
            from builder.service import preflight, ConstructionBlocked
            try:
                prepared = preflight(handoff, str(root))
            except (ConstructionBlocked, ImportError):
                result["state"] = "CONSTRUCTION_BLOCKED"
                raise
            result['kernel_cutover_preparation'] = prepared['kernel_cutover_preparation']
            existing = prepared['existing_files']
            self.provider.learning_advisory_loader = None
            selection = getattr(runtime, '_build_learning_scope', None)
            runtime._build_learning_scope = None
            if selection is not None:
                scope = {'operator_id': operator, 'project': str(root), 'domain': data['semantic_domain'],
                         'capability': request['system_purpose']}
                if selection != (thread, scope):
                    raise PermissionError('Selected Learning scope does not match governed build')
                from learning.runtime import prompt_advisory
                self.provider.learning_advisory_loader = lambda: prompt_advisory(runtime, selection=selection)
        except Exception as exc:
            result["reasons"].append(str(exc))
            return result

        self._used.add(rid)
        self.provider.generated = []
        result["request_id"] = rid
        result["request_hash"] = digest(envelope)
        result["operator_request"] = deepcopy(envelope)
        self._observe(result, "BUILD_ELIGIBLE")
        if self._observation_custody_failed:
            return result
        result['claim_binding'] = digest({'request_hash': result['request_hash'], 'specification_hash': digest(specification)})
        result['attempts'] = []
        corrective_analysis = None
        for attempt_number in (1, 2):
            if attempt_number == 2:
                result['attempt_id'] = 'build-attempt:' + uuid4().hex
            try:
                self._execution_allowed()
                from builder.service import execute as construct, snapshot_evidence
                result['execution_attempted'] = True
                self.provider.generated = []
                output = (self.builder or construct)(deepcopy(handoff), str(root), code_generation_provider=self.provider,
                    repository_context=deepcopy({'specification': specification, 'existing_files': existing,
                                                 'corrective_analysis': corrective_analysis}),
                    execution_guard=self._execution_allowed,
                    kernel_client=getattr(runtime, 'kernel_client', None),
                    require_kernel=getattr(runtime, 'kernel_execution_required', False), stage_observer=self._stage)
                result['build'] = asdict(output)
                result['generated_contents'] = deepcopy(self.provider.generated)
                result['state'] = {'PASS': 'BUILD_PASS_RP_PENDING', 'FAIL': 'BUILD_FAIL',
                    'UNPROVEN': 'BUILD_UNPROVEN'}.get(output.validation_status, 'CONSTRUCTION_BLOCKED')
                retained = snapshot_evidence(result['build'])
                result['attempt_evidence'] = retained
            except Exception as exc:
                result['generated_contents'] = deepcopy(self.provider.generated)
                result.update(state='GENERATION_FAILED' if isinstance(exc, GenerationFailure) else 'CONSTRUCTION_BLOCKED',
                              reasons=[str(exc)])
                self._observe(result, result['state'])
                if attempt_number == 1 or self._observation_custody_failed:
                    return result
                result['attempts'].append({'attempt_number': 2, 'attempt_id': result['attempt_id'],
                    'claim_binding': result['claim_binding'], 'specification_hash': digest(specification),
                    'build': None, 'evidence_snapshots': [], 'execution_status': 'NOT_COMPLETED',
                    'error': str(exc), 'observation_id': result['observation_ids'][-1]})
                break
            self._observe(result, result['state'])
            if self._observation_custody_failed:
                return result
            attempt = {'attempt_number': attempt_number, 'attempt_id': result['attempt_id'],
                'claim_binding': result['claim_binding'], 'specification_hash': digest(specification),
                'build': deepcopy(result['build']), 'evidence_snapshots': retained,
                'execution_status': 'COMPLETED',
                'observation_id': result['observation_ids'][-1],
                'generated_contents': json.loads(json.dumps(self.provider.generated, allow_nan=False))}
            result['attempts'].append(attempt)
            if attempt_number == 2 or output.validation_status != 'FAIL' or corrective_authority is None:
                break
            try:
                from learning.service import LearningService
                from learning.corrective import validate_adjustment
                observation = runtime.runtime_observation_collector.store.load_record(operator, attempt['observation_id'])
                corrective_analysis = LearningService.analyze_corrective_attempt(specification=specification,
                    claim_binding=result['claim_binding'], attempt=attempt, observation=observation.to_dict(),
                    authorization=corrective_authority)
                validate_adjustment(corrective_analysis, specification=specification,
                    claim_binding=result['claim_binding'], authorization=corrective_authority)
                result['corrective_analysis'] = deepcopy(corrective_analysis)
                existing = preflight(handoff, str(root))['existing_files']
            except Exception as exc:
                result['corrective_blocked'] = str(exc)
                break
        # The external preparer constructs canonical RP evaluation data. Mode
        # never creates a trusted evidence batch or a reality decision.
        if self._observation_custody_failed:
            return result
        prepare = getattr(runtime, "prepare_build_reality_request", None)
        if prepare is not None:
            try:
                result['observation_evidence'] = []
                for attempt in result['attempts']:
                    store = runtime.runtime_observation_collector.store
                    record = store.load_record(operator, attempt['observation_id'])
                    result['observation_evidence'].append({'observation_id': record.observation_id,
                        'path': str(store._record_path(operator, record.observation_id).resolve()),
                        'record_hash': digest(record.to_dict())})
                request = prepare(deepcopy(result))
                from interactive_mode_ai import RuntimeState
                runtime._set_state(RuntimeState.INTERPRETING)
                runtime.require_reality_transition(RuntimeState.COMPLETE, request)
                if output.validation_status == "PASS":
                    accepted = runtime._set_state(RuntimeState.COMPLETE)
                else:
                    accepted = False
                    runtime.context.reality_primacy_result = runtime.reality_acceptance_client.evaluate(request)
                    runtime.understanding_engine.receive_rp_outcome(runtime.context.reality_primacy_result)
                result["rp"] = deepcopy(runtime.context.reality_primacy_result)
                rp_state = result["rp"].get("rp_state")
                if output.validation_status == "PASS":
                    if rp_state == "CONFIRMED" and accepted: result["state"] = "BUILD_PASS_RP_CONFIRMED"
                    elif rp_state == "DISCONFIRMED": result["state"] = "BUILD_PASS_RP_DISCONFIRMED"
            except Exception as exc:
                result["reasons"].append("External RP unavailable: " + str(exc))
                result['rp'] = {'accepted': False, 'rp_state': None, 'reason': str(exc)}
            finally:
                # The scoped build gate is consumed; ordinary chat COMPLETE is
                # operational and must not reuse this build's RP authorization.
                getattr(runtime, "_reality_requirements", {}).pop("COMPLETE", None)
        else:
            result["reasons"].append("External RP build evidence preparation is not configured")
            result['rp'] = {'accepted': False, 'rp_state': None,
                            'reason': getattr(runtime, 'rp_readiness', 'NOT_CONFIGURED')}
        self._observe(result, result["state"])
        runtime.context.build_result = deepcopy(result)
        return result

    def _stage(self, name):
        from interactive_mode_ai import RuntimeState
        if name not in {'BUILDING','VALIDATING'}:
            raise ValueError('Unknown Builder runtime stage')
        if not self.runtime._set_state(RuntimeState(name)):
            raise PermissionError('Runtime rejected Builder state transition')

    def _observe(self, result, stage):
        result.setdefault('attempt_id','build-attempt:'+uuid4().hex)
        build = result.get('build', {})
        rp = result.get('rp', {})
        failure = stage in {'BUILD_FAIL', 'GENERATION_FAILED'}
        request = result.get('operator_request', {}).get('request', {})
        if not isinstance(request, dict): request = {}
        understanding = (result.get('understanding', {}).get('result', result.get('understanding_attempt', {}))
                         .get('final_understanding') or {})
        metadata = {"runtime_component": "integration.build_runtime", "affected_runtime_stage": stage,
            "correlation_id": result["request_id"], "interaction_id": result['request_id'],
            "runtime_session_id": getattr(self.runtime,'_observation_session_id',None),
            "attempt_id": result['attempt_id'], "objective_id": build.get('spec_id'),
            "semantic_state_id": understanding.get('understanding_id', ''),
            "execution_attempted": result.get('execution_attempted', False),
            "execution_status": stage, "builder_status": build.get('validation_status'),
            "specification_id": result.get('specification', {}).get('spec_id'), "build_id": build.get('build_id'),
            "rp_request": rp.get('request'), "rp_result": rp.get('rp_state'), "rp_receipt": rp.get('receipt_id'),
            "observed_outcome": deepcopy(result), "completion_claim": stage,
            "executed_components": ['builder.core'] if build else [],
            "execution_path": ['Understanding', 'Specification', 'Generation', 'Builder'] if build else [],
            "output_artifacts": build.get('files_written', []),
            "validation_results": build.get('validation_results', []),
            "produced_receipts": [v for v in [build.get('receipt_path'), rp.get('receipt_id')] if v],
            "validation_references": build.get('evidence_references', []),
            "source_traces": list(result['observation_ids']),
            "unresolved_outcome_evidence": result.get('reasons', []) or ([stage] if stage != 'BUILD_PASS_RP_CONFIRMED' else []),
            "required_evidence_fields": ['correlation_id', 'observed_outcome', 'validation_results', 'produced_receipts']}
        assembled = getattr(self.runtime.context, 'assembled_context', None)
        context_state = assembled.get('runtime', {}) if isinstance(assembled, dict) else getattr(assembled, 'runtime', None)
        readiness = context_state.get('context_ready') if isinstance(context_state, dict) else getattr(context_state, 'context_ready', None)
        if type(readiness) is not bool:
            readiness = None
        record = self.runtime.runtime_observation_collector.collect(
            operator_id=self.runtime.context.identity.operator_id,
            thread_id=self.runtime.context.active_thread.thread_id,
            runtime_state_end=stage, trace_reference=result["request_id"],
            input_text=request.get('operator_input', ''), context_ready=readiness,
            runtime_error='; '.join(result.get('reasons', [])) or stage if failure else None,
            metadata=metadata)
        try:
            persisted = self.runtime.runtime_observation_collector.store.load_record(record.operator_id, record.observation_id)
            if record.collection_errors or persisted is None or digest(persisted.to_dict()) != digest(record.to_dict()):
                raise OSError('Runtime Observation not persisted and retrievable')
        except Exception as exc:
            self._observation_custody_failed = True
            result['reasons'].append('Observation custody failed: '+type(exc).__name__)
            result['state'] = 'CONSTRUCTION_BLOCKED'
            if result.get('build'):
                from builder.core.build_models import BuilderOutputObject
                from runtime_observation.observation_collector import _finalize_observation_custody
                failed = _finalize_observation_custody(BuilderOutputObject(**result['build']), None, 'Runtime observation unavailable')
                result['build'] = asdict(failed)
                result['state'] = 'BUILD_FAIL'
            self.runtime.context.build_result = deepcopy(result)
            return
        result["observation_ids"].append(record.observation_id)
        # Keep the presentation's current attempt authoritative even on early exits.
        self.runtime.context.build_result = deepcopy(result)

    def _execution_allowed(self):
        if getattr(self, '_observation_custody_failed', False):
            raise PermissionError('Observation custody failed; explicit new attempt required')
        if (getattr(self.runtime, '_halt_latch', None)
                or getattr(self.runtime.context.active_thread, 'halt', None)):
            raise PermissionError('Runtime halt remains authoritative')
        system_layer = getattr(self.runtime, 'system_layer', None)
        if system_layer is not None:
            system_layer.require_internal_execution()
        guard = getattr(self, '_active_capability_guard', None)
        if guard is not None:
            guard()
        if getattr(self.runtime.context.runtime_state, "value", None) == "HALTED":
            raise PermissionError("Runtime halted")
        bridge = getattr(self.runtime, "supervisor_bridge", None)
        if bridge is not None:
            from integration.builder_hooks import require_builder_active
            from supervisor_bridge.builder_adapter import BuilderAdapter
            require_builder_active(BuilderAdapter(bridge), self.runtime.supervisor_task_id)
