from types import SimpleNamespace

import pytest

from persistent_memory.persistent_memory_manager import PersistentMemoryManager
from persistent_memory.persistent_memory_store import PersistentMemoryStore
from persistent_memory.persistent_memory_record import PersistentMemoryStorageScope as Scope
from runtime_state.pending_action import create_memory_save_pending_action
from runtime_state.pending_action_router import PendingActionRouter


FACT = "My preferred report format is CSV."


def propose(manager, scope=Scope.PERSISTENT):
    return manager.propose_create_memory(
        operator_id="operator", content=FACT, source_thread_id="thread",
        source_message_id="message", original_operator_statement=FACT,
        storage_scope=scope,
    )


@pytest.mark.parametrize("reply,status,saved", [
    ("yes", "SUCCESS", True), ("no", "REJECTED", False),
    ("do not save to persistent memory", "REJECTED", False),
    ("don't remember", "REJECTED", False),
    ("yes, do not save", "REJECTED", False),
    ("session-only", "SESSION_ONLY", False),
    ("maybe", "AMBIGUOUS", False),
    ("persistent or session", "AMBIGUOUS", False),
])
def test_manager_consent_and_receipt(tmp_path, reply, status, saved):
    manager = PersistentMemoryManager(PersistentMemoryStore(tmp_path))
    candidate = propose(manager).candidate
    result = manager.confirm_candidate(candidate, reply)
    assert result.receipt.status == status
    assert result.receipt.new_content == FACT
    assert result.receipt.consent_status == candidate.consent_status
    assert result.receipt.storage_scope == candidate.storage_scope
    assert result.requires_confirmation == (status == "AMBIGUOUS")
    records = manager.store.load_records_for_operator("operator")
    assert len(records) == int(saved)
    if saved:
        assert records[0].content == FACT
        assert records[0].evidence.original_operator_statement == FACT
        assert records[0].content != "Operator created this runtime."


def test_session_scope_never_promoted(tmp_path):
    manager = PersistentMemoryManager(PersistentMemoryStore(tmp_path))
    result = propose(manager, Scope.SESSION_ONLY)
    assert result.session_only_payload["content"] == FACT
    result = manager.confirm_candidate(result.candidate, "persistent")
    assert result.receipt.storage_scope == Scope.SESSION_ONLY
    assert not list(tmp_path.rglob("*.json"))


def test_invalid_scope_rejected(tmp_path):
    manager = PersistentMemoryManager(PersistentMemoryStore(tmp_path))
    with pytest.raises(ValueError, match="storage_scope"):
        propose(manager, "SESSION_ONLY")


@pytest.mark.parametrize("reply", ["no", "do not save to persistent memory", "don't remember"])
def test_router_refusal_precedes_scope(reply):
    result = PendingActionRouter().handle(create_memory_save_pending_action(FACT), reply)
    assert result["authorization_state"] == "REJECTED"
    assert result["operator_confirmation"] == reply
    assert result["memory_text"] == FACT


@pytest.mark.parametrize("reply,saved", [("yes", True), ("no", False),
    ("do not save to persistent memory", False), ("session-only", False), ("maybe", False)])
def test_interactive_save_path_preserves_input(monkeypatch, tmp_path, capsys, reply, saved):
    from interactive_mode_ai import ModeRuntime

    runtime = ModeRuntime.__new__(ModeRuntime)
    import threading
    runtime._interaction_lock = threading.RLock()
    from memory.thread_store import ThreadStore
    runtime.thread_store = ThreadStore(str(tmp_path / 'threads'))
    runtime.context = SimpleNamespace(
        profile=SimpleNamespace(operator_id="operator", operator_managed=SimpleNamespace(
            preferred_name="Operator", name="Operator")),
        active_thread=runtime.thread_store.create_thread("operator"),
    )
    runtime.pending_action = None
    runtime.pending_action_router = PendingActionRouter()
    runtime.persistent_memory_manager = PersistentMemoryManager(PersistentMemoryStore(tmp_path))
    statement = "Save to persistent memory: " + FACT
    replies = iter([statement, reply, "quit"])
    def operator_input(_):
        response = next(replies)
        if response == reply:
            assert not runtime.persistent_memory_manager.store.load_records_for_operator("operator")
            assert runtime.pending_action.payload["memory_text"] == statement
        return response
    monkeypatch.setattr("builtins.input", operator_input)
    runtime.run()
    records = runtime.persistent_memory_manager.store.load_records_for_operator("operator")
    assert len(records) == int(saved)
    if saved:
        assert records[0].content == statement
        assert records[0].evidence.original_operator_statement == statement
    if reply == "maybe":
        assert runtime.pending_action is not None
    printed = capsys.readouterr().out
    assert statement in printed
    assert "Operator created this runtime." not in printed
