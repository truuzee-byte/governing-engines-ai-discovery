"""
Reasoning Agent v3

Preserves the existing draft -> critique -> revision workflow while adding
bounded provider-request telemetry for economic/runtime measurement.

Instrumentation is observational:
- no prompt changes
- no model-routing changes
- no retry changes
- no cost calculation
- provider usage is preserved as reported by the provider
"""

from __future__ import annotations

import os
import time
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Optional

from dotenv import load_dotenv
from openai import OpenAI

from core.utils import load_json_file
from runtime_economics.economic_telemetry_store import EconomicTelemetryStore
from runtime_economics.provider_request_telemetry import (
    ProviderRequestTelemetry,
)


@dataclass
class ModelCallResult:
    output_text: str
    telemetry: ProviderRequestTelemetry
    telemetry_evidence_reference: Optional[str] = None
    telemetry_persistence_error: Optional[str] = None


@dataclass
class ReasoningResult:
    reasoning_id: str
    provider: str
    model: str
    draft: str
    critique: str
    final_response: str
    execution_time_seconds: float
    provider_requests: list[ProviderRequestTelemetry] = field(default_factory=list)
    telemetry_evidence_references: list[str] = field(default_factory=list)
    telemetry_persistence_errors: list[str] = field(default_factory=list)
    context_admission: list[dict] = field(default_factory=list)
    raw_final_response: str = ""
    context_validation_requests: list[dict] = field(default_factory=list)


