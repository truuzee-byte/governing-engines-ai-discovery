from concurrent.futures import ThreadPoolExecutor
from threading import Barrier, Event, Lock
from types import SimpleNamespace as NS

import pytest

from supervisor_bridge.config import BridgeConfig
from supervisor_bridge.service import SupervisorBridgeService
from supervisor_bridge.mode_adapter import ModeAdapter


def bridge(tmp_path):
    service = SupervisorBridgeService(BridgeConfig(db_path=str(tmp_path / "bridge.db")))
    service.create_task("task")
    return service


def state(service, message_id):
    with service.db.connection() as conn:
        return conn.execute("SELECT delivery_state FROM supervisor_messages WHERE message_id=?",
                            (message_id,)).fetchone()[0]


def test_two_workers_have_one_owner(tmp_path):
    first = bridge(tmp_path)
    second = SupervisorBridgeService(first.config)
    msg = first.send_message("task", "work")
    barrier = Barrier(2)
    calls = []
    def worker(service):
        adapter = ModeAdapter(service)
        adapter._process_one = lambda *args: calls.append(args[-1]) or NS(success=True)
        barrier.wait(timeout=5)
        adapter.process_pending_messages(NS(context=None), "task")
    with ThreadPoolExecutor(max_workers=2) as pool:
        list(pool.map(worker, [first, second]))
    assert calls == ["work"]
    assert state(first, msg.message_id) == "DELIVERED"


def test_claim_invisible_and_only_owner_can_finish(tmp_path):
    service = bridge(tmp_path)
    msg = service.send_message("task", "work")
    claim = service.db.claim_message("task")
    other = SupervisorBridgeService(service.config)
    assert other.db.claim_message("task") is None
    assert other.messages.pending("task") == []
    with pytest.raises(ValueError):
        other.db.finish_message(msg.message_id, "wrong owner")
    service.db.finish_message(msg.message_id, claim["owner_token"])
    assert other.db.claim_message("task") is None


@pytest.mark.parametrize("command", ["PAUSE", "HALT"])
def test_execution_control_blocks_claim_and_processing(tmp_path, command):
    service = bridge(tmp_path)
    msg = service.send_message("task", "work")
    service.supervisor.apply("task", command, "test")
    adapter = ModeAdapter(service)
    adapter._process_one = lambda *args: pytest.fail("must not execute")
    assert adapter.process_pending_messages(NS(context=None), "task") == []
    assert service.db.claim_message("task") is None
    assert state(service, msg.message_id) == "PENDING"


def test_failure_is_durable_and_not_retried(tmp_path):
    service = bridge(tmp_path)
    msg = service.send_message("task", "work")
    adapter = ModeAdapter(service)
    calls = []
    def fail(*args):
        calls.append("started")
        raise RuntimeError("partial side effects; review required")
    adapter._process_one = fail
    for _ in range(2):
        adapter.process_pending_messages(NS(context=None), "task")
    assert calls == ["started"]
    assert state(service, msg.message_id) == "FAILED"
    with service.db.connection() as conn:
        rows = conn.execute("SELECT failure_detail FROM supervisor_message_claims").fetchall()
    assert len(rows) == 1
    assert "partial side effects" in rows[0][0]


def test_runtime_starts_one_listener_and_shutdown_joins_it():
    from interactive_mode_ai import ModeRuntime
    runtime = ModeRuntime.__new__(ModeRuntime)
    runtime._supervisor_stop_event = Event()
    runtime._supervisor_thread = None
    runtime._supervisor_lifecycle_lock = Lock()
    runtime.supervisor_bridge = None
    runtime.supervisor_adapter = None
    runtime._start_supervisor_listener()
    worker = runtime._supervisor_thread
    runtime._start_supervisor_listener()
    assert runtime._supervisor_thread is worker
    runtime._stop_supervisor_listener()
    assert not worker.is_alive()
    assert runtime._supervisor_thread is None


def test_continue_cannot_clear_halt(tmp_path):
    service = bridge(tmp_path)
    service.supervisor.apply("task", "HALT", "test")
    service.supervisor.apply("task", "CONTINUE", "test")
    assert service.state.get_execution_control("task") == "HALTED"
    assert service.tasks.get("task").status == "HALTED"


def test_unsuccessful_result_is_failed_not_delivered(tmp_path):
    service = bridge(tmp_path)
    msg = service.send_message("task", "work")
    adapter = ModeAdapter(service)
    adapter._process_one = lambda *args: NS(success=False)
    adapter.process_pending_messages(NS(context=None), "task")
    assert state(service, msg.message_id) == "FAILED"
    assert service.db.claim_message("task") is None
