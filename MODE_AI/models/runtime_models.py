from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any, Dict, List, Optional


INPUT_KINDS = {
    "statement",
    "question",
    "build_request",
    "clarification_response",
    "document_review",
    "mixed_input",
}

INTENT_TYPES = {
    "interpret",
    "build",
    "audit",
    "clarify",
    "preserve",
    "discuss",
}

DOMAINS = {
    "governance",
    "software",
    "architecture",
    "creative",
    "research",
    "conversation",
    "mixed",
}

MODES = {
    "Interpretation",
    "Development",
    "Canon Check",
    "Creative Collaboration",
}

POSTURES = {
    "DIRECT_RESPONSE",
    "CLARIFY_FIRST",
    "INTERPRET",
    "DEVELOPMENT_ANALYSIS",
    "CANON_VALIDATION",
    "HALT",
}

REVIEWER_ROLES = {
    "system_operator",
    "domain_embedded_reviewer",
    "independent_reviewer",
    "automated_scorer",
}

HUMAN_SCORING_AUTHORITIES = {
    "human_score",
    "human_review",
    "human_final",
    "human_override",
}

PRESSURE_TYPES = {
    "none",
    "urgency",
    "social_pressure",
    "authority_pressure",
    "emotional_pressure",
    "compliance_pressure",
    "escalation_pressure",
    "ambiguity_pressure",
    "contradiction_pressure",
}

CONVERSATION_QUALITY_FLAGS = {
    "unsupported_preference",
    "low_clarity",
    "low_responsiveness",
    "low_coherence",
    "ambiguity_not_surfaced",
    "pressure_mishandled",
    "unstable_interpretation",
    "conversational_breakdown",
    "continuity_risk",
    "excessive_assumption",
    "human_usability_risk",
}


@dataclass(frozen=True)
class OperatorInput:
    raw_input: str
    session_id: str
    timestamp: str
    input_source: str

    def __post_init__(self) -> None:
        _require_non_empty_string(self.raw_input, "raw_input")
        _require_non_empty_string(self.session_id, "session_id")
        _require_non_empty_string(self.timestamp, "timestamp")
        _require_non_empty_string(self.input_source, "input_source")


