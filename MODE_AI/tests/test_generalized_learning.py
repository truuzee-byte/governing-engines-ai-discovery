from copy import deepcopy
import json
import pytest
from learning.relationships import derive,propose
from learning.contracts import digest
from learning.runtime import command,service
from integration.conversation_understanding import prompt_context
from understanding.declaration_delta import apply_delta
from understanding import UnderstandingEngine,UnderstandingStore,UnderstandingRequest,AuthorityContext,AuthorityLevel
from tests.generalized_learning_fixtures import runtime,context,observe,evidence,task,reference,acquire,signed_observation

SCOPE={'operator_id':'operator','project':'synthetic-goals','domain':'OPERATOR','capability':'Preserve declared task intent'}


def test_structural_transfer_without_shared_topics():
    p=evidence(SCOPE);relationship=derive(p['causal_contrast'],p['relational_evidence'],SCOPE)
    fresh=context('Prepare maritime customs review','shipping');result=propose(relationship,fresh)
    assert observe(fresh,result)['accepted']
    assert 'archive' not in str(result) and 'greenhouse' not in str(result)
    assert result['objective']==fresh['objective'] and result['constraints']==fresh['constraints']


@pytest.mark.parametrize('change',['single','predicted','recovery','conditions','objective','authority','scope','ambiguous','false_success'])
def test_evidence_never_authorizes_unsupported_transfer(change):
    p=evidence(SCOPE);e=p['relational_evidence']
    if change=='single':e['cases']=e['cases'][:1]
    elif change=='predicted':e['cases'][1]['observation_kind']='PREDICTED'
    elif change=='scope':e['scope']={**SCOPE,'project':'other'}
    elif change=='recovery':e['cases'][1]['contrast']['recovery']['output']={'accepted':True}
    elif change=='conditions':e['cases'][1]['contrast']['intervention']['input']['conditions']=[]
    elif change=='objective':e['cases'][1]['contrast']['intervention']['input']['objective']='Unrequested goal'
    elif change=='authority':
        for c in e['cases']:c['contrast']['intervention']['input']['execution_authority']=True
    elif change=='ambiguous':e['cases'][1]['contrast']['intervention']['input']['new_field']='different schema'
    elif change=='false_success':e['cases'][1]['contrast']['intervention']['output']['accepted']=False
    with pytest.raises((ValueError,PermissionError)):derive(p['causal_contrast'],e,SCOPE)


def test_unrelated_and_context_change_are_not_keyword_transfer():
    p=evidence(SCOPE);r=derive(p['causal_contrast'],p['relational_evidence'],SCOPE)
    assert propose(r,context(intent='question')) is None
    missing=context();del missing['conditions']
    assert propose(r,missing) is None


@pytest.mark.parametrize('text,quote',[
    ('If the operator approves, prepare a launch plan.','prepare a launch plan'),
    ('Prepare a launch plan only after the operator approves.','Prepare a launch plan'),
    ('Could you prepare a launch plan?','prepare a launch plan'),
])
def test_conditional_or_question_cannot_be_promoted(text,quote):
    d={'subject_id':'goal','expected_version':0,'edits':[{'operation':'ADD','kind':'REQUIREMENT','quote':quote,'target_id':None}]}
    with pytest.raises(ValueError):apply_delta(None,d,text=text,source_reference='operator:current')


