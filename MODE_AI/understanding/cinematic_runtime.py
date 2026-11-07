"""Cinematic commands on the existing /creative custody and Understanding path.

All stages are locally persisted as candidate DOCUMENTs using the exact incoming
Operator approval. No fabricated approval, source replacement or execution.
"""
import json
from copy import deepcopy
from specs.document_service import DocumentService
from specs.cinematic_specification import generate, executor_handoff
from system_layer.contracts import authorize, digest
from data_governance.document_admission import _DOCUMENT_WRITER
from .cinematic_models import loads, ExecutionSpecification
from .cinematic_derivation import parse_story, derive_requirements, candidates, structural_input
from .understanding_engine import UnderstandingRequest
from .understanding_record import Evidence, normalize_meaning
from .semantic_custody_policy import AuthorityContext, AuthorityLevel


def _documents(runtime):
    return DocumentService(runtime.understanding_engine.store.path.with_name('content_custody.sqlite3'))


def _source(runtime, request):
    docs = _documents(runtime); owner = runtime.context.identity.operator_id
    ref = request['reference']
    if type(ref) is not dict or set(ref) != {'object_id', 'version', 'expected_hash'}: raise ValueError('Pinned source required')
    source = docs.retrieve(owner, **ref)
    if source['metadata']['project_id'] != request['project_id']: raise PermissionError('Project mismatch')
    if source['metadata']['kind'] not in {'CANON', 'AUTHORITATIVE', 'SPECIFICATION'}:
        raise PermissionError('Candidate document is not authored cinematic authority')
    # A changed selected source requires a new processing approval.
    if docs.store.history('DOCUMENT', owner, ref['object_id'])[-1]['record_hash'] != ref['expected_hash']:
        raise PermissionError('Stale cinematic source selection')
    if len(source['content'].encode('utf-8')) > 2_000_000: raise ValueError('Cinematic source bound exceeded')
    if 'story_selection' in request:
        from .story_source import load_story
        interpretation, parsed, lineage = load_story(docs, owner, request)
        source = dict(source, story_interpretation=interpretation, story_lineage=lineage)
        return docs, source, parsed
    return docs, source, parse_story(loads(source['content']), request['project_id'])


def _persist(docs, owner, thread, source, stage, value, request, approval):
    encoded = json.dumps(value, ensure_ascii=False, sort_keys=True, allow_nan=False)
    if len(encoded.encode('utf-8')) > 2_000_000: raise ValueError('Cinematic stage output bound exceeded')
    object_id = 'cinematic:' + stage + ':' + digest({'request': request, 'value': value})
    history = docs.store.history('DOCUMENT', owner, object_id)
    if history:
        existing = history[-1]
        if existing['content'] != encoded: raise ValueError('Stage identity collision')
        return {'object_id': object_id, 'version': existing['version'], 'expected_hash': existing['record_hash']}
    record = docs.store.append('DOCUMENT', owner, object_id, encoded,
        {'project_id': source['metadata']['project_id'], 'thread_id': thread, 'kind': 'GENERATED_CANDIDATE',
         'visual_authority': 'GENERATED_CANDIDATE', 'knowledge_class': source['metadata']['knowledge_class'],
         'authority': 'DERIVED_FROM_SELECTED_AUTHORED_INTENT', 'source_reference': source['record_hash'],
         'stage': stage, 'derivation_request': deepcopy(request), 'claims_validated': False, 'execution_authority': False},
        expected_previous=None, authorization=deepcopy(approval),document_admission=_DOCUMENT_WRITER)
    return {'object_id': object_id, 'version': record['version'], 'expected_hash': record['record_hash']}


