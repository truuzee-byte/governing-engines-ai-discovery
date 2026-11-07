"""Bounded inspection qualification of engineering interfaces; no provider/model.

Fixture grants are operator configuration. Positive evidence is measured from
fixture filesystem/current Understanding, never injected justified=True records.
"""
import json,sqlite3,hashlib,os
from pathlib import Path
from copy import deepcopy
from datetime import datetime,timezone,timedelta
from types import SimpleNamespace as NS
import pytest
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
from cryptography.hazmat.primitives import serialization
from reality_primacy.action_decision import ActionDecisionSession
from reality_primacy.decision_coordinator import DecisionLedger
from reality_primacy.contracts import ContractError
from integration.reality_primacy import RealityAcceptanceClient,digest
from data_governance.response_gate import evaluate
from supervisor_bridge.repository_reader import RepositoryReader,RepositoryAccessError

RP_SOURCE=Path('C:/REALITY_PRIMACY/reality_primacy/action_decision.py')
READER=Path('C:/MODE_AI/supervisor_bridge/repository_reader.py')

def fixture(tmp_path):
    from tests.test_conversation_understanding import runtime
    from integration.conversation_understanding import prepare
    r=runtime(tmp_path);q='Organize local files.'
    r.context.active_thread.messages.append(NS(role='operator',content=q,message_id='m'))
    proposal={'subject_id':'scenario','edits':[{'operation':'ADD','kind':'FACT','quote':q,'target_id':None}]}
    result=prepare(r,q,interpreter=lambda *_:(proposal,{}))
    assert not result['result']['errors'],result
    u=json.loads(json.dumps(r.context.understanding_result.final_understanding.to_dict()))
    root=tmp_path/'workspace';root.mkdir();(root/'a.txt').write_text('original')
    g={'operator_id':'op','thread_id':'t','objective_hash':digest(q),'root':str(root.resolve()),
        'understanding_store':str((tmp_path/'meaning.sqlite3').resolve()),'authority_reference':'isolated-fixture-operator-authorization',
        'valid_until':(datetime.now(timezone.utc)+timedelta(minutes=3)).isoformat(),'control':'ACTIVE','evidence':[]}
    policy={k:g[k] for k in ('operator_id','thread_id','objective_hash','root','valid_until')}
    policy.update(operation='INSPECT_DIRECTORY',executor_path=str(READER),executor_sha256=hashlib.sha256(READER.read_bytes()).hexdigest(),
        collector_sha256=hashlib.sha256(RP_SOURCE.read_bytes()).hexdigest(),recursive=False,max_entries=256)
    g['inspection_authorization']={'request':policy,'approval':{'operator_id':'op','action':'OBJECTIVE_READ_ONLY_INSPECTION','decision':'APPROVE','hash':digest(policy)}}
    path=tmp_path/'grant.json';path.write_text(json.dumps(g))
    payload={'objective':q,'understanding':u,'action':{'operation':'INSPECT_DIRECTORY','source':str(root.resolve()),'destination':None,'rationale':'Inspect current files before choosing modifications.'},'proposal_reference':'isolated-proposal:1'}
    r.context.assembled_context=NS(runtime=NS(context_ready=True));r.context.runtime_state='INTERPRETING'
    return r,q,g,path,payload


def session(tmp_path,path):
    key=Ed25519PrivateKey.generate();ledger=tmp_path/('ledger-'+str(len(list(tmp_path.glob('ledger-*'))))+'.sqlite')
    s=ActionDecisionSession(path,DecisionLedger(ledger),key,'fixture-key')
    c=RealityAcceptanceClient(s.evaluate,{'fixture-key':key.public_key().public_bytes(serialization.Encoding.Raw,serialization.PublicFormat.Raw)})
    return s,c


