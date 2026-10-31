import json
import sys
from copy import deepcopy
from pathlib import Path
import pytest
from tests.test_execution_spine import runtime,envelope,authorize,CONTENTS,digest
from learning.contracts import digest as learning_hash, CandidateType, LearningCandidate
from learning.store import LearningStore,IntegrityError
from learning.service import LearningService
from learning.runtime import command,service,prompt_advisory


def built(tmp_path,kind='canonical',name='artifact',target='RUNTIME_OUTCOME'):
    r=runtime(tmp_path);e=envelope(tmp_path/name)
    if kind=='failure':e['understanding']['requirements'][0]['prohibited_states']=['file:calculator.py']
    if kind=='unresolved':e['understanding']['completion_conditions']=['unsupported condition']
    authorize(e)
    if kind in {'success','disconfirmed','canonical'}:
        from reality_primacy.build_validation import BuildValidationSession
        from reality_primacy import DecisionLedger
        from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
        from cryptography.hazmat.primitives import serialization
        from integration.reality_primacy import RealityAcceptanceClient
        key=Ed25519PrivateKey.generate()
        properties={'sum':5}
        verifier="from calculator import add; import json; print(json.dumps({'sum':add(2,3)}))"
        if kind=='canonical':
            controls={'first_operand':2}
            properties={'improvement_target':target,'causal_contrast':{'protocol':'controlled_intervention/1',
                'variable':'second_operand','baseline':{'input':0,'output':2,'controls':controls},
                'intervention':{'input':3,'output':5,'controls':controls},
                'recovery':{'input':0,'output':2,'controls':controls},'controls':controls,'unresolved':[]}}
            verifier="from calculator import add; import json; p="+repr(properties)+"; p['causal_contrast']['baseline']['output']=add(2,0); p['causal_contrast']['intervention']['output']=add(2,3); p['causal_contrast']['recovery']['output']=add(2,0); print(json.dumps(p))"
        if kind=='disconfirmed':verifier="import json; print(json.dumps({'sum':6}))"
        external=BuildValidationSession(grant={'operator_id':'operator','thread_id':'thread','request_hash':digest(e),
            'root':str(tmp_path/name),'claim_text':'2+3=5','required_files':list(CONTENTS),'authority_reference':'operator:test',
            'expected_observation':properties,'verification_command':[sys.executable,'-B','-c',verifier]},
            ledger=DecisionLedger(tmp_path/(name+'.rp.sqlite')),signing_key=key,key_id='test')
        r.prepare_build_reality_request=external.prepare
        r.reality_acceptance_client=RealityAcceptanceClient(external.evaluate,{'test':key.public_key().public_bytes(serialization.Encoding.Raw,serialization.PublicFormat.Raw)})
    out=r.handle_build_request('/build '+json.dumps(e))
    assert not getattr(r.context,'learning_error',None),getattr(r.context,'learning_error',None)
    return r,out,r.context.learning_candidate


def approve(r,c):
    return command(r,'/learning approve '+json.dumps({'id':c['candidate_id'],'hash':learning_hash(c)}))

@pytest.mark.parametrize('kind,status',[('success','PENDING_VALIDATION'),('failure','PENDING_VALIDATION'),('unresolved','PENDING_VALIDATION'),('canonical','ELIGIBLE')])
def test_capture_real_build(tmp_path,kind,status):
    r,out,c=built(tmp_path,kind)
    assert c['candidate_status']==status
    assert c['source_observation_ids'] and c['source_understanding_ids']
    assert c['lineage']['understanding_processing']['observation_id']==out['observation_ids'][-1]
    assert service(r).retrieve('operator',c['scope'])==[]
    if kind!='canonical':
        with pytest.raises(PermissionError):approve(r,c)
    else:
        record=approve(r,c)
        assert record['lesson']['generalization']=='NONE'
        command(r,'/learning use '+json.dumps(c['scope']))
        text=prompt_advisory(r)
        assert record['learning_id'] in text
        assert 'Known bounded failure' in text if kind=='failure' else c['claim']['rp_claim']==out['rp']['request']['evaluation']['resolution']['claim_snapshot']
        assert r.context.learning_influence['decision_changed'] is None
        assert any(x['kind']=='influence' for x in service(r).store.history('operator'))

@pytest.mark.parametrize('source',['observation','understanding','memory','model_output','PASS','CONFIRMED'])
def test_untrusted_source_never_approves(tmp_path,source):
    s=LearningService(LearningStore(tmp_path/'learning.sqlite'))
    scope={'operator_id':'operator','project':'project','domain':'domain','capability':'capability'}
    c=s.propose('operator',scope,{'claim':'always works'},'EXECUTION_SUCCESS',{source:True})
    assert c['candidate_status']=='PENDING_VALIDATION'
    with pytest.raises(PermissionError):s.review('operator',c['candidate_id'],learning_hash(c),'APPROVE')
    assert s.advisory('operator',scope,'test')[0]==''

