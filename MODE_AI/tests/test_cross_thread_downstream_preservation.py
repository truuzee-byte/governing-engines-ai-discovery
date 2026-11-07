"""Offline engineering falsifiers, not cross-thread behavioral qualification."""
import json
from pathlib import Path
from types import SimpleNamespace as NS
import pytest
from data_governance.context_admission import Admission, verify
from persistent_memory.persistent_memory_manager import PersistentMemoryManager
from persistent_memory.persistent_memory_store import PersistentMemoryStore
from memory.thread_store import ThreadStore
from context_assembly.context_assembler import ContextAssembler
from conversation_quality.admitted_context_preservation import metadata_context, assess_preservation
from agents.reasoning_agent import ReasoningAgent, ModelCallResult

@pytest.fixture
def context(tmp_path):
    ts=ThreadStore(str(tmp_path/'threads'));a=ts.create_thread('op','Origin');b=ts.create_thread('op','Receiver')
    manager=PersistentMemoryManager(PersistentMemoryStore(tmp_path/'memory'))
    def write(content):
        msg=a.add_message('user',content);ts.save_thread(a)
        proposal=manager.propose_create_memory('op',content,a.thread_id,msg.message_id,content)
        result=manager.confirm_candidate(proposal.candidate,'yes')
        assert result.success
        return result.record
    old=write('The Neral dispatch code is OLD-418.')
    msg=a.add_message('user','Update the Neral dispatch code to VALID-726.');ts.save_thread(a)
    proposal=manager.propose_update_memory('op',old.memory_id,'The Neral dispatch code is VALID-726.',a.thread_id,msg.message_id,msg.content)
    current=manager.confirm_candidate(proposal.candidate,'yes').record
    unrelated=write('Orchid planter label is FLOWER-284.')
    inactive=write('Neral dispatch obsolete note is INVALID-955.')
    manager.lifecycle('op',inactive.memory_id,'ARCHIVE','yes')
    del manager
    manager=PersistentMemoryManager(PersistentMemoryStore(tmp_path/'memory'))
    retrieved=manager.retrieve_memories('op',query='Which Neral dispatch code?')
    # Existing assembly owner; minimal no-profile plan avoids unrelated context.
    from context_orchestration.orchestration_plan import ContextOrchestrationPlan
    plan=ContextOrchestrationPlan('plan','op',b.thread_id,'Which Neral dispatch code?','PUBLIC',[],b.updated_at)
    assembled=ContextAssembler().assemble(NS(operator_id='op',continuity_summary=''),b,None,'LISTENING',plan,persistent_memories=retrieved)
    admitted=Admission('op',b.thread_id);admitted.consider('OPERATOR_INPUT','query','Which Neral dispatch code?',source='operator')
    admitted.include(assembled.to_prompt_context())
    return NS(prompt=admitted.finish(),current=current,origin=a,receiver=b,unrelated=unrelated,inactive=inactive,manager=manager)

def run(prompt,outputs):
    agent=ReasoningAgent.__new__(ReasoningAgent);agent.provider='offline-fixture';agent.model='offline-fixture'
    calls=[]
    def call(value,**kwargs):
        verify(value);calls.append((value,kwargs));return ModelCallResult(outputs[len(calls)-1],NS())
    agent._call_model=call
    result=agent.generate('Mode','Reasoning',{'purpose':'Answer using admitted facts','schema':[],'constraints':[]},prompt)
    return result,calls

def test_all_stages_receive_compact_source_metadata(context):
    result,calls=run(context.prompt,['VALID-726','The reasoning is supported.','VALID-726'])
    for prompt,_ in calls:
        assert context.current.memory_id in prompt
        assert context.current.source_thread_id in prompt
        assert context.current.source_message_id in prompt
        assert context.current.governance_decision['decision_id'] in prompt
        assert '"record_version":2' in prompt and 'CURRENT_RETRIEVED_VERSION' in prompt
        assert '"admissibility":"ADMITTED"' in prompt and '"downstream_use_eligible":true' in prompt
        assert 'OPERATOR_ATTESTED' in prompt and '"approval":"APPROVED"' in prompt
        assert 'original_operator_statement' not in prompt
    assert result.final_response=='VALID-726'

def test_controls_not_rendered_or_retrieved(context):
    result,calls=run(context.prompt,['VALID-726','Reasoning is supported.','VALID-726'])
    for prompt,_ in calls:
        assert all(code not in prompt for code in ['OLD-418','FLOWER-284','INVALID-955'])
        assert context.unrelated.memory_id not in prompt and context.inactive.memory_id not in prompt

