import json
from copy import deepcopy
from types import SimpleNamespace as NS
import pytest
from learning.contracts import digest
from persistent_memory.persistent_memory_manager import PersistentMemoryManager
from persistent_memory.persistent_memory_store import PersistentMemoryStore
from data_governance.artifact_metadata import GovernedArtifactMetadata
from data_governance.diagnostics import inspect

def memory(tmp_path):
    m=PersistentMemoryManager(PersistentMemoryStore(tmp_path))
    c=m.propose_create_memory('operator','Reports use CSV.','thread','message','Reports use CSV.').candidate
    return m,m.confirm_candidate(c,'yes').record

def test_memory_lifecycle_preserves_every_version(tmp_path):
    m,r=memory(tmp_path)
    assert r.version==1 and r.governed_metadata['validation_status']=='OPERATOR_ATTESTED'
    for action in ['ARCHIVE','RESTORE','REMOVE']:
        r=m.lifecycle('operator',r.memory_id,action,'yes')
    versions=m.store.history('operator',r.memory_id)
    assert [v['version'] for v in versions]==[1,2,3,4]
    assert [v['status'] for v in versions]==['ACTIVE','ARCHIVED','ACTIVE','REMOVED']
    assert m.retrieve_memories('operator')==[]
    assert len({v['governance_decision']['decision_id'] for v in versions})==4

@pytest.mark.parametrize('source',['OBSERVATION','UNDERSTANDING','LEARNING','MODEL_OUTPUT'])
def test_raw_sources_rejected_as_ordinary_memory(tmp_path,source):
    m=PersistentMemoryManager(PersistentMemoryStore(tmp_path))
    c=m.propose_create_memory('operator','Raw claim','thread','message','Raw claim',metadata={'source_kind':source}).candidate
    with pytest.raises(PermissionError):m.confirm_candidate(c,'yes')
    assert m.store.load_records_for_operator('operator')==[]

def test_memory_cannot_reuse_approval_for_changed_content(tmp_path):
    m,r=memory(tmp_path);r.content='substituted'
    with pytest.raises(PermissionError):m.store.save_record(r)
    assert m.store.load_record('operator',r.memory_id).content=='Reports use CSV.'
    with pytest.raises((PermissionError,ValueError)):m.lifecycle('other',r.memory_id,'REMOVE','yes')

def test_metadata_requires_exact_authorized_transition():
    meta=GovernedArtifactMetadata('id','operator',('source',),'test','operator','OPERATOR_DATA','UNVALIDATED','PENDING','NOT_APPLICABLE','CANDIDATE','CANDIDATE')
    with pytest.raises(PermissionError):meta.transition({'durability_status':'DURABLE'},{})
    with pytest.raises(PermissionError):meta.transition({'authority':'other'},{})
    with pytest.raises(PermissionError):meta.transition({'classification':'REALITY_DATA'},{})
    change={'governance_status':'APPROVED'}
    decision={'decision_id':'g','decision':'APPROVED','subject_id':'id','operator_id':'operator',
        'lineage':{'metadata_hash':digest(meta.to_dict()),'metadata_changes':change,'field_authorities':{'governance_status':'Governance'}}}
    assert meta.transition(change,decision).lineage==('g',)
    assert GovernedArtifactMetadata.from_dict(json.loads(json.dumps(meta.to_dict())))==meta

def test_diagnostics_do_not_mutate_memory(tmp_path):
    m,r=memory(tmp_path);runtime=NS(context=NS(identity=NS(operator_id='operator')),persistent_memory_manager=m)
    before={p.name:p.read_bytes() for p in tmp_path.iterdir() if p.is_file()}
    report=inspect(runtime,r.memory_id)
    after={p.name:p.read_bytes() for p in tmp_path.iterdir() if p.is_file()}
    assert before==after
    assert report['memory'][0]['versions'][0]['governance_decision']['decision']=='APPROVED'
    assert report['subsystems']['memory']=={'ACTIVE':1}

def test_material_response_is_blocked_but_trivial_conversation_is_not():
    from data_governance.response_gate import evaluate
    r=NS(context=NS(identity=NS(operator_id='operator'),active_thread=NS(thread_id='thread')))
    assert evaluate(r,'Hello')['allowed']
    assert not evaluate(r,'Hello',generated_text='I guarantee this is safe to deploy.')['allowed']
    r.context.knowledge_classification=NS(primary_domain=NS(value='EXTERNAL_CURRENT'))
    result=evaluate(r,'Confirm the current result')
    assert not result['allowed'] and result['material']

