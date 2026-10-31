"""Bounded cinematic derivation within Understanding (Animation §§35–48).

No model calls, physics simulator, renderer, execution grants or RP decisions.
Structured authored source provides facts/policy; this module derives obligations
and alternatives, not new canon. Unsupported prose remains unresolved upstream.
"""
from copy import deepcopy
from dataclasses import fields, is_dataclass
from .cinematic_models import (
    Fact, Governed, WorldModel, WorldState, EntityModel, NarrativeState, TruthState,
    SceneState, BeatState, AudienceState, CinematicRequirement, CinematicMechanism,
    ContinuityRequirement, Camera, Performance, identity, MECHANISMS,
)
from system_layer.contracts import digest

MODEL_TYPES = {'world_models': WorldModel, 'world_states': WorldState, 'entities': EntityModel,
               'narratives': NarrativeState, 'truth_states': TruthState, 'scenes': SceneState,
               'beats': BeatState, 'audiences': AudienceState}

# These are mechanism dimensions from Animation §42, not invented story facts.
EXPRESSION_PARAMETERS = {
    'CAMERA': ('framing', 'angle', 'position', 'lens', 'movement', 'focus', 'depth'),
    'BLOCKING': ('position', 'orientation', 'movement', 'proximity', 'grouping', 'access', 'visibility'),
    'PERFORMANCE': ('gesture', 'posture', 'facial_expression', 'eye_line', 'timing', 'vocal_behavior'),
    'EDITING': ('information_order', 'temporal_order', 'rhythm', 'contrast', 'simultaneity', 'reveal', 'concealment'),
    'LIGHTING': ('visibility', 'attention', 'depth', 'separation', 'environment', 'time_perception'),
    'SOUND': ('environmental_sound', 'effects', 'offscreen_information', 'spatial_sound', 'silence'),
    'MUSIC': ('emotional_framing', 'anticipation', 'tension', 'release', 'rhythm', 'theme'),
    'ENVIRONMENT': ('geography', 'architecture', 'weather', 'lighting', 'spatial_continuity'),
    'ANIMATION': ('pose', 'timing', 'weight', 'locomotion', 'interaction', 'physics', 'transition'),
    'DIALOGUE': ('speaker', 'content', 'delivery', 'timing', 'information_release'),
}


def walk(value):
    yield value
    if is_dataclass(value):
        for f in fields(value): yield from walk(getattr(value, f.name))
    elif type(value) is dict:
        for v in value.values(): yield from walk(v)
    elif type(value) is list:
        for v in value: yield from walk(v)


def grounding(fact, source_facts):
    """Compare with exact selected authored facts, not available-model confidence."""
    if fact.state == 'UNKNOWN': return 'UNKNOWN'
    if fact.state == 'CONFLICTED': return 'CONFLICTED'
    if not fact.source_references or any(r not in source_facts for r in fact.source_references): return 'UNSUPPORTED'
    values = [source_facts[r] for r in fact.source_references]
    if fact.state == 'INFERRED': return 'REASONABLE_INFERENCE'
    return 'SUPPORTED' if all(digest(v) == digest(fact.value) for v in values) else 'CONFLICTED'


