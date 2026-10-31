"""Deterministic authored fixtures; no provider, Unreal or Pipeline execution."""
import base64
from copy import deepcopy
import hashlib
import io
import json
from types import SimpleNamespace as NS
import pytest
from PIL import Image
from understanding.cinematic_models import *
from understanding.cinematic_derivation import parse_story, derive_requirements, candidates, evaluate, continuity, audience_transition
from specs.cinematic_specification import generate, executor_handoff
from understanding.cinematic_validation import compare
from understanding import UnderstandingEngine, UnderstandingStore
from specs.document_service import DocumentService
from integration.content_custody import execute
from system_layer.contracts import digest


def fact(value, name='x'):
    return Fact(value, 'ESTABLISHED', ['fact:' + name], [], 'SUPPORTED')


def meta(name):
    return dict(object_id=name, scope='p', authority='operator-authored', source_references=['fact:purpose'])


def story():
    purpose = fact('Let audience notice the signal', 'purpose')
    change = fact(True, 'noticed')
    beat = BeatState(**meta('beat'), scene_id='scene', purpose=purpose, participants=['person'],
        preconditions={'noticed': fact(False, 'unnoticed')}, trigger=fact('signal', 'signal'),
        action=fact('looks toward signal', 'look'), state_change={'noticed': change},
        required_information=['signal'], hidden_information=['sender'],
        continuity_inputs={'prop': fact('held', 'held')}, continuity_outputs={'prop': fact('held', 'held')})
    scene = SceneState(**meta('scene'), participants=['person'], scene_objective=purpose,
        required_beats=['beat'], environment={'weather': Fact(), 'time': Fact()},
        entry_state=deepcopy(beat.preconditions), exit_state=deepcopy(beat.state_change),
        knowledge_states=[KnowledgeState(**meta('knowledge'), holder_id='person', does_not_know=['sender'])],
        belief_states=[BeliefState(**meta('belief'), holder_id='person', believes={'sender': Fact('friend','INFERRED',['fact:signal'],[],'REASONABLE_INFERENCE')})],
        truth_state_map={'sender': Fact()})
    audience = AudienceState(**meta('audience'), does_not_know=['signal', 'sender'],
        must_understand=['signal'], must_not_yet_understand=['sender'], expected_transition={'signal': change},
        required_evidence={'signal': ['NONBLACK_FRAME', 'SIGNAL_VISIBLE']}, perceives={'signal': Fact()})
    model = dict(world_models=[WorldModel(**meta('world'))], world_states=[WorldState(**meta('world-state'))],
        entities=[EntityModel(**meta('person'), identity={'name': fact('person','name')})],
        narratives=[NarrativeState(**meta('narrative'), objective=purpose)],
        truth_states=[TruthState(**meta('truth'), world_truth={'sender': Fact()})],
        scenes=[scene], beats=[beat], audiences=[audience])
    source = {'fact:purpose': purpose.value, 'fact:noticed': True, 'fact:unnoticed': False,
              'fact:signal': 'signal', 'fact:look': 'looks toward signal', 'fact:held': 'held', 'fact:name': 'person'}
    return dict(schema_version='CinematicStory/1', source_facts=source,
        policies={'beat': dict(audience_id='audience', acceptable_classes=['CAMERA','PERFORMANCE'],
            implementation_freedom=['CAMERA','PERFORMANCE'], prohibited_interpretations=['sender'])},
        **{k: [x.to_dict() for x in v] for k,v in model.items()})


def prepared():
    models, policies, source = parse_story(story(),'p')
    req = derive_requirements(models,policies)
    options = candidates(req[0], models['beats'][0])
    return models, req, options


def test_complete_contract_roundtrip_and_derived_lineage():
    models, requirements, options = prepared()
    spec = generate(models,requirements,options,[m.object_id for m in options],'understanding:hash',{'state':'UNPROVEN'})
    assert ExecutionSpecification.from_dict(loads(json.dumps(spec.to_dict()))).to_dict() == spec.to_dict()
    assert spec.scenes == models['scenes'] and spec.world_models == models['world_models']
    assert spec.shots[0].purpose == models['beats'][0].purpose
    assert spec.shots[0].requirement_id == requirements[0].object_id
    assert set(spec.shots[0].mechanism_ids) == {m.object_id for m in options}
    assert spec.shots[0].withheld_information == ['sender']
    assert not spec.execution_authority and spec.validation_state == 'UNVALIDATED'
    assert generate(models,requirements,options,[m.object_id for m in options],'understanding:hash',{'state':'UNPROVEN'}).object_id == spec.object_id


