from types import SimpleNamespace as NS
import pytest
from data_governance.response_gate import evaluate
from data_governance.context_admission import Admission


def runtime():return NS(context=NS(identity=NS(operator_id='op'),active_thread=NS(thread_id='t')))


@pytest.mark.parametrize('text',[
    'For this conversation, I will use that name. Please confirm if you want it saved to Persistent Memory.',
    'You care more about whether the artifact actually exists than whether the system reports it succeeded.',
    'The cause is unknown. I cannot infer who acted.',
])
def test_descriptions_and_uncertainty_are_not_completed_transitions(text):
    assert evaluate(runtime(),'Explain.',text)['allowed']


def test_memory_attribution_requires_actual_admitted_memory():
    text='Based on your statement stored in persistent memory, you value tangible results.'
    assert not evaluate(runtime(),'What did I say?',text)['allowed']
    a=Admission('op','t')
    a.consider('MEMORY','m1','I value tangible results.',source='MemoryGateway',basis={
        'verified':True,'governance_state':'APPROVED','lineage':['receipt:1'],
        'classification':'PERSISTENT_DATA','validation_state':'OPERATOR_ATTESTED','authority':'OPERATOR'})
    assert evaluate(runtime(),'What did I say?',text,reasoning_input=a.finish())['allowed']


@pytest.mark.parametrize('text',[
    'That information is not stored in persistent memory.',
    "I don't have that stored in persistent memory.",
    'Is that stored in persistent memory?',
])
def test_absent_memory_disclosure_is_not_a_positive_attribution(text):
    assert evaluate(runtime(),'What did I say?',text)['allowed']


def test_negative_clause_does_not_hide_positive_memory_attribution():
    assert not evaluate(runtime(),'What did I say?',
        'That fact is not stored in persistent memory, but your preference comes from persistent memory.')['allowed']


@pytest.mark.parametrize('text',['The build completed.','The deployment is successful.',
    'I have saved it permanently.','You may execute it.','The source is authoritative.'])
def test_material_success_and_permission_still_block(text):
    assert not evaluate(runtime(),'Explain.',text)['allowed']
