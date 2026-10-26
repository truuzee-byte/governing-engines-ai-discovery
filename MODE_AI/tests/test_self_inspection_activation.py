import json
from pathlib import Path
from types import SimpleNamespace as NS
import pytest
from data_governance.context_admission import Admission
from data_governance.response_gate import governed_interaction
from integration.self_inspection_activation import classify,assess,BOUNDED_RESULT
from integration.runtime_self_inspection import reasoning_context
from tests.test_interaction_inspection import case

@pytest.mark.parametrize('query',[
 'What can you currently do?',"What can’t you do?",'What prevents you from achieving this objective?',
 'What part of your architecture is missing?','Inspect yourself against this objective.',
 'What mechanism do you need?','Are you capable of X right now?',
 'What can you currently inspect about yourself?','What can MODE currently do?',
 'Explain MODE architecture.','Does MODE currently have this capability?',
 'Can you achieve this objective?', 'Inspect your current state.',
 'Translate this sentence, then state what can you currently do.',
])
def test_current_capability_activation(query):assert classify(query)=='CURRENT_CAPABILITY'

@pytest.mark.parametrize('query',[
 'Why did your last interaction enter this state?','Why did you behave this way?',
 'What state caused this result?','Inspect the completed interaction.',
])
def test_behavior_activation(query):assert classify(query)=='COMPLETED_INTERACTION'

@pytest.mark.parametrize('query',[
 'What is 2 + 2?','Explain photosynthesis.','Hello','Can you explain photosynthesis?',
 'What can plants do?','Explain state machines.',
 'Translate "What can you currently do?" into French.',
 'Write a story where a robot asks what can you currently do.',
])
def test_ordinary_prompts_not_activated(query):
 assert classify(query) is None
 assert reasoning_context(NS(),query) is None

def routed(case,query):
 inspector,r,t,_=case;runtime=NS(context=NS(identity=NS(operator_id='owner'),active_thread=t))
 prompt=reasoning_context(runtime,query,inspector=inspector,
     selector=lambda _:json.dumps({'tool':'inspect_interaction','interaction_id':'interaction-prior'}))
 return runtime,prompt

def test_automatic_route_produces_unchanged_ledger_and_coverage(case):
 from runtime_observation.evidence_ledger import normalize
 runtime,prompt=routed(case,'What can you currently inspect about yourself?')
 audit=runtime.context.self_inspection
 assert audit['activation']['required'] and audit['prerequisite']['execution_authority'] is False
 assert audit['evidence_ledger']==normalize(audit['tool_result'])
 assert audit['coverage_contract']['ledger_id']==audit['evidence_ledger']['ledger_id']
 assert assess('What can you currently inspect about yourself?',prompt)['allowed']

def test_current_capability_cannot_be_inferred_from_historical_evidence(case):
 from runtime_observation.evidence_ledger import line
 query='What can you currently do?';runtime,prompt=routed(case,query)
 ledger=runtime.context.self_inspection['evidence_ledger']
 explanation=line(ledger,ledger['entries'][0])
 result=assess(query,prompt,explanation)
 assert not result['allowed'] and result['reason']=='CURRENT_CAPABILITY_NOT_ESTABLISHED_BY_COMPLETED_INTERACTION_EVIDENCE'
 assert result['inspected_response_hash']

@pytest.mark.parametrize('generated', ['canonical','I lack an inspection interface and need a new architecture.'])
def test_publication_returns_only_bounded_scope_failure(case,generated):
 from runtime_observation.evidence_ledger import line
 query='What can you currently do?';runtime,prompt=routed(case,query)
 if generated=='canonical':
  ledger=runtime.context.self_inspection['evidence_ledger'];generated=line(ledger,ledger['entries'][0])
 raw=NS(response_text=generated,trace_reference='trace',failure_state={},halt_required=False,clarification_required=False)
 result=governed_interaction(runtime,NS(raw_input=query,session_id=runtime.context.active_thread.thread_id),prompt,lambda *a,**k:raw)
 assert result.response_text==BOUNDED_RESULT and result.response_text!=generated
 assert not runtime.context.response_governance['allowed']

def test_recent_behavior_accepts_exact_inspected_explanation(case):
 from runtime_observation.evidence_ledger import line
 query='Why did your last interaction enter this state?';runtime,prompt=routed(case,query)
 ledger=runtime.context.self_inspection['evidence_ledger']
 generated=line(ledger,ledger['entries'][0])
 assert assess(query,prompt,generated)['allowed']

