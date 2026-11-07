"""Synthetic narrative qualification. No external corpus or provider calls."""
from copy import deepcopy
import json
from types import SimpleNamespace as NS
import pytest
from system_layer.contracts import digest
from understanding.story_contracts import StorySource, StoryInterpretation, StoryClaim
from understanding.story_interpretation import StoryInterpreter
from understanding.story_cinematic_handoff import admit
from understanding.cinematic_derivation import derive_requirements, candidates
from specs.cinematic_specification import generate, executor_handoff
from understanding import UnderstandingEngine, UnderstandingStore
from specs.document_service import DocumentService
from integration.content_custody import execute


CASES={
 'SIMPLE_SCENE':'Mara enters the hall.',
 'MULTI_BEAT_SCENE':'Mara is silent. Mara enters the hall. Then Mara takes the seal. Then Mara leaves the hall.',
 'AMBIGUOUS_ENTRANT':'The bearer enters the hall.',
 'UNKNOWN_TIME':'Mara enters the hall.',
 'UNKNOWN_WEATHER':'Mara enters the hall.',
 'OFFSCREEN_EVENT':'Off-screen, the tower explodes.',
 'AUDIENCE_KNOWS_CHARACTER_DOES_NOT':'The audience knows the key is false. Mara does not know the key is false. Mara enters the hall.',
 'CHARACTER_KNOWS_AUDIENCE_DOES_NOT':'Mara knows the key is false. The audience does not know the key is false. Mara enters the hall.',
 'RELATIONSHIP_CHANGE':'Mara trusts Tovin. Then Mara no longer trusts Tovin.',
 'POLITICAL_MEANING_VS_EMOTIONAL_MEANING':'Mara commands the council. Tovin is silent.',
 'CAUSE_UNKNOWN':'The tower explodes. Then Mara retreats.',
 'PRONOUN_AMBIGUITY':'Mara enters the hall. Tovin enters the hall. He takes the seal.',
 'SCENE_BOUNDARY_AMBIGUITY':'Mara enters the hall. Later, Mara leaves the hall.',
 'PROP_CONTINUITY':'Mara takes the seal. Then Mara enters the hall. Then Mara drops the seal.',
 'CREATIVE_PROPOSAL_SEPARATION':'Mara enters the hall. Proposal: rain could emphasize the arrival.'}


def source(text, identity='a', **changes):
    args=dict(source_id=identity,document_id=identity,version=1,record_hash=digest(identity),content_hash=digest(text),
        authority='operator-authored',project='p',story_scope='synthetic-story',scene_scope='',source_type='CANON',
        text=text,start=0,end=len(text),operator_constraints=[])
    args.update(changes);return StorySource(**args)


def interpret(text, *others):return StoryInterpreter([source(text),*[source(t,str(i)) for i,t in enumerate(others)]]).run()


@pytest.mark.parametrize('case',sorted(CASES))
def test_fixture_lineage_roundtrip_determinism_and_inspectable_stages(case):
    result=interpret(CASES[case]);value=result.to_dict()
    assert StoryInterpretation.from_dict(value).to_dict()==value==interpret(CASES[case]).to_dict()
    assert len(result.stages)==13
    for claim in result.claims+result.creative_proposals:
        assert claim.source_references and set(claim.source_references)<=result.spans.keys()
    for span in result.spans.values():assert source(CASES[case]).text[span['start']:span['end']]==span['text']


@pytest.mark.parametrize('case',sorted(CASES))
def test_fixture_direct_cinematic_handoff_keeps_uncertainty_and_no_execution(case):
    result=interpret(CASES[case]);parsed,lineage=admit(result)
    assert parsed is not None
    models,policies,_=parsed
    requirements=derive_requirements(models,policies)
    beats={b.object_id:b for b in models['beats']}
    options=[m for r in requirements for m in candidates(r,beats[r.beat_id])]
    assert all(m.state!='ELIGIBLE' for m in options)
    spec=generate(models,requirements,options,[],'synthetic-understanding',{'state':'UNPROVEN'})
    assert executor_handoff(spec,'BUILDER',[])['state']=='UNPROVEN'
    assert not spec.execution_authority
    assert lineage['interpretation']==result.to_dict()
    assert all(r.unresolved_questions for r in requirements)


