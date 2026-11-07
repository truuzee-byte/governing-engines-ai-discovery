"""Offline engineering evidence only; no provider behavioral qualification."""
import json
from types import SimpleNamespace as NS
import pytest
from data_governance.context_admission import Admission,verify,basis_for_memory
from conversation_quality.source_grounding import assess,learned_rule_context
from tests.test_general_learning_memory_repairs import memory,learned,empty
from tests.test_cross_thread_downstream_preservation import run
from persistent_memory.tests.test_memory_injection import setup_context,save
from tests.test_learning import built,approve
from tests.test_learning_understanding_bridge import adopt,adoption
from understanding import UnderstandingEngine,UnderstandingStore
from integration.conversation_understanding import prompt_context
from learning.runtime import command
from learning.contracts import digest

def test_receipt_representation_relevance(tmp_path):
    m,_,_=setup_context(tmp_path)
    r=save(m,'Oriel parcel relay delivery receipt reports use structured-form format.')
    assert [x.memory_id for x in m.retrieve_memories('operator','Which representation does Oriel parcel relay delivery receipt intake require?')]==[r.memory_id]

def test_same_subject_other_task_excluded(tmp_path):
    m,_,_=setup_context(tmp_path)
    save(m,'Solace greenhouse tray labeling uses purple labels.')
    assert m.retrieve_memories('operator','Describe Solace greenhouse irrigation.')==[]

def support_prompt(tmp_path):
    m,_,_=setup_context(tmp_path);r=save(m,'Harbor irrigation pumps use brine.')
    refs=m.provenance_support('operator','Verify attribution to '+r.memory_id)
    a=Admission('operator','B')
    a.consider('OPERATOR_INPUT','q','Verify attribution to '+r.memory_id,source='operator')
    for row in refs:a.support('MEMORY',row.memory_id,row.content,source='owner evidence reference',basis=basis_for_memory(row))
    return m,r,a.finish()

def test_provenance_only_not_model_visible(tmp_path):
    _,r,p=support_prompt(tmp_path)
    assert r.content not in str(p)
    result,calls=run(p,['unknown','No support claim is needed.','unknown'])
    assert all(r.content not in q for q,_ in calls)
    assert assess('Provenance verification: According to memory '+r.memory_id+', "'+r.content+'"',p)['allowed']
    assert not assess('According to memory '+r.memory_id+', "'+r.content+'"',p)['allowed']

def test_provenance_nonexistent_and_wrong_claim(tmp_path):
    m,r,p=support_prompt(tmp_path)
    assert m.provenance_support('operator','Check pm-missing')==[]
    assert not assess('Provenance verification: According to memory pm-missing, "brine"',p)['allowed']
    assert not assess('Provenance verification: According to memory '+r.memory_id+', "Harbor pumps use drinking water"',p)['allowed']

def test_sealed_support_tampering_rejected(tmp_path):
    _,_,p=support_prompt(tmp_path);p.support_sources[0]['content']='injected'
    with pytest.raises(PermissionError):verify(p)


def test_generated_reference_resolves_current_owner_without_topic_injection(tmp_path):
    m,r,_=support_prompt(tmp_path)
    a=Admission('operator','B');a.support_loader=m.provenance_support
    a.consider('OPERATOR_INPUT','q','Verify attribution to '+r.memory_id,source='operator');p=a.finish()
    claimed='Provenance verification: According to memory '+r.memory_id+', "'+r.content+'"'
    result=assess(claimed,p)
    assert result['allowed'] and result['claim_links'][0]['source_id']==r.memory_id
    assert r.content not in str(p) and all(x['record']['artifact_type']=='OPERATOR_INPUT' for x in p.sources)
    ordinary=Admission('operator','B');ordinary.support_loader=m.provenance_support
    ordinary.consider('OPERATOR_INPUT','q','Which irrigation route should Solace use?',source='operator')
    assert not assess(claimed,ordinary.finish())['allowed']
    m.lifecycle('operator',r.memory_id,'ARCHIVE','yes')
    assert not assess(claimed,p)['allowed']


