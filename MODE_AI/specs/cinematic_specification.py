"""Animation §48: lossless governed cinematic handoff, no execution approval.

This is the domain payload for an executor adapter, not a second Builder or RP.
Semantic constraints remain explicit when an executor cannot represent them.
"""
from copy import deepcopy
from dataclasses import fields, is_dataclass
from system_layer.contracts import digest
from understanding.cinematic_models import ExecutionSpecification, ShotRequirement, Fact
from understanding.cinematic_derivation import governed, continuity


def generate(models, requirements, mechanisms, selected_ids, understanding_reference, system_assessment):
    if not understanding_reference: raise ValueError('Governed Understanding reference required')
    candidates = {m.object_id: deepcopy(m) for m in mechanisms}
    if type(selected_ids) is not list or len(set(selected_ids)) != len(selected_ids) or set(selected_ids)-candidates.keys():
        raise ValueError('Exact unique candidate selections required')
    requirements_by_id = {r.object_id: r for r in requirements}
    beats = {b.object_id: b for b in models['beats']}
    scenes = {s.object_id: s for s in models['scenes']}
    shots = []; missing = []
    for requirement in requirements:
        selected = [candidates[i] for i in selected_ids if candidates[i].requirement_id == requirement.object_id]
        if not selected: missing.append('SELECTION_REQUIRED:' + requirement.object_id); continue
        if any(m.state != 'ELIGIBLE' for m in selected): raise PermissionError('Unresolved or conflicting candidate cannot be selected')
        for m in selected: m.state = 'SELECTED'
        beat = beats[requirement.beat_id]; scene = scenes[requirement.scene_id]
        args = governed(requirement, 'shot', [m.object_id for m in selected], *[m.object_id for m in selected])
        camera = next((m.camera for m in selected if m.mechanism_class == 'CAMERA'), None)
        blocking = next((m.blocking for m in selected if m.mechanism_class == 'BLOCKING'), None)
        performance = next((m.performance for m in selected if m.mechanism_class == 'PERFORMANCE'), None)
        extras = {k: deepcopy(v) for k, v in dict(camera=camera, blocking=blocking, performance=performance).items() if v is not None}
        shots.append(ShotRequirement(**args, scene_id=scene.object_id, beat_id=beat.object_id,
            requirement_id=requirement.object_id, mechanism_ids=[m.object_id for m in selected],
            purpose=deepcopy(beat.purpose), start_state=deepcopy(beat.preconditions), end_state=deepcopy(beat.state_change),
            delivered_information=list(requirement.information_requirement), withheld_information=list(requirement.hidden_information),
            action=deepcopy(beat.action), continuity_inputs=deepcopy(beat.continuity_inputs),
            continuity_outputs=deepcopy(beat.continuity_outputs), environment=deepcopy(scene.environment),
            required_evidence=list(requirement.required_evidence), failure_conditions=list(beat.failure_conditions),
            implementation_freedom=list(requirement.implementation_freedom), **extras))
    links = []
    for scene in models['scenes']:
        ordered = [beats[b] for b in scene.required_beats]
        for previous, following in zip(ordered, ordered[1:]):
            link = continuity(previous, following)
            links.append(link)
            missing.extend('CONTINUITY_CONFLICT:' + k for k in link.conflicts)
            missing.extend(link.unresolved_questions)
    for previous, following in zip(models['scenes'], models['scenes'][1:]):
        link = continuity(previous, following); links.append(link)
        missing.extend('SCENE_CONTINUITY_CONFLICT:' + k for k in link.conflicts)
        missing.extend(link.unresolved_questions)
    for req in requirements: missing.extend(req.unresolved_questions)
    first = models['scenes'][0]
    args = governed(first, 'execution-spec', {'models': {k: [v.to_dict() for v in values] for k, values in models.items()},
        'selection': selected_ids, 'understanding': understanding_reference, 'system': system_assessment})
    args['unresolved_questions'] = sorted(set(args['unresolved_questions'] + missing))
    spec = ExecutionSpecification(**args, **deepcopy(models), requirements=deepcopy(requirements),
        candidates=list(candidates.values()), shots=shots, continuity=links,
        required_proof=sorted({e for r in requirements for e in r.required_evidence}),
        understanding_reference=understanding_reference, system_assessment=deepcopy(system_assessment))
    # Each material fact is categorized; unknown camera numbers remain choices
    # only when the authored freedom actually permits that mechanism class.
    def visit(value, path):
        if isinstance(value, Fact):
            spec.dispositions[path] = 'REQUIRED' if value.state == 'ESTABLISHED' else 'UNRESOLVED'
        elif is_dataclass(value):
            for f in fields(value):
                if f.name != 'dispositions': visit(getattr(value, f.name), path + '/' + f.name)
        elif type(value) is list:
            for i, item in enumerate(value): visit(item, path + '/' + str(i))
        elif type(value) is dict:
            for k, item in value.items(): visit(item, path + '/' + k)
    visit(spec, '')
    for m in spec.candidates:
        spec.dispositions['mechanism:' + m.object_id] = 'AUTHORIZED' if m.state == 'SELECTED' else 'OPTIONAL'
    for shot in shots:
        for choice in shot.implementation_freedom:
            spec.dispositions['shot:' + shot.object_id + '/parameters/' + choice] = 'IMPLEMENTATION_CHOICE'
        for info in shot.withheld_information: spec.dispositions['shot:' + shot.object_id + '/reveal/' + info] = 'PROHIBITED'
    return spec


