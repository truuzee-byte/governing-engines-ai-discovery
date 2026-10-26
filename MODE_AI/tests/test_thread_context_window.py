from context_assembly.context_assembler import ContextAssembler
from context_assembly.assembled_context import AssembledContext,AssembledRuntimeContext
from memory.thread_memory import ThreadMemory
import pytest


def test_zero_thread_window_excludes_all_messages_and_reports_omission():
    thread=ThreadMemory.create('op');thread.add_message('operator','Retained only in source')
    selected=ContextAssembler()._assemble_thread(thread,0)
    assert selected.message_count==1 and selected.recent_messages==[]
    prompt=AssembledContext(None,None,selected,AssembledRuntimeContext('IDLE',True)).to_prompt_context()
    assert 'Omitted Messages: 1' in prompt and 'Retained only in source' not in prompt


def test_bounded_thread_window_preserves_selected_message_identity():
    thread=ThreadMemory.create('op');thread.add_message('operator','Older context')
    last=thread.add_message('operator','Recent context')
    selected=ContextAssembler()._assemble_thread(thread,1)
    assert selected.recent_messages[0].message_id==last.message_id
    assert selected.recent_messages[0].created_at==last.created_at
    prompt=AssembledContext(None,None,selected,AssembledRuntimeContext('IDLE',True)).to_prompt_context()
    assert last.message_id in prompt and last.created_at in prompt and 'Older context' not in prompt
    assert 'Included Messages: 1' in prompt and 'Omitted Messages: 1' in prompt


@pytest.mark.parametrize('limit',[-1,True,1.5])
def test_invalid_thread_window_rejected(limit):
    with pytest.raises(ValueError):ContextAssembler()._assemble_thread(ThreadMemory.create('op'),limit)


def test_thread_admission_uses_stored_identity_and_actual_operator_role():
    from types import SimpleNamespace as NS
    from context_orchestration.context_source import ContextSource
    thread=ThreadMemory.create('op');message=thread.add_message('operator','Exact authored words')
    profile=NS(operator_id='op',operator_managed=NS())
    plan=NS(included_sources=lambda:[ContextSource.THREAD_MEMORY],missing_sources=lambda:[],
        context_ready=lambda:True,source_selections=[])
    context=ContextAssembler().assemble(profile,thread,None,'LISTENING',plan)
    decisions=context.to_prompt_context().decisions
    source=next(item for item in decisions if item['artifact_id']==message.message_id)
    assert source['authority']=='OPERATOR' and source['decision']=='ADMITTED'
    assert source['scope']=={'operator_id':'op','thread_id':thread.thread_id}
