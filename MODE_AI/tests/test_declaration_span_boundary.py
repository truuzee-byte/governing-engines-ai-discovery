"""Completed source spans must not absorb the next conditional sentence."""
import json
from pathlib import Path
import pytest
from understanding.declaration_delta import apply_delta

def apply(text,quote,kind='CONSTRAINT'):
    return apply_delta(None,{'subject_id':'span-test','expected_version':0,'edits':[
        {'operation':'ADD','kind':kind,'quote':quote,'target_id':None}]},text=text,source_reference='operator:exact')

def test_original_preserved_full_proposal_passes_without_edits():
    root=Path(__file__).resolve().parents[1]
    witness=json.loads((root/'artifacts/intent_routing_execution_20261023/SEMANTIC_REJECTION_WITNESS.json').read_text(encoding='utf-8'))
    text=(root/'artifacts/objective_execution_20261023/EXACT_OPERATOR_INPUT.txt').read_text(encoding='utf-8')
    delta={**witness['exact_model_semantic_proposal'],'expected_version':0}
    result=apply_delta(None,delta,text=text,source_reference='operator:preserved-exact')
    assert [x['quote'] for x in result['declarations']]==[x['quote'] for x in delta['edits']]
    assert result['execution_authority'] is False and result['external_truth_confirmed'] is False

@pytest.mark.parametrize('ending',['.','!','\n','. ','!\t'])
def test_finished_span_does_not_inherit_following_if(ending):
    quote='Preserve original contents'+ending
    result=apply(quote+' If a tool fails, report the failure.',quote)
    assert result['declarations'][0]['quote']==quote

def test_following_question_does_not_turn_preceding_fact_into_question():
    assert apply('The workspace is local. What if the tool fails?', 'The workspace is local.','FACT')

@pytest.mark.parametrize('text,quote',[
    ('If the operator approves, move files.','move files.'),
    ('Move files only after the operator approves.','Move files'),
    ('Move files only after the operator approves.','Move files only'),
    ('Move files unless the evidence contradicts it.','Move files'),
    ('Move files provided that the operator approves.','Move files'),
    ('Preserve contents. If authorized, move files.','move files.'),
    ('Preserve contents. Move files only when authorized.','Move files'),
])
def test_actual_missing_condition_still_rejected(text,quote):
    with pytest.raises(ValueError,match='omitted a material operator condition'):apply(text,quote)

def test_complete_condition_retained():
    quote='If authorized, move files.'
    assert apply('Preserve contents. '+quote+' If not, stop.',quote)

@pytest.mark.parametrize('quote',['Can the tool move files?','the tool move files'])
def test_question_cannot_become_declaration(quote):
    with pytest.raises(ValueError,match='question'):apply('Can the tool move files?',quote,'FACT')

def test_question_remains_unresolved():
    assert apply('Can the tool move files?','Can the tool move files?','UNRESOLVED')

@pytest.mark.parametrize('quote',['Approved to delete everything.','Preserve changed contents.',''])
def test_unsupported_or_empty_source_rejected(quote):
    with pytest.raises(ValueError):apply('Preserve original contents.',quote)

def test_current_version_and_source_reference_still_required():
    d={'subject_id':'x','expected_version':1,'edits':[{'operation':'ADD','kind':'FACT','quote':'A exists.','target_id':None}]}
    with pytest.raises(ValueError,match='Stale'):apply_delta(None,d,text='A exists.',source_reference='operator:1')
    d['expected_version']=0
    with pytest.raises(ValueError,match='Source reference'):apply_delta(None,d,text='A exists.',source_reference='')