def executor_handoff(specification, target, supported_obligations):
    """Read-only package export. Unsupported semantics block readiness explicitly."""
    spec = ExecutionSpecification.from_dict(specification.to_dict())
    if target not in {'BUILDER', 'CODEX', 'PIPELINE', 'UNREAL_ADAPTER'}: raise ValueError('Unknown executor')
    if type(supported_obligations) is not list or any(type(x) is not str for x in supported_obligations):
        raise ValueError('Explicit executor capability contract required')
    required = sorted({r.object_id for r in spec.requirements} | set(spec.required_proof))
    unsupported = sorted(set(required) - set(supported_obligations))
    unresolved = list(spec.unresolved_questions)
    material_claims = []
    def inspect(value, path):
        if isinstance(value, Fact):
            disposition = spec.dispositions.get(path)
            if value.state != 'ESTABLISHED' and disposition in {'REQUIRED', 'AUTHORIZED'}:
                raise PermissionError('Unresolved or inferred specification fact was promoted: ' + path)
            material_claims.append({'path': path, 'epistemic_state': value.state,
                'rp_state': value.rp_state, 'source_references': list(value.source_references),
                'fact_hash': digest(value.to_dict()), 'disposition': disposition})
        elif is_dataclass(value):
            for field in fields(value):
                inspect(getattr(value, field.name), path + '/' + field.name)
        elif type(value) is list:
            for index, item in enumerate(value): inspect(item, path + '/' + str(index))
        elif type(value) is dict:
            for key, item in value.items(): inspect(item, path + '/' + key)
    inspect(spec, '')
    # A caller capability list is a declaration only, never a System/RP finding.
    state = 'UNPROVEN' if unsupported or unresolved else 'SPECIFICATION_PREPARED'
    return {'contract': 'CinematicExecutorHandoff/1', 'target': target, 'specification': spec.to_dict(),
        'specification_hash': digest(spec.to_dict()), 'state': state, 'unsupported_obligations': unsupported,
        'unresolved': unresolved, 'execution_authority': False, 'capability_proven': False,
        'external_rp_required': True, 'required_obligations': required,
        'material_claims': material_claims,
        'execution_readiness': {'state': 'NOT_READY', 'rp_state': 'PENDING_VALIDATION',
            'reason': 'Candidate preparation does not establish material claim admission or executor readiness',
            'specification_hash': digest(spec.to_dict()), 'executor_eligible': False},
        'field_map': {
            'world_state': 'world_states', 'world_laws': 'world_models[].laws',
            'entity_identity': 'entities[].identity', 'entity_models': 'entities',
            'physical_state': 'scenes[].character_states[].physical', 'character_state': 'scenes[].character_states',
            'knowledge_state': 'scenes[].knowledge_states', 'belief_state': 'scenes[].belief_states',
            'perspective_state': 'scenes[].perspective_state', 'truth_state_map': 'scenes[].truth_state_map',
            'relationship_state': 'scenes[].relationship_states', 'scene_objective': 'scenes[].scene_objective',
            'entry_state': 'scenes[].entry_state', 'exit_state': 'scenes[].exit_state',
            'required_beats': 'beats', 'required_transitions': 'scenes[].required_transitions',
            'information_movement': 'scenes[].information_movement', 'causal_requirements': 'scenes[].causal_requirements',
            'physical_constraints': 'world_models[].physical_constraints', 'audience_state': 'audiences',
            'required_audience_state': 'requirements[].required_audience_state',
            'required_perceptual_evidence': 'requirements[].required_evidence', 'continuity_invariants': 'continuity[].expected',
            'cinematic_requirements': 'requirements', 'candidate_mechanisms': 'candidates',
            'selected_mechanisms': 'candidates[state=SELECTED]', 'shot_requirements': 'shots',
            'performance_requirements': 'shots[].performance', 'sound_requirements': 'candidates[mechanism_class=SOUND].expression_parameters',
            'environment_requirements': 'shots[].environment', 'implementation_freedom': 'requirements[].implementation_freedom',
            'required_proof': 'required_proof', 'unresolved_questions': 'unresolved_questions'},
        'source_to_shot_lineage': {s.object_id: [*s.source_references, spec.understanding_reference,
            s.scene_id, s.beat_id, s.requirement_id, *s.mechanism_ids] for s in spec.shots}}