def parse_story(value, project_id):
    required = {'schema_version', 'source_facts', 'policies', *MODEL_TYPES}
    if type(value) is not dict or set(value) != required or value['schema_version'] != 'CinematicStory/1':
        raise ValueError('CinematicStory/1 exact structured source required; prose is not silently parsed')
    if type(value['source_facts']) is not dict or any(not k.startswith('fact:') for k in value['source_facts']):
        raise ValueError('Explicit source fact locators required')
    source = value['source_facts']
    result = {}
    for key, kind in MODEL_TYPES.items():
        if type(value[key]) is not list or len(value[key]) > 256: raise ValueError('Bounded model list required')
        result[key] = [kind.from_dict(x) for x in value[key]]
    all_objects = [x for x in walk(result) if isinstance(x, Governed)]
    ids = [x.object_id for x in all_objects]
    if len(set(ids)) != len(ids): raise ValueError('Duplicate domain identity')
    for obj in all_objects:
        if obj.scope != project_id: raise PermissionError('Cinematic project mismatch')
        if any(ref not in source for ref in obj.source_references): raise ValueError('Unbound object source')
    for fact in (x for x in walk(result) if isinstance(x, Fact)):
        actual = grounding(fact, source)
        if fact.grounding != actual: raise ValueError('Source grounding mismatch: ' + actual)
        if fact.state == 'ESTABLISHED' and actual != 'SUPPORTED': raise ValueError('Unsupported established assertion')
    scenes = {s.object_id: s for s in result['scenes']}
    beats = {b.object_id: b for b in result['beats']}
    if not scenes or not beats: raise ValueError('Scene and meaningful beat required')
    entities = {e.object_id for e in result['entities']}
    for scene in scenes.values():
        if set(scene.participants) - entities: raise ValueError('Unknown participant identity')
        if not scene.required_beats or set(scene.required_beats) - beats.keys(): raise ValueError('Unresolved beat references')
        for b in scene.required_beats:
            if beats[b].scene_id != scene.object_id: raise ValueError('Scene/beat lineage mismatch')
        for knowledge in scene.knowledge_states:
            if knowledge.holder_id not in scene.participants: raise ValueError('Unknown knowledge holder')
            if set(knowledge.knows) & set(knowledge.does_not_know): raise ValueError('Conflicting character knowledge')
        for belief in scene.belief_states:
            if belief.holder_id not in scene.participants: raise ValueError('Unknown belief holder')
        for character in scene.character_states:
            if character.entity_id not in scene.participants: raise ValueError('Unknown character identity')
    for beat in beats.values():
        if beat.scene_id not in scenes or beat.object_id not in scenes[beat.scene_id].required_beats:
            raise ValueError('Orphan beat')
        if set(beat.participants) - set(scenes[beat.scene_id].participants): raise ValueError('Unknown entrant')
        if not beat.state_change or beat.purpose.state not in {'ESTABLISHED', 'INFERRED'}: raise ValueError('Meaningful state transition and purpose required')
        if all(k in beat.preconditions and digest(v.value) == digest(beat.preconditions[k].value)
               for k, v in beat.state_change.items()): raise ValueError('Beat has no state transition')
        if set(beat.required_information) & set(beat.hidden_information): raise ValueError('Reveal/hide conflict')
        if set(beat.dependencies) - beats.keys(): raise ValueError('Unbound beat dependency')
        if any(beats[d].order >= beat.order for d in beat.dependencies): raise ValueError('Cyclic/reversed beat order')
    for scene in scenes.values():
        orders = [beats[b].order for b in scene.required_beats]
        if orders != sorted(set(orders)): raise ValueError('Ambiguous scene ordering')
    audiences = {a.object_id: a for a in result['audiences']}
    for audience in audiences.values():
        if set(audience.knows) & set(audience.does_not_know): raise ValueError('Conflicting audience knowledge')
        if set(audience.must_understand) & set(audience.must_not_yet_understand): raise ValueError('Conflicting audience obligations')
        # Audience state never inherits world/character truth implicitly.
        for key, fact in audience.knows.items():
            if not fact.evidence: raise ValueError('Audience knowledge needs perceptual/narrative evidence')
    policies = value['policies']
    if type(policies) is not dict or set(policies) != set(beats): raise ValueError('Each beat needs explicit policy')
    policy_fields = {'audience_id', 'acceptable_classes', 'implementation_freedom', 'prohibited_interpretations'}
    for beat_id, policy in policies.items():
        if type(policy) is not dict or set(policy) != policy_fields or policy['audience_id'] not in audiences:
            raise ValueError('Explicit audience/policy required')
        for key in policy_fields - {'audience_id'}:
            if type(policy[key]) is not list or any(type(x) is not str or not x for x in policy[key]): raise ValueError('Policy list required')
        if set(policy['acceptable_classes']) - MECHANISMS: raise ValueError('Unknown mechanism class')
    return result, deepcopy(policies), deepcopy(source)


def governed(source, kind, value, *lineage):
    return dict(object_id=identity(kind, source.source_references, value), scope=source.scope,
                authority=source.authority, source_references=list(source.source_references),
                lineage=[source.object_id, *lineage], unresolved_questions=list(source.unresolved_questions))