def test_multiturn_correction_preserves_original_objective_and_unrelated_context(tmp_path):
    engine=UnderstandingEngine(UnderstandingStore(tmp_path/'meaning.sqlite3'))
    authority=AuthorityContext('operator',AuthorityLevel.DIRECT_OPERATOR_STATEMENT,'OPERATOR',True)
    original='Prepare a release review.'
    def turn(text,edits,version):
        result=engine.process(UnderstandingRequest('operator','A',text,
            declaration_delta={'subject_id':'goal','expected_version':version,'edits':edits},
            operator_objective=original,authority_context=authority,runtime_metadata={'operator_source_reference':'operator:'+digest(text)}))
        assert not result.errors,result.to_dict()
        return result.final_understanding
    def add(text,kind='REQUIREMENT'):return {'operation':'ADD','kind':kind,'quote':text,'target_id':None}
    first=turn(original+' Never publish files.',[add(original),add('Never publish files.','CONSTRAINT')],0)
    second=turn('If approval arrives, prepare a launch plan.',[add('If approval arrives, prepare a launch plan.')],first.version)
    target=next(x['id'] for x in second.context['declarations'] if x['quote'].startswith('If approval'))
    new='If safety approval arrives, prepare a launch plan.'
    third=turn('Correction: replace "If approval arrives, prepare a launch plan." with "'+new+'".',
        [{'operation':'REPLACE','kind':'REQUIREMENT','quote':new,'target_id':target}],second.version)
    assert third.operator_objective==first.operator_objective==original
    assert 'Never publish files.' in third.constraints
    assert original in third.canonical_meaning and new in third.canonical_meaning
    assert engine.store.history('operator',third.understanding_id)[0]==first


@pytest.fixture
def learned(tmp_path):
    return acquire(tmp_path)


def fresh_task(r):
    b=runtime(r.understanding_engine.store.path.parent);c=context('Review a maritime customs handover','shipping')
    head,governed=task(b,c)
    return b,c,head,governed


def feedback(b,root,head,governed,app,accepted):
    observation,_=signed_observation(b,root,head,governed,{},extra_scope={
        'learning_application_id':app['application_id'],'proposal_hash':digest(app['proposal']),
        'task_understanding_hash':reference(head)['hash'],'context_hash':app['context_hash']},observed=accepted)
    return observation


def test_integrated_learning_memory_understanding_new_thread_application_verification(learned):
    r,record,adopted,initial_obs,properties=learned;b,c,head,governed=fresh_task(r)
    assert b.context.active_thread.thread_id!=r.context.active_thread.thread_id
    before=deepcopy(head.to_dict());command(b,'/learning apply '+json.dumps(reference(head)))
    admitted=prompt_context(b,query='How should this task be handled?');app=b.context.learning_application
    assert app['state']=='PROPOSED' and observe(c,app['proposal'])['accepted']
    assert app['selected'][0]['learning_id']==record['learning_id']
    assert app['selected'][0]['understanding_id']==adopted['understanding_id']
    assert 'BOUNDED_LEARNED_APPLICATION' in str(admitted) and not app['execution_authority']
    assert b.understanding_engine.store.get('operator',head.understanding_id).to_dict()==before
    obs=feedback(b,r.understanding_engine.store.path.parent,head,governed,app,observe(c,app['proposal'])['accepted'])
    result=command(b,'/learning verify_application '+json.dumps({'application_id':app['application_id'],'observation_id':obs.observation_id}))
    assert result['state']=='VERIFIED_APPLICATION_ONLY' and not result['execution_authority']
    assert service(b).store.get('operator',record['learning_id'])==record
    with pytest.raises(PermissionError):service(b).verify_application(b,app['application_id'],obs.observation_id)


def test_consent_required_before_retention(tmp_path):
    r=runtime(tmp_path);head,governed=task(r,context())
    obs,package=signed_observation(r,tmp_path,head,governed,evidence(SCOPE))
    result=command(r,'/learning experience '+json.dumps({'observation_id':obs.observation_id,'package':package}))
    assert result['status']=='ELIGIBLE' and service(r).retrieve('operator',SCOPE)==[]
    assert not r.learning_memory_gateway.available('operator',result['candidate_ids'][0])


def test_unrelated_task_excluded_after_actual_adoption(learned):
    r,record,*_=learned;b,c,_,_=fresh_task(r);c['intent']='unrelated_search';head,_=task(b,c)
    result=service(b).apply_understanding(b,reference(head))
    assert result['state']=='NO_MATCH' and not result['selected'] and result['excluded']