def execute(runtime, action, request, approval):
    owner = runtime.context.identity.operator_id; thread = runtime.context.active_thread.thread_id
    if action not in {'interpret', 'derive', 'specify', 'handoff', 'compare_frames', 'compare_audio', 'review_candidate'}: raise ValueError('Unsupported cinematic action')
    base = {'reference', 'project_id'}
    expected = (base | {'stage', 'provider_status', 'output_text', 'prior_references'} if action == 'review_candidate'
                else base | {'story_selection'} if action == 'interpret'
                else base if action == 'derive' else base | {'candidate_reference', 'selected_ids'} if action == 'specify'
                else {'specification_reference', 'requirement_id', 'frame_references'} if action == 'compare_frames'
                else {'specification_reference', 'requirement_id', 'audio_reference'} if action == 'compare_audio'
                else {'specification_reference', 'target', 'supported_obligations'})
    optional = {'operational_binding'} if action == 'specify' else set()
    if action in {'derive', 'specify'}: optional.add('story_selection')
    if type(request) is not dict or not expected <= set(request) or set(request)-expected-optional: raise ValueError('Exact cinematic request required')
    if action in {'interpret', 'derive', 'specify'}: runtime.context.understanding_result = None
    authorize(owner, 'CINEMATIC_' + action.upper(), request, approval)
    docs = _documents(runtime)
    if action == 'review_candidate':
        from .cinematic_stages import inspect_candidate
        docs, source, _ = _source(runtime, request)
        # Prior hashes must resolve to actual same-owner/project/source stages,
        # not arbitrary strings claiming that upstream work happened.
        prior = {}
        for stage, ref in request['prior_references'].items():
            record = docs.retrieve(owner, **ref)
            if (record['metadata'].get('stage') != 'provider_candidate_' + stage or
                    record['metadata']['source_reference'] != source['record_hash']):
                raise ValueError('Unbound prior provider stage')
            content = loads(record['content'])
            if content['assessment']['state'] != 'CANDIDATE_REQUIRES_GROUNDING': raise ValueError('Rejected prior stage')
            prior[stage] = record['record_hash']
        assessment = inspect_candidate(request['stage'], request['provider_status'], request['output_text'], source['record_hash'], prior)
        reference = _persist(docs, owner, thread, source, 'provider_candidate_' + request['stage'],
            {'assessment': assessment, 'output_text': request['output_text']}, request, approval)
        return {'contract': 'CinematicProviderReview/1', 'assessment': assessment, 'reference': reference,
                'canon_accepted': False, 'execution_authority': False}
    if action in {'handoff', 'compare_frames', 'compare_audio'}:
        record = docs.retrieve(owner, **request['specification_reference'])
        if record['metadata'].get('stage') != 'specification': raise ValueError('Not a governed cinematic specification')
        value = loads(record['content'])
        selected_source = value['selected_source']
        _source(runtime, selected_source)  # No stale-source handoff.
        from .understanding_record import digest as semantic_digest
        governed_meaning = value['governed_understanding']
        current = runtime.understanding_engine.store.get(owner, governed_meaning['understanding_id'])
        if current is None or semantic_digest(current) != governed_meaning['understanding_hash']:
            raise PermissionError('Cinematic Understanding has changed; rederive before handoff')
        spec = ExecutionSpecification.from_dict(value['specification'])
        if action in {'compare_frames', 'compare_audio'}:
            from .cinematic_validation import compare
            from .creative_production import CreativePreparation
            requirements = {r.object_id: r for r in spec.requirements}
            if request['requirement_id'] not in requirements: raise ValueError('Unknown requirement')
            refs = request['frame_references'] if action == 'compare_frames' else [request['audio_reference']]
            if type(refs) is not list or not 1 <= len(refs) <= 32: raise ValueError('Bounded exact frame selection required')
            contents = []
            for ref in refs:
                if type(ref) is not dict or set(ref) != {'object_id', 'version', 'expected_hash'}: raise ValueError('Exact frame reference required')
                frame = docs.retrieve(owner, **ref)
                if frame['metadata']['project_id'] != spec.scope: raise PermissionError('Frame project mismatch')
                contents.append(frame['content'])
            if action == 'compare_frames':
                result = compare(requirements[request['requirement_id']], frame_contents=contents)
            else:
                import base64
                audio = loads(contents[0])
                if (type(audio) is not dict or set(audio) != {'schema_version', 'encoding', 'data', 'sha256'} or
                        audio['schema_version'] != 'AudioSource/1' or audio['encoding'] != 'BASE64_WAV'):
                    raise ValueError('Exact audio source required')
                if len(audio['data']) > 12_000_000: raise ValueError('Audio bound exceeded')
                result = compare(requirements[request['requirement_id']], pcm=base64.b64decode(audio['data'], validate=True), pcm_hash=audio['sha256'])
            result.update(specification_reference=request['specification_reference'], evidence_references=deepcopy(refs))
            observation = runtime.runtime_observation_collector.collect(operator_id=owner, thread_id=thread,
                trace_reference=digest(request), runtime_error=None if result['comparison'] == 'MATCH' else result['comparison'],
                metadata={'runtime_component': 'understanding.cinematic_validation', 'project_id': spec.scope,
                    'creative_evidence_kind': 'CINEMATIC_REQUIREMENT_COMPARISON', 'source_references': deepcopy(refs),
                    'specification_reference': request['specification_reference'], 'requirement_id': request['requirement_id'],
                    'observed_outcome': result, 'required_evidence_fields': ['observed_outcome']})
            CreativePreparation._require_persisted_observation(runtime.runtime_observation_collector, observation)
            result.update(observation_id=observation.observation_id, observation_hash=digest(observation.to_dict()))
            return result
        result = executor_handoff(spec, request['target'], request['supported_obligations'])
        result['specification_reference'] = request['specification_reference']
        result['selected_source'] = selected_source
        if 'story_lineage' in value: result['story_lineage'] = value['story_lineage']
        return result
    runtime.context.understanding_result = None
    docs, source, parsed = _source(runtime, request)
    story_refs = {}
    if 'story_interpretation' in source:
        interpretation = source['story_interpretation']
        for stage in interpretation.stages:
            story_refs[stage['stage']] = _persist(docs, owner, thread, source, 'story_' + stage['stage'], stage, request, approval)
        story_refs['interpretation'] = _persist(docs, owner, thread, source, 'story_interpretation', source['story_lineage'], request, approval)
        if parsed is None:
            return {'contract': 'StoryInterpretation/1', 'state': 'UNRESOLVED', 'references': story_refs,
                    'interpretation': interpretation.to_dict(), 'claims_validated': False, 'execution_authority': False}
    models, policies, facts = parsed
    if 'story_selection' in request: base = base | {'story_selection'}
    selected_source = {k: deepcopy(request[k]) for k in base}
    runtime.context.understanding_result = None
    meaning = json.dumps({'cinematic_authored_story': source['content_hash'], 'source_reference': source['record_hash'],
                          **({'story_selection_hash': digest(request['story_selection'])} if 'story_selection' in request else {})}, sort_keys=True)
    interpreted = {'subject_id': 'cinematic:' + source['object_id'], 'subject_type': 'AUTHORED_CREATIVE_INTENT',
        'semantic_domain': 'OPERATOR', 'meaning': meaning, 'scope': request['project_id'],
        'claim': {'predicate': 'selected_authored_story', 'value': source['content_hash']},
        'source_references': [source['record_hash']]}
    interpreted.update(structural_input(models, policies, source['record_hash'], interpreted['subject_id']))
    understood = runtime.understanding_engine.process(UnderstandingRequest(owner, thread, meaning,
        project_id=request['project_id'], request_id='cinematic:' + digest(selected_source), interpreted_input=interpreted,
        authoritative_document_context={'source_reference': source['record_hash'], 'interpretation': interpreted},
        authority_context=AuthorityContext(owner, AuthorityLevel.AUTHORIZED_OPERATOR, 'OPERATOR', authenticated=True,
            confirmation_reference='operator-approval:' + digest(approval)),
        evidence=(Evidence('operator-approval:' + digest(approval), 'OPERATOR_STATEMENT', True, 'OPERATOR', normalize_meaning(meaning)),
                  Evidence(source['record_hash'], 'DOCUMENT', False, 'OPERATOR'))))
    runtime.context.understanding_result = understood
    if understood.errors or understood.to_dict().get('review_required'):
        raise PermissionError('Semantic custody review required before cinematic derivation')
    governed_meaning = understood.governed_handoff()
    references = dict(story_refs)
    references['understanding'] = _persist(docs, owner, thread, source, 'understanding', understood.to_dict(), request, approval)
    references['scene_audience'] = _persist(docs, owner, thread, source, 'scene_audience',
        {k: [x.to_dict() for x in values] for k, values in models.items()}, request, approval)
    requirements = derive_requirements(models, policies)
    references['requirements'] = _persist(docs, owner, thread, source, 'requirements',
        [r.to_dict() for r in requirements], request, approval)
    beats = {b.object_id: b for b in models['beats']}
    mechanisms = [m for r in requirements for m in candidates(r, beats[r.beat_id])]
    candidate_value = {'selected_source': selected_source, 'requirements': [r.to_dict() for r in requirements],
                       'candidates': [m.to_dict() for m in mechanisms]}
    references['candidates'] = _persist(docs, owner, thread, source, 'candidates', candidate_value, selected_source, approval)
    result = {'contract': 'CinematicDerivation/1', 'state': 'DERIVED_CANDIDATES', 'references': references,
        **candidate_value, 'claims_validated': False, 'execution_authority': False}
    if 'story_interpretation' in source: result['interpretation'] = source['story_interpretation'].to_dict()
    if action in {'specify', 'interpret'}:
        if action == 'specify':
            prior = docs.retrieve(owner, **request['candidate_reference'])
            if prior['metadata'].get('stage') != 'candidates' or loads(prior['content']) != candidate_value:
                raise PermissionError('Selection must bind exact current derived candidates')
        # Existing System owner supplies capability evaluations through /creative
        # operations. No operational binding is invented by this domain stage.
        system_assessment = {'state': 'UNPROVEN', 'required_operation': '/creative operations',
            'capability_reference': None, 'execution_authority': False}
        if 'operational_binding' in request:
            from .creative_production import CreativePreparation
            from system_layer.runtime import service
            binding = request['operational_binding']
            if type(binding) is not dict or set(binding) != {'preparation', 'bindings'}:
                raise ValueError('Exact existing creative operational binding required')
            if binding['preparation']['request']['project_id'] != request['project_id']:
                raise PermissionError('Operational binding project mismatch')
            system_assessment = CreativePreparation(docs.store.path).operational_models(owner,
                binding['preparation'], binding['bindings'], system_store=service(runtime).store)
        spec = generate(models, requirements, mechanisms, request.get('selected_ids', []), references['understanding']['expected_hash'], system_assessment)
        analysis = understood.to_dict()
        spec.understanding_analysis = {key: deepcopy(analysis[key]) for key in (
            'system_relationships', 'chain_recognition_result', 'chain_relationship_map', 'decomposition_result',
            'governing_principle_result', 'mechanism_derivation_result', 'structural_gaps', 'specification_readiness') if key in analysis}
        try:
            understood.specification_handoff()
        except PermissionError:
            # A draft is inspectable; existing readiness cannot be bypassed by a
            # new cinematic exporter. Its unresolved obligation reaches handoff.
            spec.unresolved_questions.append('UNDERSTANDING_SPECIFICATION_READINESS_BLOCKED:' + str(understood.specification_readiness.value))
        value = {'selected_source': selected_source, 'specification': spec.to_dict(), 'stage_references': references,
            'governed_understanding': {k: governed_meaning[k] for k in ('understanding_id', 'version', 'understanding_hash')}}
        if 'story_lineage' in source: value['story_lineage'] = source['story_lineage']
        references['specification'] = _persist(docs, owner, thread, source, 'specification', value, request, approval)
        result.update(contract='CinematicSpecification/1', state='UNPROVEN' if spec.unresolved_questions else 'SPECIFICATION_PREPARED',
                      specification=spec.to_dict(), specification_hash=digest(spec.to_dict()))
    return result
