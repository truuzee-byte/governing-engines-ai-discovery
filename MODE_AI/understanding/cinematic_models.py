"""CU core contracts / Animation §§3–48. Authored state is not RP truth.

Facts carry epistemic state per dimension. None means unavailable, never zero.
JSON decoding is strict; no unknown fields, enum coercion or upstream PASS.
"""
from dataclasses import dataclass, field, fields, asdict
from typing import get_type_hints, get_origin, get_args
import json
from system_layer.contracts import digest

EPISTEMIC = {'ESTABLISHED', 'INFERRED', 'UNKNOWN', 'CONFLICTED'}
GROUNDING = {'SUPPORTED', 'REASONABLE_INFERENCE', 'UNKNOWN', 'CONFLICTED', 'UNSUPPORTED'}
DISPOSITIONS = {'REQUIRED', 'AUTHORIZED', 'OPTIONAL', 'PROHIBITED', 'UNRESOLVED', 'IMPLEMENTATION_CHOICE'}
MECHANISMS = {'CAMERA', 'BLOCKING', 'PERFORMANCE', 'EDITING', 'LIGHTING', 'SOUND', 'MUSIC', 'ENVIRONMENT', 'ANIMATION', 'DIALOGUE'}
MECHANISM_STATES = {'GENERATED', 'ELIGIBLE', 'CONFLICTING', 'REQUIRES_AUTHORITY', 'SELECTED', 'REJECTED', 'SUPERSEDED'}


class Contract:
    def to_dict(self):
        return asdict(self)

    @classmethod
    def from_dict(cls, value):
        if type(value) is not dict or set(value) - {f.name for f in fields(cls)}:
            raise ValueError('Unknown fields: ' + cls.__name__)
        hints = get_type_hints(cls)
        return cls(**{k: _decode(hints[k], v) for k, v in value.items()})

    def __post_init__(self):
        # Construction and deserialization enforce the same boundary.
        for name, kind in get_type_hints(type(self)).items():
            _check(kind, getattr(self, name))


def _decode(kind, value):
    origin = get_origin(kind)
    if origin is list:
        if type(value) is not list: raise ValueError('List required')
        return [_decode(get_args(kind)[0], x) for x in value]
    if origin is dict:
        if type(value) is not dict: raise ValueError('Object required')
        key, item = get_args(kind)
        return {_decode(key, k): _decode(item, v) for k, v in value.items()}
    if isinstance(kind, type) and issubclass(kind, Contract): return kind.from_dict(value)
    _check(kind, value)
    return value


def _check(kind, value):
    origin = get_origin(kind)
    if origin is list:
        if type(value) is not list: raise ValueError('List required')
        for item in value: _check(get_args(kind)[0], item)
    elif origin is dict:
        if type(value) is not dict: raise ValueError('Mapping required')
        for k, v in value.items():
            _check(get_args(kind)[0], k); _check(get_args(kind)[1], v)
    elif kind is object:
        json.dumps(value, allow_nan=False)
    elif type(value) is not kind:
        raise ValueError('Wrong contract type: ' + str(kind))


def loads(text):
    def unique(pairs):
        out = {}
        for k, v in pairs:
            if k in out: raise ValueError('Duplicate JSON key')
            out[k] = v
        return out
    def invalid(value): raise ValueError('Nonfinite number')
    return json.loads(text, object_pairs_hook=unique, parse_constant=invalid)


@dataclass
class Fact(Contract):
    value: object = None
    state: str = 'UNKNOWN'
    source_references: list[str] = field(default_factory=list)
    evidence: list[str] = field(default_factory=list)
    grounding: str = 'UNKNOWN'
    rp_state: str = 'PENDING_VALIDATION'

    def __post_init__(self):
        super().__post_init__()
        if self.state not in EPISTEMIC or self.grounding not in GROUNDING: raise ValueError('Invalid fact state')
        if self.rp_state != 'PENDING_VALIDATION': raise ValueError('Authored fact cannot issue an RP verdict')
        if self.state == 'ESTABLISHED' and (self.value is None or not self.source_references or self.grounding != 'SUPPORTED'):
            raise ValueError('Established authored fact needs grounded source')
        if self.state == 'UNKNOWN' and self.value is not None: raise ValueError('Unknown fact cannot assert value')
        if self.grounding == 'REASONABLE_INFERENCE' and self.state != 'INFERRED': raise ValueError('Inference promotion')