def test_meaningful_beats_not_sentences():
    result=interpret(CASES['MULTI_BEAT_SCENE']);models,_,_=admit(result)[0]
    assert len(models['beats'])==3
    assert len(models['scenes'])==1
    assert not any(c.category=='EMOTION' for c in result.claims)


def test_role_and_pronoun_do_not_acquire_named_identity():
    result=interpret(CASES['AMBIGUOUS_ENTRANT']);models,_,_=admit(result)[0]
    assert models['entities'][0].identity['identity'].state=='UNKNOWN'
    result=interpret(CASES['PRONOUN_AMBIGUITY'])
    assert any(r['reference']=='He' and r['state']=='AMBIGUOUS' for r in result.references)
    assert len(admit(result)[0][0]['entities'])==3


def test_alias_resolves_only_explicit_identity():
    result=interpret('Mara is also known as the Captain. The Captain enters the hall.')
    entities=next(s['state']['entities'] for s in result.stages if s['stage']=='ENTITY_REFERENCE_RESOLUTION')
    assert len(entities)==1 and len(result.references)==2


def test_role_identity_requires_explicit_named_alias_and_survives_handoff():
    result=interpret('The bearer is called Mara. Mara enters the hall.')
    models,_,_=admit(result)[0]
    assert len(models['entities'])==1
    assert models['entities'][0].identity['identity'].value=='Mara'
    assert models['entities'][0].identity['source_mention'].value=='The bearer'


@pytest.mark.parametrize('case',['UNKNOWN_TIME','UNKNOWN_WEATHER','CAUSE_UNKNOWN'])
def test_unknowns_never_filled(case):
    result=interpret(CASES[case])
    for name in ('weather','time of day','architecture','cause'):
        assert any(c.predicate==name and c.value is None and c.epistemic_state=='UNKNOWN' for c in result.claims)
    assert not any(r['type']=='CAUSES' for r in result.relationships)


def test_truth_belief_knowledge_audience_separation():
    result=interpret('Mara believes the key is false. Tovin knows the key is false. The audience does not know the key is false. Mara enters the hall.')
    models,_,_=admit(result)[0];scene=models['scenes'][0]
    assert any('the key is false' in b.believes for b in scene.belief_states)
    assert any('the key is false' in k.knows for k in scene.knowledge_states)
    assert models['audiences'][0].does_not_know==['the key is false']
    assert not any(f.value=='the key is false' for f in models['truth_states'][0].world_truth.values())


@pytest.mark.parametrize('case',['AUDIENCE_KNOWS_CHARACTER_DOES_NOT','CHARACTER_KNOWS_AUDIENCE_DOES_NOT'])
def test_asymmetry(case):
    models,_,_=admit(interpret(CASES[case]))[0]
    knowledge=models['scenes'][0].knowledge_states[0];audience=models['audiences'][0]
    assert bool(knowledge.knows)!=bool(audience.knows)
    assert bool(knowledge.does_not_know)!=bool(audience.does_not_know)


def test_offscreen_is_not_audience_knowledge_or_concealment_authority():
    models,_,_=admit(interpret(CASES['OFFSCREEN_EVENT']))[0]
    audience=models['audiences'][0]
    assert not audience.knows and not audience.must_not_yet_understand


def test_political_state_not_emotional_label():
    result=interpret(CASES['POLITICAL_MEANING_VS_EMOTIONAL_MEANING'])
    assert any(c.category=='AUTHORITY' and c.predicate=='commands' for c in result.claims)
    assert not any(c.category=='EMOTION' for c in result.claims)
    assert any(c.category=='PURPOSE' and c.value=='establish authority' and c.epistemic_state=='INFERRED' for c in result.claims)


