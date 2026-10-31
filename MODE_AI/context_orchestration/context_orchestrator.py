from __future__ import annotations

from context_orchestration.context_source import (
    ContextSource,
    ContextSourceAvailability,
    ContextSourceDecision,
    ContextSourceRequirement,
)
from context_orchestration.orchestration_plan import (
    ContextOrchestrationPlan,
    ContextSourceSelection,
    generate_orchestration_plan_id,
    utc_now_iso,
)
from knowledge.knowledge_domain import KnowledgeClassification, KnowledgeDomain
from knowledge.knowledge_router import KnowledgeRoute


class ContextOrchestrator:
    """
    Determines which context sources may participate in Context Assembly.

    The orchestrator selects sources; it does not assemble, retrieve, rank
    evidence within a source, or decide that a factual requirement is
    satisfied.

    Governing rules:
    - Current-thread context is selected before historical memory sources.
    - Persistent Memory may satisfy durable-fact requirements.
    - Thread Memory remains a summary/continuity source.
    - SYSTEM_CONTEXT is supplemental unless a route explicitly requires it.
    - A source name is not itself an evidence requirement.
    """

    def build_plan(
        self,
        *,
        operator_id: str,
        thread_id: str,
        input_text: str,
        classification: KnowledgeClassification,
        route: KnowledgeRoute,
        available_sources: set[ContextSource],
    ) -> ContextOrchestrationPlan:
        knowledge_domain = classification.primary_domain.value
        selections: list[ContextSourceSelection] = []
        selected_sources: set[ContextSource] = set()

        def add_source(
            source: ContextSource,
            *,
            required: bool,
            include: bool,
            reason: str,
            knowledge_dependency: str | None = None,
        ) -> None:
            if source in selected_sources:
                raise ValueError(
                    f"Context source selected more than once: {source.value}"
                )

            selected_sources.add(source)

            available = source in available_sources

            if required:
                decision = ContextSourceDecision.REQUIRED
                requirement = ContextSourceRequirement.REQUIRED
            elif include:
                decision = ContextSourceDecision.INCLUDED
                requirement = ContextSourceRequirement.OPTIONAL
            else:
                decision = ContextSourceDecision.EXCLUDED
                requirement = ContextSourceRequirement.OPTIONAL

            if available:
                availability = ContextSourceAvailability.AVAILABLE
            elif required:
                availability = ContextSourceAvailability.MISSING
            else:
                availability = ContextSourceAvailability.NOT_APPLICABLE

            selections.append(
                ContextSourceSelection(
                    source=source,
                    decision=decision,
                    requirement=requirement,
                    availability=availability,
                    reason=reason,
                    knowledge_domain_dependency=knowledge_dependency,
                )
            )

        add_source(
            ContextSource.KNOWLEDGE_ROUTING,
            required=True,
            include=True,
            reason="Knowledge routing participates in every execution.",
            knowledge_dependency=knowledge_domain,
        )

        add_source(
            ContextSource.THREAD_MEMORY,
            required=False,
            include=True,
            reason=(
                "Current-thread context is selected first; stored thread "
                "summaries remain historical continuity only."
            ),
            knowledge_dependency=knowledge_domain,
        )

        add_source(
            ContextSource.PERSISTENT_MEMORY,
            required=False,
            include=True,
            reason=(
                "Persistent Memory supplies approved durable facts but may "
                "not override the current thread."
            ),
            knowledge_dependency=knowledge_domain,
        )

        add_source(
            ContextSource.RUNTIME_STATE,
            required=route.requires_runtime_context,
            include=route.requires_runtime_context,
            reason=(
                "Runtime state is required only when the KnowledgeRoute "
                "declares a runtime-context dependency."
            ),
            knowledge_dependency=knowledge_domain,
        )

        add_source(
            ContextSource.OPERATOR_PROFILE,
            required=False,
            include=True,
            reason="Operator profile is available as supplemental operator context.",
            knowledge_dependency=knowledge_domain,
        )

        secondary_domains = set(classification.secondary_domains)

        system_context_relevant = (
            classification.primary_domain == KnowledgeDomain.SYSTEM
            or KnowledgeDomain.SYSTEM in secondary_domains
        )

        add_source(
            ContextSource.SYSTEM_CONTEXT,
            required=route.requires_system_context,
            include=route.requires_system_context or system_context_relevant,
            reason=(
                "System context is supplemental for system questions and "
                "required only when explicitly declared by KnowledgeRoute."
            ),
            knowledge_dependency="SYSTEM",
        )

        add_source(
            ContextSource.PRIVATE_DOCUMENT,
            required=route.requires_private_document,
            include=route.requires_private_document,
            reason="Private documents participate only when explicitly routed.",
            knowledge_dependency="PRIVATE_DOCUMENT",
        )

        add_source(
            ContextSource.TEMPORAL_CONTEXT,
            required=False,
            include=True,
            reason=(
                "Temporal context is available for time-sensitive execution "
                "and trace chronology."
            ),
            knowledge_dependency="TEMPORAL",
        )

        add_source(
            ContextSource.UNDERSTANDING,
            required=False,
            include=True,
            reason="Governed semantic understanding participates when available.",
            knowledge_dependency=knowledge_domain,
        )

        add_source(
            ContextSource.PROJECT_CONTEXT,
            required=False,
            include=True,
            reason="Project context participates when available and applicable.",
            knowledge_dependency=knowledge_domain,
        )

        add_source(
            ContextSource.BUILDER_CONTEXT,
            required=False,
            include=False,
            reason="Builder context remains excluded unless execution requires Builder.",
            knowledge_dependency=knowledge_domain,
        )

        return ContextOrchestrationPlan(
            plan_id=generate_orchestration_plan_id(),
            operator_id=operator_id,
            thread_id=thread_id,
            input_text=input_text,
            knowledge_domain=knowledge_domain,
            source_selections=selections,
            created_at=utc_now_iso(),
        )

    def build_plan_with_observation(
        self,
        *,
        operator_id: str,
        thread_id: str,
        input_text: str,
        classification: KnowledgeClassification,
        route: KnowledgeRoute,
        available_sources: set[ContextSource],
    ) -> tuple[ContextOrchestrationPlan, dict[str, object]]:
        """
        Builds a ContextOrchestrationPlan and returns runtime observation
        evidence describing the orchestration decision.
        """

        plan = self.build_plan(
            operator_id=operator_id,
            thread_id=thread_id,
            input_text=input_text,
            classification=classification,
            route=route,
            available_sources=available_sources,
        )

        requested = []
        loaded = []
        missing = []
        retrieval_order = []

        for selection in plan.source_selections:
            requested.append(selection.source.value)

            if (
                selection.decision
                != ContextSourceDecision.EXCLUDED
            ):
                retrieval_order.append(selection.source.value)

            if (
                selection.availability
                == ContextSourceAvailability.AVAILABLE
            ):
                loaded.append(selection.source.value)

            elif (
                selection.availability
                == ContextSourceAvailability.MISSING
            ):
                missing.append(selection.source.value)

        confidence = 1.0

        if requested:
            confidence = len(loaded) / len(requested)

        observation = {
            "requested_context_sources": requested,
            "loaded_context_sources": loaded,
            "missing_context_sources": missing,
            "failed_context_sources": [],
            "retrieval_order": retrieval_order,
            "context_confidence": confidence,
        }

        return plan, observation