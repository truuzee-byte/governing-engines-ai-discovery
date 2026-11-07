"""
Context Orchestration Package

Purpose
-------
Context Orchestration determines which governed context sources should
participate before Context Assembly occurs.

Context Orchestration selects sources.
Context Assembly builds the final runtime context.

Hard Line
---------
Context Assembly shall not decide what context matters.

Context Orchestrator decides what participates.
"""

from context_orchestration.context_source import (
    ContextSource,
)

from context_orchestration.orchestration_plan import (
    ContextOrchestrationPlan,
    generate_orchestration_plan_id,
    utc_now_iso,
)

from context_orchestration.context_orchestrator import (
    ContextOrchestrator,
)

__all__ = [
    "ContextSource",
    "ContextOrchestrationPlan",
    "ContextOrchestrator",
    "generate_orchestration_plan_id",
    "utc_now_iso",
]