def test_owner_resolution_capability_tampering_rejected(tmp_path):
    m,_,_=support_prompt(tmp_path);a=Admission('operator','B');a.support_loader=m.provenance_support;p=a.finish()
    p.support_loader=lambda owner,text:[]
    with pytest.raises(PermissionError):verify(p)

def test_inadmissible_support(tmp_path):
    m,r,_=support_prompt(tmp_path);m.lifecycle('operator',r.memory_id,'ARCHIVE','yes')
    assert m.provenance_support('operator','Check '+r.memory_id)==[]

def test_superseded_support_version(tmp_path):
    m,r,_=support_prompt(tmp_path)
    proposed=m.propose_update_memory('operator',r.memory_id,'Harbor irrigation pumps use fresh water.','A','message-new','Update Harbor irrigation pumps to fresh water.')
    assert m.confirm_candidate(proposed.candidate,'yes').success
    assert m.provenance_support('operator','Check '+r.memory_id+'@1')==[]
    assert m.provenance_decisions[0]['reason']=='SUPERSEDED_SUPPORT_REFERENCE'

def test_complete_fact_attribution_links_without_forced_citation():
    p=memory('Solace greenhouse seedlings receive irrigation through the bottom reservoir; their leaves must stay dry.')
    result=assess('Based on admitted memory stating that Solace greenhouse seedlings receive irrigation through the bottom reservoir and that their leaves must stay dry.',p)
    assert result['allowed'] and result['claim_links'][0]['source_id']=='pm-valid'
    assert not assess('According to memory, Solace seedlings receive brine.',p)['allowed']

@pytest.fixture
def cross(tmp_path):
    r,_,c=built(tmp_path,'canonical');record=approve(r,c);receipt=adopt(r,adoption(r,record))
    b=NS(context=NS(identity=NS(operator_id='operator'),active_thread=NS(thread_id='genuinely-new-B')),
         understanding_engine=UnderstandingEngine(UnderstandingStore(r.understanding_engine.store.path)))
    return r,b,record,receipt

def test_new_thread_discovers_persisted_compact_head(cross):
    r,b,record,receipt=cross;p=prompt_context(b,query=record['scope']['capability'])
    verify(p,'genuinely-new-B');v=json.loads(str(p))
    assert v['understanding_id']==receipt['understanding_id']
    assert v['origin_thread_id']=='thread' and v['destination_thread_id']=='genuinely-new-B'
    assert record['learning_id'] in str(p) and '"record"' not in str(p)
    assert len(str(p).encode())<16384 and '"observed_outcome"' not in str(p)
    assert p.sources[0]['record']['scope']['source_thread_id']=='thread'
    assert not hasattr(b,'_learned_understanding_scope')

def test_new_thread_irrelevant_excluded(cross):
    _,b,_,_=cross
    assert 'BOUNDED_HISTORICAL_UNDERSTANDING' not in str(prompt_context(b,query='Explain chlorophyll leaves'))


def test_cross_thread_cannot_cross_operator_boundary(cross):
    _,b,record,_=cross;b.context.identity.operator_id='different-owner'
    assert record['learning_id'] not in str(prompt_context(b,query=record['scope']['capability']))


def test_cross_thread_semantic_consumption_reaches_all_stages(cross):
    _,b,record,receipt=cross
    p=prompt_context(b,query=record['scope']['capability'])
    result,calls=run(p,['A bounded historical inference.','Preserve the measured conditions.','A bounded historical inference.'])
    assert all(record['learning_id'] in q and receipt['understanding_id'] in q and 'genuinely-new-B' in q and 'source_thread_id' in q for q,_ in calls)
    assert result.final_response=='A bounded historical inference.'