@pytest.mark.parametrize('critique',[
    'The persistent memory is not confirmed as eligible evidence; return unknown.',
    'The source is unverified and cannot be used.',
    'There is no eligible memory; code should be null.',
    'The record is superseded; return unknown.',
    'The memory is invalid; do not use the code.',
])
def test_unsupported_critique_not_promoted(context,critique):
    result,calls=run(context.prompt,['VALID-726',critique,'VALID-726'])
    assert result.context_admission[1]['promoted_to_revision'] is False
    assert 'critique was rejected' in calls[2][0]
    assert critique not in str(calls[2][0])
    assert result.final_response=='VALID-726'

def test_reasoning_challenge_still_allowed(context):
    result,calls=run(context.prompt,['VALID-726','Explain why the current code matches the query, and do not claim execution.','VALID-726'])
    assert result.context_admission[1]['promoted_to_revision']

def test_contradictory_evidence_routes_to_owner_review_without_revocation(context):
    a=Admission('op',context.receiver.thread_id);a.include(context.prompt)
    a.consider('OPERATOR_INPUT','new-measurement','A new measurement conflicts with the dispatch note; please investigate.',source='operator')
    critique='New-measurement evidence contradicts the stored claim; flag new-measurement for authorized revalidation, not a state revocation.'
    result,calls=run(a.finish(),['VALID-726',critique,'The recorded code is VALID-726; the conflicting measurement requires authorized review.'])
    assert result.context_validation_requests
    review=result.context_validation_requests[0]
    assert review['status']=='PENDING_AUTHORIZED_REVALIDATION'
    assert review['admissibility_changed'] is False
    assert 'new-measurement' in review['cited_admitted_evidence_ids']
    assert context.manager.store.load_record('op',context.current.memory_id).content.endswith('VALID-726.')

def test_finalizer_rejects_unsupported_override_preserves_raw_output(context):
    bad='The persistent memory is not confirmed as admitted; code is null.'
    result,calls=run(context.prompt,['VALID-726','The draft is correct.',bad])
    assert result.final_response=='VALID-726' and result.raw_final_response==bad
    assert result.context_admission[-1]['selection']=='DRAFT_RETAINED_AFTER_UNSUPPORTED_FINAL_OVERRIDE'
    assert 'Draft (unvalidated' in calls[2][0]

def test_no_safe_draft_does_not_force_a_value(context):
    bad='No eligible memory is available.'
    result,calls=run(context.prompt,[bad,bad,bad])
    assert result.context_admission[-1]['selection']=='REVIEW_REQUIRED_NO_SAFE_PROPOSAL'
    assert 'No admission state was changed' in result.final_response

def test_replay_exact_failed_provider_outputs_is_engineering_only(context):
    root=Path(__file__).resolve().parents[1]/'artifacts/cross_thread_memory_qualification_20261012'
    outputs=[json.loads((root/f'later_call_{n}_response.json').read_text())['output_text'] for n in [4,5,6]]
    result,calls=run(context.prompt,outputs)
    # The historical draft does not cite/quote an admitted source, and its
    # NERAL-prefixed value is not this fixture's exact VALID-726 claim. Do not
    # retain it as a safe fallback under the stricter source-grounding contract.
    assert result.context_admission[-1]['selection']=='REVIEW_REQUIRED_NO_SAFE_PROPOSAL'
    assert result.draft==outputs[0]
    assert result.raw_final_response==outputs[2]
    assert not result.context_admission[1]['promoted_to_revision']

def test_tampered_metadata_fails_closed(context):
    context.prompt.sources[0]['record']['authority']='VALIDATION_OWNER'
    with pytest.raises(PermissionError):metadata_context(context.prompt)

def test_expired_admitted_source_requires_reassembly():
    from unittest.mock import patch
    from datetime import datetime, timezone
    a=Admission('op','t')
    a.consider('MEMORY','m','Value',source='PersistentMemoryStore',basis={
        'verified':True,'governance_state':'APPROVED','classification':'PERSISTENT_DATA',
        'validation_state':'OPERATOR_ATTESTED','authority':'OPERATOR','lineage':['approval'],
        'freshness':'2099-01-01T00:00:00+00:00'})
    with patch('conversation_quality.admitted_context_preservation.datetime') as clock:
        clock.fromisoformat.side_effect=datetime.fromisoformat
        clock.now.return_value=datetime(2100,1,1,tzinfo=timezone.utc)
        with pytest.raises(PermissionError,match='expired'):metadata_context(a.finish())