def test_explicit_cause_vs_sequence():
    result=interpret('Mara retreats because the tower explodes.')
    cause=next(r for r in result.relationships if r['type']=='CAUSES')
    events={e['event_id']:e for e in result.events}
    assert events[cause['source']]['verb']=='explodes' and events[cause['target']]['verb']=='retreats'
    result=interpret('The tower explodes. Then Mara retreats.')
    assert any(r['type']=='FOLLOWS' for r in result.relationships)
    assert not any(r['type']=='CAUSES' for r in result.relationships)


def test_spatial_and_temporal_no_coordinates_or_duration_invention():
    result=interpret('Mara is behind Tovin. Mara enters the hall while Tovin leaves the hall.')
    assert any(r['domain']=='SPATIAL' and r['type']=='behind' for r in result.relationships)
    assert any(r['type']=='OVERLAP' for r in result.relationships)
    assert not any(c.predicate in {'coordinates','duration'} for c in result.claims)


def test_scene_headings_not_blank_lines():
    result=interpret('Scene 1: Hall\nMara enters the hall.\n\nMara takes the seal.\nScene 2: Court\nMara enters the court.')
    assert len(result.scenes)==2 and all(s['boundary_state']=='ESTABLISHED' for s in result.scenes)
    ambiguous=interpret(CASES['SCENE_BOUNDARY_AMBIGUITY'])
    assert any('SCENE_BOUNDARY_AMBIGUOUS' in x for x in ambiguous.unresolved)


def test_conflicting_sources_retained_and_blocked():
    result=interpret('The weather is rain. Mara enters the hall.', 'The weather is clear. Mara enters the court.')
    assert result.conflicts
    assert all(set(c)=={'source_a','claim_a','source_b','claim_b','scope','materiality','required_authority_for_resolution'} for c in result.conflicts)
    assert any(c.epistemic_state=='CONFLICTED' for c in result.claims)
    models,policies,_=admit(result)[0]
    assert all('SOURCE_CONFLICT_REQUIRES_ADJUDICATION' in r.unresolved_questions for r in derive_requirements(models,policies))


def test_prop_changes_are_material_and_preserved():
    models,_,_=admit(interpret(CASES['PROP_CONTINUITY']))[0]
    assert len(models['beats'])==3
    possession=[v for k,v in models['scenes'][0].character_states[0].physical.items() if k.startswith('possession:')]
    assert len(possession)==1 and possession[0].value['action']=='drops'
    first,last=models['beats'][0],models['beats'][-1]
    key=next(iter(first.state_change))
    assert first.state_change[key].value['predicate']=='takes' and last.state_change[key].value['predicate']=='drops'


def test_proposals_cannot_enter_canon_or_weather():
    result=interpret(CASES['CREATIVE_PROPOSAL_SEPARATION'])
    assert result.creative_proposals and all(c.epistemic_state!='PROPOSED' for c in result.claims)
    assert next(c for c in result.claims if c.predicate=='weather').epistemic_state=='UNKNOWN'
    altered=result.to_dict();altered['claims'].append(altered['creative_proposals'].pop())
    with pytest.raises(ValueError,match='Proposal in canon'):StoryInterpretation.from_dict(altered)


@pytest.mark.parametrize('change',[{'version':0},{'start':-1},{'end':999},{'source_type':'GENERATED_CANDIDATE'},
                                 {'content_hash':'0'*64},{'authority':''}])
def test_bad_source_fails_closed(change):
    with pytest.raises(ValueError):source('Mara enters the hall.',**change)


def test_unsupported_and_conditional_prose_is_not_canon():
    result=interpret('Perhaps the bearer could be Mara. Mara opens the gate if Tovin commands it.')
    assert not result.events and any('UNRESOLVED' in x or 'UNPARSED' in x for x in result.unresolved)
    assert admit(result)[0] is None


