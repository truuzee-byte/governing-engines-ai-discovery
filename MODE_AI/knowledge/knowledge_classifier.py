from typing import Any
import re
from knowledge.knowledge_domain import KnowledgeClassification, KnowledgeDomain


class KnowledgeClassifier:
    """
    Classifies the operator request before reasoning begins.

    This component does not answer questions.
    This component does not retrieve memory.
    This component does not perform reasoning.
    """

    def classify(self, user_input: str) -> KnowledgeClassification:
        text = (user_input or "").strip().lower()

        if not text:
            return KnowledgeClassification(
                primary_domain=KnowledgeDomain.UNKNOWN,
                confidence=0.0,
                reason="Empty operator input.",
            )

        # A dated first-person preference is supplied session context, not a
        # request for externally current facts. Require every clause to match;
        # a mixed request still follows the source-requirement routing below.
        clauses = [part.strip() for part in re.split(r'(?<=[.!?;])\s+|\n+', text) if part.strip()]
        preference = r'(?:actually,?\s+)?i (?:prefer|like|dislike)\b[^\n]+'
        restriction = r'(?:keep|use) (?:this|that|it) (?:in|within|for) (?:this|the current) (?:conversation|session|thread) only[.!]?'
        if (any(re.fullmatch(preference, part) for part in clauses)
                and all(re.fullmatch(preference, part) or re.fullmatch(restriction, part) for part in clauses)
                and not re.search(r'\b(?:and then|and execute|and deploy|and delete)\b', text)):
            return KnowledgeClassification(
                primary_domain=KnowledgeDomain.SESSION,
                confidence=0.9,
                reason="Operator supplied a personal preference for the conversation; no external fact established.",
            )

        private_document_terms = [
            "uploaded document",
            "uploaded file",
            "pdf",
            "document say",
            "implementation document",
            "source document",
            "client document",
            "file say",
        ]

        external_current_terms = [
            "weather",
            "stock price",
            "share price",
            "news",
            "sports score",
            "live event",
        ]

        runtime_terms = [
            "my name",
            "who am i",
            "where do i live",
            "my favorite",
            "what did i say",
            "what are we working on",
            "remember",
            "active thread",
            "thread memory",
            "operator profile",
            "context",
            "session",
        ]

        system_terms = [
            "mode",
            "builder",
            "runtime",
            "source of truth",
            "implementation spec",
            "governing engines",
            "backend",
            "frontend",
            "context assembly",
            "knowledge layer",
            "persistent memory",
            "context orchestrator",
            "context assembler",
            "assembled context",
            "operator requirement",
            "requirement resolution",
            "system context",
            "audit tool",
            "reality primacy",
            "understanding layer",

            # runtime behavior / policy
            "posture",
            "clarify_first",
            "direct_response",
            "halt",
            "halted",
            "ambiguity",
            "route",
            "routing",
            "classification",
            "classifier",
            "knowledge domain",
            "knowledge route",
            "runtime behavior",
            "selected posture",
            "mode behavior",
            "governance",
            "governance halt",
            "response generation blocked",
        ]

        inference_terms = [
            "what do you think",
            "why do you think",
            "infer",
            "conclude",
            "prediction",
            "estimate",
            "likely",
        
        ]

        temporal_terms = [
            "what time",
            "what day",
            "date",
            "tomorrow",
            "yesterday",
            "this week",
        ]

        if self._contains_any(text, private_document_terms):
            return KnowledgeClassification(
                primary_domain=KnowledgeDomain.PRIVATE_DOCUMENT,
                confidence=0.9,
                reason="Request references uploaded, private, or document-based information.",
            )

        # A temporal qualifier is not an external source requirement. Bind it
        # to an external subject; session statements and runtime-state questions
        # must not acquire a live-world proof obligation merely by saying now.
        current_external_subject = re.search(
            r'\b(?:latest|current|today\x27s)\s+(?:news|prices?|rates?|scores?|'
            r'president|prime minister|ceo|election|forecast|release|version)\b', text)
        if self._contains_any(text, external_current_terms) or current_external_subject:
            return KnowledgeClassification(
                primary_domain=KnowledgeDomain.EXTERNAL_CURRENT,
                confidence=0.85,
                reason="Request requires live or time-sensitive external information.",
            )

        if self._contains_any(text, temporal_terms) and self._contains_any(text, runtime_terms):
            return KnowledgeClassification(
                primary_domain=KnowledgeDomain.MIXED,
                secondary_domains=[
                    KnowledgeDomain.RUNTIME,
                    KnowledgeDomain.TEMPORAL,
                ],
                confidence=0.85,
                reason="Request requires runtime/user context and temporal/current context.",
            )

        # System architecture takes precedence when both runtime and system terms appear.
        runtime_hit = self._contains_any(text, runtime_terms)
        system_hit = self._contains_any(text, system_terms)

        if runtime_hit and system_hit:
            return KnowledgeClassification(
                primary_domain=KnowledgeDomain.SYSTEM,
                secondary_domains=[KnowledgeDomain.RUNTIME],
                confidence=0.95,
                reason="Request concerns Mode architecture or runtime implementation.",
            )

        if runtime_hit:
            return KnowledgeClassification(
                primary_domain=KnowledgeDomain.RUNTIME,
                confidence=0.85,
                reason="Request depends on operator profile, session, or runtime memory.",
            )

        if self._contains_any(text, system_terms):
            return KnowledgeClassification(
                primary_domain=KnowledgeDomain.SYSTEM,
                confidence=0.85,
                reason="Request concerns Mode, runtime behavior, routing policy, or system architecture.",
            )

        if self._contains_any(text, inference_terms):
            return KnowledgeClassification(
                primary_domain=KnowledgeDomain.INFERENCE,
                confidence=0.75,
                reason="Request asks for interpretation, prediction, or reasoned judgment.",
            )

        if self._looks_temporal(text):
            return KnowledgeClassification(
                primary_domain=KnowledgeDomain.TEMPORAL,
                confidence=0.95,
                reason="Request concerns runtime or temporal information."
            )
        
        if self._looks_public_knowledge(text):
            return KnowledgeClassification(
                primary_domain=KnowledgeDomain.PUBLIC,
                confidence=0.75,
                reason="Request appears to ask for stable public knowledge.",
            )

        if self._looks_inference(text):
            return KnowledgeClassification(
                primary_domain=KnowledgeDomain.INFERENCE,
                confidence=0.8,
                reason="Request asks for analysis, pattern recognition, summarization, prediction, or inference from available evidence.",
            )
        
        return KnowledgeClassification(
            primary_domain=KnowledgeDomain.UNKNOWN,
            confidence=0.25,
            reason="Knowledge domain could not be determined with sufficient confidence.",
        )

    def _contains_any(self, text: str, terms: list[str]) -> bool:
        return any(term in text for term in terms)

    def _looks_public_knowledge(self, text: str) -> bool:
        starters = [
            "who is",
            "who owns",
            "who founded",
            "who created",
            "who invented",
            "who discovered",
            "who wrote",
            "what is",
            "what are",
            "where is",
            "when did",
            "when was",
            "define",
            "explain",
            "history of",
            "compare",
            "difference between",
            "compare the",
            "compare python",
            "advantages of",
            "disadvantages of",
            "pros and cons",
        ]
    
        if any(text.startswith(starter) for starter in starters):
            return True

        return self._contains_any(
            text,
            [
                "stand for",
                "what does",
                "what is",
                "define",
                "explain",
                "meaning of",
                "history of",
            ],
        )
    
        return any(text.startswith(starter) for starter in starters)    
    
    def _looks_temporal(self, text: str) -> bool:
        starters = [
            "what time",
            "what day",
            "what date",
            "what month",
            "what year",
            "what timezone",
            "what is today's date",
            "today",
            "tomorrow",
            "yesterday",
            "how long",
            "how many days",
        ]

        return any(text.startswith(starter) for starter in starters)
    
    def _looks_inference(self, text: str) -> bool:
        starters = [
            "what pattern",
            "what do you notice",
            "what do you infer",
            "what conclusion",
            "what does this suggest",
            "based on everything",
            "based on this",
            "analyze",
            "summarize",
            "predict",
        ]

        return any(text.startswith(starter) for starter in starters)

    def classify_with_observation(
        self,
        user_input: str,
    ) -> tuple[KnowledgeClassification, dict[str, Any]]:
        """
        Performs normal classification while returning routing evidence
        for the Runtime Observation layer.
        """
        classification = self.classify(user_input)

        observation = {
            "requested_domain": classification.primary_domain.value,
            "routed_domain": classification.primary_domain.value,
            "routing_confidence": classification.confidence,
            "routing_reason": classification.reason,
            "fallback_used": (
                classification.primary_domain == KnowledgeDomain.UNKNOWN
            ),
        }

        return classification, observation