def consume(tmp_path, *, change=None, expected_state='CONFIRMED'):
    r,q,g,path,payload=fixture(tmp_path)
    if change:change(g,payload);path.write_text(json.dumps(g))
    s,c=session(tmp_path,path);req=s.prepare(payload);out=c.evaluate(req)
    if expected_state is not None:assert out['rp_state']==expected_state,out
    def call(op,value):return {'current':s.check_current,'claim_execution':s.claim_execution}[op](value)
    process=NS(client=c,call=call)
    r._objective_rp_grant_path=str(path);r._objective_rp_grant=g;r._objective_rp_process=process
    r.context.material_response_claim={'source':'ObjectiveActionRP/1','operator_input_hash':digest(q),'claim_id':req['claim_id']}
    r.context.objective_action_rp={'outcome':out,'action_hash':req['scope']['action_hash'],'grant_snapshot_hash':digest(g)}
    r.context.reality_primacy_result=out
    return r,q,g,path,payload,s,c,req,out,process


def execute(args,action=None,**changes):
    r,q,g,path,p,s,c,req,out,process=args
    kw=dict(process=process,operator_id='op',thread_id='t',objective=q,grant_path=str(path));kw.update(changes)
    return RepositoryReader(g['root']).execute_confirmed_inspection(action or p['action'],out,**kw)


def test_actual_measured_conditions_and_existing_executor(tmp_path):
    a=consume(tmp_path);r,q,g,path,p,s,c,req,out,process=a
    assert out['rp_state']=='CONFIRMED',out
    batch=req['evaluation']['batch'];assert len(batch['checks'])==5 and all(x['admissible'] and x['valid'] for x in batch['checks'])
    assert all('justified' not in str(x['content']) for x in batch['evidence_snapshots'])
    assert g['evidence']==[] and evaluate(r,q)['allowed']
    receipt=execute(a)
    assert receipt['action_executed'] and receipt['findings']['entries'][0]['name']=='a.txt'
    assert not receipt['findings']['source_contents_read'] and not receipt['objective_completion_established']
    assert (Path(g['root'])/'a.txt').read_text()=='original'
    (tmp_path/'canonical_receipt.json').write_text(json.dumps(out,indent=2))
    (tmp_path/'inspection_receipt.json').write_text(json.dumps(receipt,indent=2))
    assert not evaluate(r,q,generated_text='The task is complete.')['allowed']


def test_missing_measured_evidence_remains_pending(tmp_path,monkeypatch):
    real=ActionDecisionSession.collect_preconditions
    def missing(self,*args):
        observed=real(self,*args);observed.pop('execution_readiness');return observed
    monkeypatch.setattr(ActionDecisionSession,'collect_preconditions',missing)
    a=consume(tmp_path,expected_state='PENDING_VALIDATION');assert a[8]['rp_state']=='PENDING_VALIDATION'
    with pytest.raises(RepositoryAccessError):execute(a)


def test_failed_native_access_open_blocks_without_fallback(tmp_path,monkeypatch):
    r,q,g,path,p=fixture(tmp_path);s,c=session(tmp_path,path)
    original=ActionDecisionSession.reader_module
    def denied(self,policy):
        module=original(self,policy)
        def refuse(*args):raise PermissionError('fixture native access denied')
        module.WindowsDirectoryBinding._open_relative=refuse
        return module
    monkeypatch.setattr(ActionDecisionSession,'reader_module',denied)
    with pytest.raises(ContractError,match='fixture native access denied'):s.prepare(p)


def test_invalid_provenance_is_not_admitted(tmp_path,monkeypatch):
    from reality_primacy.rp_evidence_validator import EvidenceValidator
    real=EvidenceValidator.validate
    def invalid(self,resolution,evidence,**kwargs):
        items=deepcopy(evidence);items[0]['provenance']['references']=['unknown-source'];return real(self,resolution,items,**kwargs)
    monkeypatch.setattr(EvidenceValidator,'validate',invalid)
    a=consume(tmp_path,expected_state=None);assert not a[8]['accepted']
    assert any(x['admissible'] is False for x in a[7]['evaluation']['batch']['checks'])
    with pytest.raises(RepositoryAccessError):execute(a)


@pytest.mark.parametrize('change',['missing','approval','root','recursive','write','bounds'])
def test_invalid_operator_policy_blocks_before_request(tmp_path,change):
    r,q,g,path,p=fixture(tmp_path)
    if change=='missing':g.pop('inspection_authorization')
    elif change=='approval':g['inspection_authorization']['approval']['hash']='wrong'
    else:
        policy=g['inspection_authorization']['request']
        policy[{'root':'root','recursive':'recursive','write':'operation','bounds':'max_entries'}[change]]={'root':str(tmp_path),'recursive':True,'write':'MOVE_FILE','bounds':10000}[change]
        g['inspection_authorization']['approval']['hash']=digest(policy)
    path.write_text(json.dumps(g));s,c=session(tmp_path,path)
    with pytest.raises(ContractError):s.prepare(p)


