import json
import sqlite3
from copy import deepcopy
import pytest
from learning.store import LearningStore,IntegrityError
from learning.contracts import digest
from tests.test_legacy_rp_final_boundaries import forged_learning
from tests.test_knowledge_registry import setup,approve


@pytest.mark.parametrize('missing',['outcome','canonical_v2','governance_decision'])
def test_incomplete_legacy_learning_cannot_be_written(tmp_path,missing):
    value=forged_learning();value['lineage'].pop(missing,None)
    store=LearningStore(tmp_path/'learning.sqlite3')
    with pytest.raises((PermissionError,ValueError)):
        with store.transaction('op') as (_,__,append):append(value['learning_id'],'record',value)
    assert store.history('op')==[]


def test_raw_sql_import_cannot_gain_legitimacy_on_restart(tmp_path):
    path=tmp_path/'learning.sqlite3';LearningStore(path)
    value=forged_learning();checksum=digest(['op',value['learning_id'],'record',value,''])
    with sqlite3.connect(path) as db:
        db.execute('INSERT INTO journal(operator,entity,kind,payload,previous,checksum) VALUES(?,?,?,?,?,?)',
            ('op',value['learning_id'],'record',json.dumps(value),'',checksum))
    with pytest.raises(IntegrityError):LearningStore(path).get('op',value['learning_id'])


def test_transaction_snapshot_cannot_fabricate_admission_history(tmp_path):
    store=LearningStore(tmp_path/'learning.sqlite3');value=forged_learning()
    with pytest.raises((PermissionError,ValueError,TypeError)):
        with store.transaction('op') as (state,history,append):
            state[value['learning_id']]=value
            assert not hasattr(history,'append')
            append(value['learning_id'],'record',value)
    assert store.history('op')==[]


def test_serialized_governance_cannot_issue_itself(tmp_path):
    store=LearningStore(tmp_path/'learning.sqlite3');decision=forged_learning()['lineage']['governance_decision']
    with pytest.raises(PermissionError):
        with store.transaction('op') as (_,__,append):append(decision['decision_id'],'governance',decision)


@pytest.mark.parametrize('kind',['capture_admission','record'])
def test_corrective_analysis_cannot_self_promote(tmp_path,kind):
    store=LearningStore(tmp_path/'learning.sqlite3')
    with pytest.raises((PermissionError,ValueError,TypeError)):
        with store.transaction('op') as (_,__,append):
            append('provisional',kind,{'state':'PROVISIONAL','durable_learning':False})
    assert store.history('op')==[]


@pytest.mark.parametrize('change',['pool','metadata','source','provenance','governing','learned'])
def test_knowledge_import_classification_is_checked_before_insert(tmp_path,change):
    registry,request=setup(tmp_path,pool='EXTERNAL' if change=='governing' else 'INTERNAL')
    first=registry.register('op',request,approve(request))
    body=json.loads(first['content']);metadata=dict(first['metadata'])
    body['request']['expected_previous']=first['record_hash']
    if change=='pool':body['request']['pool']='SYSTEM'
    elif change=='metadata':metadata['knowledge_class']='SYSTEM'
    elif change=='source':body['source_lineage'][0]['source_pool']='SYSTEM'
    elif change=='provenance':body['source_lineage']=[]
    elif change=='governing':body['request']['knowledge_type']='GOVERNING_AUTHORITY';metadata['kind']='GOVERNING_AUTHORITY'
    elif change=='learned':body['request'].update(pool='SYSTEM',knowledge_type='LEARNED_KNOWLEDGE');metadata.update(knowledge_class='SYSTEM',kind='LEARNED_KNOWLEDGE')
    with pytest.raises((PermissionError,ValueError)):
        registry.store.append('KNOWLEDGE','op','term',json.dumps(body),metadata,
            expected_previous=first['record_hash'],authorization=approve(body['request']))
    assert len(registry.store.history('KNOWLEDGE','op','term'))==1
    assert registry.retrieve('op','term',1,first['record_hash'])['knowledge']['request']['pool']==request['pool']


