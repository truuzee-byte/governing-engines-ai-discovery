from __future__ import annotations

import traceback
from typing import Optional
from uuid import uuid4

from agents.reasoning_agent import (
    ReasoningAgent,
    ReasoningResult,
)

from ambiguity.ambiguity_scoring_engine import (
    calculate_ambiguity_score,
)
from clarification.clarification_engine import (
    evaluate_clarification_state,
)
from context.context_resolver import (
    append_interaction_context,
    resolve_context_state,
)
from conversation_quality.conversation_quality_evaluator import (
    evaluate_conversation_quality,
)
from domain.domain_detector import (
    detect_domain,
)
from input.input_kind_detector import (
    detect_input_kind,
)
from input.input_processor import (
    normalize_input,
)
from intent.intent_classifier import (
    classify_intent,
)
from intent.intent_signal_detector import (
    detect_intent_signals,
)
from runtime_logging.response_logger import (
    write_response_log,
)
from runtime_logging.trace_logger import (
    write_trace_log,
)
from manifest.manifest_builder import (
    generate_interaction_manifest,
)
from mode.mode_resolution_engine import (
    resolve_mode,
)
from models.runtime_models import (
    CanonicalInteractionState,
    InteractionProcessingResult,
    OperatorInput,
    make_failure_state,
)
from posture.response_posture_engine import (
    determine_posture,
)
from pressure.pressure_detector import (
    detect_pressure_state,
)
from stability.interpretation_stability_engine import (
    calculate_interpretation_stability,
)
from stability.operator_alignment_engine import (
    calculate_operator_alignment,
)


POSTURE_TO_RESPONSE_POSTURE = {
    "DIRECT_RESPONSE": "direct",
    "INTERPRET": "analytical",
    "DEVELOPMENT_ANALYSIS": "technical",
    "CANON_VALIDATION": "analytical",
    "CLARIFY_FIRST": "clarification",
    "HALT": "blocked",
}


def _debug(label: str, **values) -> None:
    print(f"\nDEBUG {label}")
    print("-" * 80)
    for key, value in values.items():
        print(f"{key}: {value}")