@pytest.mark.parametrize('target,dimension',[('INTERPRETATION_CORRECTNESS','CORRECTNESS'),('RUNTIME_OUTCOME','OUTCOME'),('OPERATOR_CONTINUITY','OPERATOR'),('RUNTIME_ARCHITECTURE','SYSTEM')])
def test_all_dimensions_use_real_governed_evidence(tmp_path,target,dimension):
    from tests.test_learning import built
    from integration.interaction_learning import evaluate
    from learning.runtime import service
    r,out,c=built(tmp_path,target=target)
    obs=r.runtime_observation_collector.store.load_record('operator',out['observation_ids'][-1])
    package={'scope':c['scope'],'outcome':out}
    result=evaluate(r,obs,package)
    assert result['status']=='ELIGIBLE' and len(result['candidate_ids'])==1
    candidate=service(r).store.get('operator',result['candidate_ids'][0])
    assert candidate['source_build_id'] is None
    assert candidate['lineage']['canonical_v2']['classification']['dimensions']==[dimension]
    assert evaluate(r,obs,package)['candidate_ids']==result['candidate_ids']
    assert evaluate(r,obs)['candidate_ids']==[]

@pytest.mark.parametrize('action',['MAINTAIN_EXISTING','SUPERSEDE','REPLACE','MERGE_COMPATIBLE','SUSPEND_BOTH','REQUEST_ADDITIONAL_EVIDENCE','COEXIST'])
def test_conflict_options_preserve_sources(tmp_path,action):
    import shutil
    from tests.test_learning import built,approve
    from learning.runtime import service
    from learning.conflicts import resolve
    r,_,c=built(tmp_path);left=approve(r,c)
    if action!='COEXIST':shutil.rmtree(tmp_path/'artifact')
    r,_,c=built(tmp_path,name='other' if action=='COEXIST' else 'artifact');right=approve(r,c)
    manager=service(r)
    result=resolve(manager,'operator',left['learning_id'],right['learning_id'],digest(left),digest(right),action)
    assert result['decision']['lineage']['sources']==[left['learning_id'],right['learning_id']]
    assert manager.store.get('operator',left['learning_id'])
    assert manager.store.get('operator',right['learning_id'])
    if action=='MERGE_COMPATIBLE':assert len(result['records'])==3 and result['records'][0]['lineage']['merge_sources']==[left,right]
    if action=='REQUEST_ADDITIONAL_EVIDENCE':assert result['resolution_state']=='PENDING'

@pytest.mark.parametrize('kind',['NEW_EVIDENCE','CONTRADICTORY_EVIDENCE','ARCHITECTURE_CHANGE','OPERATOR_PREFERENCE_CHANGE','GOVERNANCE_POLICY_CHANGE','RP_INVALIDATION','REPEATED_EXECUTION_FAILURE'])
def test_trigger_dedup_and_governed_stop(tmp_path,kind):
    from tests.test_learning import built,approve
    from learning.runtime import service
    from learning.revalidation_sources import trigger
    r,_,c=built(tmp_path,target='OPERATOR_CONTINUITY');record=approve(r,c);manager=service(r)
    changed=trigger(manager,'operator',kind,'observed-source',c['scope'])
    assert bool(changed)==(kind!='NEW_EVIDENCE')
    assert trigger(manager,'operator',kind,'observed-source',c['scope'])==[]
    assert any(h['kind']=='revalidation_trigger' for h in manager.store.history('operator'))

def test_preference_change_is_detected_before_use(tmp_path):
    from tests.test_learning import built,approve
    from learning.runtime import service,prompt_advisory,command
    from learning.revalidation_sources import poll
    r,_,c=built(tmp_path,target='OPERATOR_CONTINUITY');record=approve(r,c)
    r.context.profile=NS(operator_managed=NS(language='English'))
    changed=poll(r,service(r))
    assert changed and changed[0]['status']=='SUSPENDED'
    assert changed[0]['lineage']['revalidation_history'][-1]['trigger']=='OPERATOR_PREFERENCE_CHANGE'

def test_learning_explainability_and_read_only_diagnostics(tmp_path):
    from tests.test_learning import built,approve
    from learning.runtime import service,command,prompt_advisory
    r,_,c=built(tmp_path);record=approve(r,c)
    command(r,'/learning use '+json.dumps(c['scope']));prompt_advisory(r)
    path=service(r).store.path;before=path.read_bytes()
    report=inspect(r,record['learning_id'])
    assert path.read_bytes()==before
    assert not report['missing_links']
    assert report['learning_memory_versions'] and report['context_history']

def test_memory_update_preserves_original_source(tmp_path):
    m,r=memory(tmp_path)
    candidate=m.propose_update_memory(operator_id='operator',memory_id=r.memory_id,new_content='Reports use JSON.',
        source_thread_id='thread',source_message_id='new-message',original_operator_statement='Reports use JSON.').candidate
    result=m.confirm_candidate(candidate,'yes')
    versions=m.store.history('operator',r.memory_id)
    assert result.record.content=='Reports use JSON.' and len(versions)==2
    assert result.receipt.memory_version==2
    assert result.receipt.governance_reference==result.record.governance_decision['decision_id']
    assert versions[0]['content']=='Reports use CSV.' and versions[1]['source_message_id']=='new-message'