@dataclass
class Governed(Contract):
    object_id: str
    scope: str
    authority: str
    source_references: list[str]
    schema_version: str = 'Cinematic/1'
    version: int = 1
    evidence: list[str] = field(default_factory=list)
    assumptions: list[str] = field(default_factory=list)
    constraints: dict[str, Fact] = field(default_factory=dict)
    dependencies: list[str] = field(default_factory=list)
    relationships: list[str] = field(default_factory=list)
    temporal_scope: str = 'UNRESOLVED'
    confidence: object = None
    validation_state: str = 'UNVALIDATED'
    lineage: list[str] = field(default_factory=list)
    unresolved_questions: list[str] = field(default_factory=list)
    rp_state: str = 'PENDING_VALIDATION'

    def __post_init__(self):
        super().__post_init__()
        if not all(x.strip() for x in (self.object_id, self.scope, self.authority)) or not self.source_references:
            raise ValueError('Identity/scope/source/authority required')
        if self.schema_version != 'Cinematic/1' or self.version < 1: raise ValueError('Unsupported version')
        if self.rp_state != 'PENDING_VALIDATION': raise ValueError('Candidate model cannot issue an RP verdict')
        if self.validation_state not in {'UNVALIDATED', 'PENDING_VALIDATION'}: raise ValueError('RP verdict cannot be self-issued')
        if self.confidence is not None and (type(self.confidence) not in (int, float) or not 0 <= self.confidence <= 1):
            raise ValueError('Invalid confidence')

    @property
    def object_type(self): return type(self).__name__


@dataclass
class WorldModel(Governed):
    laws: dict[str, Fact] = field(default_factory=dict)
    physical_constraints: dict[str, Fact] = field(default_factory=dict)


@dataclass
class WorldState(Governed):
    dimensions: dict[str, Fact] = field(default_factory=dict)


@dataclass
class EntityModel(Governed):
    identity: dict[str, Fact] = field(default_factory=dict)
    composition: list[str] = field(default_factory=list)
    capabilities: dict[str, Fact] = field(default_factory=dict)


@dataclass
class SpatialState(Governed):
    positions: dict[str, Fact] = field(default_factory=dict)
    orientations: dict[str, Fact] = field(default_factory=dict)
    topology: dict[str, Fact] = field(default_factory=dict)
    movement: dict[str, Fact] = field(default_factory=dict)


@dataclass
class TemporalState(Governed):
    order: list[str] = field(default_factory=list)
    temporal_relationships: dict[str, Fact] = field(default_factory=dict)
    durations: dict[str, Fact] = field(default_factory=dict)
    time_of_day: Fact = field(default_factory=Fact)


@dataclass
class CharacterState(Governed):
    entity_id: str = ''
    physical: dict[str, Fact] = field(default_factory=dict)
    emotional: dict[str, Fact] = field(default_factory=dict)
    goals: dict[str, Fact] = field(default_factory=dict)
    behavior: dict[str, Fact] = field(default_factory=dict)


@dataclass
class KnowledgeState(Governed):
    holder_id: str = ''
    knows: dict[str, Fact] = field(default_factory=dict)
    does_not_know: list[str] = field(default_factory=list)
    perceptual_access: dict[str, Fact] = field(default_factory=dict)


@dataclass
class BeliefState(Governed):
    holder_id: str = ''
    believes: dict[str, Fact] = field(default_factory=dict)


@dataclass
class TruthState(Governed):
    # Authored world truth, not validated external reality.
    world_truth: dict[str, Fact] = field(default_factory=dict)
    interpretations: dict[str, Fact] = field(default_factory=dict)


@dataclass
class RelationshipState(Governed):
    participants: list[str] = field(default_factory=list)
    dimensions: dict[str, Fact] = field(default_factory=dict)


@dataclass
class NarrativeState(Governed):
    objective: Fact = field(default_factory=Fact)
    stakes: dict[str, Fact] = field(default_factory=dict)
    causal_links: dict[str, Fact] = field(default_factory=dict)
    chains: list[str] = field(default_factory=list)


@dataclass
class SceneState(Governed):
    participants: list[str] = field(default_factory=list)
    environment: dict[str, Fact] = field(default_factory=dict)
    entry_state: dict[str, Fact] = field(default_factory=dict)
    exit_state: dict[str, Fact] = field(default_factory=dict)
    scene_objective: Fact = field(default_factory=Fact)
    character_states: list[CharacterState] = field(default_factory=list)
    relationship_states: list[RelationshipState] = field(default_factory=list)
    knowledge_states: list[KnowledgeState] = field(default_factory=list)
    belief_states: list[BeliefState] = field(default_factory=list)
    truth_state_map: dict[str, Fact] = field(default_factory=dict)
    spatial_states: list[SpatialState] = field(default_factory=list)
    temporal_states: list[TemporalState] = field(default_factory=list)
    required_beats: list[str] = field(default_factory=list)
    required_transitions: list[str] = field(default_factory=list)
    causal_requirements: dict[str, Fact] = field(default_factory=dict)
    information_movement: dict[str, Fact] = field(default_factory=dict)
    perspective_state: dict[str, Fact] = field(default_factory=dict)
    continuity_inputs: dict[str, Fact] = field(default_factory=dict)
    continuity_outputs: dict[str, Fact] = field(default_factory=dict)
    authorized_continuity_changes: dict[str, Fact] = field(default_factory=dict)