class ReasoningAgent:

    def __init__(
        self,
        config_path: str = "data/model_config.json",
        telemetry_store: Optional[EconomicTelemetryStore] = None,
    ) -> None:

        load_dotenv()

        self.config = load_json_file(config_path)

        self.provider = self.config.get("provider", "openai")
        self.model = self.config.get("model", "gpt-4.1-mini")
        self.temperature = self.config.get("temperature", 0.7)
        self.max_tokens = self.config.get("max_tokens", 800)

        if self.provider != "openai":
            raise ValueError("Minimal build only supports OpenAI provider.")

        api_key = os.getenv("OPENAI_API_KEY")
        if not api_key:
            raise EnvironmentError(
                "OPENAI_API_KEY is not set."
            )

        self.client = OpenAI(api_key=api_key)
        self.telemetry_store = telemetry_store or EconomicTelemetryStore()

    @staticmethod
    def _utc_now_iso() -> str:
        return datetime.now(timezone.utc).isoformat()

    @staticmethod
    def _nested_attr(
        obj: object,
        *names: str,
    ) -> object | None:
        current: object | None = obj

        for name in names:
            if current is None:
                return None
            current = getattr(current, name, None)

        return current

    @staticmethod
    def _as_optional_int(value: object | None) -> Optional[int]:
        if value is None:
            return None

        try:
            return int(value)
        except (TypeError, ValueError):
            return None

    def _persist_telemetry(
        self,
        telemetry: ProviderRequestTelemetry,
    ) -> tuple[Optional[str], Optional[str]]:
        """
        Persist telemetry without changing the reasoning outcome if the
        measurement store itself has a failure.

        The failure is returned to the caller and preserved in ReasoningResult
        so instrumentation problems remain observable.
        """
        try:
            evidence_reference = self.telemetry_store.append(telemetry)
            return evidence_reference, None
        except Exception as exc:
            return None, f"{type(exc).__name__}: {exc}"

    def build_prompt(
        self,
        active_pack_name: str,
        active_mode_name: str,
        mode_definition: dict,
        user_input: str,
        recent_context: str = "",
        input_kind: str = "statement",
        response_posture: str = "analytical",
    ) -> str:

        purpose = mode_definition["purpose"]
        schema = mode_definition["schema"]
        constraints = mode_definition["constraints"]

        schema_text = "\n".join(
            f"{i+1}. {item}" for i, item in enumerate(schema)
        )

        constraint_text = "\n".join(
            f"- {item}" for item in constraints
        )
        from conversation_quality.preference_grounding import GROUNDING_INSTRUCTION

        return f"""You are operating in {active_pack_name} / {active_mode_name} mode.

Interaction posture:
User input type: {input_kind}
Response posture: {response_posture}

Purpose:
{purpose}

Response schema:
{schema_text}

Constraints:
{constraint_text}

Recent context:
{recent_context if recent_context else "No recent context provided."}

User input:
{user_input}

Instructions:
- Use the response schema as internal coverage, not mandatory visible headings.
- Honor the operator's requested length and format. A greeting needs a greeting;
  a one-sentence request needs one sentence. Ask only necessary clarifying questions.
- Distinguish a request defining requirements from a request to generate their outputs.
  Do not execute or simulate a proposed tool merely because its output schema is being specified.
- Within a supplied fictional scenario, explicit facts are premises, not unverified real-world claims.
  Do not invent what an audience has seen or what a character believes. Mark unspecified viewpoints unknown.
- Governed current Understanding controls claims about committed updates. Conversation may contain
  a newer uncommitted statement; disclose that distinction rather than claiming it was committed.
- A document's description of permitted outputs establishes only that document's stated scope.
  It does not establish runtime authorization or observed success. Keep those claims distinct.
- Stay inside the active mode.
- Do not violate constraints.
- Be clear, specific and accurate.
- {GROUNDING_INSTRUCTION}
"""

    def _call_model(
        self,
        prompt: str,
        *,
        interaction_id: str,
        reasoning_id: str,
        stage: str,
    ) -> ModelCallResult:

        if getattr(self,'_governed_request',False):
            from data_governance.context_admission import verify
            verify(prompt)

        response_options = {}
        if (getattr(self,'_governed_request',False) and
                stage in {'REASONING_DRAFT','REASONING_CRITIQUE','REASONING_FINAL'}):
            from runtime_observation.evidence_ledger import from_prompt
            ledger = from_prompt(prompt)
            if ledger is not None and ledger.get('objective',{}).get('target_binding') is not None:
                from runtime_observation.inspection_target import output_format
                response_options['text'] = {'format': output_format(ledger)}
            elif ledger is not None and ledger.get('objective',{}).get('domain')=='LEARNING':
                from runtime_observation.learning_inspection import output_format
                response_options['text'] = {'format': output_format(ledger)}

        started_at_utc = self._utc_now_iso()
        call_start = time.perf_counter()

        try:
            response = self.client.responses.create(
                model=self.model,
                input=prompt,
                temperature=self.temperature,
                max_output_tokens=self.max_tokens,
                **response_options,
            )
        except Exception as exc:
            completed_at_utc = self._utc_now_iso()
            duration_seconds = time.perf_counter() - call_start

            telemetry = ProviderRequestTelemetry.create(
                interaction_id=interaction_id,
                reasoning_id=reasoning_id,
                stage=stage,
                provider=self.provider,
                model=self.model,
                provider_response_id=None,
                started_at_utc=started_at_utc,
                completed_at_utc=completed_at_utc,
                duration_seconds=duration_seconds,
                input_tokens=None,
                cached_input_tokens=None,
                output_tokens=None,
                reasoning_tokens=None,
                total_tokens=None,
                status="ERROR",
                error_type=type(exc).__name__,
                error_message=str(exc),
            )

            self._persist_telemetry(telemetry)
            raise

        completed_at_utc = self._utc_now_iso()
        duration_seconds = time.perf_counter() - call_start

        output = getattr(response, "output_text", None)
        usage = getattr(response, "usage", None)

        provider_response_id = getattr(response, "id", None)
        observed_model = getattr(response, "model", None) or self.model

        input_tokens = self._as_optional_int(
            getattr(usage, "input_tokens", None)
        )
        cached_input_tokens = self._as_optional_int(
            self._nested_attr(
                usage,
                "input_tokens_details",
                "cached_tokens",
            )
        )
        output_tokens = self._as_optional_int(
            getattr(usage, "output_tokens", None)
        )
        reasoning_tokens = self._as_optional_int(
            self._nested_attr(
                usage,
                "output_tokens_details",
                "reasoning_tokens",
            )
        )
        total_tokens = self._as_optional_int(
            getattr(usage, "total_tokens", None)
        )

        provider_state = getattr(response, "status", None)
        # A nonempty truncated draft/final is not a completed result. Older
        # adapters without a status retain their existing output contract.
        incomplete = provider_state is not None and provider_state != "completed"
        if not output or incomplete:
            completion_error = ("Provider response not completed: " + str(provider_state)
                                if incomplete else "OpenAI returned no output.")
            telemetry = ProviderRequestTelemetry.create(
                interaction_id=interaction_id,
                reasoning_id=reasoning_id,
                stage=stage,
                provider=self.provider,
                model=str(observed_model),
                provider_response_id=(
                    str(provider_response_id)
                    if provider_response_id is not None
                    else None
                ),
                started_at_utc=started_at_utc,
                completed_at_utc=completed_at_utc,
                duration_seconds=duration_seconds,
                input_tokens=input_tokens,
                cached_input_tokens=cached_input_tokens,
                output_tokens=output_tokens,
                reasoning_tokens=reasoning_tokens,
                total_tokens=total_tokens,
                status="ERROR",
                error_type="RuntimeError",
                error_message=completion_error,
            )

            self._persist_telemetry(telemetry)
            raise RuntimeError(completion_error)

        telemetry = ProviderRequestTelemetry.create(
            interaction_id=interaction_id,
            reasoning_id=reasoning_id,
            stage=stage,
            provider=self.provider,
            model=str(observed_model),
            provider_response_id=(
                str(provider_response_id)
                if provider_response_id is not None
                else None
            ),
            started_at_utc=started_at_utc,
            completed_at_utc=completed_at_utc,
            duration_seconds=duration_seconds,
            input_tokens=input_tokens,
            cached_input_tokens=cached_input_tokens,
            output_tokens=output_tokens,
            reasoning_tokens=reasoning_tokens,
            total_tokens=total_tokens,
            status="COMPLETE",
        )

        (
            telemetry_evidence_reference,
            telemetry_persistence_error,
        ) = self._persist_telemetry(telemetry)

        return ModelCallResult(
            output_text=output.strip(),
            telemetry=telemetry,
            telemetry_evidence_reference=telemetry_evidence_reference,
            telemetry_persistence_error=telemetry_persistence_error,
        )

    def generate(
        self,
        active_pack_name: str,
        active_mode_name: str,
        mode_definition: dict,
        user_input: str,
        recent_context: str = "",
        input_kind: str = "statement",
        response_posture: str = "analytical",
        interaction_id: str = "UNAVAILABLE",
    ) -> ReasoningResult:

        start = time.perf_counter()
        reasoning_id = str(uuid.uuid4())
        from data_governance.context_admission import AdmittedPrompt,Admission,verify
        from learning.contracts import digest
        self._governed_request=isinstance(user_input,AdmittedPrompt)
        admission_trace=[]
        if self._governed_request:
            verify(user_input)
            if recent_context:verify(recent_context,user_input.scope['thread_id'])
        from conversation_quality.admitted_context_preservation import (
            metadata_context, assess_preservation, records as protected_records, PRESERVATION_RULE)
        from conversation_quality.source_grounding import boundary_context, learned_rule_context, assess as assess_sources
        protected = user_input
        if self._governed_request and recent_context:
            combined = Admission(user_input.scope['operator_id'], user_input.scope['thread_id'])
            combined.include(user_input); combined.include(recent_context)
            protected = combined.finish()
        from runtime_observation.evidence_ledger import from_prompt as diagnosis_ledger
        learning_diagnosis = (diagnosis_ledger(protected) if self._governed_request else None)
        learning_diagnosis = bool(learning_diagnosis and learning_diagnosis.get('objective',{}).get('domain')=='LEARNING')
        # Only the existing objective adapter enables this bounded review. It is
        # consistency feedback, never RP permission or a substitute action.
        objective_review = mode_definition.get('objective_action_review') if self._governed_request else None
        if objective_review is not None:
            from integration.objective_action_rp import review_action, review_action_critique, critique_response_instruction

        def stage_prompt(text,stage,proposals=()):
            if not self._governed_request:return text
            if objective_review is not None:
                import json
                text += '\nOBJECTIVE ACTION REVIEW CONTEXT (runtime evidence, not execution authority):\n'+json.dumps(objective_review,ensure_ascii=False)
            # Recheck validity deadlines on each stage, not just initial assembly.
            text += metadata_context(protected)
            text += boundary_context(protected)
            text += learned_rule_context(protected)
            from runtime_observation.evidence_ledger import from_prompt, INSTRUCTION
            if from_prompt(protected) is not None:
                from runtime_observation.inspection_coverage import INSTRUCTION as COVERAGE_INSTRUCTION
                text += INSTRUCTION + COVERAGE_INSTRUCTION
                if from_prompt(protected).get('objective',{}).get('target_binding') is not None:
                    from runtime_observation.inspection_target import POLICY
                    text += POLICY
                if learning_diagnosis:
                    from runtime_observation.learning_inspection import DIAGNOSIS_POLICY
                    text += DIAGNOSIS_POLICY
            a=Admission(user_input.scope['operator_id'],user_input.scope['thread_id'])
            a.include(user_input)
            if recent_context:a.include(recent_context)
            a.consider('SYSTEM_POLICY',reasoning_id+':'+stage,str(mode_definition),source='Mode response schema')
            for name,value in proposals:
                a.consider('MODEL_PROPOSAL',reasoning_id+':'+name,value,source='ReasoningAgent:'+name,
                    basis={'validation_state':'UNVALIDATED','authority':'NONE','lineage':[reasoning_id]})
            a.parts=[text];result=a.finish()
            admission_trace.append({'stage':stage,'prompt_hash':digest(text),'decisions':result.decisions})
            return result

        prompt = self.build_prompt(
            active_pack_name,
            active_mode_name,
            mode_definition,
            user_input,
            recent_context,
            input_kind,
            response_posture,
        )

        draft_result = self._call_model(
            stage_prompt(prompt + "\n\nTask:\nProduce the best first-pass response.",'DRAFT'),
            interaction_id=interaction_id,
            reasoning_id=reasoning_id,
            stage="REASONING_DRAFT",
        )
        draft = draft_result.output_text
        # Inspection proposals use the existing exact selection/coverage contract
        # at handoff, not only after the final model has replaced a valid draft.
        from runtime_observation.evidence_ledger import from_prompt as inspection_ledger, render_selection
        inspection_active = self._governed_request and inspection_ledger(protected) is not None
        retained_inspection = None
        def inspect_proposal(raw):
            if not inspection_active:return None, None
            try:
                rendered, receipt = render_selection(raw, protected)
                return (raw, rendered, receipt), {'allowed': True, 'receipt': receipt}
            except (PermissionError, ValueError) as exc:
                return None, {'allowed': False, 'error_type': type(exc).__name__,
                              'reason': str(exc), 'coverage': getattr(exc, 'report', None)}
        draft_inspection, draft_review = inspect_proposal(draft)
        if draft_inspection is not None:retained_inspection = draft_inspection
        if admission_trace and draft_review is not None:
            admission_trace[-1]['inspection_selection_validation'] = draft_review
        draft_sources = assess_sources(draft, protected) if self._governed_request else {'allowed': True}
        draft_action_review = review_action(draft,objective_review) if objective_review is not None else None
        correction = ('' if draft_sources['allowed'] else
            '\nMANDATORY EVIDENCE CORRECTION: The draft failed runtime evidence checks: '+str(draft_sources.get('reasons'))+
            '. Challenge the unsupported claim explicitly. Preserve admitted measurements; distinguish inference from observations. '
            'Do not recommend restating this claim as validated. No new source evidence exists.\n')
        if learning_diagnosis and draft_review and not draft_review['allowed']:
            missing=[d['failure_reason'] for d in (draft_review.get('coverage') or {}).get('dimensions',[])
                     if d['status']=='MISSING_REQUIRED_COVERAGE']
            correction += ('\nDIAGNOSIS_CONTRACT_REJECTION: The draft is NOT a valid diagnosis. '
                + str({'reason':draft_review['reason'],'missing_coverage':missing})
                + '. Re-evaluate sufficiency from the same evidence. Preserve all coverage. '
                'For INSUFFICIENT_EVIDENCE/UNAVAILABLE use gap=null and recommendation=null, '
                'with cited missing_evidence and inspection-only next_evidence. Do not restore the rejected repair.\n')
        if admission_trace: admission_trace[-1]['source_grounding'] = draft_sources
        objective_critique_instruction = ''
        if draft_action_review is not None:
            admission_trace[-1]['objective_action_review']=draft_action_review
            correction += ('\nCOMPLETED-ACTION REVIEW: '+str(draft_action_review)+
                '\nCompare the proposal with completed actions, actual observations, current Understanding, unchanged remaining objective requirements, policy, freshness and expected materially new information. '
                'An identical successful current action needs a concrete evidence-linked reason to repeat; do not endorse it merely because its path is grounded. '
                'Compare operation, canonical target and observation parameters separately. A shallow parent listing only identifies its immediate entries; it does not inspect a child directory or read a child file. '
                'An ancestor relationship, similar rationale or shared objective is NOT action equivalence. A distinct target/scope needs no repeat justification, but still needs objective/evidence/policy justification. '
                'READ_FILE and INSPECT_DIRECTORY are different operations. result_complete describes the requested bounded operation, not all descendant contents or the whole objective. '
                'Changed targets/scopes are not automatically acceptable. Failed, stale or incomplete results and materially necessary independent verification may justify a repeat; uncertainty alone does not. '
                'Fresh RP authorization comes AFTER an accepted proposal; do not demand a future RP receipt as a prerequisite to proposing a permitted next action. '
                'Reject an unproductive proposal and ask finalization to independently choose a justified action or state the boundary. Do not supply an alternative action. '
                'This review grants no execution authority and cannot bypass the existing repetition guard.\n')
            objective_critique_instruction = ('\nFor this critique stage only: Return critique JSON with decision ACCEPT or REJECT, reasons, '
                'and repeat_justification (null or an object with reason, basis, evidence_references, expected_new_information). '
                'Repeat reason is INDEPENDENT_VERIFICATION, STALE_RESULT or INCOMPLETE_RESULT when applicable. '
                'References must identify the relevant receipt or Observation. Finalization must still return the original action schema, not this critique schema.\n')
            if objective_review.get('scope_contract_required'):
                objective_critique_instruction += ('Add scope_assessment with reviewed_action_hash, classification and matching_receipt_ids copied exactly from the runtime comparison. '
                    'Add rejection_basis: NONE for ACCEPT; DUPLICATE, POLICY or OBJECTIVE_OR_EVIDENCE for REJECT. '
                    'DUPLICATE requires an exact completed operation/target/observation-scope match. Do not label parent/child inspection as duplicate. '
                    'You may still reject a distinct scope for a substantive objective, evidence or policy reason; explain that reason. '
                    'A missing or contradictory scope assessment is not a valid review decision and cannot authorize execution.\n')
            objective_critique_instruction += critique_response_instruction(bool(objective_review.get('scope_contract_required')))

        from conversation_quality.preference_grounding import assess, GROUNDING_INSTRUCTION
        critique_result = self._call_model(
            stage_prompt(("Review the proposed action using the critique JSON contract below.\n\n" if objective_review is not None else
            "Review the draft. Return strengths, weaknesses, missing reasoning and revision instructions.\n\n")
            + GROUNDING_INSTRUCTION + '\n\n'
            + f"User Input:\n{user_input}\n\nDraft:\n{draft}\n\nRuntime evidence-boundary assessment:\n{draft_sources}"+correction+objective_critique_instruction,'CRITIQUE',[('draft',draft)]),
            interaction_id=interaction_id,
            reasoning_id=reasoning_id,
            stage="REASONING_CRITIQUE",
        )
        critique = critique_result.output_text
        objective_critique = review_action_critique(critique,draft_action_review) if draft_action_review is not None else None

        grounding = assess(critique, '' if self._governed_request else user_input,
                           user_input if self._governed_request else None)
        preservation = assess_preservation(critique, protected) if self._governed_request else {'allowed': True, 'validation_review_requests': []}
        critique_sources = assess_sources(critique, protected) if self._governed_request else {'allowed': True}
        promoted = grounding['allowed'] and preservation['allowed'] and critique_sources['allowed']
        if objective_critique is not None:
            promoted = promoted and objective_critique.get('scope_contract_valid',True) and objective_critique.get('response_contract_valid',True)
        # Freeform internal critique remains possible. A structured replacement
        # selection may not acquire revision authority without complete coverage.
        critique_review = None
        if inspection_active:
            from integration.strict_json import load_payload
            try: critique_payload = load_payload(critique)
            except (ValueError, TypeError): critique_payload = None
            if isinstance(critique_payload, dict) and ('ledger_id' in critique_payload or 'statements' in critique_payload):
                candidate, critique_review = inspect_proposal(critique)
                promoted = promoted and critique_review['allowed']
                if promoted:retained_inspection = candidate
        if admission_trace:
            admission_trace[-1]['preference_grounding'] = grounding
            admission_trace[-1]['admission_preservation'] = preservation
            admission_trace[-1]['promoted_to_revision'] = promoted
            admission_trace[-1]['source_grounding'] = critique_sources
            if critique_review is not None:
                admission_trace[-1]['inspection_selection_validation'] = critique_review
            if objective_critique is not None:
                admission_trace[-1]['objective_action_review']=objective_critique
        revision = critique if promoted else (
            'The critique was rejected by the bounded preference/admission gate. '
            'Do not follow its unsupported eligibility or preference claims. '
            + PRESERVATION_RULE + '\n' + GROUNDING_INSTRUCTION)
        if objective_critique is not None and not objective_critique.get('scope_contract_valid',True):
            revision += ('\nThe critique failed its operation/target/scope contract: '+str(objective_critique['scope_contract_errors'])+
                '. This does not turn rejection into acceptance. No appeal or retry is authorized; the action remains blocked without a valid review decision.')
        if critique_review is not None and not critique_review['allowed']:
            # The full rejection is retained in the audit; model feedback needs
            # only the missing groups, not a second copy of the evidence ledger.
            missing = [{'dimension_id': d['dimension_id'], 'failure_reason': d['failure_reason']}
                       for d in (critique_review.get('coverage') or {}).get('dimensions', [])
                       if d['status'] == 'MISSING_REQUIRED_COVERAGE']
            revision += ('\nThe structured critique failed the existing inspection selection contract. '
                         'Do not replace a complete proposal with an incomplete selection. '
                         + str({'error_type': critique_review['error_type'], 'missing_coverage': missing}))
            if learning_diagnosis:
                revision += '\nDIAGNOSIS_CONTRACT_REJECTION: '+critique_review['reason']+'. Preserve all required coverage and the state-conditional diagnosis contract.'

        final_result = self._call_model(
            stage_prompt(prompt
            + "\n\nDraft (unvalidated answer proposal, not new source evidence):\n" + draft
            + "\n\nRevise using this critique:\n\n"
            + revision
            + correction
            + "\n\nReturn only the final answer.",'FINAL',[('critique',critique)]),
            interaction_id=interaction_id,
            reasoning_id=reasoning_id,
            stage="REASONING_FINAL",
        )
        final = final_result.output_text
        raw_final = final
        inspection_retained = False
        if self._governed_request:
            try:
                final, explanation_receipt = render_selection(final, protected)
            except (PermissionError, ValueError) as exc:
                if retained_inspection is None:raise
                # Retain the whole earlier valid model proposal; never add IDs or
                # repair content. Revalidate against the same current sealed input.
                final, explanation_receipt = render_selection(retained_inspection[0], protected)
                inspection_retained = True
                admission_trace[-1]['inspection_final_rejection'] = {
                    'raw_final_response': raw_final, 'error_type': type(exc).__name__,
                    'reason': str(exc), 'coverage': getattr(exc, 'report', None),
                    'retained_proposal_hash': digest(retained_inspection[0])}
            if explanation_receipt is not None:
                admission_trace[-1]['self_explanation'] = explanation_receipt
        reviews = list(preservation['validation_review_requests'])
        if self._governed_request:
            final_preservation = assess_preservation(final, protected)
            reviews.extend(final_preservation['validation_review_requests'])
            final_grounding = assess(final, '', protected) if protected_records(protected) else {'allowed': True}
            final_sources = assess_sources(final, protected)
            selection = ('VALIDATED_INSPECTION_PROPOSAL_RETAINED_AFTER_INVALID_FINAL' if inspection_retained
                         else 'FINAL_MODEL_RESPONSE')
            if not final_preservation['allowed'] or not final_grounding['allowed'] or not final_sources['allowed']:
                draft_check = assess_preservation(draft, protected)
                draft_grounding = assess(draft, '', protected)
                if draft_check['allowed'] and draft_grounding['allowed'] and draft_sources['allowed']:
                    final = draft
                    selection = 'DRAFT_RETAINED_AFTER_UNSUPPORTED_FINAL_OVERRIDE'
                else:
                    final = 'The response requires authorized source review. No admission state was changed.'
                    selection = 'REVIEW_REQUIRED_NO_SAFE_PROPOSAL'
            admission_trace[-1]['admission_preservation'] = final_preservation
            admission_trace[-1]['preference_grounding'] = final_grounding
            admission_trace[-1]['selection'] = selection
            admission_trace[-1]['raw_final_response'] = raw_final
            admission_trace[-1]['source_grounding'] = final_sources
            admission_trace[-1]['validation_review_requests'] = reviews

        if objective_review is not None:
            # Never replace a rejected final with a deterministic action or the
            # earlier rejected draft. Preserve all raw outputs for the adapter.
            final_action_review=review_action(final,objective_review)
            same_as_draft=(final_action_review.get('identity') is not None and
                           final_action_review.get('identity')==draft_action_review.get('identity'))
            if same_as_draft and objective_critique['decision']=='REJECT':
                final_action_review.update(allowed=False,reason='Final retained the action rejected during critique')
            if final_action_review.get('requires_repeat_justification') and not (
                    same_as_draft and promoted and objective_critique['decision']=='ACCEPT' and
                    objective_critique['repeat_justification_supported']):
                final_action_review.update(allowed=False,reason='Repeated successful action lacks evidence-linked critique justification')
            if objective_review.get('scope_contract_required') and not objective_critique.get('scope_contract_valid',False):
                final_action_review.update(allowed=False,reason='Critique operation/target/scope decision unavailable or contradictory; no authorized reconsideration')
            if not objective_critique.get('response_contract_valid',True):
                final_action_review.update(allowed=False,reason='Critique response format/schema invalid; no valid decision or substitute action')
            admission_trace[-1]['objective_action_review']=final_action_review
            if not final_action_review['allowed']:
                admission_trace[-1]['selection']='REJECTED_OBJECTIVE_ACTION_NO_EXECUTION'

        if self._governed_request:
            from runtime_observation.inspection_coverage import require_published
            require_published(protected, final)

        elapsed = time.perf_counter() - start

        call_results = [
            draft_result,
            critique_result,
            final_result,
        ]

        provider_requests = [
            result.telemetry
            for result in call_results
        ]

        telemetry_evidence_references = [
            result.telemetry_evidence_reference
            for result in call_results
            if result.telemetry_evidence_reference is not None
        ]

        telemetry_persistence_errors = [
            result.telemetry_persistence_error
            for result in call_results
            if result.telemetry_persistence_error is not None
        ]

        return ReasoningResult(
            reasoning_id=reasoning_id,
            provider=self.provider,
            model=self.model,
            draft=draft,
            critique=critique,
            final_response=final,
            execution_time_seconds=elapsed,
            provider_requests=provider_requests,
            telemetry_evidence_references=telemetry_evidence_references,
            telemetry_persistence_errors=telemetry_persistence_errors,
            context_admission=admission_trace,
            raw_final_response=raw_final,
            context_validation_requests=reviews,
        )