def derive_requirements(models, policies):
    """Story transition + audience obligation -> perception/evidence requirement.

    Missing perceptual evidence is an unresolved obligation, not an invented shot.
    """
    audiences = {a.object_id: a for a in models['audiences']}
    scenes = {s.object_id: s for s in models['scenes']}
    requirements = []
    for beat in models['beats']:
        policy = policies[beat.object_id]; audience = audiences[policy['audience_id']]
        scene = scenes[beat.scene_id]
        required = sorted(set(beat.required_information) | set(audience.must_understand))
        hidden = sorted(set(beat.hidden_information) | set(audience.must_not_yet_understand))
        evidence = sorted({ref for key in required for ref in audience.required_evidence.get(key, [])})
        args = governed(beat, 'requirement', {'beat': beat.to_dict(), 'audience': audience.to_dict(), 'policy': policy}, audience.object_id)
        unresolved = args['unresolved_questions']
        if beat.purpose.state != 'ESTABLISHED': unresolved.append('INFERRED_PURPOSE_REQUIRES_REVIEW')
        if set(required) & set(hidden): unresolved.append('INFORMATION_CONFLICT')
        for key in required:
            if not audience.required_evidence.get(key): unresolved.append('PERCEPTUAL_EVIDENCE_UNRESOLVED:' + key)
        if not required: unresolved.append('AUDIENCE_EFFECT_UNRESOLVED')
        if not policy['acceptable_classes']: unresolved.append('MECHANISM_AUTHORITY_UNRESOLVED')
        for key, fact in beat.state_change.items():
            if fact.state != 'ESTABLISHED': unresolved.append('STATE_TRANSITION_UNRESOLVED:' + key)
        physical = {}
        for world in models['world_models']:
            for constraints in (world.laws, world.physical_constraints):
                for key, value in constraints.items():
                    if value.state != 'ESTABLISHED': unresolved.append('WORLD_CONSTRAINT_UNRESOLVED:' + key)
                    if key in physical and physical[key] != value:
                        unresolved.append('WORLD_CONSTRAINT_CONFLICT:' + key)
                    else: physical[key] = deepcopy(value)
        req = CinematicRequirement(**args, scene_id=beat.scene_id, beat_id=beat.object_id,
            source_story_requirement=beat.object_id, required_audience_state=deepcopy(audience.expected_transition),
            required_perception={k: deepcopy(audience.perceives.get(k, Fact())) for k in required},
            information_requirement=required, hidden_information=hidden,
            relationship_requirement=[x.object_id for x in scene.relationship_states],
            state_transition_requirement=deepcopy(beat.state_change), causal_requirement=deepcopy(beat.causal_link),
            emotional_requirement=deepcopy(beat.audience_effect), continuity_requirement=deepcopy(beat.continuity_inputs),
            physical_constraints=physical,
            acceptable_mechanism_classes=list(policy['acceptable_classes']), implementation_freedom=list(policy['implementation_freedom']),
            prohibited_interpretations=list(policy['prohibited_interpretations']), required_evidence=evidence,
            validation_rule='REQUIREMENT_BOUND_PERCEPTUAL_EVIDENCE_THEN_EXTERNAL_RP')
        requirements.append(req)
    return requirements


def structural_input(models, policies, source_reference, subject_id):
    """Existing chain/decomposition input: authored obligations, not proven events."""
    requirements = []; edges = []
    composition = {subject_id: {'children': [s.object_id for s in models['scenes']]}}
    for scene in models['scenes']:
        composition[scene.object_id] = {'children': list(scene.required_beats)}
    for beat in models['beats']:
        requirements.append({'requirement_id': beat.object_id, 'text': str(beat.purpose.value),
            'source_references': [source_reference], 'kind': 'REQUIREMENT'})
        common = {'requirement_ids': [beat.object_id], 'source_references': [source_reference],
            'authority_requirements': ['Selected authored source; no independent execution authority'],
            'invariants': ['No invented canon', 'Preserve hidden information'],
            'failure_condition': 'Required authored transition or perceptual evidence absent'}
        edges.append(dict(common, source=beat.object_id, target=beat.object_id + ':required_exit', type='TRANSITIONS_TO',
            evidence_requirements=list(beat.required_information) or ['Explicit audience evidence required']))
        audience_id = policies[beat.object_id]['audience_id']
        edges.append(dict(common, source=beat.object_id + ':perceptual_evidence', target=audience_id + ':' + beat.object_id,
            type='PROVES', evidence_requirements=list(beat.required_information) or ['Explicit audience evidence required']))
        for dependency in beat.dependencies:
            edges.append(dict(common, source=dependency, target=beat.object_id, type='PRESERVES',
                evidence_requirements=list(beat.continuity_inputs) or ['Continuity comparison required']))
    return {'requirements': requirements, 'relationships': edges, 'composition': composition}