@pytest.mark.parametrize('state',['PASS','VALID','CONFIRMED','anything'])
def test_upstream_labels_cannot_establish_reality(state):
    with pytest.raises(ValueError): SceneState(**meta('x'),validation_state=state)
    with pytest.raises(ValueError): Fact('value',state,['fact:x'])


@pytest.mark.parametrize('field,value',[('weather','rain'),('time','dusk'),('entrant','father'),('completion','search completed')])
def test_unsupported_source_dimension_rejected(field,value):
    source=story(); source['scenes'][0]['environment'][field]=fact(value,'purpose').to_dict()
    with pytest.raises(ValueError,match='grounding mismatch'):parse_story(source,'p')


def test_unknown_participant_and_conflicting_fact_rejected():
    source=story();source['beats'][0]['participants'].append('invented')
    with pytest.raises(ValueError,match='Unknown entrant'):parse_story(source,'p')
    source=story();source['source_facts']['fact:held']='lost'
    with pytest.raises(ValueError,match='grounding mismatch'):parse_story(source,'p')


def test_world_event_does_not_create_audience_knowledge():
    models, req, options=prepared();aud=models['audiences'][0]
    assert not aud.knows and models['beats'][0].state_change['noticed'].value
    with pytest.raises(ValueError):audience_transition(aud,['signal'],[],'fact:purpose')
    updated=audience_transition(aud,['signal'],['NONBLACK_FRAME','SIGNAL_VISIBLE'],'fact:purpose')
    assert updated.knows['signal'].value and 'signal' not in updated.does_not_know
    assert not aud.knows and not models['scenes'][0].knowledge_states[0].knows
    with pytest.raises(ValueError):audience_transition(aud,['sender'],['NONBLACK_FRAME'],'fact:purpose')


@pytest.mark.parametrize('who',['audience','character'])
def test_knowledge_asymmetry_and_belief_remain_distinct(who):
    source=story();known=fact(True,'noticed').to_dict();known['evidence']=['authored_perception']
    if who=='audience':
        source['audiences'][0]['knows']={'signal':known};source['audiences'][0]['does_not_know']=['sender']
    else: source['scenes'][0]['knowledge_states'][0]['knows']={'signal':known}
    models,_,_=parse_story(source,'p')
    assert bool(models['audiences'][0].knows) == (who=='audience')
    assert bool(models['scenes'][0].knowledge_states[0].knows) == (who=='character')
    assert models['scenes'][0].truth_state_map['sender'].state=='UNKNOWN'
    assert models['scenes'][0].belief_states[0].believes['sender'].state=='INFERRED'


@pytest.mark.parametrize('dimension',['identity','appearance','clothing','damage','prop','position','orientation','movement',
    'environment','lighting','time','weather','physics','knowledge','belief','relationship','emotion','causality'])
def test_continuity_dimension_conflict_missing_and_authorized_change(dimension):
    previous=BeatState(**meta('before'),continuity_outputs={dimension:fact('lost')})
    following=BeatState(**meta('after'),continuity_inputs={dimension:fact('held')})
    result=continuity(previous,following)
    assert result.conflicts==[dimension] and result.expected[dimension].value=='lost'
    assert not continuity(previous,following,{dimension:fact('held')}).conflicts
    following.continuity_inputs={}
    assert continuity(previous,following).unresolved_questions==['MISSING_CONTINUITY_DIMENSION:'+dimension]


@pytest.mark.parametrize('kind',sorted(MECHANISMS))
def test_all_mechanism_classes_need_explicit_policy(kind):
    models, req, _=prepared();req[0].acceptable_mechanism_classes=[kind];req[0].implementation_freedom=[kind]
    option=candidates(req[0],models['beats'][0])[0]
    assert option.mechanism_class==kind and option.state=='ELIGIBLE' and option.feasibility=='UNPROVEN'
    req[0].implementation_freedom=[]
    assert evaluate(option,req[0]).state=='REQUIRES_AUTHORITY'


