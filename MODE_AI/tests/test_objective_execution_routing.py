"""Observed objective-ingestion boundaries; no provider or execution grants."""
from pathlib import Path
from types import SimpleNamespace as NS
import pytest
from integration.self_inspection_activation import classify,is_file_operation_objective,assess
from interactive_mode_ai import ModeRuntime
from mode_operator.operator_requirement_models import OperatorRequirementDomain as Domain

ORIGINAL=Path(__file__).resolve().parents[1]/'artifacts/objective_execution_20261023/EXACT_OPERATOR_INPUT.txt'

def domain(text):
    return ModeRuntime._resolve_operator_requirement_domain(NS(),user_input=text,classification=NS())

def test_exact_original_is_execution_intent_not_self_inspection():
    query=ORIGINAL.read_text(encoding='utf-8')
    assert is_file_operation_objective(query)
    assert classify(query) is None
    assert assess(query,None) is None
    # This repair removes the demonstrated financial-path false positive;
    # other existing domain rules are not rewritten by this regression.
    assert domain(query)!=Domain.FINANCIAL_PLANNING

@pytest.mark.parametrize('query',[
    'Organize the project directory. You may inspect files through existing capabilities.',
    'Please move files in the workspace. MODE must inspect the environment.',
    'Sort these files. Record runtime behavior and stop if an action fails.',
])
def test_operational_inspection_not_self_diagnosis(query):
    assert is_file_operation_objective(query)
    assert classify(query) is None

@pytest.mark.parametrize('query',[
    'Inspect your current state.', 'Inspect yourself against this objective.',
    'What prevents you from achieving this objective?',
    'Organize files, then inspect yourself against this objective.',
])
def test_explicit_self_inspection_preserved(query):
    assert classify(query)=='CURRENT_CAPABILITY'
    assert not assess(query,None)['allowed']

@pytest.mark.parametrize('query',[
    'Create organized/assets/.','Inspect C:\\project\\assets\\logo.svg.',
    'Read assets/logo.svg.', 'Copy "assets/" to the destination.',
    'Explain asset_cache.py.',
])
def test_paths_not_financial(query):assert domain(query)==Domain.GENERAL

@pytest.mark.parametrize('query',[
    'Help plan my financial goals.', 'What is my income?',
    'Review my budget and debt.', 'How should I manage my assets?',
    'Read assets/logo.svg, then help plan my budget.',
])
def test_financial_intent_preserved(query):assert domain(query)==Domain.FINANCIAL_PLANNING

@pytest.mark.parametrize('query',['Hello MODE.','Explain photosynthesis.','Write a poem about files.','What are file permissions?'])
def test_unrelated_requests_not_objective_execution(query):assert not is_file_operation_objective(query)

def test_execution_intent_does_not_grant_file_authority(tmp_path):
    from builder.core.execution_contract import contained,validate_operations
    assert is_file_operation_objective('Move files outside the workspace.')
    with pytest.raises(ValueError):contained(tmp_path,'../outside.txt')
    with pytest.raises(ValueError):validate_operations([NS(path='file.txt',operation='MOVE')],tmp_path)