@pytest.mark.parametrize('change',['objective','understanding','outside','write','rationale','schema'])
def test_wrong_payload_and_executor_action(tmp_path,change):
    a=consume(tmp_path);r,q,g,path,p,s,c,req,out,process=a
    action=deepcopy(p['action'])
    if change=='rationale':action['rationale']='Different decision';
    if change=='outside':action['source']=str(tmp_path.parent)
    if change=='write':action.update(operation='MOVE_FILE',destination=str(tmp_path/'move'))
    if change=='schema':action['extra']='hidden'
    if change=='understanding':
        with sqlite3.connect(g['understanding_store']) as db:db.execute('UPDATE heads SET version=version+1')
    extra={'objective':'Different objective'} if change=='objective' else {}
    with pytest.raises(RepositoryAccessError):execute(a,action,**extra)


@pytest.mark.parametrize('change',['stale','revoked','directory','executor','signature','owner','thread','action_scope','checksum'])
def test_stale_changed_or_unauthorized_dispatch_rejected(tmp_path,change):
    a=consume(tmp_path);r,q,g,path,p,s,c,req,out,process=a
    if change in {'stale','revoked','executor'}:
        if change=='stale':g['valid_until']='2000-01-01T00:00:00+00:00'
        if change=='revoked':g['control']='REVOKED'
        if change=='executor':g['inspection_authorization']['request']['executor_sha256']='wrong'
        path.write_text(json.dumps(g))
    if change=='directory':
        info=Path(g['root']).stat();os.utime(g['root'],ns=(info.st_atime_ns,info.st_mtime_ns+1000000000))
    if change=='signature':out['response']['signature']='invalid'
    if change=='action_scope':out['request']['scope']['action_hash']='wrong'
    if change=='checksum':
        with sqlite3.connect(g['understanding_store']) as db:db.execute("UPDATE versions SET checksum='wrong'")
    kwargs={'operator_id':'other'} if change=='owner' else {'thread_id':'other'} if change=='thread' else {}
    with pytest.raises(RepositoryAccessError):execute(a,**kwargs)


def test_expired_signed_confirmation_rejected(tmp_path):
    a=consume(tmp_path);a[6]._clock=lambda:datetime.now(timezone.utc)+timedelta(days=1)
    with pytest.raises(RepositoryAccessError):execute(a)


def test_single_use_and_executor_refusal(tmp_path,monkeypatch):
    a=consume(tmp_path)
    def denied(*args,**kwargs):raise PermissionError('fixture access refused')
    monkeypatch.setattr(RepositoryReader,'_list_bound',denied)
    with pytest.raises(RepositoryAccessError,match='fixture access refused') as error:execute(a)
    assert error.value.inspection_started
    with pytest.raises(RepositoryAccessError,match='already consumed'):execute(a)


def test_list_limits_protected_files_and_no_content_read(tmp_path):
    (tmp_path/'a.txt').write_text('payload');(tmp_path/'.env').write_text('fixture-private')
    result=RepositoryReader(str(tmp_path)).list_directory()
    assert [x['name'] for x in result['entries']]==['a.txt']
    assert result['excluded']==[{'name':'.env','reason':'PROTECTED_REPOSITORY_PATH'}]
    with pytest.raises(RepositoryAccessError):RepositoryReader(str(tmp_path)).list_directory(max_entries=1)
    with pytest.raises(RepositoryAccessError):RepositoryReader(str(tmp_path))._resolve('a.txt:stream')


def test_links_never_followed(tmp_path):
    outside=tmp_path/'outside';outside.mkdir();(outside/'secret.txt').write_text('fixture')
    root=tmp_path/'root';root.mkdir()
    try:(root/'linked').symlink_to(outside,target_is_directory=True)
    except OSError:pytest.skip('Host does not permit fixture symlink creation')
    reader=RepositoryReader(str(root));result=reader.list_directory()
    assert result['entries']==[] and result['excluded'][0]['reason']=='LINK_NOT_FOLLOWED'
    with pytest.raises(RepositoryAccessError):reader.list_directory('linked')


