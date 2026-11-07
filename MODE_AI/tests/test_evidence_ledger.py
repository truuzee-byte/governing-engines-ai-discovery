import json
from copy import deepcopy
from pathlib import Path
import pytest
from runtime_observation.evidence_ledger import normalize,from_prompt,render_selection,assess_rendered,PREFIX,INSTRUCTION
from data_governance.context_admission import Admission

SOURCE=Path(__file__).resolve().parents[1]/'artifacts/transformation_provenance_20261020/CONTROL_EVIDENCE.json'

@pytest.fixture
def projection():return json.loads(SOURCE.read_text(encoding='utf-8'))

def prompt_for(ledger):
    a=Admission(ledger['operator_id'],ledger['thread_id'])
    a.consider('RUNTIME','inspection',PREFIX+json.dumps(ledger),source='InteractionEvidenceLedger/1',
        basis={'validation_state':'UNVALIDATED','authority':'READ_ONLY_RUNTIME_EVIDENCE','lineage':[ledger['observation_id']]})
    a.consider('SYSTEM_POLICY','contract',INSTRUCTION,source='Scoped runtime explanation contract')
    return a.finish()

def test_recorded_values_and_scoped_unknowns(projection):
    ledger=normalize(projection)
    entries=ledger['entries'];events={s for s,v in ledger['sources'].items() if v['source_type']=='TRANSITION_RECORD'}
    assert len(events)==3
    for field in ('clarification_disposition','understanding.reason'):
        missing=next(e for e in entries if e['source_id']=='legacy' and e['field']==field)
        assert missing['evidence_class']=='UNAVAILABLE' and missing['recorded_alternatives']
        for alternative in missing['recorded_alternatives']:
            actual=next(e for e in entries if e['entry_id']==alternative['entry_id'])
            assert actual['evidence_class']=='OBSERVED' and actual['source_id'] in events
    assert next(e for e in entries if e['field']=='controller.clarification_required')['evidence_class']=='OBSERVED'
    for e in entries:
        if e['value'] in (False,0,[],{}):assert e['evidence_class']=='OBSERVED'
    assert not ledger['execution_authority'] and ledger['validation_state']=='RECORDED_NOT_INDEPENDENTLY_VALIDATED'

def test_trace_posture_never_becomes_transition_output(projection):
    ledger=normalize(projection)
    posture=next(e for e in ledger['entries'] if e['field']=='controller.selected_posture')
    source=ledger['sources'][posture['source_id']]
    assert source['source_type']=='TRACE_ROW' and source['transition_id'] is None and source['producer'] is None
    assert posture['allowed_attribution_target']=='trace:controller.selected_posture'
    for e in ledger['entries']:
        if e['field']=='result' and ledger['sources'][e['source_id']]['sequence']==1:
            assert 'selected_posture' not in e['value'] and 'ambiguity_score' not in e['value']

def test_disagreement_is_preserved_without_choosing(projection):
    projection['observed']['public_result']['clarification_required']=True
    ledger=normalize(projection)
    assert ledger['conflicts'] and ledger['conflicts'][0]['left_value'] is False and ledger['conflicts'][0]['right_value'] is True
    for identity in [ledger['conflicts'][0]['left'],ledger['conflicts'][0]['right']]:
        assert next(e for e in ledger['entries'] if e['entry_id']==identity)['conflicts']

def test_matching_understanding_request_conflict_preserved(projection):
    projection['observed']['understanding']['state']='DIFFERENT_RECORDED_STATE'
    ledger=normalize(projection)
    conflict=next(c for c in ledger['conflicts'] if c['field']=='understanding.state')
    assert conflict['left_value']=='DIFFERENT_RECORDED_STATE' and conflict['right_value']=='CLARIFICATION_REQUIRED'
    assert projection['observed']['understanding']['state']=='DIFFERENT_RECORDED_STATE'

def test_synthesis_is_inferred_and_supported(projection):
    ledger=normalize(projection)
    synthesized=[e for e in ledger['entries'] if e['evidence_class']=='INFERRED']
    assert {e['field'] for e in synthesized}=={'separate_result_relation','operator_presentation'}
    assert all(e['derived'] and not e['directly_recorded'] and len(e['support'])>=2 for e in synthesized)

