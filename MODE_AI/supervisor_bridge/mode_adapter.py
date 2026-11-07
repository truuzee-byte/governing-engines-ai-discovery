from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from .models import SupervisorTaskState


class ModeAdapter:
    """Thin adapter around the existing ModeRuntime object.

    This adapter intentionally calls ModeRuntime's existing governed input path.
    It does not create a second reasoning engine.
    """

    def __init__(self, bridge_service: Any) -> None:
        self.bridge = bridge_service

    def ensure_task(self, runtime: Any, task_id: str) -> SupervisorTaskState:
        try:
            return self.bridge.tasks.get(task_id)
        except Exception:
            session_id = None
            if getattr(runtime, "context", None) is not None:
                session_id = runtime.context.active_thread.thread_id
            state = SupervisorTaskState(task_id=task_id, session_id=session_id)
            self.bridge.tasks.upsert(state)
            self.bridge.events.append(task_id, "MODE_TASK_STARTED", actor="MODE")
            return state

    def process_pending_messages(self, runtime: Any, task_id: str) -> list[Any]:
        self.ensure_task(runtime, task_id)
        responses = []
        for _ in range(10):
            if getattr(runtime, "_supervisor_stop_event", None) is not None and runtime._supervisor_stop_event.is_set():
                break
            control = self.bridge.state.get_execution_control(task_id)
            if control in {"PAUSED", "HALTED"}:
                self._observe(runtime, "supervisor_control", {"task_id": task_id, "control": control, "execution_started": False})
                break
            msg = self.bridge.db.claim_message(task_id)
            if msg is None:
                break
            self._observe(runtime, "supervisor_claim", {"task_id": task_id, "message_id": msg["message_id"], "claimed": True})
            try:
                if self.bridge.state.get_execution_control(task_id) != "ACTIVE":
                    raise RuntimeError("Execution control changed after claim; review before recovery")
                result = self._process_one(runtime, task_id, msg["message"])
                failure = None if getattr(result, "success", False) else "Processing returned an unsuccessful result"
            except Exception as exc:
                self.bridge.db.finish_message(msg["message_id"], msg["owner_token"],
                                              failure=f"{type(exc).__name__}: {exc}")
                self._observe(runtime, "supervisor_failure", {"task_id": task_id, "message_id": msg["message_id"], "state": "FAILED"}, str(exc))
                break
            self.bridge.db.finish_message(msg["message_id"], msg["owner_token"], failure=failure)
            self._observe(runtime, "supervisor_result", {"task_id": task_id, "message_id": msg["message_id"],
                "trace_reference": getattr(result, "trace_reference", None), "failure": failure,
                "context_admission":getattr(runtime.context,'context_admission',None),
                "response_governance":getattr(runtime.context,'response_governance',None),
                "reasoning_context_admission":getattr(result,'context_admission',[])}, failure)
            responses.append(result)
        return responses

    @staticmethod
    def _observe(runtime, name, payload, error=None):
        observer = getattr(runtime, "_observe_runtime_event", None)
        if observer is not None:
            try:
                observer(name, payload, runtime_error=error)
            except Exception as exc:
                import logging
                logging.getLogger(__name__).warning("Supervisor observation failed: %s", exc)

    def _process_one(self, runtime: Any, task_id: str, message: str):
        # Imports are local so the bridge package can be imported independently.
        from core.mode_controller import process_interaction
        from models.runtime_models import OperatorInput

        if runtime.context is None:
            runtime.boot()

        thread = runtime.context.active_thread
        thread.add_message(
            role="system",
            content=f"SUPERVISOR MESSAGE:\n{message}",
            metadata={"input_source": "supervisor_bridge", "task_id": task_id},
        )
        runtime.thread_store.save_thread(thread)

        reasoning_input = runtime._build_engine_input(
            f"SUPERVISOR MESSAGE\nTask: {task_id}\n\n{message}"
        )
        from data_governance.response_gate import governed_interaction
        result = governed_interaction(runtime,
            OperatorInput(
                raw_input=message,
                session_id=thread.thread_id,
                timestamp=datetime.now(timezone.utc).isoformat(),
                input_source="supervisor_bridge",
            ),
            reasoning_input=reasoning_input,
            processor=process_interaction,
        )

        manifest = result.interaction_manifest
        mode_state = "HALTED" if result.halt_required else (
            "CLARIFYING" if result.clarification_required else "COMPLETE"
        )
        # Do not write stale execution-control flags from a task snapshot.
        with self.bridge.db.connection() as conn:
            conn.execute("""UPDATE supervisor_tasks SET interaction_id=?, session_id=?,
                trace_reference=?, mode_state=?, current_stage='SUPERVISOR_RESPONSE',
                updated_at=? WHERE task_id=?""",
                (result.interaction_id, thread.thread_id, result.trace_reference,
                 mode_state, datetime.now(timezone.utc).isoformat(), task_id))
        self.bridge.events.append(
            task_id, "MODE_INTERACTION_COMPLETED", actor="MODE",
            status=mode_state,
            detail={
                "interaction_id": result.interaction_id,
                "reasoning_id": result.reasoning_id,
                "trace_reference": result.trace_reference,
                "selected_mode": getattr(manifest, "selected_mode", None),
                "selected_posture": getattr(manifest, "selected_posture", None),
                "downstream_authority_allowed": getattr(manifest, "downstream_authority_allowed", None),
                "failure_state": result.failure_state,
                "response_governance":getattr(runtime.context,'response_governance',None),
                "context_admission":getattr(runtime.context,'context_admission',None),
            },
        )
        for disclosure in getattr(runtime.context,'response_governance',{}).get('disclosures',[]):
            self.bridge.responses.record(task_id=task_id,message='GOVERNANCE NOTICE: '+disclosure,
                current_state=mode_state,response_type='GOVERNANCE_NOTICE')
        self.bridge.responses.record(
            task_id=task_id,
            message=result.response_text,
            current_state=mode_state,
            response_type="FAILURE" if not result.success else "ANSWER",
        )
        return result