def test_real_private_service_and_dispatch(tmp_path):
    from integration.rp_process import ExternalRPProcess
    r,q,g,path,p=fixture(tmp_path)
    process=ExternalRPProcess('C:/REALITY_PRIMACY',str(path),str(tmp_path/'private.sqlite'),module='reality_primacy.action_decision')
    try:
        req=process.call('prepare',p);out=process.client.evaluate(req)
        assert out['accepted'],out
        result=RepositoryReader(g['root']).execute_confirmed_inspection(p['action'],out,process=process,operator_id='op',thread_id='t',objective=q,grant_path=str(path))
        assert result['findings']['entries'][0]['name']=='a.txt'
        (tmp_path/'private_rp_receipt.json').write_text(json.dumps(out,indent=2))
        (tmp_path/'private_inspection_receipt.json').write_text(json.dumps(result,indent=2))
        with pytest.raises(RepositoryAccessError,match='already consumed'):
            RepositoryReader(g['root']).execute_confirmed_inspection(p['action'],out,process=process,operator_id='op',thread_id='t',objective=q,grant_path=str(path))
    finally:process.close()


def test_normal_handoff_uses_real_rp_and_existing_reader(tmp_path,monkeypatch):
    from integration.objective_action_rp import connect,propose_and_evaluate
    from data_governance.context_admission import Admission
    from agents.reasoning_agent import ReasoningResult
    from interactive_mode_ai import ModeRuntime,RuntimeState
    from runtime_observation import RuntimeObservationCollector
    from runtime_observation.observation_store import RuntimeObservationStore
    from types import MethodType
    r,q,g,path,p=fixture(tmp_path)
    r.context.runtime_state=RuntimeState.INTERPRETING
    r.runtime_observation_collector=RuntimeObservationCollector(store=RuntimeObservationStore(tmp_path/'observations'))
    r._observe_runtime_event=MethodType(ModeRuntime._observe_runtime_event,r)
    class Proposal:
        def generate(self,**kw):return ReasoningResult('fixture-proposal','no-provider','no-provider','fixture draft','fixture critique',json.dumps(p['action']),0)
    monkeypatch.setattr('agents.reasoning_agent.ReasoningAgent',Proposal)
    a=Admission('op','t');assert a.consider('OPERATOR_INPUT','q',q,source='isolated fixture');admitted=a.finish()
    connect(r,{'repository':'C:/REALITY_PRIMACY','grant':str(path.resolve()),'ledger':str((tmp_path/'normal.sqlite').resolve())})
    try:
        trace=propose_and_evaluate(r,q,admitted)
        assert trace['state']=='READ_ONLY_INSPECTION_RETURNED',trace
        assert trace['outcome']['accepted'] and trace['consumer_gate']['allowed']
        assert trace['inspection_receipt']['findings']['entries'][0]['name']=='a.txt'
        persisted=r.runtime_observation_collector.store.load_record('op',trace['observation_id'])
        assert persisted.metadata['observed_outcome']['inspection_receipt']==trace['inspection_receipt']
        (tmp_path/'handoff_trace.json').write_text(json.dumps(trace,indent=2))
    finally:r._objective_rp_process.close()


def test_model_cannot_submit_evidence_or_approval(tmp_path):
    r,q,g,path,p=fixture(tmp_path);p['evidence']=[{'justified':True}]
    s,c=session(tmp_path,path)
    with pytest.raises(ContractError,match='Exact action evaluation payload required'):s.prepare(p)


def test_target_directory_changed_before_confirmation_is_rejected(tmp_path):
    r,q,g,path,p=fixture(tmp_path);s,c=session(tmp_path,path);req=s.prepare(p)
    info=Path(g['root']).stat();os.utime(g['root'],ns=(info.st_atime_ns,info.st_mtime_ns+1000000000))
    result=c.evaluate(req)
    assert not result['accepted'] and 'changed' in result['reason']