def runtime_fixture(tmp_path,text):
    runtime=NS(context=NS(identity=NS(operator_id='op'),active_thread=NS(thread_id='t')),
        understanding_engine=UnderstandingEngine(UnderstandingStore(tmp_path/'meaning.db')))
    runtime.events=[];runtime._observe_runtime_event=lambda name,payload,**kw:runtime.events.append((name,payload))
    docs=DocumentService(tmp_path/'content_custody.sqlite3')
    intake=dict(object_id='story',content=text,kind='CANON',visual_authority='NOT_APPLICABLE',knowledge_class='INTERNAL',
        source_reference='operator:story',authority='operator',project_id='p',thread_id='t',expected_previous=None,validation_references=[])
    record=docs.intake('op',intake,approval('DOCUMENT_INTAKE',intake))
    ref=dict(object_id='story',version=record['version'],expected_hash=record['record_hash'])
    request=dict(reference=ref,project_id='p',story_selection=dict(story_scope='synthetic',scene_scope='',
        sources=[dict(reference=ref,start=0,end=len(text))],operator_constraints=[]))
    return runtime,docs,request,intake


def approval(action,request):return dict(operator_id='op',action=action,decision='APPROVE',hash=digest(request))
def command(runtime,action,request,approved=True):
    return execute(runtime,'/creative cinematic '+action+' '+json.dumps(dict(request=request,
        approval=approval('CINEMATIC_'+action.upper(),request) if approved else {})))


def test_normal_command_raw_story_to_spec_and_preserved_source(tmp_path):
    runtime,docs,request,intake=runtime_fixture(tmp_path,CASES['MULTI_BEAT_SCENE'])
    with pytest.raises(PermissionError):command(runtime,'interpret',request,False)
    result=command(runtime,'interpret',request)
    assert result['state']=='UNPROVEN' and result['specification']['beats']
    assert runtime.context.understanding_result and result['references']['interpretation']
    assert docs.retrieve('op',**request['reference'])['content']==intake['content']
    for ref in result['references'].values():assert docs.retrieve('op',**ref)['metadata']['kind']=='GENERATED_CANDIDATE'
    handoff=command(runtime,'handoff',dict(specification_reference=result['references']['specification'],target='BUILDER',supported_obligations=[]))
    assert handoff['state']=='UNPROVEN' and not handoff['execution_authority']
    assert runtime.events[-1][1]['cinematic_lineage']['selected_source']==request


def test_runtime_unparsed_still_persists_coverage_and_no_spec(tmp_path):
    runtime,docs,request,_=runtime_fixture(tmp_path,'A riddle without a known answer.')
    result=command(runtime,'interpret',request)
    assert result['state']=='UNRESOLVED' and 'specification' not in result
    assert result['interpretation']['unresolved'] and runtime.events[-1][1]['cinematic_lineage']


def test_runtime_stale_source_and_foreign_project_fail_closed(tmp_path):
    runtime,docs,request,intake=runtime_fixture(tmp_path,CASES['SIMPLE_SCENE'])
    foreign=deepcopy(request);foreign['project_id']='other'
    with pytest.raises(PermissionError):command(runtime,'interpret',foreign)
    intake['expected_previous']=request['reference']['expected_hash'];intake['content']='Mara exits the hall.'
    docs.intake('op',intake,approval('DOCUMENT_INTAKE',intake))
    with pytest.raises(PermissionError,match='Stale'):command(runtime,'interpret',request)


@pytest.mark.parametrize('text',['If Mara enters the hall.', 'Perhaps Mara enters the hall.',
    'Mara might enters the hall.', 'Mara and Tovin enters the hall.', 'Mara opens the gate unless Tovin refuses.'])
def test_modal_conditional_or_unresolved_group_cannot_become_established_event(text):
    result=interpret(text)
    assert not result.events and admit(result)[0] is None