def candidates(requirement, beat):
    """Generate class-level alternatives only within explicit authored freedom.

    Parameter values stay implementation choices. Eligibility is structural, not
    demonstrated feasibility or selection permission.
    """
    result = []
    for kind in dict.fromkeys(requirement.acceptable_mechanism_classes):
        args = governed(requirement, 'mechanism', {'requirement': requirement.to_dict(), 'class': kind})
        candidate = CinematicMechanism(**args, requirement_id=requirement.object_id, mechanism_class=kind,
            camera=Camera(subject=beat.participants[0] if len(beat.participants) == 1 else '',
                          visibility=list(requirement.information_requirement) if kind == 'CAMERA' else [],
                          reveal=list(requirement.information_requirement) if kind == 'CAMERA' else [],
                          conceal=list(requirement.hidden_information) if kind == 'CAMERA' else []),
            performance=Performance(action=deepcopy(beat.action), reaction=deepcopy(beat.reaction),
                                    emotional_intent=deepcopy(beat.audience_effect)) if kind == 'PERFORMANCE' else Performance(),
            delivered_information=list(requirement.information_requirement),
            implementation={'intent': deepcopy(beat.purpose)},
            expression_parameters={k: Fact() for k in EXPRESSION_PARAMETERS[kind]},
            risks=['PHYSICAL_AND_PERCEPTUAL_EFFECT_NOT_EXECUTED_OR_VALIDATED'])
        result.append(evaluate(candidate, requirement))
    return result


def evaluate(candidate, requirement):
    result = deepcopy(candidate)
    result.constraint_satisfaction = []; result.constraint_violations = []; result.authority_required = []
    if candidate.requirement_id != requirement.object_id or candidate.scope != requirement.scope:
        raise ValueError('Mechanism requirement lineage mismatch')
    if set(candidate.source_references) != set(requirement.source_references) or candidate.authority != requirement.authority:
        raise PermissionError('Mechanism source authority mismatch')
    if candidate.mechanism_class not in requirement.acceptable_mechanism_classes:
        result.constraint_violations.append('MECHANISM_CLASS_NOT_ALLOWED')
    if set(candidate.delivered_information) & set(requirement.hidden_information): result.constraint_violations.append('HIDDEN_INFORMATION_LEAK')
    if set(requirement.information_requirement) - set(candidate.delivered_information): result.constraint_violations.append('REQUIRED_INFORMATION_MISSING')
    if set(candidate.impacts) & set(requirement.prohibited_interpretations): result.constraint_violations.append('PROHIBITED_INTERPRETATION')
    if candidate.mechanism_class not in requirement.implementation_freedom: result.authority_required.append('MECHANISM_CHOICE_APPROVAL_REQUIRED')
    for dimension, fact in candidate.impacts.items():
        expected = requirement.physical_constraints.get(dimension) or requirement.continuity_requirement.get(dimension)
        if expected and fact.to_dict() != expected.to_dict(): result.constraint_violations.append('CONSTRAINT_CONFLICT:' + dimension)
        if fact.state != 'ESTABLISHED': result.authority_required.append('IMPACT_UNRESOLVED:' + dimension)
        if expected is None: result.authority_required.append('NEW_STATE_IMPACT_REQUIRES_AUTHORITY:' + dimension)
    result.unresolved_questions = sorted(set(result.unresolved_questions + requirement.unresolved_questions))
    if result.constraint_violations: result.state = 'CONFLICTING'
    elif result.authority_required or result.unresolved_questions: result.state = 'REQUIRES_AUTHORITY'
    else:
        result.state = 'ELIGIBLE'
        result.constraint_satisfaction = ['SOURCE_INTENT_PRESERVED', 'ALLOWED_CLASS', 'NO_DECLARED_INFORMATION_LEAK', 'NO_DECLARED_CONSTRAINT_CONFLICT']
    result.feasibility = 'UNPROVEN'
    return result