@dataclass
class BeatState(Governed):
    scene_id: str = ''
    purpose: Fact = field(default_factory=Fact)
    participants: list[str] = field(default_factory=list)
    preconditions: dict[str, Fact] = field(default_factory=dict)
    trigger: Fact = field(default_factory=Fact)
    action: Fact = field(default_factory=Fact)
    reaction: Fact = field(default_factory=Fact)
    state_change: dict[str, Fact] = field(default_factory=dict)
    causal_link: Fact = field(default_factory=Fact)
    audience_effect: Fact = field(default_factory=Fact)
    visibility: dict[str, Fact] = field(default_factory=dict)
    required_information: list[str] = field(default_factory=list)
    hidden_information: list[str] = field(default_factory=list)
    order: int = 0
    continuity_inputs: dict[str, Fact] = field(default_factory=dict)
    continuity_outputs: dict[str, Fact] = field(default_factory=dict)
    authorized_continuity_changes: dict[str, Fact] = field(default_factory=dict)
    failure_conditions: list[str] = field(default_factory=list)


@dataclass
class AudienceState(Governed):
    knows: dict[str, Fact] = field(default_factory=dict)
    may_infer: dict[str, Fact] = field(default_factory=dict)
    believes: dict[str, Fact] = field(default_factory=dict)
    perceives: dict[str, Fact] = field(default_factory=dict)
    does_not_know: list[str] = field(default_factory=list)
    must_understand: list[str] = field(default_factory=list)
    must_not_yet_understand: list[str] = field(default_factory=list)
    emotional_state: dict[str, Fact] = field(default_factory=dict)
    expected_transition: dict[str, Fact] = field(default_factory=dict)
    required_evidence: dict[str, list[str]] = field(default_factory=dict)
    prohibited_evidence: list[str] = field(default_factory=list)


@dataclass
class CinematicRequirement(Governed):
    scene_id: str = ''
    beat_id: str = ''
    source_story_requirement: str = ''
    required_audience_state: dict[str, Fact] = field(default_factory=dict)
    required_perception: dict[str, Fact] = field(default_factory=dict)
    information_requirement: list[str] = field(default_factory=list)
    hidden_information: list[str] = field(default_factory=list)
    relationship_requirement: list[str] = field(default_factory=list)
    state_transition_requirement: dict[str, Fact] = field(default_factory=dict)
    causal_requirement: Fact = field(default_factory=Fact)
    emotional_requirement: Fact = field(default_factory=Fact)
    continuity_requirement: dict[str, Fact] = field(default_factory=dict)
    physical_constraints: dict[str, Fact] = field(default_factory=dict)
    acceptable_mechanism_classes: list[str] = field(default_factory=list)
    implementation_freedom: list[str] = field(default_factory=list)
    prohibited_interpretations: list[str] = field(default_factory=list)
    required_evidence: list[str] = field(default_factory=list)
    validation_rule: str = 'PENDING_EXTERNAL_VALIDATION'
    disposition: str = 'REQUIRED'

    def __post_init__(self):
        super().__post_init__()
        if self.disposition not in DISPOSITIONS or set(self.acceptable_mechanism_classes)-MECHANISMS:
            raise ValueError('Invalid requirement vocabulary')


@dataclass
class Camera(Contract):
    subject: str = ''
    viewpoint: Fact = field(default_factory=Fact)
    framing: Fact = field(default_factory=Fact)
    movement: Fact = field(default_factory=Fact)
    lens: Fact = field(default_factory=Fact)
    position: Fact = field(default_factory=Fact)
    angle: Fact = field(default_factory=Fact)
    focus: Fact = field(default_factory=Fact)
    depth: Fact = field(default_factory=Fact)
    reveal: list[str] = field(default_factory=list)
    conceal: list[str] = field(default_factory=list)
    visibility: list[str] = field(default_factory=list)


@dataclass
class Blocking(Contract):
    positions: dict[str, Fact] = field(default_factory=dict)
    orientations: dict[str, Fact] = field(default_factory=dict)
    movement_paths: dict[str, Fact] = field(default_factory=dict)
    interactions: list[str] = field(default_factory=list)
    proximity: dict[str, Fact] = field(default_factory=dict)
    access: dict[str, Fact] = field(default_factory=dict)
    visibility: dict[str, Fact] = field(default_factory=dict)


