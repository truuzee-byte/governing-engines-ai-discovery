"""Actual governed acquisition and custody; no replacement path generator."""
import json
from copy import deepcopy
import pytest
from tests.test_learning import built, approve
from learning.runtime import command, service
from learning.contracts import digest
from system_layer.contracts import digest as approval_hash
from integration.conversation_understanding import prompt_context
from understanding import UnderstandingRequest
from understanding.understanding_record import Evidence, normalize_meaning
from understanding.semantic_custody_policy import AuthorityContext, AuthorityLevel


def adoption(r, record, version=0, **changes):
    request={'learning_id':record['learning_id'],'learning_hash':digest(record),
             'scope':record['scope'],'conditions':{'first_operand':2},'expected_version':version,'thread_id':'thread'}
    request.update(changes)
    return {'request':request,'approval':{'operator_id':'operator','action':'LEARNING_UNDERSTANDING_UPDATE',
            'decision':'APPROVE','hash':approval_hash(request)}}


def adopt(r, envelope):
    return command(r,'/learning understand '+json.dumps(envelope))


@pytest.fixture
def acquired(tmp_path):
    r,out,c=built(tmp_path,'canonical')
    return r,out,c,approve(r,c)


def test_unvalidated_rejected(tmp_path):
    r,_,c=built(tmp_path,'unresolved')
    fake={'learning_id':c['candidate_id'],'scope':c['scope']}
    with pytest.raises(PermissionError):adopt(r,adoption(r,fake))
    assert not r.understanding_engine.store.query('operator',semantic_domain='RUNTIME')


def test_adoption_evidence_provenance_and_authority(acquired):
    r,out,c,record=acquired
    result=adopt(r,adoption(r,record))
    u=r.understanding_engine.store.get('operator',result['understanding_id'])
    binding=u.context['learning_updates'][record['learning_id']]
    assert u.semantic_state.value=='CONFIRMED'
    assert binding['record']==record
    assert binding['record']['evidence']==record['evidence'] and record['evidence']
    assert binding['update_cause']=='VALIDATED_LEARNING'
    assert any(e.reference==digest(record) for e in u.supporting_evidence)
    assert result['execution_authority'] is False
    assert u.metadata['capability_proven'] is False
    assert u.semantic_domain=='RUNTIME' and u.context['learning_updates'][record['learning_id']]['conditions']=={'first_operand':2}
    assert record['lesson']['generalization']=='NONE'


def test_preserved_before_unknowns_conflicts_and_objective(acquired):
    r,_,_,record=acquired
    scope=record['scope'];subject='governed-learning:'+digest(scope)
    meaning='Historical experience remains bounded.'
    before=r.understanding_engine.process(UnderstandingRequest('operator','thread',meaning,project_id=scope['project'],
        interpreted_input={'subject_id':subject,'subject_type':'GOVERNED_LEARNING','semantic_domain':'RUNTIME',
            'meaning':meaning,'objective':'Preserve legitimate objective X',
            'claim':{'predicate':'historical_experience_scope','value':'bounded'},
            'qualifiers':['Original qualifier remains bounded'],
            'context':{'uncertainty':['Unmeasured input remains unknown'],
                       'contradictions':['Earlier contrary observation remains unresolved']},
            'constraints':['No execution without new authority']},
        evidence=(Evidence('historic-evidence','REALITY_VALIDATION',True,'RUNTIME',normalize_meaning(meaning)),),
        authority_context=AuthorityContext('operator',AuthorityLevel.VALIDATED_RUNTIME_EVIDENCE,'RUNTIME',True)))
    assert not before.errors
    original=before.final_understanding
    result=adopt(r,adoption(r,record,original.version))
    after=r.understanding_engine.store.get('operator',result['understanding_id'])
    assert after.version==original.version+1
    assert after.context['uncertainty']==original.context['uncertainty']
    assert after.context['contradictions']==original.context['contradictions']
    assert after.operator_objective==original.operator_objective
    assert after.constraints==original.constraints and after.canonical_meaning==original.canonical_meaning
    assert after.metadata['claim']==original.metadata['claim']
    assert after.qualifiers==original.qualifiers
    assert r.understanding_engine.store.history('operator',after.understanding_id)[0]==original
    assert set(e.reference for e in original.supporting_evidence)<=set(e.reference for e in after.supporting_evidence)
    assert 'BOUNDED_HISTORICAL_UNDERSTANDING' in str(prompt_context(r, query=record['scope']['capability']))
    assert '"version": '+str(after.version) in str(prompt_context(r, query=record['scope']['capability']))
    assert 'Unmeasured input remains unknown' in str(prompt_context(r, query=record['scope']['capability']))
    assert 'Earlier contrary observation remains unresolved' in str(prompt_context(r, query=record['scope']['capability']))
    assert 'No execution without new authority' in str(prompt_context(r, query=record['scope']['capability']))
    assert 'Original qualifier remains bounded' in str(prompt_context(r, query=record['scope']['capability']))


@pytest.mark.parametrize('change',[{'conditions':{'first_operand':3}}, {'learning_hash':'forged'},
    {'scope':{'operator_id':'other','project':'p','domain':'d','capability':'c'}}, {'expected_version':1},
    {'thread_id':'other-thread'}])
def test_wrong_applicability_hash_owner_or_head_rejected(acquired,change):
    r,_,_,record=acquired
    with pytest.raises((PermissionError,ValueError)):adopt(r,adoption(r,record,**change))
    assert not r.understanding_engine.store.query('operator',semantic_domain='RUNTIME')


def test_separate_exact_adoption_approval(acquired):
    r,_,_,record=acquired
    envelope=adoption(r,record);envelope['approval']['hash']='old'
    with pytest.raises(PermissionError):adopt(r,envelope)


def test_replay_is_idempotent_and_stale_rejected(acquired):
    r,_,_,record=acquired
    first=adopt(r,adoption(r,record))
    second=adopt(r,adoption(r,record,first['version']))
    assert second['state']=='NO_CHANGE' and second['version']==first['version']
    assert len(r.understanding_engine.store.history('operator',first['understanding_id']))==1
    with pytest.raises(ValueError):adopt(r,adoption(r,record))


def test_later_consumer_automatic_current_head_and_revocation(acquired):
    r,_,_,record=acquired
    assert 'BOUNDED_HISTORICAL_UNDERSTANDING' not in str(prompt_context(r, query=record['scope']['capability']))
    receipt=adopt(r,adoption(r,record))
    text=str(prompt_context(r, query=record['scope']['capability']))
    assert 'BOUNDED_HISTORICAL_UNDERSTANDING' in text and record['learning_id'] in text
    assert '"version": '+str(receipt['version']) in text
    command(r,'/learning revoke '+json.dumps({'id':record['learning_id'],'hash':digest(record)}))
    assert record['learning_id'] not in str(prompt_context(r, query=record['scope']['capability']))
    assert r.understanding_engine.store.get('operator',receipt['understanding_id']) is not None


def test_later_scope_and_thread_filter(acquired):
    r,_,_,record=acquired
    adopt(r,adoption(r,record))
    r._learned_understanding_scope=('other-thread',record['scope'],{'first_operand':2})
    assert record['learning_id'] not in str(prompt_context(r, query=record['scope']['capability']))
    r._learned_understanding_scope=('thread',record['scope'],{'first_operand':999})
    assert record['learning_id'] not in str(prompt_context(r, query=record['scope']['capability']))