def test_reader_protected_path_is_not_execution_ready(tmp_path):
    r,q,g,path,p=fixture(tmp_path);target=Path(g['root'])/'.git';target.mkdir()
    p['action']['source']=str(target)
    s,c=session(tmp_path,path);result=c.evaluate(s.prepare(p))
    assert result['rp_state']=='DISCONFIRMED' and not result['accepted']


def test_stale_grant_cannot_start_session(tmp_path):
    r,q,g,path,p=fixture(tmp_path);g['valid_until']='2000-01-01T00:00:00+00:00';path.write_text(json.dumps(g))
    with pytest.raises(ContractError,match='stale'):session(tmp_path,path)


def test_new_nested_target_identity_invalidates_confirmation(tmp_path):
    r,q,g,path,p=fixture(tmp_path);nested=Path(g['root'])/'nested';nested.mkdir();p['action']['source']=str(nested)
    s,c=session(tmp_path,path);req=s.prepare(p);result=c.evaluate(req);assert result['accepted']
    info=nested.stat();os.utime(nested,ns=(info.st_atime_ns,info.st_mtime_ns+1000000000))
    with pytest.raises(ContractError,match='target changed'):s.check_current({'request_id':req['request_id'],'scope':req['scope']})


def test_preloaded_justification_cannot_replace_measured_evidence(tmp_path):
    r,q,g,path,p=fixture(tmp_path);g['evidence']=[{'justified':True}];path.write_text(json.dumps(g))
    s,c=session(tmp_path,path)
    with pytest.raises(ContractError,match='Preloaded action attestations'):s.prepare(p)


def test_outside_proposal_rejected_before_target_probe(tmp_path,monkeypatch):
    from reality_primacy.action_decision import bound_action
    import reality_primacy.action_decision as action_module
    root=tmp_path/'root';root.mkdir();outside=tmp_path/'outside';visited=[];real=action_module.unlinked
    def probe(path):visited.append(Path(path));return real(path)
    monkeypatch.setattr(action_module,'unlinked',probe)
    with pytest.raises(ContractError,match='outside authorized workspace'):
        bound_action(str(root),{'operation':'INSPECT_DIRECTORY','source':str(outside),'destination':None,'rationale':'Unapproved target'})
    assert outside not in visited and visited==[root]


def continuation_fixture(tmp_path,monkeypatch,choices,after_observation=None,*,file_reads=False):
    """Real local RP/guarded reads; scripted model only, never behavioral proof."""
    from types import MethodType
    from interactive_mode_ai import ModeRuntime,RuntimeState
    from runtime_observation import RuntimeObservationCollector
    from runtime_observation.observation_store import RuntimeObservationStore
    from data_governance.context_admission import Admission
    from agents.reasoning_agent import ReasoningResult
    r,q,g,path,p=fixture(tmp_path);root=Path(g['root']);(root/'child').mkdir();(root/'child/b.txt').write_text('child fixture')
    if file_reads:
        policy=g['inspection_authorization']['request']
        policy.update(operation='READ_ONLY_OBSERVATION',operations=['INSPECT_DIRECTORY','READ_FILE'],max_bytes=16384,max_chars=8192)
        g['inspection_authorization']['approval']['hash']=digest(policy);path.write_text(json.dumps(g))
    s,c=session(tmp_path,path);events=[];prompts=[];stages=[]
    def call(operation,value):
        events.append(operation)
        # Match the real private JSON transport, including enum serialization.
        return {'prepare':s.prepare,'current':s.check_current,'claim_execution':s.claim_execution}[operation](json.loads(json.dumps(value)))
    r._objective_rp_process=NS(client=c,call=call);r._objective_rp_grant=g;r._objective_rp_grant_path=str(path)
    r.context.runtime_state=RuntimeState.INTERPRETING
    r.runtime_observation_collector=RuntimeObservationCollector(store=RuntimeObservationStore(tmp_path/'observations'))
    def observe(self,name,payload):
        record=ModeRuntime._observe_runtime_event(self,name,payload)
        if after_observation:after_observation(self,payload,record)
        return record
    r._observe_runtime_event=MethodType(observe,r)
    class Proposal:
        def _call_model(self,*a,**kw):stages.append(kw['stage'])
        def generate(self,**kw):
            prompts.append(kw['user_input'])
            for stage in ('draft','critique','final'):self._call_model(stage=stage)
            choice=choices[len(prompts)-1]
            action={**p['action'],'operation':choice[0],'source':str(root/choice[1]),'rationale':'Synthetic next proposal '+str(len(prompts))}
            return ReasoningResult('proposal:'+str(len(prompts)),'no-provider','no-provider','draft','critique',json.dumps(action),0)
    monkeypatch.setattr('agents.reasoning_agent.ReasoningAgent',Proposal)
    admission=Admission('op','t');assert admission.consider('OPERATOR_INPUT','q',q,source='fixture')
    return r,q,admission.finish(),events,prompts,stages


