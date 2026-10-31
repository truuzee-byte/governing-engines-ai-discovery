from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from typing import Any
from uuid import uuid4

from context_orchestration.context_source import (
    ContextSource,
    ContextSourceAvailability,
    ContextSourceDecision,
    ContextSourceRequirement,
)


@dataclass
class ContextSourceSelection:
    source: ContextSource
    decision: ContextSourceDecision
    requirement: ContextSourceRequirement
    availability: ContextSourceAvailability
    reason: str
    knowledge_domain_dependency: str | None = None
    confidence: float = 1.0
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        data = asdict(self)
        data["source"] = self.source.value
        data["decision"] = self.decision.value
        data["requirement"] = self.requirement.value
        data["availability"] = self.availability.value
        return data


@dataclass
class ContextOrchestrationPlan:
    plan_id: str
    operator_id: str
    thread_id: str
    input_text: str
    knowledge_domain: str
    source_selections: list[ContextSourceSelection]
    created_at: str

    def included_sources(self) -> list[ContextSource]:
        return [
            item.source
            for item in self.source_selections
            if item.decision in (
                ContextSourceDecision.INCLUDED,
                ContextSourceDecision.REQUIRED,
            )
            and item.availability == ContextSourceAvailability.AVAILABLE
        ]

    def excluded_sources(self) -> list[ContextSource]:
        return [
            item.source
            for item in self.source_selections
            if item.decision == ContextSourceDecision.EXCLUDED
        ]

    def required_sources(self) -> list[ContextSource]:
        return [
            item.source
            for item in self.source_selections
            if item.requirement == ContextSourceRequirement.REQUIRED
        ]

    def missing_sources(self) -> list[ContextSource]:
        return [
            item.source
            for item in self.source_selections
            if (
                item.requirement == ContextSourceRequirement.REQUIRED
                and item.availability == ContextSourceAvailability.MISSING
            )
        ]

    def context_ready(self) -> bool:
        return len(self.missing_sources()) == 0

    def to_dict(self) -> dict[str, Any]:
        return {
            "plan_id": self.plan_id,
            "operator_id": self.operator_id,
            "thread_id": self.thread_id,
            "input_text": self.input_text,
            "knowledge_domain": self.knowledge_domain,
            "included_sources": [source.value for source in self.included_sources()],
            "excluded_sources": [source.value for source in self.excluded_sources()],
            "required_sources": [source.value for source in self.required_sources()],
            "missing_sources": [source.value for source in self.missing_sources()],
            "context_ready": self.context_ready(),
            "source_selections": [
                selection.to_dict() for selection in self.source_selections
            ],
            "created_at": self.created_at,
        }


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def generate_orchestration_plan_id() -> str:
    return f"cop-{uuid4().hex}"