def test_conflicting_mechanism_cannot_be_selected():
    models,req,options=prepared();bad=options[0];bad.delivered_information.append('sender')
    evaluated=evaluate(bad,req[0]);assert evaluated.state=='CONFLICTING'
    with pytest.raises(PermissionError):generate(models,req,[evaluated],[evaluated.object_id],'understanding',{})
    bad=deepcopy(options[1]);bad.mechanism_class='DIALOGUE'
    assert 'MECHANISM_CLASS_NOT_ALLOWED' in evaluate(bad,req[0]).constraint_violations


def test_no_silent_selection_or_executor_success():
    models,req,options=prepared()
    spec=generate(models,req,options,[],'understanding',{})
    assert any(x.startswith('SELECTION_REQUIRED') for x in spec.unresolved_questions)
    handoff=executor_handoff(spec,'BUILDER',[])
    assert handoff['state']=='UNPROVEN' and handoff['unsupported_obligations'] and not handoff['execution_authority']
    assert handoff['specification']==spec.to_dict()


def test_six_specification_dispositions_and_no_numeric_fabrication():
    models,req,options=prepared()
    spec=generate(models,req,options,[options[0].object_id],'understanding',{})
    assert set(spec.dispositions.values())==DISPOSITIONS
    assert spec.shots[0].camera.lens.value is None


def image(color):
    data=io.BytesIO()
    with Image.new('RGB',(2,2),color) as im:im.save(data,format='PNG')
    raw=data.getvalue()
    return json.dumps(dict(schema_version='ImageSource/1',encoding='BASE64',data=base64.b64encode(raw).decode(),sha256=hashlib.sha256(raw).hexdigest()))


@pytest.mark.parametrize('expected,color,result',[('BLACK_FRAME','black','MATCH'),('BLACK_FRAME','red','MISMATCH'),
    ('NONBLACK_FRAME','black','MISMATCH'),('NONBLACK_FRAME','red','MATCH'),('CHARACTER_VISIBLE','red','UNRESOLVED'),
    ('CHARACTER_VISIBLE','black','MISMATCH'),('ACTION_VISIBLE','black','MISMATCH')])
def test_requirement_bound_pixels_not_semantic_truth(expected,color,result):
    _,req,_=prepared();req[0].required_evidence=[expected]
    actual=compare(req[0],frame_contents=[image(color)])
    assert actual['comparison']==result and actual['claim_state']=='PENDING_VALIDATION'
    assert not actual['character_visibility_proven'] and not actual['cinematic_success_proven']


def test_uninspectable_evidence_and_empty_requirements_do_not_pass():
    _,req,_=prepared();assert compare(req[0],frame_contents=['bad'])['comparison']=='UNRESOLVED'
    req[0].required_evidence=[];assert compare(req[0])['comparison']=='UNRESOLVED'


def runtime_fixture(tmp_path, source=None):
    runtime=NS(context=NS(identity=NS(operator_id='op'),active_thread=NS(thread_id='t')),
        understanding_engine=UnderstandingEngine(UnderstandingStore(tmp_path/'meaning.db')))
    runtime.events=[]
    runtime._observe_runtime_event=lambda name,payload,**kw:runtime.events.append((name,payload))
    docs=DocumentService(tmp_path/'content_custody.sqlite3')
    request=dict(object_id='story',content=json.dumps(source or story()),kind='CANON',visual_authority='NOT_APPLICABLE',
        knowledge_class='INTERNAL',source_reference='operator:story',authority='operator',project_id='p',thread_id='t',
        expected_previous=None,validation_references=[])
    record=docs.intake('op',request,dict(operator_id='op',action='DOCUMENT_INTAKE',decision='APPROVE',hash=digest(request)))
    return runtime,docs,dict(reference=dict(object_id='story',version=record['version'],expected_hash=record['record_hash']),project_id='p')


def command(runtime,action,request,approval=True):
    payload={'request':request,'approval':dict(operator_id='op',action='CINEMATIC_'+action.upper(),decision='APPROVE',hash=digest(request)) if approval else {}}
    return execute(runtime,'/creative cinematic '+action+' '+json.dumps(payload))