def test_cross_thread_revoked_learning_excluded(cross):
    r,b,record,_=cross
    command(r,'/learning revoke '+json.dumps({'id':record['learning_id'],'hash':digest(record)}))
    assert record['learning_id'] not in str(prompt_context(b,query=record['scope']['capability']))

def test_cross_thread_current_head_only(cross):
    r,b,record,receipt=cross
    # Existing owner idempotent adoption does not create an older alternate head.
    adopt(r,adoption(r,record,receipt['version']))
    p=prompt_context(b,query=record['scope']['capability'])
    assert str(p).count('"understanding_id": "'+receipt['understanding_id']+'"')==1
    assert p.sources[0]['record']['scope']['supersession_state']=='CURRENT_UNDERSTANDING_HEAD'


def test_superseded_learning_cannot_outrank_new_valid_head(cross):
    import shutil
    from learning.runtime import service
    r,b,old,receipt=cross
    root=r.understanding_engine.store.path.parent.resolve()
    target=(root/'artifact').resolve()
    assert target.is_relative_to(root) and target!=root
    shutil.rmtree(target)  # only the explicitly verified disposable test fixture
    fresh,_,candidate=built(root,'canonical')
    manager=service(fresh)
    candidate=manager.relate('operator',candidate['candidate_id'],old['learning_id'],'New governed contrast supersedes prior evidence')
    new=manager.review('operator',candidate['candidate_id'],digest(candidate),'APPROVE','SUPERSEDE')
    fresh.learning_memory_gateway.publish('operator',new['learning_id'])
    updated=adopt(fresh,adoption(fresh,new,receipt['version']))
    p=prompt_context(b,query=new['scope']['capability'])
    assert new['learning_id'] in str(p) and old['learning_id'] not in str(p)
    assert json.loads(str(p))['version']==updated['version']==receipt['version']+1

def test_raw_stage_contract_and_correction_before_finalization():
    p=learned();bad='UTF-8 naïve causes UnicodeDecodeError.'
    corrected='UTF-16LE is a bounded inference; no fresh-title exception is established.'
    result,calls=run(p,[bad,'Reject the unsupported fresh-title exception.',corrected])
    assert 'known_rule' in calls[0][0] and 'known_exception' in calls[0][0]
    assert 'hypothetical_exception' in calls[0][0] and 'unsupported_speculation' in calls[0][0]
    assert 'MANDATORY EVIDENCE CORRECTION' in calls[1][0] and 'MANDATORY EVIDENCE CORRECTION' in calls[2][0]
    assert result.draft==bad and result.final_response==corrected

def test_finalizer_cannot_restore_unsupported_exception():
    bad='UTF-8 naïve causes UnicodeDecodeError.'
    result,_=run(learned(),['UTF-16LE is a scoped inference.','Reject an unmeasured exception.',bad])
    assert result.raw_final_response==bad and result.final_response=='UTF-16LE is a scoped inference.'

def test_legitimate_documented_exception_and_hypothesis():
    p=learned()
    assert assess('Historical understanding-valid records "UnicodeDecodeError"; future inputs remain unmeasured.',p)['allowed']
    assert assess('Hypothetically, another receiver could raise UnicodeDecodeError; this is not established.',p)['allowed']
    assert not assess('If naïve is encoded, UnicodeDecodeError occurs.',p)['allowed']
    assert not assess('Hypothetical: naïve causes UnicodeDecodeError.',p)['allowed']

def test_future_harness_utf8_decoding():
    from pathlib import Path
    root=Path(__file__).resolve().parents[1]
    s=(root/'artifacts/prepare_general_rerun.py').read_text(encoding='utf-8')
    assert "run_battery.py').read_text(encoding='utf-8')" in s
    source=(root/'artifacts/general_learning_memory_battery_20261012/run_battery.py').read_text(encoding='utf-8')
    assert 'café' in source and 'naïve' in source and 'cafÃ©' not in source