@pytest.mark.parametrize('change',['halt','foreign_thread','stale','project','revoked'])
def test_current_authority_context_gates(learned,change):
    r,record,*_=learned;b,c,head,_=fresh_task(r);ref=reference(head)
    if change=='halt':b._halt_latch=True
    elif change=='foreign_thread':b.context.active_thread.thread_id='different'
    elif change=='stale':ref['hash']='stale'
    elif change=='project':head,_=task(b,c,project='different-project');ref=reference(head)
    elif change=='revoked':command(r,'/learning revoke '+json.dumps({'id':record['learning_id'],'hash':digest(record)}))
    if change in {'halt','foreign_thread','stale'}:
        with pytest.raises(PermissionError):service(b).apply_understanding(b,ref)
    else:assert service(b).apply_understanding(b,ref)['state']=='NO_MATCH'


def test_failed_consequence_blocks_only_that_context_pending_review(learned):
    r,record,*_=learned;b,c,head,governed=fresh_task(r);app=service(b).apply_understanding(b,reference(head))
    obs=feedback(b,r.understanding_engine.store.path.parent,head,governed,app,False)
    receipt=service(b).verify_application(b,app['application_id'],obs.observation_id)
    assert receipt['state']=='REVIEW_REQUIRED' and service(b).apply_understanding(b,reference(head))['state']=='NO_MATCH'
    assert service(b).store.get('operator',record['learning_id'])==record
    newer,_=task(b,context('Prepare a medical supplies review','medical'))
    assert service(b).apply_understanding(b,reference(newer))['state']=='PROPOSED'


def test_no_consequence_never_becomes_success(learned):
    r,record,*_=learned;b,c,head,_=fresh_task(r);app=service(b).apply_understanding(b,reference(head))
    assert app['validation_state']=='APPLICATION_REQUIRES_CONSEQUENCE'
    with pytest.raises((FileNotFoundError,ValueError,PermissionError)):
        service(b).verify_application(b,app['application_id'],'invented-observation')


def test_question_lesson_is_not_universal_policy(tmp_path):
    r,record,*_=acquire(tmp_path,intent='question');b=runtime(tmp_path)
    c=context('Consider a satellite antenna revision','antenna',intent='question');head,_=task(b,c)
    result=service(b).apply_understanding(b,reference(head))
    assert result['proposal']['decision']=='discuss' and observe(c,result['proposal'])['accepted']
    other,_=task(b,context('Consider a satellite antenna revision','antenna'))
    assert service(b).apply_understanding(b,reference(other))['state']=='NO_MATCH'


@pytest.mark.parametrize('change',['proposal_hash','context_hash','application_id','unsigned'])
def test_feedback_cannot_be_rebound_or_forged(learned,change):
    r,record,*_=learned;b,c,head,governed=fresh_task(r)
    app=service(b).apply_understanding(b,reference(head))
    altered=deepcopy(app)
    if change=='proposal_hash':altered['proposal']['decision']='forged'
    elif change=='context_hash':altered['context_hash']='different'
    elif change=='application_id':altered['application_id']='different'
    obs=feedback(b,r.understanding_engine.store.path.parent,head,governed,altered,True)
    if change=='unsigned':
        # Tampering with persisted content is not a valid signed RP response.
        original=b.reality_acceptance_client.verify_response
        def reject(request,response):
            changed=deepcopy(response);changed['rp_state']='CONFIRMED'
            changed['signature']='invalid'
            return original(request,changed)
        b.reality_acceptance_client.verify_response=reject
    with pytest.raises((PermissionError,ValueError,KeyError)):
        service(b).verify_application(b,app['application_id'],obs.observation_id)


def test_source_revoked_between_proposal_and_consequence(learned):
    r,record,*_=learned;b,c,head,governed=fresh_task(r)
    app=service(b).apply_understanding(b,reference(head))
    obs=feedback(b,r.understanding_engine.store.path.parent,head,governed,app,True)
    command(r,'/learning revoke '+json.dumps({'id':record['learning_id'],'hash':digest(record)}))
    with pytest.raises(PermissionError):service(b).verify_application(b,app['application_id'],obs.observation_id)


def test_task_changes_between_selection_and_consumption(learned):
    r,*_=learned;b,c,head,_=fresh_task(r)
    command(b,'/learning apply '+json.dumps(reference(head)))
    b.context.active_thread.thread_id='unauthorized-thread'
    with pytest.raises(PermissionError):prompt_context(b,query='Handle the task')