@dataclass
class Performance(Contract):
    character_id: str = ''
    action: Fact = field(default_factory=Fact)
    reaction: Fact = field(default_factory=Fact)
    timing: Fact = field(default_factory=Fact)
    emotional_intent: Fact = field(default_factory=Fact)
    gesture: Fact = field(default_factory=Fact)
    posture: Fact = field(default_factory=Fact)
    facial_expression: Fact = field(default_factory=Fact)
    eye_line: Fact = field(default_factory=Fact)
    vocal_behavior: Fact = field(default_factory=Fact)


@dataclass
class CinematicMechanism(Governed):
    requirement_id: str = ''
    mechanism_class: str = 'CAMERA'
    state: str = 'GENERATED'
    implementation: dict[str, Fact] = field(default_factory=dict)
    expression_parameters: dict[str, Fact] = field(default_factory=dict)
    camera: Camera = field(default_factory=Camera)
    blocking: Blocking = field(default_factory=Blocking)
    performance: Performance = field(default_factory=Performance)
    delivered_information: list[str] = field(default_factory=list)
    impacts: dict[str, Fact] = field(default_factory=dict)
    constraint_satisfaction: list[str] = field(default_factory=list)
    constraint_violations: list[str] = field(default_factory=list)
    authority_required: list[str] = field(default_factory=list)
    feasibility: str = 'UNPROVEN'
    risks: list[str] = field(default_factory=list)

    def __post_init__(self):
        super().__post_init__()
        if self.mechanism_class not in MECHANISMS or self.state not in MECHANISM_STATES:
            raise ValueError('Invalid mechanism state/class')


@dataclass
class ContinuityRequirement(Governed):
    previous_id: str = ''
    next_id: str = ''
    expected: dict[str, Fact] = field(default_factory=dict)
    proposed: dict[str, Fact] = field(default_factory=dict)
    authorized_changes: dict[str, Fact] = field(default_factory=dict)
    conflicts: list[str] = field(default_factory=list)


@dataclass
class ShotRequirement(Governed):
    scene_id: str = ''
    beat_id: str = ''
    requirement_id: str = ''
    mechanism_ids: list[str] = field(default_factory=list)
    purpose: Fact = field(default_factory=Fact)
    start_state: dict[str, Fact] = field(default_factory=dict)
    end_state: dict[str, Fact] = field(default_factory=dict)
    camera: Camera = field(default_factory=Camera)
    blocking: Blocking = field(default_factory=Blocking)
    performance: Performance = field(default_factory=Performance)
    visible_characters: list[str] = field(default_factory=list)
    visible_objects: list[str] = field(default_factory=list)
    delivered_information: list[str] = field(default_factory=list)
    withheld_information: list[str] = field(default_factory=list)
    action: Fact = field(default_factory=Fact)
    timing: Fact = field(default_factory=Fact)
    continuity_inputs: dict[str, Fact] = field(default_factory=dict)
    continuity_outputs: dict[str, Fact] = field(default_factory=dict)
    audio: dict[str, Fact] = field(default_factory=dict)
    environment: dict[str, Fact] = field(default_factory=dict)
    required_evidence: list[str] = field(default_factory=list)
    failure_conditions: list[str] = field(default_factory=list)
    implementation_freedom: list[str] = field(default_factory=list)


@dataclass
class ExecutionSpecification(Governed):
    world_models: list[WorldModel] = field(default_factory=list)
    world_states: list[WorldState] = field(default_factory=list)
    entities: list[EntityModel] = field(default_factory=list)
    narratives: list[NarrativeState] = field(default_factory=list)
    truth_states: list[TruthState] = field(default_factory=list)
    scenes: list[SceneState] = field(default_factory=list)
    beats: list[BeatState] = field(default_factory=list)
    audiences: list[AudienceState] = field(default_factory=list)
    requirements: list[CinematicRequirement] = field(default_factory=list)
    candidates: list[CinematicMechanism] = field(default_factory=list)
    shots: list[ShotRequirement] = field(default_factory=list)
    continuity: list[ContinuityRequirement] = field(default_factory=list)
    dispositions: dict[str, str] = field(default_factory=dict)
    required_proof: list[str] = field(default_factory=list)
    understanding_reference: str = ''
    understanding_analysis: dict[str, object] = field(default_factory=dict)
    system_assessment: dict[str, object] = field(default_factory=dict)
    execution_authority: bool = False

    def __post_init__(self):
        super().__post_init__()
        if self.execution_authority or set(self.dispositions.values())-DISPOSITIONS:
            raise ValueError('Preparation cannot grant execution authority')


def identity(kind, source, value):
    return kind + ':' + digest({'source': source, 'value': value})