def test_continuation_consumes_receipts_with_fresh_rp_and_stops_unsupported(tmp_path,monkeypatch):
    from integration.objective_action_rp import continue_objective
    r,q,base,events,prompts,stages=continuation_fixture(tmp_path,monkeypatch,[('INSPECT_DIRECTORY',''),('INSPECT_DIRECTORY','child'),('MOVE_FILE','a.txt')])
    result=continue_objective(r,q,base)
    (tmp_path/'CONTINUATION_RECEIPT.json').write_text(json.dumps(result,indent=2))
    (tmp_path/'CONTINUATION_PUBLIC_KEYS.json').write_text(json.dumps({k:v.hex() for k,v in r._objective_rp_process.client._keys.items()},indent=2))
    assert result['state']=='STOPPED_UNSUPPORTED_OPERATION',result
    assert len(result['steps'])==3 and result['provider_attempts_used']==9
    assert len(stages)==9 and result['total_provider_attempts_upper_bound']==10
    a,b=result['steps'][:2]
    assert a['request']['request_id']!=b['request']['request_id']
    assert events.count('prepare')==2 and events.count('claim_execution')==2
    sources=[x for x in prompts[1].sources if x['record']['artifact_type']=='TOOL_RESULT']
    assert len(sources)==1 and 'child' in sources[0]['content']
    assert a['observation_id'] in sources[0]['record']['lineage'] and a['inspection_receipt']['rp_receipt_id'] in sources[0]['record']['lineage']
    assert 'proposal_reasoning' not in sources[0]['content'] and 'evidence_snapshots' not in sources[0]['content']
    assert len(sources[0]['content'])<4096
    assert all(s['request']['scope']['objective_hash']==result['objective_hash'] for s in (a,b))
    assert not result['objective_completion_established'] and r.context.learning_evaluation['candidate_ids']==[]
    assert (Path(r._objective_rp_grant['root'])/'a.txt').read_text()=='original'
    (tmp_path/'CONTINUATION_RECEIPT.json').write_text(json.dumps(result,indent=2))


def test_continuation_repeated_path_ignores_rationale_changes(tmp_path,monkeypatch):
    from integration.objective_action_rp import continue_objective
    r,q,base,events,prompts,stages=continuation_fixture(tmp_path,monkeypatch,[('INSPECT_DIRECTORY',''),('INSPECT_DIRECTORY','.')])
    result=continue_objective(r,q,base)
    assert result['state']=='STOPPED_NO_PROGRESS_REPEATED_INSPECTION'
    assert events.count('prepare')==events.count('claim_execution')==1 and len(prompts)==2


@pytest.mark.parametrize('budget,expected_steps',[(1,0),(3,0),(4,1),(6,1)])
def test_continuation_provider_budget_reserves_interpretation_and_full_stages(tmp_path,monkeypatch,budget,expected_steps):
    from integration.objective_action_rp import continue_objective
    r,q,base,events,prompts,stages=continuation_fixture(tmp_path,monkeypatch,[('INSPECT_DIRECTORY','')])
    result=continue_objective(r,q,base,provider_attempt_ceiling=budget)
    assert result['state']=='STOPPED_PROVIDER_BUDGET' and len(prompts)==expected_steps
    assert result['provider_attempts_used']==3*expected_steps and result['total_provider_attempts_upper_bound']<=budget


