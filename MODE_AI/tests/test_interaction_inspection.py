import json
from pathlib import Path
from types import SimpleNamespace as NS
import pytest
from memory.thread_store import ThreadStore
from runtime_observation.observation_record import RuntimeObservationRecord
from runtime_observation.observation_store import RuntimeObservationStore
from runtime_observation.interaction_inspection import InteractionInspector,inspect_interaction
from integration.runtime_self_inspection import reasoning_context
from data_governance.context_admission import verify

@pytest.fixture
def case(tmp_path):
    threads=ThreadStore(tmp_path/'threads');thread=threads.create_thread('owner')
    record=RuntimeObservationRecord(observation_id='ro-prior',operator_id='owner',thread_id=thread.thread_id,
        input_text='What can you observe?',response_text='Recorded response',
        runtime_state_start='LISTENING',runtime_state_end='COMPLETE',
        metadata={'interaction_id':'interaction-prior','reasoning_id':'reasoning-prior',
            'interpreted_intent':{'clarification_required':False,'halt_required':False},
            'understanding':{'request_id':'u-request','state':'CLARIFICATION_REQUIRED','readiness':'CLARIFICATION_REQUIRED',
                'understanding_id':None,'transition_id':None,'errors':[]},
            'response_governance':{'decision':'ALLOW','allowed':True,'reasons':[]},
            'completion_claim':{'controller_success':True},'authority_source':'core.mode_controller'})
    store=RuntimeObservationStore(tmp_path/'observations');store.save_record(record)
    thread.add_message('mode','Recorded response',metadata={'runtime_observation_id':record.observation_id})
    threads.save_thread(thread)
    trace={'interaction_id':'interaction-prior','session_id':thread.thread_id,'clarification_required':False,
        'halt_required':False,'ambiguity_score':0.0,'selected_posture':'DIRECT_RESPONSE'}
    path=tmp_path/'interactions.jsonl';path.write_text(json.dumps(trace)+'\n',encoding='utf-8')
    inspector=InteractionInspector(store.storage_dir,threads.storage_dir,path)
    return inspector,record,thread,trace

def test_correlated_projection_preserves_false_unknown_and_no_authority(case):
    inspector,r,t,_=case;p=inspector.inspect_interaction('owner',t.thread_id,'interaction-prior')
    assert p['observed']['controller']['clarification_required'] is False
    assert p['observed']['understanding']['state']=='CLARIFICATION_REQUIRED'
    assert p['observed']['runtime_phase']['after']=='COMPLETE'
    assert p['observed']['public_result']['success'] is True
    assert p['observed']['publication_gate']['decision']=='ALLOW'
    assert p['observed']['clarification_disposition'] is None
    assert 'understanding.warnings' in p['unavailable'] and 'understanding.result_id' in p['unavailable']
    assert p['evidence_references']['trace_row']['line']==1
    assert not p['execution_authority'] and p['interpretation'] is None
    assert p['validation_state']=='RECORDED_NOT_INDEPENDENTLY_VALIDATED'
    assert p['observed']['understanding']['errors']==[]

def test_inspection_is_read_only(case):
    inspector,r,t,_=case
    root=inspector.trace_path.parent
    before={str(p):p.read_bytes() for p in root.rglob('*') if p.is_file()}
    inspector.inspect_interaction('owner',t.thread_id,'interaction-prior')
    assert before=={str(p):p.read_bytes() for p in root.rglob('*') if p.is_file()}

@pytest.mark.parametrize('owner,thread,interaction',[
    ('other',None,'interaction-prior'),('owner','foreign','interaction-prior'),
    ('../owner',None,'interaction-prior'),('owner',None,'../trace'),('owner',None,'missing')])
def test_scope_and_identity_rejected(case,owner,thread,interaction):
    inspector,r,t,_=case
    with pytest.raises((PermissionError,ValueError)):
        inspector.inspect_interaction(owner,thread or t.thread_id,interaction)

def test_unfinished_observation_not_inspectable(case):
    inspector,r,t,_=case;r.metadata['interaction_id']='unfinished'
    r.observation_id='ro-unfinished';RuntimeObservationStore(inspector.observation_root).save_record(r)
    with pytest.raises(PermissionError):inspector.inspect_interaction('owner',t.thread_id,'unfinished')

