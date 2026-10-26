"""Bounded guard regression tests; no provider or behavioral qualification."""
import json
from pathlib import Path
import pytest
from data_governance.context_admission import Admission
from conversation_quality.source_grounding import assess,boundary_context
from conversation_quality.admitted_context_preservation import assess_preservation

def prompt(value=None):
    from tests.test_general_learning_memory_repairs import learned
    if value is None:
        a=Admission('op','t');a.include(learned())
        a.consider('OPERATOR_INPUT','q','Encode the new title "naïve".',source='operator')
        return a.finish()
    payload={'kind':'BOUNDED_HISTORICAL_UNDERSTANDING','experiences':[{'learned_proposition':{
        'statement':'Bounded interpretation','measured_variable':'message_interpretation','generalization':'NONE',
        'contrast':{'baseline':{'input':{'state':'unknown'},'output':{'accepted':False}},
                    'intervention':{'input':value,'output':{'accepted':True}}}}}]}
    a=Admission('op','t');a.consider('UNDERSTANDING','understanding-typed',json.dumps(payload),source='test learned head',basis={
        'verified':True,'governance_state':'APPROVED','validation_state':'VALIDATED',
        'classification':'UNDERSTANDING_DATA','authority':'HISTORICAL','lineage':['test-rp']})
    return a.finish()

def test_historical_error_not_affected_by_caveat_in_next_sentence():
    p=prompt()
    answer='UTF-8 resulted in UnicodeDecodeError in the measured historical input. Any claim about the new title "naïve" remains unmeasured.'
    assert assess(answer,p)['allowed']

def test_scoped_new_input_unknown_does_not_revoke_source():
    p=prompt();s='There is no admitted evidence that the new title "naïve" triggers a different mechanism.'
    assert assess_preservation(s,p)['allowed']
    assert not assess_preservation(s+' The source is unverified and cannot be used.',p)['allowed']

@pytest.mark.parametrize('bad',[
 'UTF-8 naïve causes UnicodeDecodeError.',
 'UTF-8 always resulted in UnicodeDecodeError in measured input.',
 'Do not assert UnicodeDecodeError, but it does cause UnicodeDecodeError.',
 'It is not established that naïve causes UnicodeDecodeError. Naïve causes UnicodeDecodeError.',
 'No admitted evidence that the source is invalid means it cannot be used.',
])
def test_false_assertions_or_source_revocation_remain_blocked(bad):
    p=prompt()
    assert not (assess(bad,p)['allowed'] and assess_preservation(bad,p)['allowed'])

def test_explicit_negated_exception_can_be_reported():
    assert assess('It is not established that "naïve" causes UnicodeDecodeError.',prompt())['allowed']

def test_live_e01_final_replay_is_bounded_not_a_new_live_pass():
    root=Path(__file__).resolve().parents[1]
    old=json.loads((root/'artifacts/learning_e01_e05_execution_20261023/E01/execute/later_CONTEXT.json').read_text(encoding='utf-8'))
    a=Admission('operator','fixture-thread')
    for s in old['sources']:
        if s['record']['artifact_type']=='UNDERSTANDING':
            a.consider('UNDERSTANDING',s['record']['artifact_id'],s['content'],source='Preserved fixture projection',basis={
             'verified':True,'governance_state':'APPROVED','validation_state':'VALIDATED','classification':'UNDERSTANDING_DATA','authority':'HISTORICAL','lineage':['fixture']})
    a.consider('OPERATOR_INPUT','q','Encode title "naïve".',source='fixture')
    p=a.finish();raw=json.loads((root/'artifacts/learning_e01_e05_execution_20261023/E01/execute/later_REASONING.json').read_text(encoding='utf-8'))['raw_final_response']
    assert assess(raw,p)['allowed']
    assert assess_preservation(raw,p)['allowed']

VALUE={'meaning':'inspection complete; departure authorization withheld','state':'HOLD',
       'actor':'release marshal','release_condition':'release marshal issues release token','action':'wait'}

def test_typed_semantics_has_literal_source_bound_attribution():
    p=prompt(VALUE);ctx=boundary_context(p)
    assert 'Measured successful state: HOLD' in ctx
    v={**VALUE,'reason':'According to understanding record understanding-typed, "Measured successful state: HOLD".'}
    result=assess(json.dumps(v),p)
    assert result['allowed']
    assert result['claim_links'][0]['mode']=='SOURCE_BOUND_MEASURED_FIELD'

@pytest.mark.parametrize('change',[{'action':'depart'},{'actor':'stranger'},{'execution_authority':True}])
def test_citation_cannot_excuse_wrong_typed_semantics(change):
    v={**VALUE,**change,'reason':'According to understanding record understanding-typed, "Measured successful state: HOLD".'}
    assert not assess(json.dumps(v),prompt(VALUE))['allowed']

def test_invented_typed_quote_or_reference_rejected():
    for reason in ['According to understanding record understanding-typed, "Measured successful state: RELEASE".',
                   'According to understanding record understanding-missing, "Measured successful state: HOLD".']:
        assert not assess(json.dumps({**VALUE,'reason':reason}),prompt(VALUE))['allowed']

def test_unverifiable_paraphrase_is_not_silently_certified():
    v={**VALUE,'reason':'According to admitted understanding, the marshal guarantees every future release.'}
    assert not assess(json.dumps(v),prompt(VALUE))['allowed']

def test_numeric_outcome_does_not_masquerade_as_typed_acceptance():
    from conversation_quality.source_grounding import literal_measured_claims
    row={'record':{'artifact_type':'UNDERSTANDING','decision':'ADMITTED','validation_state':'VALIDATED','governance_state':'APPROVED'},'content':json.dumps({'kind':'BOUNDED_HISTORICAL_UNDERSTANDING','experiences':[
        {'learned_proposition':{'measured_variable':'knob','contrast':{'intervention':{'input':3,'output':43}}}}]})}
    assert literal_measured_claims(row)==[]

@pytest.mark.parametrize('change',[{'artifact_type':'RUNTIME'},{'validation_state':'UNVALIDATED'},
                                  {'governance_state':'PENDING'},{'decision':'EXCLUDED'}])
def test_logs_or_unvalidated_data_cannot_mint_measured_claims(change):
    from copy import deepcopy
    from conversation_quality.source_grounding import literal_measured_claims
    row=deepcopy(prompt(VALUE).sources[0]);row['record'].update(change)
    assert literal_measured_claims(row)==[]