def process_interaction(
    operator_input: OperatorInput,
    reasoning_input: Optional[str] = None,
) -> InteractionProcessingResult:
    """Process one interaction with separate interpretation and reasoning inputs.

    ``operator_input.raw_input`` must contain only the exact operator message. It is
    used by normalization, pressure detection, intent classification, ambiguity,
    clarification, posture, and governance.

    ``reasoning_input`` may contain the assembled governed runtime prompt. It is
    used only by the response-generation agent after interpretation and governance
    have completed. If omitted, response generation falls back to the normalized
    operator input for backward compatibility.
    """
    if not isinstance(operator_input, OperatorInput):
        raise TypeError("operator_input must be OperatorInput")

    if reasoning_input is not None and not isinstance(reasoning_input, str):
        raise TypeError("reasoning_input must be a string or None")
    if reasoning_input is not None or operator_input.input_source in {'interactive_mode_bot','supervisor_bridge'}:
        from data_governance.context_admission import verify
        verify(reasoning_input,operator_input.session_id)

    current_stage = "initialize"
    response_text = ""

    interaction_id = _generate_interaction_id()

    state = CanonicalInteractionState(
        interaction_id=interaction_id,
        session_id=operator_input.session_id,
        raw_input=operator_input.raw_input,
    )

    try:
        current_stage = "normalize_input"
        state.normalized_input = normalize_input(
            operator_input.raw_input,
        )

        _debug(
            "NORMALIZE",
            raw_input=state.raw_input,
            normalized_input=state.normalized_input,
        )

        current_stage = "detect_pressure_state"
        state.pressure_state = detect_pressure_state(
            raw_input=operator_input.raw_input,
            normalized_input=state.normalized_input,
        )

        _debug(
            "PRESSURE",
            pressure_state=(
                state.pressure_state.to_dict()
                if state.pressure_state is not None
                else None
            ),
        )

        current_stage = "resolve_context_state"
        state.resolved_context_state = resolve_context_state(
            operator_input.session_id,
        )

        _debug(
            "CONTEXT",
            resolved_context_state=state.resolved_context_state,
        )

        current_stage = "detect_input_kind"
        state.input_kind = detect_input_kind(
            state.normalized_input,
        )

        _debug(
            "INPUT KIND",
            input_kind=state.input_kind,
        )

        current_stage = "detect_intent_signals"
        state.intent_signals = detect_intent_signals(
            state.normalized_input,
        )

        _debug(
            "INTENT SIGNALS",
            intent_signals=state.intent_signals,
        )

        current_stage = "classify_intent"
        state.intent_type = classify_intent(
            state.input_kind,
            state.intent_signals,
        )

        _debug(
            "INTENT",
            input_kind=state.input_kind,
            intent_signals=state.intent_signals,
            intent_type=state.intent_type,
        )

        current_stage = "detect_domain"
        state.detected_domain = detect_domain(
            state.normalized_input,
        )

        _debug(
            "DOMAIN",
            detected_domain=state.detected_domain,
        )

        current_stage = "resolve_mode"
        state.selected_mode = resolve_mode(
            state.intent_type,
            state.detected_domain,
        )

        _debug(
            "MODE",
            intent_type=state.intent_type,
            detected_domain=state.detected_domain,
            selected_mode=state.selected_mode,
        )

        current_stage = "calculate_ambiguity_score"
        (
            state.ambiguity_score,
            state.ambiguity_contributors,
            state.ambiguity_profile,
        ) = calculate_ambiguity_score(state)

        _debug(
            "AMBIGUITY",
            ambiguity_score=state.ambiguity_score,
            ambiguity_contributors=state.ambiguity_contributors,
            ambiguity_profile=state.ambiguity_profile,
        )

        current_stage = "calculate_interpretation_stability"
        state.interpretation_stability_score = (
            calculate_interpretation_stability(state)
        )

        current_stage = "calculate_operator_alignment"
        state.operator_alignment_score = (
            calculate_operator_alignment(state)
        )

        _debug(
            "STABILITY",
            interpretation_stability_score=state.interpretation_stability_score,
            operator_alignment_score=state.operator_alignment_score,
        )

        current_stage = "evaluate_clarification_state"
        clarification_state = evaluate_clarification_state(
            state,
        )

        state.interpretation_notes.append(
            clarification_state["disposition"]
        )

        _debug(
            "CLARIFICATION",
            clarification_state=clarification_state,
            halt_required=state.halt_required,
            clarification_required=state.clarification_required,
            downstream_authority_allowed=state.downstream_authority_allowed,
        )

        current_stage = "determine_posture"
        state.selected_posture = determine_posture(
            state,
        )

        _debug(
            "POSTURE",
            selected_posture=state.selected_posture,
            halt_required=state.halt_required,
            clarification_required=state.clarification_required,
            downstream_authority_allowed=state.downstream_authority_allowed,
            selected_mode=state.selected_mode,
            input_kind=state.input_kind,
            intent_type=state.intent_type,
        )

        current_stage = "generate_semantic_response"
        reasoning_result = None

        try:
            reasoning_result = _generate_reasoning_result(
                state,
                reasoning_input=reasoning_input,
            )

            response_text = reasoning_result.final_response

        except Exception as generation_exc:
            state.selected_posture = "HALT"
            state.halt_required = True
            state.clarification_required = True
            state.downstream_authority_allowed = False
            response_text = "RESPONSE_GENERATION_FAILURE"
            state.failure_state = make_failure_state(
                failure_type="RESPONSE_GENERATION_FAILURE",
                failure_reason=str(generation_exc),
                source_stage=current_stage,
                terminal=True,
            )
            state.interpretation_notes.append(
                traceback.format_exc(limit=1).strip()
            )

            _debug(
                "RESPONSE GENERATION FAILURE",
                failure_reason=str(generation_exc),
                traceback=traceback.format_exc(limit=1).strip(),
            )

        current_stage = "evaluate_conversation_quality"
        state.conversation_quality_state = (
            evaluate_conversation_quality(
                state=state,
                response_text=response_text,
                reasoning_input=reasoning_input,
            )
        )

        current_stage = "write_response_log"
        write_response_log(
            interaction_id=state.interaction_id,
            session_id=state.session_id,
            response_text=response_text,
            pressure_state=state.pressure_state,
            conversation_quality_state=(
                state.conversation_quality_state
            ),
        )

        current_stage = "write_trace_log"
        state.trace_reference = write_trace_log(
            state,
        )

        current_stage = "generate_interaction_manifest"
        interaction_manifest = generate_interaction_manifest(
            state,
        )

        current_stage = "append_interaction_context"
        append_interaction_context(
            session_id=state.session_id,
            interaction_record={
                "interaction_id": state.interaction_id,
                "selected_mode": state.selected_mode,
                "selected_posture": state.selected_posture,
                "ambiguity_score": state.ambiguity_score,
                "ambiguity_contributors": list(state.ambiguity_contributors),
                "ambiguity_profile": dict(state.ambiguity_profile),
                "pressure_state": (
                    state.pressure_state.to_dict()
                    if state.pressure_state is not None
                    else {}
                ),
                "conversation_quality_state": (
                    state.conversation_quality_state.to_dict()
                    if state.conversation_quality_state is not None
                    else {}
                ),
                "trace_reference": state.trace_reference,
            },
        )

        return InteractionProcessingResult(
            success=state.failure_state == {},
            context_admission=getattr(reasoning_result,'context_admission',[]) if reasoning_result is not None else [],
            interaction_manifest=interaction_manifest,
            trace_reference=state.trace_reference,
            failure_state=state.failure_state,
            clarification_required=state.clarification_required,
            halt_required=state.halt_required,
            response_text=response_text,
            raw_input=state.raw_input,
            pressure_state=state.pressure_state,
            conversation_quality_state=(
                state.conversation_quality_state
            ),
            interaction_id=state.interaction_id,
            reasoning_id=(
                reasoning_result.reasoning_id
                if reasoning_result is not None
                else ""
            ),
            provider_request_telemetry=(
                [
                    telemetry.to_dict()
                    for telemetry in reasoning_result.provider_requests
                ]
                if reasoning_result is not None
                else []
            ),
            telemetry_evidence_references=(
                list(reasoning_result.telemetry_evidence_references)
                if reasoning_result is not None
                else []
            ),
            telemetry_persistence_errors=(
                list(reasoning_result.telemetry_persistence_errors)
                if reasoning_result is not None
                else []
            ),
        )

    except Exception as exc:
        _apply_failure_recovery_state(
            state,
        )

        state.failure_state = make_failure_state(
            failure_type="RUNTIME_SLICE_FAILURE",
            failure_reason=str(exc),
            source_stage=current_stage,
            terminal=True,
        )

        state.interpretation_notes.append(
            traceback.format_exc(limit=1).strip()
        )

        _debug(
            "RUNTIME SLICE FAILURE",
            current_stage=current_stage,
            failure_reason=str(exc),
            traceback=traceback.format_exc(limit=1).strip(),
        )

        try:
            state.trace_reference = write_trace_log(
                state,
            )

        except Exception:
            state.trace_reference = ""

        return InteractionProcessingResult(
            success=False,
            interaction_manifest=None,
            trace_reference=state.trace_reference,
            failure_state=state.failure_state,
            clarification_required=state.clarification_required,
            halt_required=state.halt_required,
            response_text=response_text,
            pressure_state=state.pressure_state,
            conversation_quality_state=(
                state.conversation_quality_state
            ),
            interaction_id=state.interaction_id,
            reasoning_id="",
            provider_request_telemetry=[],
            telemetry_evidence_references=[],
            telemetry_persistence_errors=[],
        )