@pytest.mark.parametrize('field,value',[('rp_state','CONFIRMED'),('canonical_meaning','SUBSTITUTED'),('request_pool','SYSTEM')])
def test_rehashed_sql_import_still_fails_hydration_or_retrieval(tmp_path,field,value):
    registry,request=setup(tmp_path);first=registry.register('op',request,approve(request))
    with sqlite3.connect(registry.store.path) as db:
        row=db.execute("SELECT payload FROM objects WHERE namespace='KNOWLEDGE'").fetchone()
        envelope=json.loads(row[0]);body=json.loads(envelope['content'])
        if field=='request_pool':body['request']['pool']=value
        else:body[field]=value
        envelope['content']=json.dumps(body);envelope['content_hash']=digest(envelope['content'])
        checksum=digest(envelope)
        db.execute("UPDATE objects SET payload=?,checksum=? WHERE namespace='KNOWLEDGE'",(json.dumps(envelope),checksum))
    with pytest.raises((ValueError,PermissionError)):
        registry.retrieve('op','term',1,checksum)


def test_valid_knowledge_restart_retains_nontruth_status(tmp_path):
    from knowledge.registry import KnowledgeRegistry
    registry,request=setup(tmp_path);first=registry.register('op',request,approve(request))
    reopened=KnowledgeRegistry(registry.store.path,registry.understanding_store)
    got=reopened.retrieve('op','term',1,first['record_hash'])
    assert got['knowledge']['source_lineage']==json.loads(first['content'])['source_lineage']
    assert got['knowledge']['request']['pool']=='INTERNAL'
    assert got['knowledge']['rp_state']=='PENDING_VALIDATION'
    assert not got['claims_validated'] and not got['execution_authority']


def test_pending_or_corrective_candidate_cannot_jump_to_eligible(tmp_path):
    from learning.service import LearningService
    store=LearningStore(tmp_path/'learning.sqlite3');manager=LearningService(store)
    scope=forged_learning()['scope']
    candidate=manager.propose('op',scope,{'statement':'provisional'},'EXECUTION_FAILURE')
    candidate['candidate_status']='ELIGIBLE'
    with pytest.raises(PermissionError):
        with store.transaction('op') as (_,__,append):append(candidate['candidate_id'],'candidate',candidate)
    assert store.get('op',candidate['candidate_id'])['candidate_status']=='PENDING_VALIDATION'


@pytest.fixture(scope='module')
def admitted_learning(tmp_path_factory):
    from tests.test_learning import built,approve as approve_learning
    from learning.runtime import service
    runtime,_,candidate=built(tmp_path_factory.mktemp('admitted-learning'))
    record=approve_learning(runtime,candidate)
    return service(runtime).store.path,record


@pytest.mark.parametrize('field',['analysis','rp','lesson','scope','evidence','deadline'])
def test_valid_source_cannot_authorize_substituted_learning(tmp_path,admitted_learning,field):
    import shutil
    source,record=admitted_learning;path=tmp_path/'learning.sqlite3';shutil.copyfile(source,path)
    store=LearningStore(path);bad=deepcopy(record)
    if field=='analysis':bad['lineage']['canonical_v2']['outcome_analysis']['status']='PENDING'
    elif field=='rp':bad['lineage']['canonical_v2']['reality_validation']['state']='PENDING_VALIDATION'
    elif field=='lesson':bad['lesson']['statement']='substituted'
    elif field=='scope':bad['scope']['project']='other'
    elif field=='evidence':bad['evidence']=[]
    else:bad['lineage']['revalidate_by']='2999-01-01T00:00:00+00:00'
    with pytest.raises(IntegrityError):
        with store.transaction('operator') as (_,__,append):append(bad['learning_id'],'record',bad)
    assert store.get('operator',record['learning_id'])==record


def test_revoked_learning_cannot_reactivate_by_replaying_old_record(tmp_path,admitted_learning):
    import shutil
    from learning.service import LearningService
    source,record=admitted_learning;path=tmp_path/'learning.sqlite3';shutil.copyfile(source,path)
    manager=LearningService(LearningStore(path))
    revoked=manager.review('operator',record['learning_id'],digest(record),'REVOKE')
    with pytest.raises(IntegrityError):
        with manager.store.transaction('operator') as (_,__,append):append(record['learning_id'],'record',record)
    assert manager.store.get('operator',record['learning_id'])==revoked
