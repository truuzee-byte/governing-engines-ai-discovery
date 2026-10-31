from types import SimpleNamespace as NS
from persistent_memory.persistent_memory_manager import PersistentMemoryManager
from persistent_memory.persistent_memory_store import PersistentMemoryStore
from integration.conversational_memory import execute


def runtime(tmp_path):
    return NS(context=NS(identity=NS(operator_id='op'),active_thread=NS(thread_id='t')),
        persistent_memory_manager=PersistentMemoryManager(PersistentMemoryStore(str(tmp_path/'memory'))),
        _observe_runtime_event=lambda *a,**k:None)


def test_explicit_content_bound_consent_persists_and_retrieves_after_restart(tmp_path):
    r=runtime(tmp_path);text='Remember this for later: I prefer verified artifacts over status labels.'
    result=execute(r,text)
    assert result['persistent_saved'],result
    stored=runtime(tmp_path).persistent_memory_manager.retrieve_memories('op',query='artifacts')
    assert len(stored)==1 and stored[0].content==text.split(': ',1)[1]
    assert stored[0].evidence.original_operator_statement==text
    assert stored[0].governance_decision['lineage']['operator_confirmation']==text


def test_consent_cannot_be_rebound_to_different_content(tmp_path):
    r=runtime(tmp_path);m=r.persistent_memory_manager
    text='Remember this for later: I like pear juice.'
    candidate=m.propose_create_memory('op','I like orange juice.','t','m',text).candidate
    assert not m.confirm_candidate(candidate,text).success
    assert m.retrieve_memories('op')==[]


def test_thread_only_correction_retires_unique_match_without_other_memory_loss(tmp_path):
    r=runtime(tmp_path)
    execute(r,'Also remember that I call the project Copper Meadow.')
    execute(r,'Remember this for later: I prefer plain language.')
    result=execute(r,"Don't remember the name Copper Meadow long term. That's just for this conversation.")
    assert result['state']=='REMOVED'
    records=runtime(tmp_path).persistent_memory_manager.retrieve_memories('op')
    assert [r.content for r in records]==['I prefer plain language.']


def test_ambiguous_reference_cannot_retire_multiple_records(tmp_path):
    r=runtime(tmp_path)
    execute(r,'Also remember that Copper Meadow is a project.')
    execute(r,'Also remember that Copper Meadow has a review process.')
    assert execute(r,"Don't remember Copper Meadow long term.")['state']=='CLARIFICATION_REQUIRED'
    assert len(r.persistent_memory_manager.retrieve_memories('op'))==2


def test_refusal_and_session_scope_do_not_save(tmp_path):
    r=runtime(tmp_path)
    for text in ["Don't remember that I like juice.", 'Remember this for later: use this for this conversation only.',
                 'Can you remember that I like juice?', 'Someone said remember that I like juice.']:
        assert execute(r,text) is None
    assert r.persistent_memory_manager.retrieve_memories('op')==[]