@pytest.mark.parametrize('change',['duplicate','cross_thread','missing','malformed','conflict'])
def test_trace_correlation_and_missing_evidence(case,change):
    inspector,r,t,trace=case
    if change=='duplicate':text=json.dumps(trace)+'\n'+json.dumps(trace)
    elif change=='cross_thread':trace['session_id']='foreign';text=json.dumps(trace)
    elif change=='missing':text=''
    elif change=='malformed':text='not json\n'+json.dumps(trace)
    else:trace['clarification_required']=True;text=json.dumps(trace)
    inspector.trace_path.write_text(text,encoding='utf-8')
    if change in {'duplicate','cross_thread'}:
        with pytest.raises(PermissionError):inspector.inspect_interaction('owner',t.thread_id,'interaction-prior')
    else:
        p=inspector.inspect_interaction('owner',t.thread_id,'interaction-prior')
        if change=='missing':assert p['observed']['controller']['clarification_required'] is None
        elif change=='malformed':assert p['trace_parse_error_lines']==[1] and p['evidence_references']['trace_row']['line']==2
        else:assert p['correlation_conflicts']

def test_model_selected_read_is_admitted_as_unvalidated_runtime_evidence(case):
    inspector,r,t,_=case;runtime=NS(context=NS(identity=NS(operator_id='owner'),active_thread=t))
    calls=[]
    def select(prompt):
        calls.append(prompt);return json.dumps({'tool':'inspect_interaction','interaction_id':'interaction-prior'})
    prompt=reasoning_context(runtime,'Inspect the completed interaction with the contradictory clarification states.',
        selector=select,inspector=inspector)
    verify(prompt,t.thread_id)
    assert len(calls)==1 and runtime.context.self_inspection['tool_result']['observation_id']==r.observation_id
    assert 'SELF-INSPECTED RUNTIME EVIDENCE' in prompt and 'u-request' in prompt
    assert prompt.decisions[0]['validation_state']=='UNVALIDATED'
    assert 'No code-analysis explanation supplied' in prompt

@pytest.mark.parametrize('selection',[
    {'tool':'execute','interaction_id':'interaction-prior'},
    {'tool':'inspect_interaction','interaction_id':'foreign'},
    {'tool':'inspect_interaction','interaction_id':'interaction-prior','operator_id':'other'}])
def test_model_cannot_change_scope_or_invoke_other_actions(case,selection):
    inspector,r,t,_=case;runtime=NS(context=NS(identity=NS(operator_id='owner'),active_thread=t))
    with pytest.raises(PermissionError):
        reasoning_context(runtime,'Inspect the completed interaction.',selector=lambda _:json.dumps(selection),inspector=inspector)

def test_ordinary_turn_has_no_inspection_or_provider_call():
    assert reasoning_context(NS(),'Hello') is None

def test_preserved_live_acceptance_case():
    p=inspect_interaction('operator-64d6f609171c49d9bbd73bf560bccb48',
        'thread-c7b82a6fcdea410d87ea9de5d5a9c1db','interaction-caa19d7db6d047e0af0ee6ee9a312b26')
    assert p['observed']['controller']['clarification_required'] is False
    assert p['observed']['understanding']['readiness']=='CLARIFICATION_REQUIRED'
    assert p['evidence_references']['trace_row']['line']==920

def test_evidence_reaches_all_reasoning_stages_without_static_code(case):
    from tests.test_cross_thread_downstream_preservation import run
    inspector,r,t,_=case;runtime=NS(context=NS(identity=NS(operator_id='owner'),active_thread=t))
    prompt=reasoning_context(runtime,'Inspect the completed interaction.',inspector=inspector,
        selector=lambda _:json.dumps({'tool':'inspect_interaction','interaction_id':'interaction-prior'}))
    ledger=runtime.context.self_inspection['evidence_ledger']
    final=json.dumps({'ledger_id':ledger['ledger_id'],'statements':[ledger['entries'][0]['entry_id']]})
    _,calls=run(prompt,['The records show separate states.','Keep unavailable events unknown.',final])
    assert len(calls)==3
    for value,_ in calls:
        assert r.observation_id in value and 'u-request' in value and 'RECORDED_NOT_INDEPENDENTLY_VALIDATED' in value
        assert 'def _interpret' not in value and 'No code-analysis explanation supplied' in value