def test_continuation_governance_rejection_never_dispatches(tmp_path,monkeypatch):
    from integration.objective_action_rp import continue_objective
    r,q,base,events,prompts,stages=continuation_fixture(tmp_path,monkeypatch,[('INSPECT_DIRECTORY','')])
    monkeypatch.setattr('data_governance.response_gate.evaluate',lambda *a,**kw:{'allowed':False,'reasons':['fixture governance denial']})
    result=continue_objective(r,q,base)
    assert result['state']=='STOPPED_ACTION_CONFIRMATION_NOT_AVAILABLE'
    assert 'prepare' in events and 'claim_execution' not in events and len(prompts)==1


@pytest.mark.parametrize('change',['directory','observation','grant','understanding'])
def test_continuation_changed_evidence_stops_before_second_reasoning(tmp_path,monkeypatch,change):
    from integration.objective_action_rp import continue_objective
    def after(r,payload,record):
        if change=='directory':(Path(r._objective_rp_grant['root'])/'changed.txt').write_text('new fixture')
        elif change=='observation':r.runtime_observation_collector.store.load_record=lambda *a:None
        elif change=='grant':
            g=deepcopy(r._objective_rp_grant);g['control']='REVOKED';Path(r._objective_rp_grant_path).write_text(json.dumps(g))
        else:r.context.understanding_result.state='PENDING_VALIDATION'
    r,q,base,events,prompts,stages=continuation_fixture(tmp_path,monkeypatch,[('INSPECT_DIRECTORY','')],after)
    result=continue_objective(r,q,base)
    assert result['state']=='STOPPED_AUTHORIZATION_OR_EVIDENCE_UNAVAILABLE' and len(prompts)==1,result


def test_continuation_halt_and_step_bound(tmp_path,monkeypatch):
    from integration.objective_action_rp import continue_objective
    r,q,base,events,prompts,stages=continuation_fixture(tmp_path,monkeypatch,[('INSPECT_DIRECTORY','')])
    r._halt_latch={'fixture':True}
    assert continue_objective(r,q,base)['state']=='STOPPED_RUNTIME_CONTROL' and not stages
    r._halt_latch=None
    result=continue_objective(r,q,base,max_steps=1)
    assert result['state']=='STOPPED_STEP_LIMIT' and len(prompts)==1


def test_continuation_wrong_owner_prompt_and_objective_fail_closed(tmp_path,monkeypatch):
    from integration.objective_action_rp import continue_objective
    from data_governance.context_admission import Admission
    r,q,base,events,prompts,stages=continuation_fixture(tmp_path,monkeypatch,[])
    wrong=Admission('other','t');wrong.consider('OPERATOR_INPUT','q',q,source='fixture')
    for query,prompt in [(q+' altered',base),(q,wrong.finish()),(q,str(base))]:
        result=continue_objective(r,query,prompt)
        assert result['state']=='STOPPED_AUTHORIZATION_OR_EVIDENCE_UNAVAILABLE'
    assert not stages


def test_continuation_real_reasoning_stages_receive_compact_tool_evidence(tmp_path,monkeypatch):
    from agents.reasoning_agent import ReasoningAgent,ModelCallResult
    from integration.objective_action_rp import continue_objective
    r,q,base,events,prompts,stages=continuation_fixture(tmp_path,monkeypatch,[])
    root=Path(r._objective_rp_grant['root']);calls=[];options=[]
    class Client:
        def with_options(self,**kw):options.append(kw);return self
    def init(self):self.client=Client();self.provider='offline';self.model='offline'
    def model(self,prompt,**kw):
        index=len(calls)//3;calls.append({'stage':kw['stage'],'prompt':prompt})
        action={'operation':'INSPECT_DIRECTORY','source':str(root if index==0 else root/'child'),'destination':None,'rationale':'Inspect metadata.'}
        if kw['stage']=='REASONING_CRITIQUE':
            from tests.test_completed_action_awareness import scoped_critique,review_context_from_stage
            return ModelCallResult(scoped_critique(action,review_context_from_stage(prompt)),None)
        return ModelCallResult(json.dumps(action),None)
    monkeypatch.setattr(ReasoningAgent,'__init__',init);monkeypatch.setattr(ReasoningAgent,'_call_model',model)
    monkeypatch.setattr('agents.reasoning_agent.ReasoningAgent',ReasoningAgent)
    result=continue_objective(r,q,base,max_steps=2)
    assert result['state']=='STOPPED_STEP_LIMIT' and result['returned_inspection_count']==2,result
    assert len(calls)==6 and options==[{'max_retries':0,'timeout':90}]*2
    assert all('ObjectiveInspectionEvidence/1' in row['prompt'] and result['steps'][0]['observation_id'] in row['prompt'] for row in calls[3:])
    assert result['action_executed'] and all(e['state']=='RETURNED' for e in result['provider_attempts'])


