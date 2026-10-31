from __future__ import annotations

from .command_store import CommandStore
from .config import BridgeConfig
from .database import BridgeDatabase
from .event_store import EventStore
from .message_store import MessageStore
from .models import SupervisorTaskState
from .response_service import ResponseService
from .state_service import StateService
from .supervisor_service import SupervisorService
from .task_store import TaskStore


class SupervisorBridgeService:
    def __init__(self, config: BridgeConfig | None = None) -> None:
        self.config = config or BridgeConfig()
        self.db = BridgeDatabase(self.config.db_path)
        self.db.initialize()
        self.tasks = TaskStore(self.db)
        self.events = EventStore(self.db)
        self.messages = MessageStore(self.db)
        self.commands = CommandStore(self.db)
        self.state = StateService(self.tasks)
        self.supervisor = SupervisorService(self.tasks, self.commands, self.events)
        self.responses = ResponseService(self.messages, self.events)

    def create_task(self, task_id: str, session_id: str | None = None) -> SupervisorTaskState:
        state = SupervisorTaskState(task_id=task_id, session_id=session_id)
        self.tasks.upsert(state)
        self.events.append(task_id, "MODE_TASK_STARTED", actor="BRIDGE")
        return state

    def send_message(self, task_id: str, message: str, message_type: str = "MESSAGE"):
        item = self.messages.create_message(task_id, message, message_type=message_type)
        self.events.append(task_id, "SUPERVISOR_MESSAGE_SENT", actor="SUPERVISOR", message=message)
        return item