def test_legacy_version_is_preserved_without_retroactive_approval(tmp_path):
    m,r=memory(tmp_path/'original')
    legacy=r.to_dict();legacy.update(version=0,previous_hash=None,governance_decision={},governed_metadata={})
    folder=tmp_path/'legacy';(folder/'operator').mkdir(parents=True)
    legacy_file=folder/'operator'/f'{r.memory_id}.json';legacy_file.write_text(json.dumps(legacy))
    before=legacy_file.read_bytes();m=PersistentMemoryManager(PersistentMemoryStore(folder))
    assert m.retrieve_memories('operator')==[]
    candidate=m.propose_update_memory(operator_id='operator',memory_id=r.memory_id,new_content='Corrected.',
        source_thread_id='thread',source_message_id='correction',original_operator_statement='Corrected.').candidate
    result=m.confirm_candidate(candidate,'yes')
    assert result.record.version==2 and legacy_file.read_bytes()==before
    assert not m.store.history('operator',r.memory_id)[0]['governance_decision']

def test_normal_boot_material_gate_prevents_model_call(tmp_path,monkeypatch):
    from interactive_mode_ai import ModeRuntime
    import interactive_mode_ai as app
    from mode_operator.operator_identity import OperatorIdentity
    from mode_operator.operator_store import OperatorStore
    from memory.thread_store import ThreadStore
    monkeypatch.chdir(tmp_path)
    operators=OperatorStore(str(tmp_path/'operators'));identity=OperatorIdentity.create('operator')
    profile=operators.create_profile(identity)
    profile.update_operator_managed_info(preferred_name='Operator',timezone='UTC',language='English')
    thread=ThreadStore(str(tmp_path/'threads')).create_thread('operator');profile.active_thread_id=thread.thread_id
    operators.save_profile(identity,profile)
    r=ModeRuntime('operator',str(tmp_path/'operators'),str(tmp_path/'threads'))
    replies=iter(['Confirm that this deployment is verified.','exit'])
    monkeypatch.setattr('builtins.input',lambda _:next(replies))
    monkeypatch.setattr(app,'process_interaction',lambda *a,**k:pytest.fail('Material gate bypassed'))
    try:
        r.boot();r.run()
        assert not r.context.response_governance['allowed']
        assert r.context.learning_evaluation['candidate_ids']==[]
        assert 'PENDING_VALIDATION' in r.context.runtime_observation.response_text
    finally:r.shutdown()

def test_scope_and_definition_disclosure():
    from data_governance.response_gate import evaluate
    meaning=NS(canonical_meaning='first')
    r=NS(context=NS(identity=NS(operator_id='operator'),understanding_result=NS(final_understanding=meaning)))
    evaluate(r,'Hello');meaning.canonical_meaning='corrected definition'
    assert evaluate(r,'Hello')['disclosures']

def test_response_gate_authenticates_retained_external_result(tmp_path):
    from tests.test_learning import built
    from data_governance.response_gate import evaluate
    r,out,_=built(tmp_path)
    text='Verify this result'
    rp=deepcopy(out['rp'])
    r.context.reality_primacy_result=rp
    r.context.material_response_claim={'operator_input_hash':digest(text),'claim_id':rp['request']['claim_id']}
    r.context.assembled_context=NS(runtime=NS(context_ready=True))
    r.context.understanding_result=NS(review_required=False,final_understanding=NS(canonical_meaning='bounded'),errors=[])
    assert evaluate(r,text)['allowed']
    for mutate in ('signature','expiry','labels'):
        altered=deepcopy(rp)
        if mutate=='signature':altered['response']['signature']='invalid'
        elif mutate=='expiry':altered['authority_valid_until']='2099-01-01T00:00:00+00:00'
        else:altered.pop('response')
        r.context.reality_primacy_result=altered
        assert not evaluate(r,text)['allowed']

