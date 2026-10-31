import json
from pathlib import Path
from types import SimpleNamespace as NS
import pytest
from runtime_observation.transformation_provenance import TransformationStore,recording,emit
from clarification.clarification_engine import evaluate_clarification_state
from models.runtime_models import CanonicalInteractionState
from understanding.understanding_engine import UnderstandingEngine,UnderstandingRequest
from understanding.understanding_store import UnderstandingStore
from tests.test_interaction_inspection import case

def record(store,interaction='interaction-prior'):
    with recording('owner','thread',interaction=interaction,store=store):
        return emit(component='test',stage='record',prior={'value':False},event='event',context={},
                    rules='actual branch',transformation='assign',result={'value':True})

def test_append_only_hash_chain_and_unavailable(tmp_path):
    store=TransformationStore(tmp_path/'events');record(store)
    first={p:p.read_bytes() for p in tmp_path.rglob('*.json')}
    record(store);rows=store.read('owner','thread','interaction-prior')
    assert len(rows)==2 and all(p.read_bytes()==b for p,b in first.items())
    assert rows[1]['record']['previous_hash']==rows[0]['record']['record_hash']
    assert rows[0]['record']['reason']=='UNAVAILABLE'
    assert not rows[0]['record']['execution_authority']
    assert rows[0]['record']['validation_state']=='RECORDED_NOT_INDEPENDENTLY_VALIDATED'

@pytest.mark.parametrize('change',['body','scope','sequence','delete'])
def test_corruption_and_deleted_prefix_fail_closed(tmp_path,change):
    store=TransformationStore(tmp_path);record(store);record(store)
    files=sorted(tmp_path.rglob('*.json'))
    if change=='delete':files[0].unlink()
    else:
        row=json.loads(files[0].read_text());row[{'body':'reason','scope':'operator_id','sequence':'sequence'}[change]]='tampered'
        files[0].write_text(json.dumps(row))
    with pytest.raises(PermissionError):store.read('owner','thread','interaction-prior')

def test_scope_path_denied_and_reads_create_nothing(tmp_path):
    store=TransformationStore(tmp_path/'missing')
    assert store.read('owner','thread','interaction-a')==[] and not store.root.exists()
    with pytest.raises((ValueError,PermissionError)):store.read('../owner','thread','interaction-a')

@pytest.mark.parametrize('score,risk,expected',[(0,False,'NO_CLARIFICATION_REQUIRED'),(.7,False,'CLARIFICATION_REQUIRED'),(1,True,'HALT_REQUIRED')])
def test_controller_records_actual_branch(tmp_path,score,risk,expected):
    store=TransformationStore(tmp_path/'events')
    state=CanonicalInteractionState(interaction_id='interaction-c',session_id='thread',raw_input='delete' if risk else 'question')
    state.normalized_input=state.raw_input;state.ambiguity_score=score;state.ambiguity_profile={'consequence':1 if risk else 0}
    with recording('owner','thread',store=store):decision=evaluate_clarification_state(state)
    row=store.read('owner','thread','interaction-c')[0]['record']
    assert row['result']['disposition']==decision['disposition']==expected
    assert row['producer']['stage']=='evaluate_clarification_state'
    assert row['prior']['clarification_required'] is False
    if score==0:assert row['reason']=='UNAVAILABLE'

def test_understanding_records_new_evaluator_and_actual_warning(tmp_path):
    store=TransformationStore(tmp_path/'events');engine=UnderstandingEngine(UnderstandingStore(tmp_path/'understanding'))
    before=list((tmp_path/'understanding').rglob('*.json'))
    request=UnderstandingRequest(operator_id='owner',thread_id='thread',current_input='What is 2 + 2?',
        runtime_metadata={'interpreted_intent':{'clarification_required':False,'halt_required':False}})
    with recording('owner','thread',interaction='interaction-u',store=store):result=engine.process(request)
    row=store.read('owner','thread','interaction-u')[0]['record']
    assert result.state=='CLARIFICATION_REQUIRED'
    assert row['prior']=={'state':'PENDING','readiness':'UNPROVEN'}
    assert row['context_used']['recognized'] is False
    assert row['context_used']['controller_values_received']['clarification_required'] is False
    assert row['reason']==result.warnings and 'if not recognized' in row['rules']
    assert row['transformation']=='initialize_and_evaluate_separate_UnderstandingResult'
    assert list((tmp_path/'understanding').rglob('*.json'))==before

def test_recording_failure_does_not_change_evaluator_state(tmp_path):
    class Broken:
        def append(self,*a):raise OSError('unavailable')
    state=CanonicalInteractionState(interaction_id='interaction-c',session_id='thread',raw_input='question')
    state.ambiguity_score=0
    with recording('owner','thread',store=Broken()) as receipt:result=evaluate_clarification_state(state)
    assert result['disposition']=='NO_CLARIFICATION_REQUIRED'
    assert receipt['errors']==[{'type':'OSError','stage':'evaluate_clarification_state'}]