def continuity(previous, following, authorized_changes=None):
    """Dimension keys cover prop/pose/knowledge/etc without conflating their values.

    Missing proposed dimensions remain unresolved; unchanged ones are propagated.
    Authorized changes must be grounded authored facts, never a caller boolean.
    """
    changes = deepcopy(authorized_changes if authorized_changes is not None else following.authorized_continuity_changes)
    args = governed(following, 'continuity', {'previous': previous.to_dict(), 'following': following.to_dict(),
                                             'changes': {k: v.to_dict() for k, v in changes.items()}}, previous.object_id)
    def dimensions(obj, exiting):
        if isinstance(obj, BeatState):
            return {**deepcopy(obj.continuity_inputs), **deepcopy(obj.preconditions),
                    **(deepcopy(obj.state_change) if exiting else {}),
                    **(deepcopy(obj.continuity_outputs) if exiting else {})}
        state = {**deepcopy(obj.entry_state), **(deepcopy(obj.exit_state) if exiting else {})}
        for key, value in obj.environment.items(): state['environment/' + key] = deepcopy(value)
        for character in obj.character_states:
            for group in ('physical', 'emotional', 'goals', 'behavior'):
                for key, value in getattr(character, group).items(): state[character.entity_id + '/' + group + '/' + key] = deepcopy(value)
        for knowledge in obj.knowledge_states:
            for key, value in knowledge.knows.items(): state[knowledge.holder_id + '/knowledge/' + key] = deepcopy(value)
        for belief in obj.belief_states:
            for key, value in belief.believes.items(): state[belief.holder_id + '/belief/' + key] = deepcopy(value)
        for spatial in obj.spatial_states:
            for group in ('positions', 'orientations', 'movement', 'topology'):
                for key, value in getattr(spatial, group).items(): state['spatial/' + group + '/' + key] = deepcopy(value)
        for relationship in obj.relationship_states:
            for key, value in relationship.dimensions.items(): state['relationship/' + '|'.join(relationship.participants) + '/' + key] = deepcopy(value)
        state.update(deepcopy(obj.continuity_outputs if exiting else obj.continuity_inputs))
        return state
    expected = dimensions(previous, True)
    for key, fact in changes.items():
        if fact.state != 'ESTABLISHED' or fact.grounding != 'SUPPORTED': raise ValueError('Unresolved continuity authorization')
        expected[key] = fact
    proposed = dimensions(following, False)
    conflicts = []
    for key, fact in expected.items():
        if key not in proposed: args['unresolved_questions'].append('MISSING_CONTINUITY_DIMENSION:' + key)
        elif fact.state != 'ESTABLISHED' or proposed[key].state != 'ESTABLISHED': args['unresolved_questions'].append('UNRESOLVED_CONTINUITY:' + key)
        elif digest(fact.value) != digest(proposed[key].value): conflicts.append(key)
    return ContinuityRequirement(**args, previous_id=previous.object_id, next_id=following.object_id,
        expected=expected, proposed=proposed, authorized_changes=changes, conflicts=conflicts)


def audience_transition(audience, delivered, evidence, authority_reference):
    """Explicit source-authorized perceptual exposure only; never world-event copy."""
    result = deepcopy(audience)
    if not authority_reference or authority_reference not in audience.source_references:
        raise PermissionError('Audience exposure authority mismatch')
    for key in delivered:
        expected = audience.required_evidence.get(key, [])
        if key in audience.must_not_yet_understand or not expected or not set(expected) <= set(evidence):
            raise ValueError('Audience exposure unproven/prohibited')
        fact = audience.expected_transition.get(key)
        if fact is None or fact.state != 'ESTABLISHED': raise ValueError('Unknown audience meaning')
        result.knows[key] = deepcopy(fact); result.knows[key].evidence = list(expected)
        result.does_not_know = [x for x in result.does_not_know if x != key]
    result.version += 1; result.lineage.append(digest(audience.to_dict()))
    return result