def test_continuation_counts_failed_stage_without_retry(tmp_path,monkeypatch):
    from integration.objective_action_rp import continue_objective
    r,q,base,events,prompts,stages=continuation_fixture(tmp_path,monkeypatch,[('INSPECT_DIRECTORY','')])
    import agents.reasoning_agent as agent_module
    def failed(self,*args,**kw):raise OSError('fixture provider failure; not transmitted')
    monkeypatch.setattr(agent_module.ReasoningAgent,'_call_model',failed)
    result=continue_objective(r,q,base)
    assert result['provider_attempts_used']==1 and len(prompts)==1 and not events
    assert result['provider_attempts'][0]['state']=='FAILED'


def test_continuation_unexpected_extra_stage_cannot_exceed_budget(tmp_path,monkeypatch):
    from integration.objective_action_rp import continue_objective
    r,q,base,events,prompts,stages=continuation_fixture(tmp_path,monkeypatch,[])
    import agents.reasoning_agent as agent_module
    def extra(self,**kw):
        for _ in range(4):self._call_model(stage='unexpected')
        pytest.fail('Fourth call bypassed ceiling')
    monkeypatch.setattr(agent_module.ReasoningAgent,'generate',extra)
    result=continue_objective(r,q,base,provider_attempt_ceiling=4)
    assert result['provider_attempts_used']==3 and len(stages)==3 and not events
    assert result['state']=='STOPPED_ACTION_RP_HANDOFF_BLOCKED'


def test_continuation_identical_information_and_context_bound_stop(tmp_path,monkeypatch):
    from integration.objective_action_rp import continue_objective
    r,q,base,events,prompts,stages=continuation_fixture(tmp_path,monkeypatch,[('INSPECT_DIRECTORY',''),('INSPECT_DIRECTORY','child'),('INSPECT_DIRECTORY','other')])
    root=Path(r._objective_rp_grant['root']);(root/'other').mkdir();(root/'other/b.txt').write_text('child fixture')
    result=continue_objective(r,q,base)
    assert result['state']=='STOPPED_NO_NEW_INSPECTION_INFORMATION' and len(prompts)==3


def test_continuation_projection_limit_fails_without_truncating_evidence(tmp_path,monkeypatch):
    from integration.objective_action_rp import continue_objective
    r,q,base,events,prompts,stages=continuation_fixture(tmp_path,monkeypatch,[('INSPECT_DIRECTORY','')])
    root=Path(r._objective_rp_grant['root'])
    for i in range(220):(root/(str(i)+'x'*60+'.txt')).write_text('fixture')
    result=continue_objective(r,q,base)
    assert result['state']=='STOPPED_AUTHORIZATION_OR_EVIDENCE_UNAVAILABLE' and len(prompts)==1
    assert result['error']['message']=='Bounded inspection context exceeded'


def test_continuation_evidence_changed_during_reasoning_blocks_next_rp(tmp_path,monkeypatch):
    from integration.objective_action_rp import continue_objective
    import agents.reasoning_agent as module
    r,q,base,events,prompts,stages=continuation_fixture(tmp_path,monkeypatch,[('INSPECT_DIRECTORY',''),('INSPECT_DIRECTORY','child')])
    original=module.ReasoningAgent.generate
    def changed(self,**kw):
        result=original(self,**kw)
        if len(prompts)==2:(Path(r._objective_rp_grant['root'])/'during-inference.txt').write_text('fixture')
        return result
    monkeypatch.setattr(module.ReasoningAgent,'generate',changed)
    result=continue_objective(r,q,base)
    assert result['state']=='STOPPED_ACTION_RP_HANDOFF_BLOCKED' and len(prompts)==2
    assert events.count('prepare')==events.count('claim_execution')==1