def test_one_example_defers_actual_governed_admission(tmp_path):
    r=runtime(tmp_path);head,governed=task(r,context());properties=evidence(SCOPE)
    properties['relational_evidence']['cases']=properties['relational_evidence']['cases'][:1]
    obs,package=signed_observation(r,tmp_path,head,governed,properties)
    result=command(r,'/learning experience '+json.dumps({'observation_id':obs.observation_id,'package':package}))
    assert result['status']!='ELIGIBLE' and not result['candidate_ids']
    assert service(r).retrieve('operator',SCOPE)==[]


def test_missing_or_unlinked_experience_cannot_create_learning(tmp_path):
    r=runtime(tmp_path)
    with pytest.raises(PermissionError):
        command(r,'/learning experience '+json.dumps({'observation_id':'missing','package':None}))
    head,governed=task(r,context())
    obs,_=signed_observation(r,tmp_path,head,governed,evidence(SCOPE))
    result=command(r,'/learning experience '+json.dumps({'observation_id':obs.observation_id,'package':None}))
    assert result['status']=='PENDING_VALIDATION' and result['candidate_ids']==[]


def test_halt_prevents_experience_capture(tmp_path):
    r=runtime(tmp_path);r._halt_latch=True
    with pytest.raises(PermissionError):
        command(r,'/learning experience '+json.dumps({'observation_id':'missing','package':None}))


def test_structural_application_reaches_all_reasoning_stages_plumbing_only(learned):
    # An offline provider double proves transport only, never live behavioral use.
    from tests.test_cross_thread_downstream_preservation import run
    r,record,*_=learned;b,c,head,_=fresh_task(r)
    command(b,'/learning apply '+json.dumps(reference(head)))
    prompt=prompt_context(b,query='How should the current task be handled?')
    _,calls=run(prompt,['Retain the current conditions before proposing a plan.',
        'Preserve the conditions and request authorization before execution.',
        'Retain the current conditions before proposing a plan.'])
    assert len(calls)==3
    for value,_ in calls:
        assert 'BOUNDED_LEARNED_APPLICATION' in value and record['learning_id'] in value
        assert c['objective'] in value and c['conditions'][0] in value and c['constraints'][0] in value
        assert 'rp_receipt_id' in value and 'APPLICATION_REQUIRES_CONSEQUENCE' in value
        assert 'validation_results' not in value and 'causal_contrast' not in value


def test_preserved_interaction_record_reopens_without_migration(tmp_path,monkeypatch):
    # Create via the preserved old capture implementation, then reopen under the
    # current store. Do not rewrite the old candidate/record or its capture proof.
    import importlib.util
    from pathlib import Path
    import data_governance.learning_governance as policy
    from learning.store import LearningStore
    base=Path(__file__).resolve().parents[1]/'artifacts/generalized_learning_completion_20261016/before'
    def load(name,path):
        spec=importlib.util.spec_from_file_location(name,path)
        module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module);return module
    old_policy=load('data_governance._preserved_learning_governance',base/'data_governance/learning_governance.py')
    old_capture=load('integration._preserved_interaction_learning',base/'integration/interaction_learning.py')
    r=runtime(tmp_path);head,governed=task(r,context())
    obs,package=signed_observation(r,tmp_path,head,governed,evidence(SCOPE))
    with monkeypatch.context() as patch:
        patch.setattr(policy,'verify_capture',old_policy.verify_capture)
        evaluation=old_capture.evaluate(r,obs,package)
    candidate=service(r).store.get('operator',evaluation['candidate_ids'][0])
    assert 'generalization' not in candidate['claim']
    record=command(r,'/learning approve '+json.dumps({'id':candidate['candidate_id'],'hash':digest(candidate)}))
    reopened=LearningStore(service(r).store.path).get('operator',record['learning_id'])
    assert reopened==record and 'generalization' not in reopened['lesson']
    # Compatibility does not silently make a previously ineligible lesson usable.
    with pytest.raises(PermissionError):
        service(r).understanding_candidate('operator',record['learning_id'],digest(record),SCOPE,
            evidence(SCOPE)['causal_contrast']['controls'])
