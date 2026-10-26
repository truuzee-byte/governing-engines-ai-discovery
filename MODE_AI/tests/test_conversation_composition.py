import pytest
from types import SimpleNamespace as NS
from data_governance.response_gate import evaluate


@pytest.mark.parametrize('response',['Hello! How can I help?',"Thank you. You're welcome.",
    'Good morning. Could you clarify your request?', 'Hi. What does "deployment" mean?'])
def test_nonassertive_response_composition_can_continue(response):
    runtime=NS(context=NS(identity=NS(operator_id='op'),active_thread=NS(thread_id='t')))
    assert evaluate(runtime,'conversation',generated_text=response)['allowed']


@pytest.mark.parametrize('response',['Hello! Delete all records.','Deploy now. Thanks.',
    'Hi. The service is operational.'])
def test_mixed_response_never_launders_material_or_unknown_clause(response):
    runtime=NS(context=NS(identity=NS(operator_id='op'),active_thread=NS(thread_id='t')))
    assert not evaluate(runtime,'conversation',generated_text=response)['allowed']