@dataclass(frozen=True)
class ReviewerRole:
    reviewer_id: str
    reviewer_role: str
    domain_context_level: str
    system_involvement_level: str
    independence_level: str
    bias_vectors: List[str]
    scoring_authority: str
    review_scope: List[str]
    notes: str = ""

    def __post_init__(self) -> None:
        _require_non_empty_string(self.reviewer_id, "reviewer_id")
        _require_enum(self.reviewer_role, REVIEWER_ROLES, "reviewer_role")
        _require_non_empty_string(
            self.domain_context_level,
            "domain_context_level",
        )
        _require_non_empty_string(
            self.system_involvement_level,
            "system_involvement_level",
        )
        _require_non_empty_string(
            self.independence_level,
            "independence_level",
        )
        _require_string_list(self.bias_vectors, "bias_vectors")
        _require_non_empty_string(self.scoring_authority, "scoring_authority")
        _require_string_list(self.review_scope, "review_scope")
        _require_string(self.notes, "notes")

        if self.reviewer_role == "domain_embedded_reviewer":
            if len(self.bias_vectors) == 0:
                raise ValueError(
                    "domain_embedded_reviewer requires non-empty bias_vectors"
                )

        if self.reviewer_role == "automated_scorer":
            normalized_authority = self.scoring_authority.strip().lower()
            if normalized_authority in HUMAN_SCORING_AUTHORITIES:
                raise ValueError(
                    "automated_scorer cannot claim human scoring authority"
                )

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class PressureState:
    pressure_state_id: str
    pressure_score: float
    pressure_profile: Dict[str, float]
    pressure_signals: List[str]
    dominant_pressure_type: str
    pressure_detected: bool
    pressure_confidence: float
    pressure_resolution_timestamp: str

    def __post_init__(self) -> None:
        _require_non_empty_string(
            self.pressure_state_id,
            "pressure_state_id",
        )

        _require_score(
            self.pressure_score,
            "pressure_score",
        )

        if not isinstance(self.pressure_profile, dict):
            raise TypeError("pressure_profile must be a dictionary")

        for pressure_type, pressure_value in self.pressure_profile.items():
            _require_enum(
                pressure_type,
                PRESSURE_TYPES - {"none"},
                "pressure_profile key",
            )

            _require_score(
                pressure_value,
                f"pressure_profile[{pressure_type}]",
            )

        _require_string_list(
            self.pressure_signals,
            "pressure_signals",
        )

        for signal in self.pressure_signals:
            _require_enum(
                signal,
                PRESSURE_TYPES - {"none"},
                "pressure_signal",
            )

        _require_enum(
            self.dominant_pressure_type,
            PRESSURE_TYPES,
            "dominant_pressure_type",
        )

        if not isinstance(self.pressure_detected, bool):
            raise TypeError("pressure_detected must be bool")

        _require_score(
            self.pressure_confidence,
            "pressure_confidence",
        )

        _require_non_empty_string(
            self.pressure_resolution_timestamp,
            "pressure_resolution_timestamp",
        )

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class ConversationQualityState:
    conversation_quality_id: str
    conversation_quality_score: float
    human_usability_score: float
    continuity_preservation_score: float
    clarity_score: float
    responsiveness_score: float
    coherence_score: float
    ambiguity_handling_score: float
    pressure_handling_score: float
    interpretation_stability_score: float
    quality_flags: List[str]
    quality_failures: List[str]
    conversation_quality_timestamp: str

    def __post_init__(self) -> None:
        _require_non_empty_string(
            self.conversation_quality_id,
            "conversation_quality_id",
        )
        _require_score(
            self.conversation_quality_score,
            "conversation_quality_score",
        )
        _require_score(
            self.human_usability_score,
            "human_usability_score",
        )
        _require_score(
            self.continuity_preservation_score,
            "continuity_preservation_score",
        )
        _require_score(
            self.clarity_score,
            "clarity_score",
        )
        _require_score(
            self.responsiveness_score,
            "responsiveness_score",
        )
        _require_score(
            self.coherence_score,
            "coherence_score",
        )
        _require_score(
            self.ambiguity_handling_score,
            "ambiguity_handling_score",
        )
        _require_score(
            self.pressure_handling_score,
            "pressure_handling_score",
        )
        _require_score(
            self.interpretation_stability_score,
            "interpretation_stability_score",
        )

        _require_string_list(
            self.quality_flags,
            "quality_flags",
        )

        for quality_flag in self.quality_flags:
            _require_enum(
                quality_flag,
                CONVERSATION_QUALITY_FLAGS,
                "quality_flag",
            )

        _require_string_list(
            self.quality_failures,
            "quality_failures",
        )

        _require_non_empty_string(
            self.conversation_quality_timestamp,
            "conversation_quality_timestamp",
        )

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class FailureState:
    failure_type: str = ""
    failure_reason: str = ""
    source_stage: str = ""
    terminal: bool = False

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class CanonicalInteractionState:
    interaction_id: str
    session_id: str
    raw_input: str
    normalized_input: str = ""

    input_kind: str = ""
    intent_signals: List[str] = field(default_factory=list)
    intent_type: str = ""
    detected_domain: str = ""
    selected_mode: str = ""
    selected_posture: str = ""

    ambiguity_score: Optional[float] = None
    ambiguity_profile: Dict[str, float] = field(default_factory=dict)
    interpretation_stability_score: Optional[float] = None
    operator_alignment_score: Optional[float] = None

    pressure_state: Optional[PressureState] = None
    conversation_quality_state: Optional[ConversationQualityState] = None

    clarification_required: bool = False
    halt_required: bool = False
    downstream_authority_allowed: bool = False

    ambiguity_contributors: List[str] = field(default_factory=list)
    interpretation_notes: List[str] = field(default_factory=list)

    trace_reference: str = ""
    failure_state: Dict[str, Any] = field(default_factory=dict)

    resolved_context_state: Dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        _require_non_empty_string(self.interaction_id, "interaction_id")
        _require_non_empty_string(self.session_id, "session_id")
        _require_string(self.raw_input, "raw_input")

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class InteractionManifest:
    interaction_id: str
    session_id: str
    timestamp: str

    selected_mode: str
    selected_posture: str

    ambiguity_score: float
    ambiguity_profile: Dict[str, float]
    interpretation_stability_score: float
    operator_alignment_score: float

    clarification_required: bool
    halt_required: bool
    downstream_authority_allowed: bool

    ambiguity_contributors: List[str]
    interpretation_notes: List[str]

    trace_reference: str
    lineage_reference: str
    adaptive_state_reference: str

    def __post_init__(self) -> None:
        _require_non_empty_string(self.interaction_id, "interaction_id")
        _require_non_empty_string(self.session_id, "session_id")
        _require_non_empty_string(self.timestamp, "timestamp")
        _require_enum(self.selected_mode, MODES, "selected_mode")
        _require_enum(self.selected_posture, POSTURES, "selected_posture")
        _require_score(self.ambiguity_score, "ambiguity_score")

        if not isinstance(self.ambiguity_profile, dict):
            raise TypeError("ambiguity_profile must be a dictionary")

        for key, value in self.ambiguity_profile.items():
            _require_non_empty_string(key, "ambiguity_profile key")
            _require_score(value, f"ambiguity_profile[{key}]")

        _require_score(
            self.interpretation_stability_score,
            "interpretation_stability_score",
        )
        _require_score(self.operator_alignment_score, "operator_alignment_score")
        _require_string(self.trace_reference, "trace_reference")
        _require_non_empty_string(self.lineage_reference, "lineage_reference")
        _require_non_empty_string(
            self.adaptive_state_reference,
            "adaptive_state_reference",
        )

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class TraceLog:
    interaction_id: str
    session_id: str

    raw_input: str
    normalized_input: str

    selected_mode: str
    selected_posture: str

    ambiguity_score: float
    ambiguity_profile: Dict[str, float]
    interpretation_stability_score: float
    operator_alignment_score: float

    clarification_required: bool
    halt_required: bool
    downstream_authority_allowed: bool

    timestamp: str

    def __post_init__(self) -> None:
        _require_non_empty_string(self.interaction_id, "interaction_id")
        _require_non_empty_string(self.session_id, "session_id")
        _require_string(self.raw_input, "raw_input")
        _require_string(self.normalized_input, "normalized_input")
        _require_enum(self.selected_mode, MODES, "selected_mode")
        _require_enum(self.selected_posture, POSTURES, "selected_posture")
        _require_score(self.ambiguity_score, "ambiguity_score")
        _require_score(
            self.interpretation_stability_score,
            "interpretation_stability_score",
        )
        _require_score(self.operator_alignment_score, "operator_alignment_score")
        _require_non_empty_string(self.timestamp, "timestamp")

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class InteractionProcessingResult:
    success: bool
    interaction_manifest: Optional[InteractionManifest]
    trace_reference: str
    failure_state: Dict[str, Any]
    clarification_required: bool
    halt_required: bool
    response_text: str = ""
    pressure_state: Optional[PressureState] = None
    conversation_quality_state: Optional[ConversationQualityState] = None
    raw_input: str = ""

    # Runtime economic telemetry bridge.
    interaction_id: str = ""
    reasoning_id: str = ""
    provider_request_telemetry: List[Dict[str, Any]] = field(default_factory=list)
    telemetry_evidence_references: List[str] = field(default_factory=list)
    telemetry_persistence_errors: List[str] = field(default_factory=list)
    context_admission: List[Dict[str, Any]] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "success": self.success,
            "interaction_manifest": (
                self.interaction_manifest.to_dict()
                if self.interaction_manifest is not None
                else {}
            ),
            "trace_reference": self.trace_reference,
            "failure_state": self.failure_state,
            "clarification_required": self.clarification_required,
            "halt_required": self.halt_required,
            "response_text": self.response_text,
            "raw_input": self.raw_input,
            "pressure_state": (
                self.pressure_state.to_dict()
                if self.pressure_state is not None
                else {}
            ),
            "conversation_quality_state": (
                self.conversation_quality_state.to_dict()
                if self.conversation_quality_state is not None
                else {}
            ),
            "interaction_id": self.interaction_id,
            "reasoning_id": self.reasoning_id,
            "provider_request_telemetry": list(self.provider_request_telemetry),
            "telemetry_evidence_references": list(self.telemetry_evidence_references),
            "telemetry_persistence_errors": list(self.telemetry_persistence_errors),
            "context_admission": list(self.context_admission),
        }