def test_cli_prompt_builder_calls_inspection_route():
    import ast
    source=Path('interactive_mode_ai.py').read_text(encoding='utf-8')
    tree=ast.parse(source)
    method=next(n for n in ast.walk(tree) if isinstance(n,ast.FunctionDef) and n.name=='_build_engine_input')
    assert any(isinstance(n,ast.Call) and isinstance(n.func,ast.Name) and n.func.id=='inspection_context' for n in ast.walk(method))

def test_candidate_selection_bound_and_trace_size_fail_closed(case):
    inspector,r,t,_=case
    assert len(inspector.candidates('owner',t.thread_id))<=8
    from unittest.mock import patch
    with patch('runtime_observation.interaction_inspection.MAX_BYTES',1):
        with pytest.raises(ValueError):inspector.inspect_interaction('owner',t.thread_id,'interaction-prior')

def test_recorded_disposition_is_not_inferred(case):
    inspector,r,t,_=case;r.metadata['clarification_state']={'disposition':'EXPLICIT_RECORDED_VALUE'}
    RuntimeObservationStore(inspector.observation_root).save_record(r)
    assert inspector.inspect_interaction('owner',t.thread_id,'interaction-prior')['observed']['clarification_disposition']=='EXPLICIT_RECORDED_VALUE'

def test_explicit_missing_id_cannot_select_other_interaction(case):
    inspector,r,t,_=case;runtime=NS(context=NS(identity=NS(operator_id='owner'),active_thread=t))
    with pytest.raises(PermissionError):
        reasoning_context(runtime,'Inspect the completed interaction interaction-absent.',inspector=inspector,
            selector=lambda _:pytest.fail('No provider should run for an unavailable explicit ID'))

def test_normal_turn_clears_previous_inspection_receipt():
    runtime=NS(context=NS(self_inspection={'old':'receipt'}))
    assert reasoning_context(runtime,'Hello') is None and runtime.context.self_inspection is None

def test_actual_booted_cli_prompt_uses_inspector(case,tmp_path,monkeypatch):
    from tests.test_behavior_runtime_edges import boot
    import integration.runtime_self_inspection as route
    inspector,record,_,trace=case
    boot_path=tmp_path/'booted';boot_path.mkdir()
    runtime=boot(boot_path,monkeypatch)
    try:
        record.operator_id='op';record.thread_id=runtime.context.active_thread.thread_id
        RuntimeObservationStore(inspector.observation_root).save_record(record)
        runtime.context.active_thread.add_message('mode','Earlier response',metadata={'runtime_observation_id':record.observation_id})
        runtime.thread_store.save_thread(runtime.context.active_thread)
        trace['session_id']=record.thread_id;inspector.trace_path.write_text(json.dumps(trace),encoding='utf-8')
        runtime.interaction_inspector=InteractionInspector(inspector.observation_root,runtime.thread_store.storage_dir,inspector.trace_path)
        original=route.reasoning_context
        monkeypatch.setattr(route,'reasoning_context',lambda r,q:original(r,q,
            selector=lambda _:json.dumps({'tool':'inspect_interaction','interaction_id':'interaction-prior'})))
        prompt=runtime._build_engine_input('Inspect the completed interaction.')
        assert 'SELF-INSPECTED RUNTIME EVIDENCE' in prompt and record.observation_id in prompt
        assert runtime.context.self_inspection['tool_result']['observed']['understanding']['state']=='CLARIFICATION_REQUIRED'
    finally:runtime.shutdown()

def test_absent_historical_fields_do_not_become_deserializer_defaults(case):
    inspector,r,t,_=case;path=inspector.observation_root/'owner'/(r.observation_id+'.json')
    raw=json.loads(path.read_text());raw.pop('runtime_state_start');raw.pop('created_at')
    path.write_text(json.dumps(raw),encoding='utf-8')
    result=inspector.inspect_interaction('owner',t.thread_id,'interaction-prior')
    assert result['observed']['runtime_phase']['before'] is None
    assert 'runtime_phase.before' in result['unavailable']
    assert inspector.candidates('owner',t.thread_id)[0]['created_at']==''
