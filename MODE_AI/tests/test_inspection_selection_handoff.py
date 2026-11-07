"""Replay the preserved provider outputs; no new behavioral evidence or provider calls."""
import json
from pathlib import Path
import pytest
from tests.test_cross_thread_downstream_preservation import run
from tests.test_inspection_coverage import sealed
from runtime_observation.evidence_ledger import render_selection
from runtime_observation.inspection_coverage import CoverageIncomplete

ROOT=Path(__file__).resolve().parents[1]
OLD=ROOT/'artifacts/self_inspection_activation_20261020'

@pytest.fixture
def evidence():
 audit=json.loads((OLD/'inspect_SELF_INSPECTION_ACCESS.json').read_text(encoding='utf-8'))
 calls=json.loads((OLD/'PROVIDER_CALLS.json').read_text(encoding='utf-8'))
 outputs=[''.join(b.get('text','') for item in c['response'].get('output',[]) for b in item.get('content',[]) if b.get('type')=='output_text') for c in calls[1:]]
 return sealed(audit['evidence_ledger'],audit['coverage_contract']),outputs

def test_preserved_draft_is_complete_and_critique_first_drops_required_rule(evidence):
 prompt,outputs=evidence
 assert render_selection(outputs[0],prompt)[1]['coverage']['complete']
 for raw in outputs[1:]:
  with pytest.raises(CoverageIncomplete) as exc:render_selection(raw,prompt)
  missing=[d for d in exc.value.report['dimensions'] if d['status']=='MISSING_REQUIRED_COVERAGE']
  assert len(missing)==1 and missing[0]['dimension_id']=='GOVERNING_RULE'

def test_actual_failed_sequence_retains_whole_valid_draft(evidence):
 prompt,outputs=evidence;expected,receipt=render_selection(outputs[0],prompt)
 result,calls=run(prompt,outputs)
 assert len(calls)==3 and result.final_response==expected
 assert result.draft==outputs[0] and result.critique==outputs[1] and result.raw_final_response==outputs[2]
 draft,critique,final=result.context_admission
 assert draft['inspection_selection_validation']['allowed']
 assert not critique['inspection_selection_validation']['allowed'] and not critique['promoted_to_revision']
 assert final['self_explanation']['statement_ids']==receipt['statement_ids']
 assert final['inspection_final_rejection']['coverage']['complete'] is False
 assert final['selection']=='VALIDATED_INSPECTION_PROPOSAL_RETAINED_AFTER_INVALID_FINAL'

def test_correct_final_is_not_replaced(evidence):
 prompt,outputs=evidence
 result,_=run(prompt,[outputs[0],outputs[1],outputs[0]])
 assert result.raw_final_response==outputs[0]
 assert result.context_admission[-1]['selection']=='FINAL_MODEL_RESPONSE'
 assert 'inspection_final_rejection' not in result.context_admission[-1]

def test_without_valid_candidate_failure_stays_closed(evidence):
 prompt,outputs=evidence
 with pytest.raises(CoverageIncomplete):run(prompt,[outputs[1],outputs[1],outputs[2]])

def test_no_id_union_or_statement_completion(evidence):
 prompt,outputs=evidence
 original=json.loads(outputs[0]);partial=json.loads(outputs[2])
 # Both invalid partial proposals together have the required entries, but they
 # must never be combined to fabricate a complete model proposal.
 other=dict(original,statements=[i for i in original['statements'] if i not in partial['statements']])
 with pytest.raises(CoverageIncomplete):run(prompt,[json.dumps(other),outputs[1],outputs[2]])

def test_freeform_internal_critique_remains_supported(evidence):
 prompt,outputs=evidence
 result,_=run(prompt,[outputs[0],'Keep all required scoped evidence.',outputs[0]])
 assert result.context_admission[-1]['self_explanation']['coverage']['complete']

def test_valid_critique_can_be_retained_when_draft_is_not_a_selection(evidence):
 prompt,outputs=evidence
 result,_=run(prompt,['Consider the ledger evidence.',outputs[0],outputs[2]])
 assert result.final_response==render_selection(outputs[0],prompt)[0]
 assert result.context_admission[1]['inspection_selection_validation']['allowed']

@pytest.mark.parametrize('bad',[
 {'ledger_id':'other','statements':['E001']},
 {'ledger_id':'ledger-7945ec19c03986cf','statements':['INVENTED']},
 {'ledger_id':'ledger-7945ec19c03986cf','statements':['E001','E001']},
])
def test_invalid_replacement_cannot_displace_valid_proposal(evidence,bad):
 prompt,outputs=evidence;raw=json.dumps(bad)
 result,_=run(prompt,[outputs[0],raw,raw])
 assert not result.context_admission[1]['promoted_to_revision']
 assert result.final_response==render_selection(outputs[0],prompt)[0]

def test_no_preserved_case_id_in_production_handoff():
 source=(ROOT/'agents/reasoning_agent.py').read_text(encoding='utf-8')
 assert 'E042' not in source and 'transformation-3f6b8983a36443cebfbcf215782fc57e' not in source
