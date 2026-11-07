"""Request intent versus task-data mentions; never execution authority."""
from pathlib import Path
from types import SimpleNamespace as NS
import pytest
from interactive_mode_ai import ModeRuntime
from mode_operator.operator_requirement_models import OperatorRequirementDomain as D
from integration.self_inspection_activation import classify,is_file_operation_objective

def domain(q):return ModeRuntime._resolve_operator_requirement_domain(NS(),user_input=q,classification=NS())

def test_exact_original_request_keeps_operational_meaning():
    q=(Path(__file__).resolve().parents[1]/'artifacts/objective_execution_20261023/EXACT_OPERATOR_INPUT.txt').read_text(encoding='utf-8')
    assert is_file_operation_objective(q) and classify(q) is None
    assert domain(q)==D.GENERAL

@pytest.mark.parametrize('q',[
    'Explain MODE Learning admission and Understanding adoption.',
    'No Learning approval is supplied; follow existing governance.',
    'Inspect the Learning subsystem candidate lesson evidence.',
    'Explain the learning runtime, not a human profile.',
    'Move files under assets/learning/grade/report.txt.',
    'Explain a software upgrade.',
])
def test_technical_words_do_not_create_education_requirements(q):assert domain(q)==D.GENERAL

@pytest.mark.parametrize('q',[
    'Help me learn French.', 'Teach me algebra.', 'I am learning English.',
    'I want to learn Python.', 'What is my grade level?',
    'Plan my school curriculum.', 'Help my child study mathematics.',
    'Recommend an educational course.',
])
def test_real_education_intent_preserved(q):assert domain(q)==D.EDUCATION

@pytest.mark.parametrize('q',[
    'Help me plan my financial goals.', 'Review my income and debt.',
    'Organize files under assets/, then review my budget.',
])
def test_financial_requests_still_take_their_workflow(q):assert domain(q)==D.FINANCIAL_PLANNING

def test_mixed_execution_education_and_inspection():
    q='Organize files under assets/. Then help me learn Python.'
    assert domain(q)==D.EDUCATION
    assert is_file_operation_objective(q)
    assert classify('Organize files. Then inspect yourself against this objective.')=='CURRENT_CAPABILITY'

@pytest.mark.parametrize('q',['Inspect yourself against this objective.','Inspect your current state.','What prevents you from achieving this objective?'])
def test_genuine_self_inspection_preserved(q):assert classify(q)=='CURRENT_CAPABILITY'

def test_intent_recognition_cannot_authorize_out_of_scope_action(tmp_path):
    from builder.core.execution_contract import contained,validate_operations
    assert is_file_operation_objective('Move files outside the authorized directory.')
    with pytest.raises(ValueError):contained(tmp_path,'../outside.txt')
    with pytest.raises(ValueError):validate_operations([NS(path='a',operation='MOVE')],tmp_path)

def test_no_generic_file_tool_dispatch_in_existing_inference_path():
    # Architectural constraint, not a declaration that Builder cannot execute.
    import inspect
    from integration.mode_generation import ModeGenerationProvider
    source=inspect.getsource(ModeGenerationProvider.generate)
    assert 'self.agent.generate' in source
    assert '"Do not execute commands or write files"' in source
    from integration.build_runtime import BuildRuntime
    r=NS(context=NS(active_thread=NS(thread_id='thread')))
    assert BuildRuntime(r).route('Organize the directory without an explicit build contract.') is None