def test_real_creative_command_source_understanding_selection_spec_handoff(tmp_path):
    runtime,docs,request=runtime_fixture(tmp_path)
    with pytest.raises(PermissionError):command(runtime,'derive',request,False)
    derived=command(runtime,'derive',request)
    assert derived['candidates'] and runtime.context.understanding_result
    for ref in derived['references'].values():assert docs.retrieve('op',**ref)['metadata']['kind']=='GENERATED_CANDIDATE'
    selection=dict(**request,candidate_reference=derived['references']['candidates'],selected_ids=[derived['candidates'][0]['object_id']])
    specified=command(runtime,'specify',selection)
    analysis=specified['specification']['understanding_analysis']
    assert analysis['system_relationships'] and analysis['chain_recognition_result']['chain_records']
    assert analysis['decomposition_result'] and analysis['mechanism_derivation_result']
    assert any(x.startswith('UNDERSTANDING_SPECIFICATION_READINESS_BLOCKED') for x in specified['specification']['unresolved_questions'])
    handoff=command(runtime,'handoff',dict(specification_reference=specified['references']['specification'],target='PIPELINE',supported_obligations=[]))
    assert handoff['specification']['scenes'][0]['scene_objective']==story()['scenes'][0]['scene_objective']
    assert handoff['state']=='UNPROVEN' and not handoff['execution_authority']
    assert handoff['selected_source']==request
    assert runtime.events[-1][1]['result_contract']=='CinematicExecutorHandoff/1'
    # Exact source bytes/authority have not been rewritten by generated stages.
    assert docs.retrieve('op',**request['reference'])['content']==json.dumps(story())


def test_missing_perception_stays_unresolved_and_selection_fails():
    source=story();source['audiences'][0]['required_evidence']={}
    models,policies,_=parse_story(source,'p');req=derive_requirements(models,policies)
    options=candidates(req[0],models['beats'][0])
    assert options[0].state=='REQUIRES_AUTHORITY'
    with pytest.raises(PermissionError):generate(models,req,options,[options[0].object_id],'understanding',{})


@pytest.mark.parametrize('bad',['{"x":1,"x":2}','{"x":NaN}'])
def test_strict_json(bad):
    with pytest.raises(ValueError):loads(bad)


@pytest.mark.parametrize('status',['incomplete','failed','cancelled','in_progress'])
def test_nonempty_incomplete_provider_result_is_not_accepted(status):
    from agents.reasoning_agent import ReasoningAgent
    agent=ReasoningAgent.__new__(ReasoningAgent)
    agent.provider='openai';agent.model='fixture';agent.temperature=0;agent.max_tokens=800
    agent.client=NS(responses=NS(create=lambda **kw:NS(output_text='partial output',status=status,usage=None)))
    telemetry=[];agent._persist_telemetry=lambda t:telemetry.append(t)
    with pytest.raises(RuntimeError,match='not completed'):
        agent._call_model('fixture',interaction_id='i',reasoning_id='r',stage='final')
    assert telemetry[0].status=='ERROR'


@pytest.mark.parametrize('status,text,reason',[
    ('incomplete','{"partial":','PROVIDER_NOT_COMPLETED'),
    ('completed','{"partial":','INVALID_STAGE_OR_LINEAGE'),
    ('completed','x'*64001,'STAGE_BOUND_EXCEEDED')], ids=['incomplete','invalid-json','oversized'])
def test_provider_stage_is_bounded_and_no_retry(status,text,reason):
    from understanding.cinematic_stages import inspect_candidate
    result=inspect_candidate('SCENE',status,text,'source',{})
    assert result['state']=='REJECTED' and result['reason']==reason
    assert not result['retry'] and not result['canon_accepted']


def test_provider_stage_lineage_and_output_never_become_canon():
    from understanding.cinematic_stages import inspect_candidate
    payload={'stage':'AUDIENCE','source_reference':'source','prior_references':{'SCENE':'hash'},'payload':{'knows':{}}}
    result=inspect_candidate('AUDIENCE','completed',json.dumps(payload),'source',{'SCENE':'hash'})
    assert result['state']=='CANDIDATE_REQUIRES_GROUNDING' and not result['canon_accepted']
    with pytest.raises(ValueError):inspect_candidate('AUDIENCE','completed','{}','source',{})


