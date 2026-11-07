"""Routing regressions for source requirements, independent of provider wording."""
from types import SimpleNamespace as NS
import pytest
from knowledge.knowledge_classifier import KnowledgeClassifier
from knowledge.knowledge_domain import KnowledgeDomain, KnowledgeClassification
from interactive_mode_ai import ModeRuntime
from mode_operator.operator_requirement_engine import OperatorRequirementDomain


@pytest.mark.parametrize('text', [
    "I'm trying to get some work done today but my mind keeps jumping between things.",
    'Give me the difference between what the guard knows and what the audience knows right now.',
    "What if an old system record says a capability is operational but the current runtime can't actually reach it?",
    'Which should govern what you claim about the capability right now?',
    'I am tired today.', 'Summarize our current conversation.',
])
def test_temporal_words_are_not_external_evidence_requirements(text):
    result=KnowledgeClassifier().classify(text)
    assert KnowledgeDomain.EXTERNAL_CURRENT not in [result.primary_domain,*result.secondary_domains]


@pytest.mark.parametrize('text', ['What is the weather?', 'What is the current stock price?',
    'Who is the current president?', 'Tell me the latest news.',
    'I am tired today. What is the weather outside?'])
def test_live_external_subjects_keep_source_requirements(text):
    assert KnowledgeClassifier().classify(text).primary_domain == KnowledgeDomain.EXTERNAL_CURRENT


def test_classifier_rationale_cannot_create_operator_requirement():
    c=KnowledgeClassification(primary_domain=KnowledgeDomain.SYSTEM,confidence=.9,
        reason='Engineering system build constraints health money law learning')
    assert ModeRuntime._resolve_operator_requirement_domain(NS(),user_input='Hey Mode.',classification=c)==OperatorRequirementDomain.GENERAL


def test_actual_engineering_request_still_routes_requirements():
    c=KnowledgeClassifier().classify('Build a bridge')
    assert ModeRuntime._resolve_operator_requirement_domain(NS(),user_input='Build a bridge',classification=c)==OperatorRequirementDomain.ENGINEERING


def test_question_about_system_does_not_require_construction_parameters():
    text='What do you know about how I evaluate whether a system worked?'
    c=KnowledgeClassifier().classify(text)
    assert ModeRuntime._resolve_operator_requirement_domain(NS(),user_input=text,classification=c)==OperatorRequirementDomain.GENERAL