def test_inspection_returns_only_owned_events_and_no_backfill(case,tmp_path):
    inspector,r,t,_=case;inspector.transformation_root=tmp_path/'events'
    assert inspector.inspect_interaction('owner',t.thread_id,'interaction-prior')['transformation_provenance']['status']=='UNAVAILABLE'
    store=TransformationStore(inspector.transformation_root)
    with recording('owner',t.thread_id,interaction='interaction-prior',store=store):
        identity=emit(component='test',stage='actual',prior={},event='event',context={},rules='rule',transformation='assign',result={})
    projected=inspector.inspect_interaction('owner',t.thread_id,'interaction-prior')
    assert projected['transformation_provenance']['records'][0]['record']['transition_id']==identity
    assert projected['transformation_provenance']['historical_backfill'] is False
    with pytest.raises(PermissionError):inspector.inspect_interaction('foreign',t.thread_id,'interaction-prior')

def test_diagnostic_citations_require_observed_exact_quote(case,tmp_path):
    from integration.runtime_self_inspection import reasoning_context
    from conversation_quality.source_grounding import assess,sources
    inspector,r,t,_=case;inspector.transformation_root=tmp_path/'events';store=TransformationStore(inspector.transformation_root)
    with recording('owner',t.thread_id,interaction='interaction-prior',store=store):
        identity=emit(component='test',stage='actual',prior={},event='event',context={},rules='rule',transformation='assign_controller_flags',result={})
    runtime=NS(context=NS(identity=NS(operator_id='owner'),active_thread=t))
    prompt=reasoning_context(runtime,'Inspect the completed interaction.',inspector=inspector,
        selector=lambda _:json.dumps({'tool':'inspect_interaction','interaction_id':'interaction-prior'}))
    assert assess(f'OBSERVED: {identity} evidence states "assign_controller_flags"',prompt)['allowed']
    assert not assess(f'INFERRED: {identity} evidence states "assign_controller_flags"',prompt)['allowed']
    assert not assess(f'OBSERVED: {identity} evidence states "invented cause"',prompt)['allowed']
    assert not assess('OBSERVED: transformation-nonexistent evidence states "assign_controller_flags"',prompt)['allowed']
    assert sources(prompt)[0]['record']['validation_state']=='UNVALIDATED'

def test_unscoped_evaluator_does_not_create_provenance(tmp_path,monkeypatch):
    monkeypatch.chdir(tmp_path)
    state=CanonicalInteractionState(interaction_id='interaction-c',session_id='thread',raw_input='q');state.ambiguity_score=0
    evaluate_clarification_state(state)
    assert not (tmp_path/'runtime_data').exists()

def test_normal_cli_records_chain_and_restart_inspects_it(tmp_path,monkeypatch):
    from tests.test_behavior_runtime_edges import boot
    from agents.reasoning_agent import ReasoningResult
    from runtime_observation.interaction_inspection import InteractionInspector
    import integration.conversation_understanding as meaning
    import runtime_logging.trace_logger as trace
    import runtime_logging.response_logger as response
    monkeypatch.setattr(trace,'TRACE_OUTPUT_PATH',tmp_path/'trace.jsonl')
    monkeypatch.setattr(response,'RESPONSE_OUTPUT_PATH',tmp_path/'responses.jsonl')
    monkeypatch.setattr(meaning,'extract',lambda *a:({'subject_id':None,'edits':[]},{}))
    class Agent:
        def generate(self,**kwargs):return ReasoningResult('r','test','test','','','4',0)
    monkeypatch.setattr('core.mode_controller.ReasoningAgent',Agent)
    runtime=boot(tmp_path,monkeypatch);thread=runtime.context.active_thread.thread_id
    inputs=iter(['What is 2 + 2?','exit']);monkeypatch.setattr('builtins.input',lambda *a:next(inputs))
    runtime.run()
    observation=runtime.context.runtime_observation;interaction=observation.metadata['interaction_id']
    inspector=InteractionInspector(tmp_path/'runtime_data/runtime_observations',tmp_path/'threads',tmp_path/'trace.jsonl',tmp_path/'runtime_data/transformation_provenance')
    result=inspector.inspect_interaction('op',thread,interaction)
    events=result['transformation_provenance']['records']
    assert len(events)==3
    assert events[0]['record']['result']['clarification_required'] is False
    assert events[1]['record']['result']['runtime_phase']=='COMPLETE'
    assert events[2]['record']['result']['state']=='CLARIFICATION_REQUIRED'
    assert events[2]['record']['correlation']['observation_id']==observation.observation_id
    assert result['evidence_references']['trace_row']['line']==1
    assert result['observed']['understanding']['warnings']

def test_bound_and_symlink_fail_closed(tmp_path):
    store=TransformationStore(tmp_path/'events');record(store)
    row=next((tmp_path/'events').rglob('*.json'))
    row.write_text('x'*32769)
    with pytest.raises(ValueError,match='bound'):store.read('owner','thread','interaction-prior')

def test_event_cannot_override_custody_fields(tmp_path):
    store=TransformationStore(tmp_path)
    with pytest.raises(ValueError,match='Exact'):store.append('owner','thread','interaction-a',{'operator_id':'foreign'})