def test_structured_candidate_cannot_forge_grounding_even_with_valid_span():
    result=interpret('Mara enters the hall.')
    claim=next(c for c in result.claims if c.predicate=='enters');claim.value='secret palace'
    with pytest.raises(ValueError,match='reproducible source grounding'):admit(result)


def test_unknown_states_and_changed_spans_fail_closed():
    result=interpret('Mara enters the hall.').to_dict()
    changed=deepcopy(result);changed['claims'][0]['epistemic_state']='CONFIRMED'
    with pytest.raises(ValueError):StoryInterpretation.from_dict(changed)
    changed=deepcopy(result);next(iter(changed['spans'].values()))['text']='forged'
    with pytest.raises(ValueError,match='Altered source span'):StoryInterpretation.from_dict(changed)


def test_two_distinct_known_facts_are_not_conflicting_sources():
    result=interpret('Mara knows the key is false. Mara enters the hall.',
                     'Mara knows the door is locked. Mara enters the hall.')
    assert not result.conflicts


def test_explicit_knowledge_contradiction_across_sources():
    result=interpret('Mara knows the key is false. Mara enters the hall.',
                     'Mara does not know the key is false. Mara enters the hall.')
    assert result.conflicts


def test_explicit_audience_obligations_and_may_infer_are_separate():
    result=interpret('The audience must understand the succession. The audience must not yet understand the killer. The audience may infer danger. Mara commands the council.')
    models,_,_=admit(result)[0];audience=models['audiences'][0]
    assert audience.must_understand==['the succession']
    assert audience.must_not_yet_understand==['the killer']
    assert audience.may_infer['danger'].state=='INFERRED' and not audience.knows


def test_explicit_duration_hold_no_invented_measurement():
    result=interpret('Mara waits for three seconds. Then Mara enters the hall.')
    assert any(r['type']=='HOLD' and r['duration']=='for three seconds' for r in result.relationships)
    parsed,_=admit(result);assert parsed


@pytest.mark.parametrize('connector,kind',[('which enables','ENABLES'),('which triggers','TRIGGERS'),
    ('which contributes to','CONTRIBUTES_TO'),('which is correlated with','CORRELATED_WITH')])
def test_explicit_relational_vocabulary(connector,kind):
    result=interpret('Mara opens the gate, '+connector+' Tovin enters the hall.')
    assert any(r['type']==kind for r in result.relationships)


def test_source_range_and_constraints_preserved():
    text='Unrelated preface. Mara enters the hall. Unrelated epilogue.'
    start=text.index('Mara');end=text.index(' Unrelated epilogue')
    result=StoryInterpreter([source(text,start=start,end=end,operator_constraints=['Do not reveal the sender'])]).run()
    assert all(start<=s['start']<s['end']<=end for s in result.spans.values())
    assert result.sources[0].operator_constraints==['Do not reveal the sender']
    assert any('OPERATOR_CONSTRAINT_REQUIRES_ENFORCEMENT' in u for u in result.unresolved)


def test_initial_possession_is_present_in_drop_pre_state():
    models,_,_=admit(interpret('Mara holds the seal. Then Mara drops the seal.'))[0]
    beat=models['beats'][0];key=next(iter(beat.state_change))
    assert beat.preconditions[key].value['predicate']=='holds'
    assert beat.state_change[key].value['predicate']=='drops'
    assert models['scenes'][0].entry_state[key].value['predicate']=='holds'


def test_intervening_static_fact_reaches_next_beat_and_scene_entry():
    result=interpret('Mara holds the seal. Mara knows the key is false. Mara enters the hall. Tovin is injured. Then Mara drops the seal.')
    models,_,_=admit(result)[0]
    assert any(v.value['predicate']=='knows' for v in models['scenes'][0].entry_state.values())
    assert any(v.value['predicate']=='injured' for v in models['beats'][1].preconditions.values())
    view=result.canonical_view()
    assert view['CANONICAL_INTERPRETATION']['ENTRY_STATE'] and 'CREATIVE_PROPOSALS' in view