def round_score(value: float) -> float:
    if not isinstance(value, (int, float)):
        raise TypeError("score value must be numeric")

    clamped = max(0.0, min(1.0, float(value)))
    return round(clamped, 4)


def make_failure_state(
    failure_type: str,
    failure_reason: str,
    source_stage: str,
    terminal: bool = True,
) -> Dict[str, Any]:
    return FailureState(
        failure_type=failure_type,
        failure_reason=failure_reason,
        source_stage=source_stage,
        terminal=terminal,
    ).to_dict()


def _require_string(value: str, field_name: str) -> None:
    if not isinstance(value, str):
        raise TypeError(f"{field_name} must be a string")


def _require_non_empty_string(value: str, field_name: str) -> None:
    _require_string(value, field_name)
    if value.strip() == "":
        raise ValueError(f"{field_name} must not be empty")


def _require_enum(value: str, allowed_values: set[str], field_name: str) -> None:
    _require_non_empty_string(value, field_name)
    if value not in allowed_values:
        raise ValueError(
            f"{field_name} must be one of {sorted(allowed_values)}; received {value!r}"
        )


def _require_score(value: float, field_name: str) -> None:
    if not isinstance(value, (int, float)):
        raise TypeError(f"{field_name} must be numeric")

    numeric_value = float(value)
    if numeric_value < 0.0 or numeric_value > 1.0:
        raise ValueError(f"{field_name} must be between 0.0 and 1.0")

    if round(numeric_value, 4) != numeric_value:
        raise ValueError(f"{field_name} must be rounded to 4 decimal places")


def _require_string_list(value: List[str], field_name: str) -> None:
    if not isinstance(value, list):
        raise TypeError(f"{field_name} must be a list")

    for item in value:
        _require_non_empty_string(item, field_name)
