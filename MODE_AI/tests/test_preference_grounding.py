"""Bounded preference grounding falsifiers; never call a provider."""
import inspect
import json
from pathlib import Path
from types import SimpleNamespace as NS
import pytest
from data_governance.context_admission import Admission
from data_governance.response_gate import evaluate
from conversation_quality.conversation_quality_evaluator import evaluate_conversation_quality
from models.runtime_models import CanonicalInteractionState

CASE = Path(__file__).resolve().parents[1] / 'artifacts/behavioral_qualification_preference_fix_20260924/retained_case.json'

def prompt(facts=(), memory=(), assistant=()):
    a = Admission('op', 't')
    for i, value in enumerate(facts):
        a.consider('THREAD', str(i), value, source='ThreadMemory', basis={'authority':'OPERATOR'})
    for i, value in enumerate(assistant):
        a.consider('THREAD', 'a'+str(i), value, source='ThreadMemory', basis={'authority':'NONE','validation_state':'UNVALIDATED'})
    for i, value in enumerate(memory):
        a.consider('MEMORY', 'm'+str(i), value, source='PersistentMemoryStore', basis={
            'verified':True, 'governance_state':'APPROVED','classification':'PERSISTENT_DATA',
            'validation_state':'OPERATOR_ATTESTED','authority':'OPERATOR','durability_state':'DURABLE','lineage':['approval']})
    return a.finish()

def publish(response, facts=(), memory=(), assistant=()):
    runtime = NS(context=NS(identity=NS(operator_id='op'),active_thread=NS(thread_id='t')))
    kwargs = {'reasoning_input':prompt(facts,memory,assistant)} if 'reasoning_input' in inspect.signature(evaluate).parameters else {}
    return evaluate(runtime,'How does that change the evening plan?',response,**kwargs)

@pytest.mark.parametrize('facts,response,allowed', [
    ([], 'You prefer tea.', False),
    (['I prefer tea.'], 'You prefer tea.', True),
    (['I ordered tea once.'], 'You prefer tea.', False),
    (['I ordered tea once.'], 'You may prefer tea; that is only a hypothesis.', True),
    (['I prefer tea.', 'I prefer coffee.'], 'You prefer tea.', False),
    (['I prefer tea.', 'I prefer coffee.'], 'Your preference is unclear; which drink would you choose?', True),
    (['I prefer tea.', 'Actually, I prefer coffee today, not tea.'], 'You prefer coffee today.', True),
    (['I prefer tea.', 'Actually, I prefer coffee today, not tea.'], 'You prefer tea.', False),
    ([], 'The evening plan can include reading and quiet music.', True),
    ([], 'I do not know your preference. Which drink would you choose?', True),
    (['I prefer tea today.'], 'Your default drink is tea outside this conversation.', False),
    (['Do not save this: I prefer tea today.', 'Actually, I prefer coffee today, not tea. Keep this in this conversation only.'],
     'The original tea-based plan remains your default outside this conversation.', False),
])
def test_preference_matrix(facts,response,allowed):
    assert publish(response,facts)['allowed'] is allowed

def test_supported_retrieved_memory_is_preserved():
    assert publish('You prefer tea.', memory=['I prefer tea.'])['allowed']

@pytest.mark.parametrize('response',[
    'Coffee might be relaxing, but your default drink is tea.',
    'If the evening is quiet, you prefer tea.',
    'You always prefer tea.',
    'Your default drink is tea outside this conversation.',
])
def test_uncertainty_or_session_scope_cannot_launder_fact(response):
    assert not publish(response,['I prefer coffee today.'])['allowed']

def test_explicit_default_is_not_rejected():
    assert publish('Your default drink is tea.',memory=['My default drink is tea.'])['allowed']

def test_today_does_not_mean_always():
    assert not publish('You always prefer tea.',['I prefer tea today.'])['allowed']

def test_explicit_durable_default_survives_temporary_session_override():
    assert publish('Your default drink is tea outside this conversation.',
        facts=['Actually, I prefer coffee today, not tea.'],memory=['My default drink is tea.'])['allowed']

def test_explicit_withdrawal_does_not_preserve_old_preference():
    assert not publish('You prefer tea.',facts=['I no longer prefer tea.'],memory=['I prefer tea.'])['allowed']

def test_wrong_owner_evidence_rejected():
    r=NS(context=NS(identity=NS(operator_id='other'),active_thread=NS(thread_id='t')))
    with pytest.raises(PermissionError):
        evaluate(r,'Discuss','You prefer tea.',reasoning_input=prompt(['I prefer tea.']))

def test_assistant_cannot_establish_operator_preference():
    assert not publish('You prefer tea.',assistant=['I prefer tea.'])['allowed']

