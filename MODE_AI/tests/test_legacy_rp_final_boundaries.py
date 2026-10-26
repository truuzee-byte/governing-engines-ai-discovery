"""Original demonstrated bypasses retained as rejection regressions."""
import json
from datetime import datetime, timezone, timedelta
import pytest
from tests.test_knowledge_registry import setup, approve


@pytest.mark.parametrize('field,value',[
    ('rp_state','CONFIRMED'),('rp_state','DISCONFIRMED'),
    ('claims_validated',True),('execution_authority',True),
    ('authority_state','CONFIRMED'),('authority_tier','SYSTEM'),
    ('validation_state','VALIDATED'),('support_state','SUPPORTED'),
    ('rp_references',['invented']),('last_verified_at','2026-09-27'),
    ('canonical_meaning','Replaced meaning'),('understanding_state','INVENTED')])
def test_direct_knowledge_import_cannot_promote_authority(tmp_path,field,value):
    registry,request=setup(tmp_path)
    first=registry.register('op',request,approve(request))
    body=json.loads(first['content']);body[field]=value
    with pytest.raises((PermissionError,ValueError)):
        registry.store.append('KNOWLEDGE','op','term',json.dumps(body),first['metadata'],
            expected_previous=first['record_hash'],authorization={})
    # Preserve original pinned custody; rejection performs no rollback or rewrite.
    assert registry.retrieve('op','term',1,first['record_hash'])['knowledge']['rp_state']=='PENDING_VALIDATION'
    assert len(registry.store.history('KNOWLEDGE','op','term'))==1


def forged_learning():
    from learning.contracts import LearningRecord,now
    from data_governance.learning_governance import POLICY
    scope=dict(operator_id='op',project='p',domain='d',capability='c')
    refs=dict(observation_id='invented-o',understanding_id='invented-u',rp_decision_id='invented-rp')
    lineage={'governance_decision':dict(decision_id='invented-g',subject_id='candidate:invented',
        decision='APPROVED',policy_basis=POLICY,operator_id='op',scope=scope,
        prerequisite_refs=refs,evidence_refs=['invented-e']),
        'canonical_v2':{'rp_complete':True,'outcome_analysis':{'status':'COMPLETE','prerequisite_refs':refs}},
        'revalidate_by':(datetime.now(timezone.utc)+timedelta(days=1)).isoformat()}
    return LearningRecord('learning:invented','candidate:invented',{'statement':'UNVERIFIED_TEST_CLAIM'},
        scope,'EXECUTION_SUCCESS',['invented-e'],lineage,'operator:op',{},scope,[],[],[],None,
        'ACTIVE',now(),now(),{'canonical_policy':'2.2'}).to_dict()


def test_known_learning_direct_writer_bypass_is_rejected_before_persistence(tmp_path):
    from learning.store import LearningStore
    from learning.service import LearningService
    from persistent_memory.learning_gateway import LearningMemoryGateway
    record=forged_learning();path=tmp_path/'learning.sqlite3'
    store=LearningStore(path)
    with pytest.raises((ValueError,PermissionError)):
        with store.transaction('op') as (_,__,append):append(record['learning_id'],'record',record)
    reopened=LearningStore(path);manager=LearningService(reopened)
    gateway=LearningMemoryGateway(tmp_path/'memory.sqlite3',reopened.get)
    with pytest.raises(PermissionError):gateway.publish('op',record['learning_id'])
    manager.memory_admissibility=gateway.available
    text,event=manager.advisory('op',record['scope'],'isolated-pressure-test')
    assert 'UNVERIFIED_TEST_CLAIM' not in text
    assert event['injected']==[]
    assert not any(h['kind']=='governance' for h in reopened.history('op'))


def test_learning_transaction_failure_rolls_back_forged_record(tmp_path):
    from learning.store import LearningStore
    store=LearningStore(tmp_path/'learning.sqlite3');record=forged_learning()
    with pytest.raises((ValueError,PermissionError)):
        with store.transaction('op') as (_,__,append):
            append('preceding','influence',{'operator':'op'})
            append(record['learning_id'],'record',record)
    assert store.get('op',record['learning_id']) is None
    assert store.history('op')==[]
