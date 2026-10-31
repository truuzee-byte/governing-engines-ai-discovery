from __future__ import annotations

import threading
import time

from supervisor_bridge.mode_adapter import ModeAdapter
from supervisor_bridge.service import SupervisorBridgeService


def attach_bridge(
    runtime,
    task_id: str,
    bridge: SupervisorBridgeService | None = None,
):
    """
    Create/attach a bridge task to an already-booted ModeRuntime.

    The bridge uses the existing ModeRuntime instance.
    It does not create a second MODE reasoning runtime.
    """
    service = bridge or SupervisorBridgeService()
    adapter = ModeAdapter(service)

    adapter.ensure_task(runtime, task_id)

    return service, adapter


def process_supervisor_messages(
    runtime,
    task_id: str,
    adapter: ModeAdapter,
):
    """
    Process currently pending supervisor messages through MODE's
    existing governed interaction path.
    """
    lock=getattr(runtime,'_interaction_lock',None)
    if lock is None:
        return adapter.process_pending_messages(runtime, task_id)
    # Never wait while shutdown/thread selection joins the listener. A busy
    # foreground interaction retains its context; unclaimed messages stay pending.
    if not lock.acquire(blocking=False):
        return []
    try:
        if getattr(runtime,'pending_action',None) is not None or any(
                getattr(runtime,name,None) is not None for name in
                ('_knowledge_context_selection','_knowledge_record_context_selection','_vault_context_selection','_system_context_selection')):
            return []
        return adapter.process_pending_messages(runtime, task_id)
    finally:
        lock.release()


def start_supervisor_worker(
    runtime,
    task_id: str,
    adapter: ModeAdapter,
    *,
    poll_interval: float = 0.5,
):
    """
    Start a background worker that continuously checks the
    Supervisor Bridge for pending messages.

    The worker routes messages through the existing ModeRuntime.
    """

    stop_event = threading.Event()

    def worker():
        while not stop_event.is_set():
            try:
                process_supervisor_messages(
                    runtime,
                    task_id,
                    adapter,
                )
            except Exception as exc:
                print(f"[SUPERVISOR BRIDGE ERROR] {exc}")

            stop_event.wait(poll_interval)

    thread = threading.Thread(
        target=worker,
        name=f"mode-supervisor-{task_id}",
        daemon=True,
    )

    thread.start()

    return stop_event, thread