@pytest.mark.parametrize('kind',[v.value for v in CandidateType])
def test_candidate_types_require_evidence(tmp_path,kind):
    s=LearningService(LearningStore(tmp_path/'learning.sqlite'))
    scope={'operator_id':'operator','project':'p','domain':'d','capability':'c'}
    c=s.propose('operator',scope,{'claim':'bounded'},kind)
    assert LearningCandidate(**c).to_dict()==c
    assert c['candidate_status']=='PENDING_VALIDATION'

@pytest.mark.parametrize('action',['REJECT','REVOKE'])
def test_inactive_cannot_influence(tmp_path,action):
    r,_,c=built(tmp_path,'canonical');s=service(r)
    item=approve(r,c) if action=='REVOKE' else c
    identity=item.get('learning_id',item.get('candidate_id'))
    s.review('operator',identity,learning_hash(item),action)
    restarted=LearningService(LearningStore(s.store.path))
    assert restarted.retrieve('operator',c['scope'])==[]
    assert restarted.advisory('operator',c['scope'],'later')[0]==''

@pytest.mark.parametrize('field',['operator_id','project','domain','capability'])
def test_scope_is_exact(tmp_path,field):
    r,_,c=built(tmp_path,'canonical');approve(r,c);scope=deepcopy(c['scope']);scope[field]='other'
    if field=='operator_id':
        with pytest.raises(PermissionError):service(r).retrieve('operator',scope)
    else:assert service(r).retrieve('operator',scope)==[]

def test_restart_and_corruption(tmp_path):
    r,_,c=built(tmp_path,'canonical');record=approve(r,c);s=service(r)
    restarted=LearningService(LearningStore(s.store.path))
    assert restarted.retrieve('operator',c['scope'])[0]==record
    preserved=restarted.store.get('operator',c['candidate_id'])['lineage']
    assert all(preserved[k]==v for k,v in c['lineage'].items())
    assert preserved['governance_decision']['decision']=='APPROVED'
    import sqlite3
    with sqlite3.connect(s.store.path) as db:db.execute("UPDATE journal SET payload='{}' WHERE seq=1")
    with pytest.raises(IntegrityError):restarted.retrieve('operator',c['scope'])

def test_stale_review_rejected(tmp_path):
    r,_,c=built(tmp_path,'canonical')
    with pytest.raises(ValueError):service(r).review('operator',c['candidate_id'],'bad','APPROVE')

def test_no_execution_or_spec_mutation(tmp_path):
    r,out,c=built(tmp_path,'canonical');before=deepcopy(out);state=r.context.runtime_state
    approve(r,c);command(r,'/learning use '+json.dumps(c['scope']));prompt_advisory(r)
    assert out==before and r.context.runtime_state==state
    assert not c['claim']['execution_authority']
    assert r.context.learning_influence['execution_authority'] is False

@pytest.mark.parametrize('resolution',['SUPERSEDE','COEXIST'])
def test_contradiction_adjudication_and_restart(tmp_path,resolution):
    import shutil
    r,_,a=built(tmp_path);old=approve(r,a)
    shutil.rmtree(tmp_path/'artifact')
    r,_,b=built(tmp_path,'canonical')
    s=service(r)
    assert b['candidate_status']=='ELIGIBLE'
    b=s.relate('operator',b['candidate_id'],old['learning_id'],'New governed evidence requires explicit adjudication')
    assert b['lineage']['contradicts'][0]['learning_id']==old['learning_id']
    assert s.store.get('operator',old['learning_id'])==old
    with pytest.raises(PermissionError):approve(r,b)
    if resolution=='COEXIST':
        # Current operator authority requires differentiated scope; identical
        # conflicting scope no longer permits a coexistence override.
        with pytest.raises(PermissionError):s.review('operator',b['candidate_id'],learning_hash(b),'APPROVE',resolution)
        assert s.retrieve('operator',a['scope'])==[old]
        return
    new=s.review('operator',b['candidate_id'],learning_hash(b),'APPROVE',resolution)
    restarted=LearningService(LearningStore(s.store.path))
    active=restarted.retrieve('operator',a['scope'])
    assert len(active)==(1 if resolution=='SUPERSEDE' else 2)
    assert len(restarted.retrieve('operator',a['scope'],include_inactive=True))==2
    if resolution=='SUPERSEDE':
        inactive=restarted.store.get('operator',old['learning_id'])
        assert inactive['status']=='SUPERSEDED' and inactive['superseded_by']==new['learning_id']
        with pytest.raises(ValueError):restarted.review('operator',old['learning_id'],learning_hash(inactive),'RESTORE')
        restarted.review('operator',new['learning_id'],learning_hash(new),'REVOKE')
        restored=restarted.review('operator',old['learning_id'],learning_hash(inactive),'RESTORE')
        assert restored['status']=='APPROVED'
        assert len(restarted.retrieve('operator',a['scope']))==1