def test_stale_source_and_tampered_candidate_cannot_handoff(tmp_path):
    runtime,docs,request=runtime_fixture(tmp_path);derived=command(runtime,'derive',request)
    selection=dict(**request,candidate_reference=deepcopy(derived['references']['candidates']),selected_ids=[derived['candidates'][0]['object_id']])
    selection['candidate_reference']['expected_hash']='bad'
    with pytest.raises(ValueError):command(runtime,'specify',selection)
    old=docs.retrieve('op',**request['reference'])
    replacement=dict(object_id='story',content=old['content'],expected_previous=old['record_hash'],**old['metadata'])
    docs.intake('op',replacement,dict(operator_id='op',action='DOCUMENT_INTAKE',decision='APPROVE',hash=digest(replacement)))
    with pytest.raises(PermissionError,match='Stale'):command(runtime,'derive',request)
    assert runtime.context.understanding_result is None


def test_provider_rejection_persisted_through_real_command(tmp_path):
    runtime,docs,request=runtime_fixture(tmp_path)
    result=command(runtime,'review_candidate',dict(**request,stage='SCENE',provider_status='incomplete',output_text='partial',prior_references={}))
    assert result['assessment']['state']=='REJECTED'
    record=docs.retrieve('op',**result['reference'])
    assert loads(record['content'])['output_text']=='partial'
    assert record['metadata']['kind']=='GENERATED_CANDIDATE'


def test_scene_character_knowledge_cannot_disappear():
    first=SceneState(**meta('first'),knowledge_states=[KnowledgeState(**meta('k'),holder_id='person',knows={'secret':fact(True)})])
    second=SceneState(**meta('second'),knowledge_states=[KnowledgeState(**meta('k2'),holder_id='person')])
    result=continuity(first,second)
    assert 'MISSING_CONTINUITY_DIMENSION:person/knowledge/secret' in result.unresolved_questions


def test_full_domain_state_is_preserved_not_reconstructed_from_summary():
    source=story()
    source['scenes'][0]['character_states']=[CharacterState(**meta('character'),entity_id='person',physical={'damage':fact('held','held')}).to_dict()]
    source['scenes'][0]['spatial_states']=[SpatialState(**meta('space'),positions={'person':fact('held','held')}).to_dict()]
    source['scenes'][0]['temporal_states']=[TemporalState(**meta('time'),order=['beat'],durations={'beat':Fact()}).to_dict()]
    source['scenes'][0]['relationship_states']=[RelationshipState(**meta('relationship'),participants=['person'],dimensions={'trust':Fact()}).to_dict()]
    source['scenes'][0]['perspective_state']={'person':Fact().to_dict()}
    models,policies,_=parse_story(source,'p');req=derive_requirements(models,policies)
    options=candidates(req[0],models['beats'][0]);spec=generate(models,req,options,[options[0].object_id],'understanding',{})
    restored=ExecutionSpecification.from_dict(spec.to_dict())
    for key in MODEL_TYPES_FOR_TEST:
        assert getattr(restored,key)==models[key]


MODEL_TYPES_FOR_TEST=('world_models','world_states','entities','narratives','truth_states','scenes','beats','audiences')


def test_comparison_runtime_persists_actual_observation_linkage(tmp_path):
    from runtime_observation.observation_collector import RuntimeObservationCollector
    from runtime_observation.observation_store import RuntimeObservationStore
    runtime,docs,request=runtime_fixture(tmp_path)
    runtime.runtime_observation_collector=RuntimeObservationCollector(store=RuntimeObservationStore(tmp_path/'observations'))
    derived=command(runtime,'derive',request)
    specified=command(runtime,'specify',dict(**request,candidate_reference=derived['references']['candidates'],selected_ids=[derived['candidates'][0]['object_id']]))
    frame_request=dict(object_id='frame',content=image('black'),kind='RENDERED_EVIDENCE',visual_authority='RENDERED_EVIDENCE',
        knowledge_class='INTERNAL',source_reference='fixture',authority='operator',project_id='p',thread_id='t',expected_previous=None,validation_references=[])
    record=docs.intake('op',frame_request,dict(operator_id='op',action='DOCUMENT_INTAKE',decision='APPROVE',hash=digest(frame_request)))
    result=command(runtime,'compare_frames',dict(specification_reference=specified['references']['specification'],
        requirement_id=derived['requirements'][0]['object_id'],frame_references=[dict(object_id='frame',version=record['version'],expected_hash=record['record_hash'])]))
    assert result['comparison']=='MISMATCH' and result['observation_id']
    stored=runtime.runtime_observation_collector.store.load_record('op',result['observation_id'])
    assert digest(stored.to_dict())==result['observation_hash']


