from dataclasses import asdict, dataclass, field
from typing import Any, Dict, List, Optional


@dataclass
class AssembledOperatorContext:
    operator_id: str
    name: str
    preferred_name: str
    language: str
    active_thread_id: Optional[str]
    continuity_summary: str
    onboarding_complete: bool


@dataclass
class AssembledTemporalContext:
    timezone: str
    current_datetime: str
    current_date: str
    current_time: str
    day_of_week: str
    utc_datetime: str
    utc_offset: str
    year: int
    month: int
    day: int
    hour: int
    minute: int
    second: int
    day_of_year: int
    week_of_year: int
    quarter: int
    is_weekend: bool


@dataclass
class AssembledThreadMessage:
    role: str
    content: str
    metadata: Dict[str, Any] = field(default_factory=dict)
    message_id: Optional[str] = None
    created_at: Optional[str] = None


@dataclass
class AssembledThreadContext:
    thread_id: str
    title: str
    message_count: int
    recent_messages: List[AssembledThreadMessage]
    thread_summary: str = ""


@dataclass
class AssembledRuntimeContext:
    runtime_state: str
    context_ready: bool

    # Diagnostic only. Missing optional sources do not block execution.
    missing_sources: List[str] = field(default_factory=list)

    # Authoritative execution gate. Context is not ready while any required
    # evidence or capability requirement remains unresolved.
    unsatisfied_requirements: List[str] = field(default_factory=list)

    # Maps each requirement to the source or authority that satisfied it.
    requirement_resolution: Dict[str, str] = field(default_factory=dict)

    # Records the source order used for this execution.
    source_priority: List[str] = field(default_factory=list)

    # Non-blocking conditions that should remain visible to the runtime.
    warnings: List[str] = field(default_factory=list)


@dataclass
class AssembledContext:
    operator: AssembledOperatorContext | None
    temporal: AssembledTemporalContext | None
    thread: AssembledThreadContext | None
    runtime: AssembledRuntimeContext

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

    def to_prompt_context(self) -> str:
        sections: list[str] = [
            "ASSEMBLED RUNTIME CONTEXT\n-------------------------"
        ]

        if self.operator is not None:
            sections.append(
                "OPERATOR\n"
                f"Operator ID: {self.operator.operator_id}\n"
                f"Name: {self.operator.name}\n"
                f"Preferred Name: {self.operator.preferred_name}\n"
                f"Language: {self.operator.language}\n"
                f"Active Thread ID: {self.operator.active_thread_id}\n"
                f"Onboarding Complete: {self.operator.onboarding_complete}\n"
                f"Continuity Summary: {self.operator.continuity_summary}"
            )

        if self.temporal is not None:
            sections.append(
                "TEMPORAL\n"
                f"Timezone: {self.temporal.timezone}\n"
                f"Current Datetime: {self.temporal.current_datetime}\n"
                f"Current Date: {self.temporal.current_date}\n"
                f"Current Time: {self.temporal.current_time}\n"
                f"Day Of Week: {self.temporal.day_of_week}\n"
                f"UTC Datetime: {self.temporal.utc_datetime}\n"
                f"UTC Offset: {self.temporal.utc_offset}\n"
                f"Year: {self.temporal.year}\n"
                f"Month: {self.temporal.month}\n"
                f"Day: {self.temporal.day}\n"
                f"Hour: {self.temporal.hour}\n"
                f"Minute: {self.temporal.minute}\n"
                f"Second: {self.temporal.second}\n"
                f"Day Of Year: {self.temporal.day_of_year}\n"
                f"Week Of Year: {self.temporal.week_of_year}\n"
                f"Quarter: {self.temporal.quarter}\n"
                f"Weekend: {self.temporal.is_weekend}"
            )

        if self.thread is not None:
            recent_thread = "\n".join(
                f"{message.role.upper()} [message_id={message.message_id or 'UNAVAILABLE'}; created_at={message.created_at or 'UNAVAILABLE'}]: {message.content}"
                for message in self.thread.recent_messages
            )

            sections.append(
                "THREAD\n"
                f"Thread ID: {self.thread.thread_id}\n"
                f"Thread Title: {self.thread.title}\n"
                f"Message Count: {self.thread.message_count}\n"
                f"Included Messages: {len(self.thread.recent_messages)}\n"
                f"Omitted Messages: {self.thread.message_count-len(self.thread.recent_messages)}\n"
                f"Thread Summary: {self.thread.thread_summary}\n"
                "Recent Messages:\n"
                f"{recent_thread}"
            )

        sections.append(
            "RUNTIME\n"
            f"Runtime State: {self.runtime.runtime_state}\n"
            f"Context Ready: {self.runtime.context_ready}\n"
            f"Unsatisfied Requirements: "
            f"{self.runtime.unsatisfied_requirements}\n"
            f"Requirement Resolution: "
            f"{self.runtime.requirement_resolution}\n"
            f"Source Priority: {self.runtime.source_priority}\n"
            f"Missing Sources (Diagnostic): "
            f"{self.runtime.missing_sources}\n"
            f"Warnings: {self.runtime.warnings}"
        )

        return "\n\n".join(sections)