def test_character_knowledge_survives_explicit_scene_boundary():
    models,_,_=admit(interpret('Scene 1: Hall\nMara knows the key is false. Mara enters the hall.\nScene 2: Court\nMara enters the court.'))[0]
    assert 'the key is false' in models['scenes'][1].knowledge_states[0].knows


def test_runtime_rejects_candidate_authority_and_cross_owner(tmp_path):
    runtime,docs,request,intake=runtime_fixture(tmp_path,CASES['SIMPLE_SCENE'])
    runtime.context.identity.operator_id='other'
    other_approval=dict(operator_id='other',action='CINEMATIC_INTERPRET',decision='APPROVE',hash=digest(request))
    with pytest.raises(FileNotFoundError,match='AUTHORITATIVE_OBJECT_UNAVAILABLE'):
        execute(runtime,'/creative cinematic interpret '+json.dumps({'request':request,'approval':other_approval}))
    runtime.context.identity.operator_id='op';intake['kind']='GENERATED_CANDIDATE'
    intake['expected_previous']=request['reference']['expected_hash']
    record=docs.intake('op',intake,approval('DOCUMENT_INTAKE',intake))
    request['reference'].update(version=record['version'],expected_hash=record['record_hash'])
    with pytest.raises(PermissionError,match='Candidate document'):command(runtime,'interpret',request)


def test_multisource_custody_is_rechecked_on_handoff(tmp_path):
    runtime,docs,request,intake=runtime_fixture(tmp_path,CASES['SIMPLE_SCENE'])
    other=dict(intake,object_id='second',content='The weather is rain. Mara enters the hall.')
    record=docs.intake('op',other,approval('DOCUMENT_INTAKE',other))
    ref=dict(object_id='second',version=record['version'],expected_hash=record['record_hash'])
    request['story_selection']['sources'].append(dict(reference=ref,start=0,end=len(other['content'])))
    result=command(runtime,'interpret',request)
    other['expected_previous']=record['record_hash'];other['content']='The weather is clear. Mara enters the hall.'
    docs.intake('op',other,approval('DOCUMENT_INTAKE',other))
    with pytest.raises(PermissionError,match='Stale story'):
        command(runtime,'handoff',dict(specification_reference=result['references']['specification'],target='BUILDER',supported_obligations=[]))


@pytest.mark.parametrize('verb,kind',[('causes','CAUSES'),('enables','ENABLES'),('triggers','TRIGGERS'),
    ('contributes to','CONTRIBUTES_TO'),('is correlated with','CORRELATED_WITH')])
def test_nominal_causal_assertion_does_not_invent_observed_events(verb,kind):
    result=interpret('Opening the gate '+verb+' escape. Mara enters the hall.')
    relation=next(r for r in result.relationships if r['type']==kind)
    assert relation['endpoint_state']=='EXPLICIT_NOMINAL_RELATION_NOT_OBSERVED_EVENT'
    assert len(result.events)==1
    assert admit(result)[0][0]['scenes'][0].causal_requirements


def test_reaction_and_perception_do_not_automatically_become_emotion_or_knowledge():
    result=interpret('Mara sees the seal. Then Mara recoils.')
    models,_,_=admit(result)[0]
    assert len(models['beats'])==2 and models['beats'][1].reaction.state=='ESTABLISHED'
    assert models['scenes'][0].knowledge_states[0].perceptual_access
    assert not models['scenes'][0].knowledge_states[0].knows
    assert not models['scenes'][0].character_states[0].emotional


def test_conflicting_purpose_blocks_handoff_without_erasing_interpretation():
    result=interpret('The scene purpose is reveal the sender. Mara enters the hall.',
                     'The scene purpose is conceal the sender. Mara enters the hall.')
    assert result.conflicts and admit(result)[0] is None