def test_conflicting_world_constraints_are_not_silently_merged():
    models,policies,_=parse_story(story(),'p')
    models['world_models'][0].laws={'teleportation':fact(False)}
    models['world_models'].append(WorldModel(**meta('other-world'),laws={'teleportation':fact(True)}))
    requirements=derive_requirements(models,policies)
    assert 'WORLD_CONSTRAINT_CONFLICT:teleportation' in requirements[0].unresolved_questions
    assert candidates(requirements[0],models['beats'][0])[0].state=='REQUIRES_AUTHORITY'


def test_same_world_law_and_physical_constraint_conflict_remains_explicit():
    models,policies,_=parse_story(story(),'p')
    models['world_models'][0].laws={'teleportation':fact(False)}
    models['world_models'][0].physical_constraints={'teleportation':fact(True)}
    assert 'WORLD_CONSTRAINT_CONFLICT:teleportation' in derive_requirements(models,policies)[0].unresolved_questions


def test_stale_understanding_blocks_current_source_export(tmp_path,monkeypatch):
    from dataclasses import replace
    runtime,docs,request=runtime_fixture(tmp_path);derived=command(runtime,'derive',request)
    specified=command(runtime,'specify',dict(**request,candidate_reference=derived['references']['candidates'],selected_ids=[derived['candidates'][0]['object_id']]))
    original=runtime.understanding_engine.store.get
    monkeypatch.setattr(runtime.understanding_engine.store,'get',lambda *args,**kwargs:replace(original(*args,**kwargs),canonical_meaning='changed',normalized_meaning='changed'))
    with pytest.raises(PermissionError,match='Understanding has changed'):
        command(runtime,'handoff',dict(specification_reference=specified['references']['specification'],target='BUILDER',supported_obligations=[]))


def test_runtime_audio_comparison_keeps_rp_pending(tmp_path):
    import wave
    from runtime_observation.observation_collector import RuntimeObservationCollector
    from runtime_observation.observation_store import RuntimeObservationStore
    source=story();source['audiences'][0]['required_evidence']={'signal':['NONSILENT_PCM']}
    runtime,docs,request=runtime_fixture(tmp_path,source)
    runtime.runtime_observation_collector=RuntimeObservationCollector(store=RuntimeObservationStore(tmp_path/'observations'))
    derived=command(runtime,'derive',request)
    specified=command(runtime,'specify',dict(**request,candidate_reference=derived['references']['candidates'],selected_ids=[derived['candidates'][0]['object_id']]))
    buffer=io.BytesIO()
    with wave.open(buffer,'wb') as stream:
        stream.setnchannels(1);stream.setsampwidth(2);stream.setframerate(8000);stream.writeframes(b'\x01\x00'*4)
    raw=buffer.getvalue()
    audio=dict(schema_version='AudioSource/1',encoding='BASE64_WAV',data=base64.b64encode(raw).decode(),sha256=hashlib.sha256(raw).hexdigest())
    req=dict(object_id='audio',content=json.dumps(audio),kind='RENDERED_EVIDENCE',visual_authority='RENDERED_EVIDENCE',knowledge_class='INTERNAL',
        source_reference='fixture',authority='operator',project_id='p',thread_id='t',expected_previous=None,validation_references=[])
    record=docs.intake('op',req,dict(operator_id='op',action='DOCUMENT_INTAKE',decision='APPROVE',hash=digest(req)))
    result=command(runtime,'compare_audio',dict(specification_reference=specified['references']['specification'],requirement_id=derived['requirements'][0]['object_id'],
        audio_reference=dict(object_id='audio',version=record['version'],expected_hash=record['record_hash'])))
    assert result['comparison']=='MATCH' and result['claim_state']=='PENDING_VALIDATION' and result['observation_id']
    assert not result['measurements']['audio']['playback_observed']