def test_generic_architecture_answer_is_rejected_despite_inspection(case):
 query='What can you currently do?';_,prompt=routed(case,query)
 result=assess(query,prompt,'I lack an inspection interface and need a new architecture.')
 assert not result['allowed'] and result['reason']=='SELF_INSPECTION_EXPLANATION_NOT_GROUNDED_OR_COMPLETE'

def test_cannot_bypass_inspection_or_reuse_other_query_receipt(case):
 query='What can you currently do?';runtime,prompt=routed(case,query)
 a=Admission('owner',runtime.context.active_thread.thread_id)
 a.consider('OPERATOR_INPUT','current',query,source='OperatorInput')
 assert not assess(query,a.finish())['allowed']
 assert not assess('What mechanism do you need?',prompt)['allowed']

def test_publication_gate_blocks_before_reasoning_without_evidence():
 a=Admission('owner','thread');a.consider('OPERATOR_INPUT','input','What can you currently do?',source='OperatorInput')
 runtime=NS(context=NS(identity=NS(operator_id='owner'),active_thread=NS(thread_id='thread')))
 operator=NS(raw_input='What can you currently do?',session_id='thread')
 result=governed_interaction(runtime,operator,a.finish(),lambda *a,**k:pytest.fail('No reasoning before evidence'))
 assert result.response_text==BOUNDED_RESULT
 assert runtime.context.response_governance['execution_authority_granted'] is False

@pytest.mark.parametrize('claim',[
 'I lack a self-inspection interface.', 'MODE has an introspection mechanism.',
 'I can inspect my runtime.', 'I cannot access my code.',
 'My architecture lacks introspection.',
])
def test_unsolicited_self_claim_cannot_survive_ordinary_prompt(claim):
 a=Admission('owner','thread');a.consider('OPERATOR_INPUT','input','Explain photosynthesis.',source='OperatorInput')
 runtime=NS(context=NS(identity=NS(operator_id='owner'),active_thread=NS(thread_id='thread')))
 called=[]
 def processor(*a,**k):
  called.append(True)
  return NS(response_text=claim,trace_reference='',failure_state={},halt_required=False,clarification_required=False)
 result=governed_interaction(runtime,NS(raw_input='Explain photosynthesis.',session_id='thread'),a.finish(),processor)
 assert called and result.response_text==BOUNDED_RESULT

def test_ordinary_fact_does_not_acquire_inspection_obligation():
 assert assess('Explain photosynthesis.',None,'Plants convert light energy into chemical energy.') is None

def test_no_candidates_is_bounded_not_generic(case,monkeypatch):
 inspector,r,t,_=case;monkeypatch.setattr(inspector,'candidates',lambda *a:[])
 runtime=NS(context=NS(identity=NS(operator_id='owner'),active_thread=t))
 query='What can you currently do?'
 prompt=reasoning_context(runtime,query,inspector=inspector,selector=lambda _:pytest.fail('No candidate provider call'))
 assert runtime.context.self_inspection['prerequisite']['status']=='UNAVAILABLE'
 assert not assess(query,prompt)['allowed']

def test_custody_failure_exposes_no_foreign_candidates(case,monkeypatch):
 inspector,r,t,_=case
 def denied(*a):raise PermissionError('foreign store')
 monkeypatch.setattr(inspector,'candidates',denied)
 runtime=NS(context=NS(identity=NS(operator_id='owner'),active_thread=t))
 prompt=reasoning_context(runtime,'What can you currently do?',inspector=inspector)
 assert not assess('What can you currently do?',prompt)['allowed']
 assert runtime.context.self_inspection['candidates']==[] and 'foreign store' not in prompt

def test_read_only_activation_and_scope_selection(case):
 inspector,r,t,_=case
 before={str(p):p.read_bytes() for p in inspector.trace_path.parent.rglob('*') if p.is_file()}
 routed(case,'Why did your last interaction enter this state?')
 assert before=={str(p):p.read_bytes() for p in inspector.trace_path.parent.rglob('*') if p.is_file()}

def test_exact_objective_prompt_is_required():
 query=Path('artifacts/self_inspection_activation_20261020/BEHAVIORAL_PROMPT.txt').read_text(encoding='utf-8')
 assert classify(query)=='CURRENT_CAPABILITY'

def test_inspection_turn_skips_semantic_and_learning_writes():
 import ast
 tree=ast.parse(Path('interactive_mode_ai.py').read_text(encoding='utf-8'))
 guarded=set()
 for node in ast.walk(tree):
  if isinstance(node,ast.If) and ast.unparse(node.test)=='not inspection_turn':
   for call in ast.walk(node):
    if isinstance(call,ast.Call):guarded.add(ast.unparse(call.func))
 assert {'prepare_meaning','self._understand_observation','evaluate_learning'}<=guarded