def test_exact_references_and_context_not_output(projection):
    ledger=normalize(projection)
    for item in projection['transformation_provenance']['records']:
        event=item['record'];sid=event['transition_id'];source=ledger['sources'][sid]
        assert source['reference']==item['reference'] and source['producer']==event['producer']['component']
        for e in ledger['entries']:
            if e['source_id']==sid:assert e['value']==event[e['field']]

def test_no_historical_producer_or_reason_backfill(projection):
    projection['transformation_provenance']['records']=[]
    projection['observed']['declared_understanding_component']=None
    ledger=normalize(projection)
    assert not any(e['field']=='separate_result_relation' for e in ledger['entries'])
    unknown=next(e for e in ledger['entries'] if e['field']=='declared_understanding_component')
    assert unknown['evidence_class']=='UNAVAILABLE' and not unknown['recorded_alternatives']

def test_input_unchanged_bounded_and_only_ledger_is_admitted(projection):
    before=deepcopy(projection);ledger=normalize(projection);prompt=prompt_for(ledger)
    assert projection==before and len(json.dumps(ledger).encode())<=49152
    assert from_prompt(prompt)==ledger and '"observed":' not in prompt
    assert '"field_sources":' not in prompt

@pytest.mark.parametrize('bad',['plain invented answer',{},[],{'ledger_id':'wrong','statements':['E001']},
    {'ledger_id':'CURRENT','statements':['E999']},{'ledger_id':'CURRENT','statements':['E001'],'text':'invented cause'},
    {'ledger_id':'CURRENT','statements':['E001','E001']}])
def test_bad_final_selection_rejected_without_rewrite(projection,bad):
    ledger=normalize(projection)
    if isinstance(bad,dict) and bad.get('ledger_id')=='CURRENT':bad={**bad,'ledger_id':ledger['ledger_id']}
    raw=bad if isinstance(bad,str) else json.dumps(bad)
    with pytest.raises((PermissionError,ValueError)):render_selection(raw,prompt_for(ledger))

def test_every_emitted_statement_has_fixed_class_scope_and_support(projection):
    ledger=normalize(projection);prompt=prompt_for(ledger)
    chosen=[e['entry_id'] for e in ledger['entries'] if e['field'] in ('result','rules','separate_result_relation','events_outside_recorded_projection')]
    text,receipt=render_selection(json.dumps({'ledger_id':ledger['ledger_id'],'statements':chosen}),prompt)
    assert receipt['statement_ids']==chosen
    assert all(v.startswith(('OBSERVED [','INFERRED [','UNAVAILABLE [')) for v in text.splitlines())
    check=assess_rendered(text,prompt)
    assert check['allowed'] and len(check['claim_links'])==len(chosen)
    assert not assess_rendered(text+'\nThe hidden cause was an internal error.',prompt)['allowed']
    assert not assess_rendered(text.replace('OBSERVED [','INFERRED [',1),prompt)['allowed']

def test_scope_and_tamper_denied(projection):
    corrupt=deepcopy(projection);corrupt['transformation_provenance']['records'][0]['record']['operator_id']='foreign'
    with pytest.raises(PermissionError):normalize(corrupt)
    ledger=normalize(projection);ledger['entries'][0]['value']='tampered'
    with pytest.raises(PermissionError):from_prompt(prompt_for(ledger))

def test_reasoning_agent_uses_declared_contract_without_manual_answer_patch(projection):
    from tests.test_cross_thread_downstream_preservation import run
    ledger=normalize(projection);prompt=prompt_for(ledger)
    choices=[e['entry_id'] for e in ledger['entries'] if e['field']=='result']
    raw=json.dumps({'ledger_id':ledger['ledger_id'],'statements':choices})
    result,calls=run(prompt,['Analyze the scoped ledger.','Keep each result within its source scope.',raw])
    assert result.raw_final_response==raw
    assert result.context_admission[-1]['self_explanation']['statement_ids']==choices
    assert result.final_response==render_selection(raw,prompt)[0]
    assert all('InteractionEvidenceLedger/1' in text for text,_ in calls)
    assert all('"observed":' not in text for text,_ in calls)
