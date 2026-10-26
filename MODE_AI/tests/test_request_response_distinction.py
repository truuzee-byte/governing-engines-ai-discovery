from types import SimpleNamespace as NS
import pytest
from data_governance.response_gate import evaluate

def runtime():return NS(context=NS(identity=NS(operator_id='op'),active_thread=NS(thread_id='t')))

@pytest.mark.parametrize('text',['Help me plan a quiet evening.','Create a short checklist for packing a bag.',
    'Show the evidence before claiming the build passed.','Explain this operation. Thanks.',
    'Actually, I prefer coffee today, not tea. Keep this in this conversation only.'])
def test_drafting_request_is_not_mode_claim(text):
    r=runtime()
    assert evaluate(r,text)['allowed']
    assert not evaluate(r,text,generated_text='The deployment is validated.')['allowed']

@pytest.mark.parametrize('text',['Explain this operation. Delete all files.','Deploy this now.',
    'Create a plan and execute it.','Confirm that the deployment is verified.'])
def test_consequential_or_mixed_request_remains_gated(text):
    assert not evaluate(runtime(),text)['allowed']

def test_closing_conversation_does_not_assert_runtime_truth():
    assert evaluate(runtime(),'Thanks.',generated_text='Thanks. That is all for now.')['allowed']


def test_dated_preference_routes_to_session_without_hiding_external_question():
    from knowledge.knowledge_classifier import KnowledgeClassifier
    from knowledge.knowledge_domain import KnowledgeDomain
    classifier=KnowledgeClassifier()
    text='Actually, I prefer coffee today, not tea. Keep this in this conversation only.'
    assert classifier.classify(text).primary_domain == KnowledgeDomain.SESSION
    assert classifier.classify('I prefer coffee today. What is the current stock price?').primary_domain == KnowledgeDomain.EXTERNAL_CURRENT