def test_current_session_overrides_retrieved_memory():
    assert not publish('You prefer tea.',facts=['Actually, I prefer coffee today, not tea.'],memory=['I prefer tea.'])['allowed']
    assert publish('You prefer coffee today.',facts=['Actually, I prefer coffee today, not tea.'],memory=['I prefer tea.'])['allowed']

def test_fluent_unsupported_claim_cannot_score_perfect():
    state=CanonicalInteractionState(interaction_id='i',session_id='t',raw_input='Plan an evening.',
        normalized_input='Plan an evening.',interpretation_stability_score=1.0,
        resolved_context_state={'session_exists':True})
    result=evaluate_conversation_quality(state,'For your evening plan, you prefer tea. Reading can help you unwind.')
    assert result.continuity_preservation_score < 1.0
    assert result.conversation_quality_score < 1.0
    assert 'unsupported_preference' in result.quality_flags

def test_supported_claim_keeps_quality():
    state=CanonicalInteractionState(interaction_id='i',session_id='t',raw_input='I prefer tea.',
        normalized_input='I prefer tea.',interpretation_stability_score=1.0,resolved_context_state={'session_exists':True})
    result=evaluate_conversation_quality(state,'You prefer tea. We can include tea in the evening plan.')
    assert result.continuity_preservation_score == 1.0
    assert 'unsupported_preference' not in result.quality_flags

def test_retained_original_output_is_rejected():
    case=json.loads(CASE.read_text(encoding='utf-8-sig'))
    assert not publish(case['response']['response_text'],case['inputs'])['allowed']

def test_sealed_sources_cannot_be_changed():
    from data_governance.context_admission import verify
    p=prompt(['I prefer tea.'])
    p.sources[0]['content']='I prefer coffee.'
    with pytest.raises(PermissionError):verify(p)

def test_excluded_memory_cannot_ground_claim():
    a=Admission('op','t')
    a.consider('MEMORY','unapproved','I prefer tea.',source='memory')
    r=NS(context=NS(identity=NS(operator_id='op'),active_thread=NS(thread_id='t')))
    assert not evaluate(r,'Plan an evening','You prefer tea.',reasoning_input=a.finish())['allowed']

def test_critique_cannot_promote_original_default(monkeypatch):
    from agents.reasoning_agent import ReasoningAgent,ModelCallResult
    case=json.loads(CASE.read_text(encoding='utf-8-sig'))
    agent=ReasoningAgent.__new__(ReasoningAgent);agent.provider='fixture';agent.model='fixture'
    seen=[]
    def call(p,**kw):
        seen.append(str(p))
        return ModelCallResult(case['calls'][len(seen)-1]['output'],NS())
    monkeypatch.setattr(agent,'_call_model',call)
    result=agent.generate('Mode','Chat',{'purpose':'Respond','schema':[],'constraints':[]},prompt(case['inputs']))
    instructions=seen[-1].split('Revise using this critique:')[1]
    assert 'critique was rejected' in instructions
    assert 'tea-based plan remains your default' not in instructions
    # Raw provider evidence is retained even if a provider ignores the instruction.
    assert result.final_response==case['response']['response_text']
    assert result.critique==case['calls'][1]['output']

@pytest.mark.parametrize('response,allowed',[
    ('You prefer tea.',False),
    ('You prefer coffee today.',True),
    ('You may prefer tea, but that is only a hypothesis.',True),
    ('Reading and quiet music still fit the evening plan.',True),
])
def test_real_controller_and_shared_publication(monkeypatch,tmp_path,response,allowed):
    from core.mode_controller import process_interaction
    from agents.reasoning_agent import ReasoningResult
    from data_governance.response_gate import governed_interaction
    from models.runtime_models import OperatorInput
    from learning.contracts import now
    monkeypatch.setattr('runtime_logging.trace_logger.TRACE_OUTPUT_PATH',tmp_path/'trace.jsonl')
    monkeypatch.setattr('runtime_logging.response_logger.RESPONSE_OUTPUT_PATH',tmp_path/'response.jsonl')
    monkeypatch.setattr('context.context_resolver.RUNTIME_STATE_ROOT',tmp_path/'sessions')
    monkeypatch.setattr('core.mode_controller._generate_reasoning_result',lambda *a,**k:
        ReasoningResult('replay','fixture','fixture','','',response,0.0))
    p=prompt(['I prefer tea today.','Actually, I prefer coffee today, not tea.'])
    r=NS(context=NS(identity=NS(operator_id='op'),active_thread=NS(thread_id='t')))
    result=governed_interaction(r,OperatorInput('How does that change the evening plan?','t',now(),'interactive_mode_bot'),p,process_interaction)
    assert r.context.response_governance['allowed'] is allowed
    if not allowed:
        assert 'UNSUPPORTED_PREFERENCE' in result.response_text
        assert result.conversation_quality_state.continuity_preservation_score==0.0
    else:assert result.response_text==response