def _nonbuild_transition_fixture(tmp_path,response_text=None):
    from datetime import datetime,timezone,timedelta
    from tests.test_execution_spine import runtime,RuntimeState
    from understanding import UnderstandingRequest,AuthorityContext,AuthorityLevel,Evidence
    from understanding.understanding_record import normalize_meaning
    from test_evidence_validation import case,engine
    from test_decision_coordinator import authority
    from reality_primacy import RPClaim,RPTruthCondition,resolve_evidence_requirements,DecisionCoordinator,DecisionLedger,TransitionEndpoint
    from reality_primacy.rp_evidence_validator import canonical_hash
    from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
    from cryptography.hazmat.primitives import serialization
    from integration.reality_primacy import RealityAcceptanceClient
    from learning.runtime import service
    r=runtime(tmp_path)
    data={'subject_id':'nonbuild','meaning':'Measure the effect of the second operand.','semantic_domain':'OPERATOR',
        'objective':'Measure addition','source_references':['operator:nonbuild'],
        'actors':['operator'],'components':['measurement'],
        'requirements':[{'requirement_id':'measure','text':'Measure addition','completion_condition':'measurements recorded'}],
        'completion_conditions':['measurements recorded']}
    understood=r.understanding_engine.process(UnderstandingRequest('operator','thread',data['meaning'],request_id='nonbuild',
        interpreted_input=data,operator_objective=data['objective'],
        authority_context=AuthorityContext('operator',AuthorityLevel.AUTHORIZED_OPERATOR,'OPERATOR',authenticated=True),
        evidence=(Evidence('operator:nonbuild','OPERATOR_STATEMENT',True,'OPERATOR',normalize_meaning(data['meaning'])),)))
    assert not understood.errors and not understood.review_required,understood.to_dict()
    with pytest.raises(PermissionError):understood.specification_handoff()
    governed=understood.governed_handoff()
    controls={'first_operand':2}
    observed={'properties':{'improvement_target':'RUNTIME_OUTCOME','causal_contrast':{'protocol':'controlled_intervention/1',
        'variable':'second_operand','controls':controls,'unresolved':[],
        'baseline':{'input':0,'output':sum((2,0)),'controls':controls},
        'intervention':{'input':3,'output':sum((2,3)),'controls':controls},
        'recovery':{'input':0,'output':sum((2,0)),'controls':controls}}}}
    resolution,item=case(modify=lambda rule:rule['validation_rule']['parameters'].update(pointer='/properties',expected=observed['properties']))
    scope={'operator_id':'operator','thread_id':'thread','project':'nonbuild','domain':'OPERATOR','capability':'addition'}
    if response_text:
        from data_governance.response_claims import extract
        scope.update(response_hash=digest(response_text),response_claims_hash=digest(extract(response_text,{'operator_id':'operator','thread_id':'thread'})['claims']))
    claim=deepcopy(resolution.claim_snapshot)
    claim.update(scope=scope,source_understanding=governed,source_state='INTERPRETING',proposed_target_state='COMPLETE')
    if response_text:claim['claim_text']=response_text
    condition=deepcopy(resolution.condition_snapshots[0]);condition['scope']=scope
    if response_text:condition['condition_text']=response_text
    resolution=resolve_evidence_requirements(RPClaim.from_dict(claim),[RPTruthCondition.from_dict(condition)])
    current=datetime.now(timezone.utc);stamp=current.isoformat();requirement=resolution.requirements[0]
    item.update(scope=scope,claim_id=claim['claim_id'],condition_id=condition['condition_id'],requirement_id=requirement['requirement_id'],
        observed_at=stamp,content=observed,content_hash=canonical_hash(observed))
    batch=engine(resolution,[item]).validate(resolution,[item],evaluated_at=stamp)
    policy=authority(resolution,batch);policy.update(valid_from=(current-timedelta(days=1)).isoformat(),valid_until=(current+timedelta(days=1)).isoformat())
    coordinator=DecisionCoordinator(ledger=DecisionLedger(tmp_path/'rp.sqlite'),issuer='external-rp',
        governed_authority_hashes=[canonical_hash(policy)],trusted_batch_hashes=[batch.content_hash()])
    key=Ed25519PrivateKey.generate();endpoint=TransitionEndpoint(coordinator,key,key_id='test',clock=lambda:stamp)
    r.reality_acceptance_client=RealityAcceptanceClient(endpoint.evaluate,{'test':key.public_key().public_bytes(serialization.Encoding.Raw,serialization.PublicFormat.Raw)},clock=lambda:current)
    request={'request_id':'nonbuild','claim_id':claim['claim_id'],'scope':scope,'source_state':'INTERPRETING','target_state':'COMPLETE',
        'evaluated_at':stamp,'evaluation':{'resolution':resolution.to_dict(),'batch':batch.to_dict(),'authority':policy}}
    r.require_reality_transition(RuntimeState.COMPLETE,request)
    assert r._set_state(RuntimeState.COMPLETE)
    assert not getattr(r.context,'learning_error',None)
    result=r.context.learning_evaluation
    assert result['status']=='ELIGIBLE',result
    candidate=service(r).store.get('operator',result['candidate_ids'][0])
    assert candidate['source_build_id'] is None and candidate['source_spec_id'] is None
    assert candidate['lineage']['canonical_v2']['classification']['dimensions']==['OUTCOME']
    r.context.understanding_result=understood
    return r

def test_nonbuild_transition_automatically_evaluates_learning(tmp_path):
    _nonbuild_transition_fixture(tmp_path)
