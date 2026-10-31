from __future__ import annotations

from .event_store import EventStore
from .message_store import MessageStore


class ResponseService:
    def __init__(self, messages: MessageStore, events: EventStore) -> None:
        self.messages = messages
        self.events = events

    def record(self, task_id: str, message: str, current_state: str, response_type: str = "ANSWER"):
        response = self.messages.record_response(
            task_id=task_id, message=message, current_state=current_state,
            response_type=response_type,
        )
        self.events.append(
            task_id, "MODE_RESPONSE_RECEIVED", actor="MODE",
            status=current_state, message=message,
        )
        return response
