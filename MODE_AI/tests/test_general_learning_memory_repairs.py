"""Offline engineering checks; not behavioral requalification."""
import json
import pytest
from types import SimpleNamespace as NS
from data_governance.context_admission import Admission
from conversation_quality.source_grounding import assess, boundary_context
from tests.test_cross_thread_downstream_preservation import run, context
from persistent_memory.tests.test_memory_injection import save, setup_context

def memory(content='Solace seedlings use the bottom reservoir.', identifier='pm-valid'):
    a=Admission('op','t')
    a.consider('MEMORY',identifier,content,source='PersistentMemoryStore',basis={
        'verified':True,'governance_state':'APPROVED','classification':'PERSISTENT_DATA',
        'validation_state':'OPERATOR_ATTESTED','authority':'OPERATOR','lineage':['approval']})
    return a.finish()

def empty():
    a=Admission('op','t');a.consider('OPERATOR_INPUT','q','Choose an Oriel receipt format.',source='operator')
    return a.finish()

def learned(error='UnicodeDecodeError'):
    a=Admission('op','t')
    p={'kind':'BOUNDED_HISTORICAL_UNDERSTANDING','experiences':[{'learned_proposition':{
        'statement':'Historical encoding contrast','generalization':'NONE',
        'contrast':{'baseline':{'input':'UTF-8','output':{'error':error}},
                    'intervention':{'input':'UTF-16LE','output':{'decoded':'café'}}}},
        'provenance':{'rp_receipt_id':'rp1'}}]}
    a.consider('UNDERSTANDING','understanding-valid',json.dumps(p),source='Learning head',basis={
        'verified':True,'governance_state':'APPROVED','classification':'UNDERSTANDING_DATA',
        'validation_state':'VALIDATED','authority':'HISTORICAL','lineage':['rp1']})
    return a.finish()

def test_correct_learned_choice_survives_all_stages():
    result,calls=run(learned(),['UTF-16LE; historical result, fresh-input mechanism is inference.',
                            'Retain the measured choice; do not invent an exception.', 'UTF-16LE'])
    assert result.final_response=='UTF-16LE'
    assert all('Historical encoding contrast' in p and 'rp1' in p for p,_ in calls)

def test_false_encoding_explanation_blocked_with_raw_preserved():
    bad='UTF-8 naïve causes UnicodeDecodeError.'
    result,calls=run(learned(),[bad,bad,bad])
    assert result.raw_final_response==bad and result.draft==bad and result.critique==bad
    assert not result.context_admission[0]['source_grounding']['allowed']
    assert not result.context_admission[1]['promoted_to_revision']
    assert result.context_admission[-1]['selection']=='REVIEW_REQUIRED_NO_SAFE_PROPOSAL'

def test_authorized_reassembled_measurement_can_change_supported_claim():
    # The source owner, not a model proposal, issues the replacement admission.
    prompt=learned('NewMeasuredError')
    answer='Historical understanding-valid records "NewMeasuredError"; future outcomes remain unknown.'
    result,calls=run(prompt,[answer,'Preserve the exact historical measurement.',answer])
    assert result.final_response==answer
    assert all('NewMeasuredError' in p and 'UnicodeDecodeError' not in p for p,_ in calls)

def test_valid_exact_memory_attribution():
    assert assess('According to memory pm-valid, "Solace seedlings use the bottom reservoir."',memory())['allowed']

@pytest.mark.parametrize('text',[
    'Based on eligible operator-attested memory, DeliveryReceiptRepresentation is defined.',
    'Memory confirms the receipt format.',
    'According to source pm-missing, "Solace seedlings use the bottom reservoir."',
])
def test_nonexistent_provenance_blocked(text):
    assert not assess(text,empty())['allowed']

def test_misattributed_claim_blocked():
    assert not assess('According to memory pm-valid, "Harbor pumps use brine."',memory())['allowed']

def test_critique_request_cannot_create_memory():
    result,calls=run(empty(),['A structured form is a tentative proposal.',
        'Incorporate explicit references to eligible memory that defines the representation.',
        'Based on eligible operator-attested memory, DeliveryReceiptRepresentation is defined.'])
    assert not result.context_admission[1]['promoted_to_revision']
    assert result.final_response=='A structured form is a tentative proposal.'
    assert 'Based on eligible' in result.raw_final_response
    assert all('empty means absent' in p for p,_ in calls)

def test_absent_support_can_be_disclosed():
    assert assess('No memory supports this tentative proposal.',empty())['allowed']

def test_unknown_answer_does_not_negate_fabricated_reason():
    assert not assess(json.dumps({'choice':'unknown','reason':'Based on memory, this format is required.'}),empty())['allowed']

def test_no_doubt_is_not_an_absence_of_support():
    assert not assess('No doubt memory confirms this format.',empty())['allowed']
    assert not assess('No doubt naïve causes UnicodeDecodeError.',learned())['allowed']

def test_real_error_citation_does_not_validate_fresh_input():
    a=Admission('op','t');a.include(learned())
    a.consider('OPERATOR_INPUT','fresh-query','Choose encoding for "naïve".',source='operator')
    result=assess('For naïve, understanding-valid reports "UnicodeDecodeError".',a.finish())
    assert not result['allowed'] and 'UNMEASURED_INPUT_EXCEPTION_CLAIM' in result['reasons']

def test_relevance_subject_binding_and_receipts(tmp_path):
    m,_,_=setup_context(tmp_path)
    current=save(m,'Solace greenhouse seedlings receive irrigation through the bottom reservoir.')
    unrelated=save(m,'Harbor maintenance irrigation pumps are flushed with brine.')
    result=m.retrieve_memories('operator','Describe Solace greenhouse irrigation for a fresh tray.')
    assert [r.memory_id for r in result]==[current.memory_id]
    receipt=next(r for r in m.retrieval_decisions if r['record_id']==unrelated.memory_id)
    assert receipt['reason']=='SUBJECT_SCOPE_MISMATCH' and 'irrigation' in receipt['lexical_overlap']

def test_relevant_subject_without_same_task_words(tmp_path):
    m,_,_=setup_context(tmp_path);record=save(m,'Solace seedlings use the bottom reservoir.')
    assert m.retrieve_memories('operator','How should Solace plants be watered?')[0].memory_id==record.memory_id

def test_same_entity_different_task_not_material(tmp_path):
    m,_,_=setup_context(tmp_path)
    record=save(m,'Solace greenhouse seedlings have blue tray labels.')
    assert m.retrieve_memories('operator','Describe Solace greenhouse seedlings irrigation.')==[]
    assert m.retrieval_decisions[0]['reason']=='TASK_SCOPE_MISMATCH'

def test_multiple_shared_words_do_not_replace_subject_scope(tmp_path):
    m,_,_=setup_context(tmp_path)
    save(m,'harbor irrigation pumps use brine.')
    assert m.retrieve_memories('operator','Describe Solace irrigation pumps.')==[]

def test_unknown_task_lexical_overlap_fails_closed(tmp_path):
    m,_,_=setup_context(tmp_path)
    save(m,'the orange widget appears near the square fixture.')
    assert m.retrieve_memories('operator','Explain the orange widget.')==[]

def test_newer_state_retrievable_archived_excluded(context):
    assert context.manager.retrieve_memories('op','Neral dispatch code')[0].version==2
    assert all(r.memory_id!=context.inactive.memory_id for r in context.manager.retrieve_memories('op','Neral dispatch code'))