def _generate_reasoning_result(
    state: CanonicalInteractionState,
    reasoning_input: Optional[str] = None,
) -> ReasoningResult:
    if state.selected_posture == "HALT" or state.halt_required is True:
        return ReasoningResult(
            reasoning_id="",
            provider="runtime",
            model="governance",
            draft="",
            critique="",
            final_response="GOVERNANCE HALT: response generation blocked.",
            execution_time_seconds=0.0,
        )

    response_posture = POSTURE_TO_RESPONSE_POSTURE[state.selected_posture]

    mode_definition = {
        "purpose": f"Operate in {state.selected_mode} mode.",
        "schema": [
            "Interpretation",
            "Reasoning",
            "Conclusion",
        ],
        "constraints": [
            "Respect ambiguity",
            "Do not hallucinate",
            "Match posture",
        ],
    }

    agent = ReasoningAgent()

    reasoning_result = agent.generate(
        active_pack_name="ModeAI",
        active_mode_name=state.selected_mode,
        mode_definition=mode_definition,
        user_input=(
            reasoning_input
            if reasoning_input is not None
            else state.normalized_input
        ),
        recent_context="",
        input_kind=state.input_kind,
        response_posture=response_posture,
        interaction_id=state.interaction_id,
    )

    if not reasoning_result.final_response.strip():
        raise ValueError("ReasoningAgent.generate() returned an empty final response")

    return reasoning_result


def _generate_interaction_id() -> str:
    return f"interaction-{uuid4().hex}"


def _apply_failure_recovery_state(
    state: CanonicalInteractionState,
) -> None:
    state.selected_mode = (
        state.selected_mode
        or "Interpretation"
    )

    state.selected_posture = "HALT"

    state.ambiguity_score = (
        state.ambiguity_score
        if state.ambiguity_score is not None
        else 1.0
    )

    if not state.ambiguity_profile:
        state.ambiguity_profile = {
            "structural": 1.0,
            "social_pressure": 0.0,
            "intent": 0.0,
            "governance_authority": 0.0,
            "temporal": 0.0,
            "semantic": 0.0,
            "consequence": 0.0,
            "identity_framing": 0.0,
            "psychological": 0.0,
            "moral_tradeoff": 0.0,
        }

    state.interpretation_stability_score = (
        state.interpretation_stability_score
        if state.interpretation_stability_score is not None
        else 0.0
    )

    state.operator_alignment_score = (
        state.operator_alignment_score
        if state.operator_alignment_score is not None
        else 0.0
    )

    state.halt_required = True
    state.downstream_authority_allowed = False
    state.clarification_required = True
