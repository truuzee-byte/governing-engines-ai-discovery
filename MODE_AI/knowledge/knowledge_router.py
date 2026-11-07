from dataclasses import dataclass
from typing import Any

from knowledge.knowledge_domain import (
    KnowledgeClassification,
    KnowledgeDomain,
)


@dataclass(frozen=True)
class KnowledgeRoute:
    requires_runtime_context: bool = False
    allows_public_knowledge: bool = False
    requires_external_source: bool = False
    requires_private_document: bool = False
    requires_system_context: bool = False
    allows_inference: bool = False
    unsupported_without_source: bool = False

    #
    # Runtime Observation Evidence
    #

    requested_domain: str = ""
    routed_domain: str = ""
    routing_confidence: float = 0.0
    routing_reason: str = ""
    fallback_used: bool = False

    def observation_metadata(self) -> dict[str, Any]:
        """
        Returns routing evidence for the Runtime Observation layer.
        """

        return {
            "requested_domain": self.requested_domain,
            "routed_domain": self.routed_domain,
            "routing_confidence": self.routing_confidence,
            "routing_reason": self.routing_reason,
            "fallback_used": self.fallback_used,
        }


class KnowledgeRouter:
    """
    Converts knowledge classification into routing decisions.

    Responsibilities

    • Convert Knowledge Classification into routing requirements.
    • Produce routing evidence.
    • Never retrieve knowledge.
    • Never answer questions.
    """

    def route(
        self,
        classification: KnowledgeClassification,
    ) -> KnowledgeRoute:

        domain = classification.primary_domain

        base_kwargs = {
            "requested_domain": domain.value,
            "routed_domain": domain.value,
            "routing_confidence": classification.confidence,
            "routing_reason": classification.reason,
            "fallback_used": domain == KnowledgeDomain.UNKNOWN,
        }

        if domain == KnowledgeDomain.PUBLIC:
            return KnowledgeRoute(
                allows_public_knowledge=True,
                **base_kwargs,
            )

        if domain == KnowledgeDomain.EXTERNAL_CURRENT:
            return KnowledgeRoute(
                requires_external_source=True,
                unsupported_without_source=True,
                **base_kwargs,
            )

        if domain == KnowledgeDomain.PRIVATE_DOCUMENT:
            return KnowledgeRoute(
                requires_private_document=True,
                unsupported_without_source=True,
                **base_kwargs,
            )

        if domain == KnowledgeDomain.RUNTIME:
            return KnowledgeRoute(
                requires_runtime_context=True,
                **base_kwargs,
            )

        if domain == KnowledgeDomain.SESSION:
            return KnowledgeRoute(
                requires_runtime_context=True,
                **base_kwargs,
            )

        if domain == KnowledgeDomain.SYSTEM:
            return KnowledgeRoute(
                requires_runtime_context=True,
                **base_kwargs,
            )

        if domain == KnowledgeDomain.INFERENCE:
            return KnowledgeRoute(
                allows_inference=True,
                requires_runtime_context=True,
                **base_kwargs,
            )

        if domain == KnowledgeDomain.MIXED:
            return self._route_mixed(
                classification,
                base_kwargs,
            )

        #
        # UNKNOWN
        #

        return KnowledgeRoute(
            **base_kwargs,
        )

    def _route_mixed(
        self,
        classification: KnowledgeClassification,
        base_kwargs: dict[str, Any],
    ) -> KnowledgeRoute:

        domains = set(classification.secondary_domains)

        requires_runtime_context = any(
            domain in domains
            for domain in (
                KnowledgeDomain.RUNTIME,
                KnowledgeDomain.SESSION,
                KnowledgeDomain.SYSTEM,
            )
        )

        return KnowledgeRoute(
            requires_runtime_context=requires_runtime_context,
            allows_public_knowledge=KnowledgeDomain.PUBLIC in domains,
            requires_external_source=KnowledgeDomain.EXTERNAL_CURRENT in domains,
            requires_private_document=KnowledgeDomain.PRIVATE_DOCUMENT in domains,
            requires_system_context=False,
            allows_inference=KnowledgeDomain.INFERENCE in domains,
            unsupported_without_source=(
                KnowledgeDomain.EXTERNAL_CURRENT in domains
                or KnowledgeDomain.PRIVATE_DOCUMENT in domains
            ),
            **base_kwargs,
        )