@pytest.mark.parametrize('change',['claim','receipt','artifact'])
def test_evidence_tampering_blocks_capture(tmp_path,change):
    r,out,c=built(tmp_path,'failure')
    if change=='claim':out['build']['validation_status']='PASS'
    elif change=='receipt':Path(out['build']['receipt_path']).write_text('{}')
    else:(tmp_path/'artifact/calculator.py').write_text('changed')
    if change in {'claim','receipt'}:
        with pytest.raises(ValueError):service(r).capture_build(r,out)
    else:
        # A second capture must not strengthen an already captured historical candidate.
        recaptured=service(r).capture_build(r,out)
        assert recaptured['candidate_id']==c['candidate_id']

@pytest.mark.parametrize('kind',['success','failure','unresolved','canonical'])
def test_normal_boot_input_approval_and_prompt(tmp_path,monkeypatch,kind):
    from interactive_mode_ai import ModeRuntime
    from mode_operator.operator_identity import OperatorIdentity
    from mode_operator.operator_store import OperatorStore
    from memory.thread_store import ThreadStore
    from tests.test_execution_spine import Model
    import interactive_mode_ai as app
    monkeypatch.chdir(tmp_path)
    operators=OperatorStore(str(tmp_path/'operators'));identity=OperatorIdentity.create('operator')
    profile=operators.create_profile(identity)
    profile.update_operator_managed_info(preferred_name='Operator',timezone='UTC',language='English')
    thread=ThreadStore(str(tmp_path/'threads')).create_thread('operator')
    profile.active_thread_id=thread.thread_id;operators.save_profile(identity,profile)
    e=envelope(tmp_path/'artifact');e['authorization']['thread_id']=thread.thread_id
    if kind=='failure':e['understanding']['requirements'][0]['prohibited_states']=['file:calculator.py']
    if kind=='unresolved':e['understanding']['completion_conditions']=['unsupported']
    authorize(e)
    properties={'sum':5}
    verifier="from calculator import add; import json; print(json.dumps({'sum':add(2,3)}))"
    if kind=='canonical':
        controls={'first_operand':2}
        properties={'improvement_target':'RUNTIME_OUTCOME','causal_contrast':{'protocol':'controlled_intervention/1',
            'variable':'second_operand','baseline':{'input':0,'output':2,'controls':controls},
            'intervention':{'input':3,'output':5,'controls':controls},
            'recovery':{'input':0,'output':2,'controls':controls},'controls':controls,'unresolved':[]}}
        verifier="from calculator import add; import json; p="+repr(properties)+"; p['causal_contrast']['baseline']['output']=add(2,0); p['causal_contrast']['intervention']['output']=add(2,3); p['causal_contrast']['recovery']['output']=add(2,0); print(json.dumps(p))"
    grant={'operator_id':'operator','thread_id':thread.thread_id,'request_hash':digest(e),
        'root':str(tmp_path/'artifact'),'claim_text':'2+3=5','required_files':list(CONTENTS),
        'authority_reference':'operator:learning-proof','expected_observation':properties,
        'verification_command':[sys.executable,'-B','-c',verifier]}
    grant_path=tmp_path/'grant.json';grant_path.write_text(json.dumps(grant))
    config=tmp_path/'rp.json';config.write_text(json.dumps({'repository':r'C:\REALITY_PRIMACY','grant':str(grant_path),'ledger':str(tmp_path/'rp.sqlite')}))
    monkeypatch.setenv('MODE_RP_CONFIG',str(config))
    r=ModeRuntime('operator',str(tmp_path/'operators'),str(tmp_path/'threads'));r.build_runtime.provider.agent=Model()
    prompts=[];original=app.process_interaction
    def process(*args,**kwargs):
        prompts.append(kwargs['reasoning_input'])
        return original(*args,**kwargs)
    monkeypatch.setattr(app,'process_interaction',process)
    step=0
    def inputs(_):
        nonlocal step
        step+=1
        if step==1:return '/build '+json.dumps(e)
        candidate=r.context.learning_candidate
        if step==2:
            assert candidate['candidate_status']==('ELIGIBLE' if kind=='canonical' else 'PENDING_VALIDATION')
            return '/learning approve '+json.dumps({'id':candidate['candidate_id'],'hash':learning_hash(candidate)})
        if step==3:return '/learning use '+json.dumps(candidate['scope'])
        if step==4:return 'Explain the prior bounded result.'
        return 'exit'
    monkeypatch.setattr('builtins.input',inputs)
    try:
        r.boot();process_handle=r._rp_process
        r.run()
        assert prompts
        if kind in {'success','failure','unresolved'}:assert 'GOVERNED LEARNING ADVISORY' not in prompts[-1]
        else:
            records=service(r).retrieve('operator',r.context.learning_candidate['scope'])
            assert records[0]['learning_id'] in prompts[-1]
            assert r.context.learning_influence['surface']=='reasoning_prompt'
            assert any(h['kind']=='influence' for h in service(r).store.history('operator'))
            assert r.context.learning_evaluation['candidate_ids']==[]
        assert r._supervisor_thread is None
        assert process_handle.process.poll() is not None
    finally:r.shutdown()
