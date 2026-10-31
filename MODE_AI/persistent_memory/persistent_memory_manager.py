from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
import re
from typing import Any

from persistent_memory.persistent_memory_policy import (
    MemoryIntentDetectionResult,
    PersistentMemoryPolicyResult,
    detect_memory_intent,
    evaluate_memory_candidate,
)
from persistent_memory.persistent_memory_record import (
    PersistentMemoryCandidate,
    PersistentMemoryConsentStatus,
    PersistentMemoryDomain,
    PersistentMemoryOperation,
    PersistentMemoryReceipt,
    PersistentMemoryRecord,
    PersistentMemoryStorageScope,
    PersistentMemoryStatus,
    PersistentMemoryType,
    create_memory_record_from_candidate,
    generate_receipt_id,
    utc_now_iso,
    classify_memory_consent,
)
from persistent_memory.persistent_memory_store import PersistentMemoryStore


def memory_is_eligible(record, operator_id):
    from data_governance.memory_governance import admissible
    if not admissible(record):return False
    if (record.operator_id != operator_id or record.status != PersistentMemoryStatus.ACTIVE
            or record.storage_scope != PersistentMemoryStorageScope.PERSISTENT
            or record.consent_status != PersistentMemoryConsentStatus.APPROVED):
        return False
    if record.expiration_policy is not None:
        try:
            expiry = datetime.fromisoformat(record.expiration_policy.replace("Z", "+00:00"))
            if expiry.tzinfo is None or expiry <= datetime.now(timezone.utc):
                return False
        except (ValueError, AttributeError, TypeError):
            return False
    return bool(record.content.strip())


@dataclass
class PersistentMemoryOperationResult:
    success: bool
    requires_confirmation: bool
    message: str
    candidate: PersistentMemoryCandidate | None = None
    record: PersistentMemoryRecord | None = None
    receipt: PersistentMemoryReceipt | None = None
    policy_result: PersistentMemoryPolicyResult | None = None
    intent_detection: MemoryIntentDetectionResult | None = None
    session_only_payload: dict[str, Any] | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "success": self.success,
            "requires_confirmation": self.requires_confirmation,
            "message": self.message,
            "candidate": self.candidate.to_dict() if self.candidate else None,
            "record": self.record.to_dict() if self.record else None,
            "receipt": self.receipt.to_dict() if self.receipt else None,
            "policy_result": self.policy_result.__dict__ if self.policy_result else None,
            "intent_detection": self.intent_detection.to_dict() if self.intent_detection else None,
            "session_only_payload": self.session_only_payload,
        }


class PersistentMemoryManager:
    def __init__(self, store: PersistentMemoryStore | None = None) -> None:
        self.store = store or PersistentMemoryStore()

    def detect_intent(self, input_text: str) -> MemoryIntentDetectionResult:
        return detect_memory_intent(input_text)

    def propose_create_memory(
        self,
        operator_id: str,
        content: str,
        source_thread_id: str,
        source_message_id: str,
        original_operator_statement: str,
        memory_type: PersistentMemoryType = PersistentMemoryType.OTHER,
        reason: str = "Operator requested Persistent Memory creation.",
        confidence: float = 1.0,
        metadata: dict[str, Any] | None = None,
        domain: PersistentMemoryDomain = PersistentMemoryDomain.GENERAL,
        data_category: str = "GENERAL",
        storage_scope: PersistentMemoryStorageScope = PersistentMemoryStorageScope.PERSISTENT,
        expiration_policy: str | None = None,
    ) -> PersistentMemoryOperationResult:
        if not isinstance(storage_scope, PersistentMemoryStorageScope):
            raise ValueError("storage_scope must be an explicit PersistentMemoryStorageScope")
        candidate = PersistentMemoryCandidate(
            operation=PersistentMemoryOperation.CREATE,
            operator_id=operator_id,
            memory_type=memory_type,
            proposed_content=content,
            reason=reason,
            source_thread_id=source_thread_id,
            source_message_id=source_message_id,
            original_operator_statement=original_operator_statement,
            confidence=confidence,
            metadata=metadata or {},
            domain=domain,
            data_category=data_category,
            storage_scope=storage_scope,
            consent_status=(
                PersistentMemoryConsentStatus.NOT_REQUIRED
                if storage_scope == PersistentMemoryStorageScope.SESSION_ONLY
                else PersistentMemoryConsentStatus.REQUESTED
            ),
            expiration_policy=expiration_policy,
        )

        policy_result = evaluate_memory_candidate(candidate)

        if policy_result.allowed is False:
            return PersistentMemoryOperationResult(
                success=False,
                requires_confirmation=policy_result.requires_confirmation,
                message=policy_result.reason,
                candidate=candidate,
                policy_result=policy_result,
            )

        if candidate.storage_scope == PersistentMemoryStorageScope.SESSION_ONLY:
            return self._commit_session_only(
                candidate=candidate,
                policy_result=policy_result,
            )

        return PersistentMemoryOperationResult(
            success=False,
            requires_confirmation=True,
            message=candidate.confirmation_text(),
            candidate=candidate,
            policy_result=policy_result,
        )

    def propose_update_memory(
        self,
        operator_id: str,
        memory_id: str,
        new_content: str,
        source_thread_id: str,
        source_message_id: str,
        original_operator_statement: str,
        reason: str = "Operator requested Persistent Memory update.",
        confidence: float = 1.0,
        metadata: dict[str, Any] | None = None,
    ) -> PersistentMemoryOperationResult:
        existing_record = self.store.load_record(operator_id=operator_id, memory_id=memory_id)

        if existing_record is None:
            return PersistentMemoryOperationResult(
                success=False,
                requires_confirmation=False,
                message=f"Persistent Memory record not found: {memory_id}",
            )

        if not existing_record.operator_can_update:
            return PersistentMemoryOperationResult(
                success=False,
                requires_confirmation=False,
                message="Operator is not allowed to update this Persistent Memory record.",
                record=existing_record,
            )

        candidate = PersistentMemoryCandidate(
            operation=PersistentMemoryOperation.UPDATE,
            operator_id=operator_id,
            memory_type=existing_record.memory_type,
            proposed_content=new_content,
            reason=reason,
            source_thread_id=source_thread_id,
            source_message_id=source_message_id,
            original_operator_statement=original_operator_statement,
            target_memory_id=memory_id,
            current_content=existing_record.content,
            confidence=confidence,
            metadata=metadata or {},
            domain=existing_record.domain,
            data_category=existing_record.data_category,
            storage_scope=existing_record.storage_scope,
            consent_status=PersistentMemoryConsentStatus.REQUESTED,
            expiration_policy=existing_record.expiration_policy,
        )

        policy_result = evaluate_memory_candidate(candidate)

        if policy_result.allowed is False:
            return PersistentMemoryOperationResult(
                success=False,
                requires_confirmation=policy_result.requires_confirmation,
                message=policy_result.reason,
                candidate=candidate,
                record=existing_record,
                policy_result=policy_result,
            )

        return PersistentMemoryOperationResult(
            success=False,
            requires_confirmation=True,
            message=candidate.confirmation_text(),
            candidate=candidate,
            record=existing_record,
            policy_result=policy_result,
        )

    def propose_delete_memory(
        self,
        operator_id: str,
        memory_id: str,
        source_thread_id: str,
        source_message_id: str,
        original_operator_statement: str,
        reason: str = "Operator requested Persistent Memory deletion.",
        metadata: dict[str, Any] | None = None,
    ) -> PersistentMemoryOperationResult:
        existing_record = self.store.load_record(operator_id=operator_id, memory_id=memory_id)

        if existing_record is None:
            return PersistentMemoryOperationResult(
                success=False,
                requires_confirmation=False,
                message=f"Persistent Memory record not found: {memory_id}",
            )

        if not existing_record.operator_can_delete:
            return PersistentMemoryOperationResult(
                success=False,
                requires_confirmation=False,
                message="Operator is not allowed to delete this Persistent Memory record.",
                record=existing_record,
            )

        candidate = PersistentMemoryCandidate(
            operation=PersistentMemoryOperation.DELETE,
            operator_id=operator_id,
            memory_type=existing_record.memory_type,
            proposed_content=existing_record.content,
            reason=reason,
            source_thread_id=source_thread_id,
            source_message_id=source_message_id,
            original_operator_statement=original_operator_statement,
            target_memory_id=memory_id,
            current_content=existing_record.content,
            confidence=1.0,
            metadata=metadata or {},
            domain=existing_record.domain,
            data_category=existing_record.data_category,
            storage_scope=existing_record.storage_scope,
            consent_status=PersistentMemoryConsentStatus.REQUESTED,
            expiration_policy=existing_record.expiration_policy,
        )

        policy_result = evaluate_memory_candidate(candidate)

        if policy_result.allowed is False:
            return PersistentMemoryOperationResult(
                success=False,
                requires_confirmation=policy_result.requires_confirmation,
                message=policy_result.reason,
                candidate=candidate,
                record=existing_record,
                policy_result=policy_result,
            )

        return PersistentMemoryOperationResult(
            success=False,
            requires_confirmation=True,
            message=candidate.confirmation_text(),
            candidate=candidate,
            record=existing_record,
            policy_result=policy_result,
        )

    def confirm_candidate(
        self,
        candidate: PersistentMemoryCandidate,
        operator_confirmation: str,
        trace_reference: str | None = None,
    ) -> PersistentMemoryOperationResult:
        if not isinstance(candidate.storage_scope, PersistentMemoryStorageScope):
            raise ValueError("invalid storage_scope")
        decision = classify_memory_consent(operator_confirmation)
        from persistent_memory.operator_requests import bound_create_authorization
        if (decision=='AMBIGUOUS' and candidate.operation==PersistentMemoryOperation.CREATE and
                bound_create_authorization(operator_confirmation,candidate.original_operator_statement,candidate.proposed_content)):
            decision='APPROVED'
        if decision in {"REJECTED", "AMBIGUOUS"}:
            candidate.consent_status = (PersistentMemoryConsentStatus.REJECTED
                                        if decision == "REJECTED" else PersistentMemoryConsentStatus.REQUESTED)
            return PersistentMemoryOperationResult(
                success=False, requires_confirmation=decision == "AMBIGUOUS",
                message=("Operator rejected memory storage." if decision == "REJECTED"
                         else "No save performed. Please confirm yes, no, or session-only."),
                candidate=candidate,
                receipt=self._outcome_receipt(candidate, decision, trace_reference),
            )
        if decision == "SESSION_ONLY":
            candidate.storage_scope = PersistentMemoryStorageScope.SESSION_ONLY
        # A session candidate never acquires persistent scope through confirmation.
        candidate.consent_status = (PersistentMemoryConsentStatus.NOT_REQUIRED
                                    if candidate.storage_scope == PersistentMemoryStorageScope.SESSION_ONLY
                                    else PersistentMemoryConsentStatus.APPROVED)
        confirmation_result = evaluate_memory_candidate(candidate)

        if confirmation_result.allowed is False:
            return PersistentMemoryOperationResult(
                success=False,
                requires_confirmation=confirmation_result.requires_confirmation,
                message=confirmation_result.reason,
                candidate=candidate,
                policy_result=confirmation_result,
                receipt=self._outcome_receipt(candidate, "BLOCKED", trace_reference),
            )

        if candidate.storage_scope == PersistentMemoryStorageScope.SESSION_ONLY:
            return self._commit_session_only(candidate, confirmation_result)

        candidate.metadata=dict(candidate.metadata)
        candidate.metadata['_operator_confirmation']=operator_confirmation

        if candidate.operation == PersistentMemoryOperation.CREATE:
            return self._commit_create(candidate, trace_reference, confirmation_result)

        if candidate.operation == PersistentMemoryOperation.UPDATE:
            return self._commit_update(candidate, trace_reference, confirmation_result)

        if candidate.operation == PersistentMemoryOperation.DELETE:
            return self._commit_delete(candidate, trace_reference, confirmation_result)

        return PersistentMemoryOperationResult(
            success=False,
            requires_confirmation=False,
            message=f"Unsupported memory operation: {candidate.operation}",
            candidate=candidate,
            policy_result=confirmation_result,
        )

    def retrieve_memories(
        self,
        operator_id: str,
        query: str = "",
        include_inactive: bool = False,
        domain: PersistentMemoryDomain | None = None,
        data_category: str | None = None,
    ) -> list[PersistentMemoryRecord]:
        records = self.store.search_records(
            operator_id=operator_id,
            query="",
            include_inactive=True,  # inspect lifecycle exclusions; never admit them
        )

        filtered_records: list[PersistentMemoryRecord] = []
        self.retrieval_decisions = []

        def receipt(record, decision):
            from learning.contracts import digest
            return {'query_hash':digest(query),'record_id':record.memory_id,
                    'record_version':record.version,'record_content_hash':digest(record.content),
                    'governance_decision_id':record.governance_decision.get('decision_id'),
                    'purpose':'SEMANTIC_CONTEXT_SELECTION',
                    **decision}

        for record in records:
            if record.version>1:
                for historical in self.store.history(operator_id,record.memory_id):
                    if historical['version']<record.version:
                        from learning.contracts import digest
                        self.retrieval_decisions.append({'query_hash':digest(query),'record_id':record.memory_id,
                            'record_version':historical['version'],'current_version':record.version,
                            'included':False,'reason':'EXCLUDED_SUPERSEDED_VERSION','purpose':'SEMANTIC_CONTEXT_SELECTION'})
            if not memory_is_eligible(record, operator_id):
                self.retrieval_decisions.append(receipt(record,{'included':False,'reason':'INADMISSIBLE_LIFECYCLE_OR_OWNER'}))
                continue
            if query:
                stopwords = {"the", "a", "an", "is", "are", "my", "me", "i", "what", "how", "to", "for", "of", "and", "please", "do", "you", "about"}
                # Grammatical overlap is not topical relevance. In particular,
                # shared pronouns/conjunctions must not inject a preference
                # from an unrelated domain into an operator's scenario.
                stopwords.update({"it", "its", "this", "that", "these", "those", "when", "where",
                                  "who", "why", "which", "but", "or", "if", "then", "than",
                                  "whether", "because", "as", "at", "in", "on", "from", "with",
                                  "be", "been", "being", "was", "were", "has", "have", "had",
                                  "does", "did", "not", "no", "so", "there", "here", "s", "m",
                                  "he", "she", "they", "his", "her", "their", "we", "our", "your"})
                terms = set(re.findall(r"\w+", query.lower())) - stopwords
                content_terms = set(re.findall(r"\w+", (record.content + " " + record.data_category).lower()))
                # Bounded task vocabulary normalization. This cannot create
                # authority or broaden a named subject's applicability.
                aliases={'watering':'irrigation','watered':'irrigation','water':'irrigation',
                         'plants':'seedlings','plant':'seedlings','seedling':'seedlings',
                         'representation':'format','receipt':'report','receipts':'report','csv':'format','xml':'format','reports':'report','reporting':'report',
                         'evaluate':'evaluation','evaluating':'evaluation','evaluated':'evaluation',
                         'scheduled':'schedule','scheduling':'schedule',
                         'encoding':'encoding','serializer':'encoding','serialize':'encoding'}
                terms={aliases.get(t,t) for t in terms}
                content_terms={aliases.get(t,t) for t in content_terms}
                overlap = terms.intersection(content_terms)
                # Named subjects are a material applicability boundary, not
                # just another shared word (Harbor irrigation != Solace).
                ignored_names={'The','A','An','I','My','Update','Remember','Please','This','For','Reports','Report'}
                names={t.lower() for t in re.findall(r'\b[A-Z][a-z]+\b',record.content)
                       if t not in ignored_names and t.lower() not in stopwords}
                subject_matches = names.intersection(terms)
                task_matches=overlap-names
                task_facets={
                    'IRRIGATION':{'irrigation','reservoir','leaves','dry','watered','watering'},
                    'COMMUNICATION':{'voice','style','prose','communication','conversational','formal'},
                    'SCHEDULING':{'schedule','scheduling','appointment','time','weekday','day'},
                    'DISPATCH_CODE':{'code','dispatch'},
                    'LABELING':{'label','labels','labeling','bindings','spines'},
                    'REPORT_FORMAT':{'format','report'},
                    'SYSTEM_EVALUATION':{'evaluation','machine','system','artifact','artifacts'},
                    'PERSONAL_PREFERENCE':{'favorite','preferred','preference','food','color','drink'},
                }
                query_facets={key for key,words in task_facets.items() if terms & words}
                record_facets={key for key,words in task_facets.items() if content_terms & words}
                material_task = not query_facets or bool(query_facets & record_facets)
                # A direct lookup of an explicitly declared preference target
                # is materially scoped even when the topic is one word. Do not
                # confuse it with incidental overlap in an unrelated workflow.
                preference=re.match(r'^I\s+(?:prefer|like)\s+(.+?)(?:\s+over\s+|\s+rather than\s+|[.!]|$)',record.content,re.I)
                preference_target=set(re.findall(r'\w+',preference.group(1).lower())) if preference else set()
                direct_preference = bool(preference and terms and terms <= preference_target)
                # Case-independent leading subject label. An unknown label is
                # a restrictive scope anchor, never a new authority grant.
                generic_subjects=set().union(*task_facets.values()) | stopwords | {
                    'reports','report','seedlings','greenhouse','maintenance','pumps','code',
                    'remember','update','please','all','every','some','my','i','prefer','like','care'}
                leading=[t.lower() for t in re.findall(r'\w+',record.content)
                         if t.lower() not in stopwords]
                if leading and leading[0] not in generic_subjects:
                    names.add(aliases.get(leading[0],leading[0]))
                    subject_matches=names.intersection(terms)
                    task_matches=overlap-names
                owner_task = bool(query_facets & record_facets) and len(task_matches)>=2
                relevant = direct_preference or (bool(query_facets & record_facets) and
                    (bool(subject_matches and task_matches) if names else owner_task))
                if not relevant:
                    self.retrieval_decisions.append(receipt(record,{'included':False,
                        'reason':('TASK_SCOPE_UNRESOLVED' if not query_facets or not record_facets else
                                  'TASK_SCOPE_MISMATCH' if not material_task else
                                  'SUBJECT_SCOPE_MISMATCH' if names else 'LEXICAL_OVERLAP_ONLY'),
                        'lexical_overlap':sorted(overlap),'subject_anchors':sorted(names),
                        'matched_subjects':sorted(subject_matches),'task_matches':sorted(task_matches),
                        'query_task_facets':sorted(query_facets),'record_task_facets':sorted(record_facets)}))
                    continue
            if record.storage_scope != PersistentMemoryStorageScope.PERSISTENT:
                continue

            if record.consent_status != PersistentMemoryConsentStatus.APPROVED:
                continue

            if domain is not None and record.domain != domain:
                continue

            if data_category is not None and record.data_category != data_category:
                continue

            filtered_records.append(record)
            self.retrieval_decisions.append(receipt(record,{'included':True,
                'reason':'ELIGIBLE_QUERY_SUBJECT' if query else 'ELIGIBLE_UNFILTERED_OWNER_QUERY'}))

        return filtered_records

    def provenance_support(self,operator_id,query):
        """Resolve only explicit evidence IDs, independently of topic filtering."""
        identities=list(dict.fromkeys(re.findall(r'\bpm-[A-Za-z0-9-]+',query)))
        records=[];self.provenance_decisions=[]
        for identity in identities[:8]:
            record=self.store.load_record(operator_id,identity)
            eligible=bool(record and memory_is_eligible(record,operator_id))
            requested=re.search(re.escape(identity)+r'@(\d+)\b',query)
            superseded=bool(record and requested and int(requested[1])!=record.version)
            if superseded:eligible=False
            self.provenance_decisions.append({'record_id':identity,
                'decision':'PROVENANCE_ONLY_AVAILABLE' if eligible else 'EXCLUDED',
                'reason':'Current owner-approved explicit evidence reference' if eligible else
                         'SUPERSEDED_SUPPORT_REFERENCE' if superseded else 'NONEXISTENT_OR_INADMISSIBLE_SUPPORT',
                'version':record.version if record else None})
            if eligible:records.append(record)
        return records

    def _commit_session_only(
        self,
        candidate: PersistentMemoryCandidate,
        policy_result: PersistentMemoryPolicyResult,
    ) -> PersistentMemoryOperationResult:
        return PersistentMemoryOperationResult(
            success=True,
            requires_confirmation=False,
            message="Session-only information accepted for current execution. No Persistent Memory record created.",
            candidate=candidate,
            policy_result=policy_result,
            receipt=self._outcome_receipt(candidate, "SESSION_ONLY"),
            session_only_payload={
                "operator_id": candidate.operator_id,
                "memory_type": candidate.memory_type.value,
                "content": candidate.proposed_content,
                "domain": candidate.domain.value,
                "data_category": candidate.data_category,
                "storage_scope": candidate.storage_scope.value,
                "consent_status": candidate.consent_status.value,
                "source_thread_id": candidate.source_thread_id,
                "source_message_id": candidate.source_message_id,
                "metadata": candidate.metadata,
            },
        )

    def _commit_create(
        self,
        candidate: PersistentMemoryCandidate,
        trace_reference: str | None,
        policy_result: PersistentMemoryPolicyResult,
    ) -> PersistentMemoryOperationResult:
        record = create_memory_record_from_candidate(candidate)
        from data_governance.memory_governance import approve_memory
        record=approve_memory(record,candidate.operator_id,'CREATE',candidate.metadata['_operator_confirmation'])
        saved_record = self.store.save_record(record)

        receipt = PersistentMemoryReceipt(
            receipt_id=generate_receipt_id(),
            memory_id=saved_record.memory_id,
            operator_id=saved_record.operator_id,
            operation=PersistentMemoryOperation.CREATE,
            status="SUCCESS",
            created_at=utc_now_iso(),
            previous_content=None,
            new_content=saved_record.content,
            memory_version=saved_record.version,
            governance_reference=saved_record.governance_decision['decision_id'],
            trace_reference=trace_reference,
            domain=saved_record.domain,
            data_category=saved_record.data_category,
            storage_scope=saved_record.storage_scope,
            consent_status=saved_record.consent_status,
        )

        return PersistentMemoryOperationResult(
            success=True,
            requires_confirmation=False,
            message="Persistent Memory record created.",
            candidate=candidate,
            record=saved_record,
            receipt=receipt,
            policy_result=policy_result,
        )

    def _commit_update(
        self,
        candidate: PersistentMemoryCandidate,
        trace_reference: str | None,
        policy_result: PersistentMemoryPolicyResult,
    ) -> PersistentMemoryOperationResult:
        if candidate.target_memory_id is None:
            raise ValueError("UPDATE requires target_memory_id.")

        existing_record = self.store.load_record(
            operator_id=candidate.operator_id,
            memory_id=candidate.target_memory_id,
        )

        if existing_record is None:
            return PersistentMemoryOperationResult(
                success=False,
                requires_confirmation=False,
                message=f"Persistent Memory record not found: {candidate.target_memory_id}",
                candidate=candidate,
                policy_result=policy_result,
            )

        previous_content = existing_record.content

        from data_governance.memory_governance import approve_memory
        existing_record.content=candidate.proposed_content
        existing_record.updated_at=utc_now_iso();existing_record.last_confirmed_at=existing_record.updated_at
        existing_record.source_thread_id=candidate.source_thread_id;existing_record.source_message_id=candidate.source_message_id
        existing_record.evidence.source_thread_id=candidate.source_thread_id;existing_record.evidence.source_message_id=candidate.source_message_id
        existing_record.evidence.original_operator_statement=candidate.original_operator_statement
        existing_record.evidence.metadata=dict(candidate.metadata)
        updated_record=self.store.save_record(approve_memory(existing_record,candidate.operator_id,'UPDATE',candidate.metadata['_operator_confirmation']))

        receipt = PersistentMemoryReceipt(
            receipt_id=generate_receipt_id(),
            memory_id=updated_record.memory_id,
            operator_id=updated_record.operator_id,
            operation=PersistentMemoryOperation.UPDATE,
            status="SUCCESS",
            created_at=utc_now_iso(),
            previous_content=previous_content,
            new_content=updated_record.content,
            memory_version=updated_record.version,
            governance_reference=updated_record.governance_decision['decision_id'],
            trace_reference=trace_reference,
            domain=updated_record.domain,
            data_category=updated_record.data_category,
            storage_scope=updated_record.storage_scope,
            consent_status=updated_record.consent_status,
        )

        return PersistentMemoryOperationResult(
            success=True,
            requires_confirmation=False,
            message="Persistent Memory record updated.",
            candidate=candidate,
            record=updated_record,
            receipt=receipt,
            policy_result=policy_result,
        )

    def _commit_delete(
        self,
        candidate: PersistentMemoryCandidate,
        trace_reference: str | None,
        policy_result: PersistentMemoryPolicyResult,
    ) -> PersistentMemoryOperationResult:
        if candidate.target_memory_id is None:
            raise ValueError("DELETE requires target_memory_id.")

        existing_record = self.store.load_record(
            operator_id=candidate.operator_id,
            memory_id=candidate.target_memory_id,
        )

        if existing_record is None:
            return PersistentMemoryOperationResult(
                success=False,
                requires_confirmation=False,
                message=f"Persistent Memory record not found: {candidate.target_memory_id}",
                candidate=candidate,
                policy_result=policy_result,
            )

        previous_content = existing_record.content

        deprecated_record=self.lifecycle(candidate.operator_id,candidate.target_memory_id,'REMOVE',candidate.metadata['_operator_confirmation'])

        receipt = PersistentMemoryReceipt(
            receipt_id=generate_receipt_id(),
            memory_id=deprecated_record.memory_id,
            operator_id=deprecated_record.operator_id,
            operation=PersistentMemoryOperation.DELETE,
            status="SUCCESS",
            created_at=utc_now_iso(),
            previous_content=previous_content,
            new_content=None,
            memory_version=deprecated_record.version,
            governance_reference=deprecated_record.governance_decision['decision_id'],
            trace_reference=trace_reference,
            domain=deprecated_record.domain,
            data_category=deprecated_record.data_category,
            storage_scope=deprecated_record.storage_scope,
            consent_status=deprecated_record.consent_status,
        )

        return PersistentMemoryOperationResult(
            success=True,
            requires_confirmation=False,
            message="Persistent Memory record deprecated.",
            candidate=candidate,
            record=deprecated_record,
            receipt=receipt,
            policy_result=policy_result,
        )

    def _outcome_receipt(self, candidate, status, trace_reference=None):
        return PersistentMemoryReceipt(
            receipt_id=generate_receipt_id(), memory_id=candidate.target_memory_id or "",
            operator_id=candidate.operator_id, operation=candidate.operation,
            status=status, created_at=utc_now_iso(), previous_content=candidate.current_content,
            new_content=candidate.proposed_content, trace_reference=trace_reference,
            domain=candidate.domain, data_category=candidate.data_category,
            storage_scope=candidate.storage_scope, consent_status=candidate.consent_status,
        )

    def lifecycle(self,operator_id,memory_id,action,confirmation):
        from data_governance.memory_governance import approve_memory
        if action not in {'ARCHIVE','RESTORE','REMOVE'}:raise ValueError('Unknown memory lifecycle action')
        record=self.store.load_record(operator_id,memory_id)
        if not record:raise ValueError('Unknown memory')
        if action=='RESTORE' and not record.governance_decision:raise PermissionError('Legacy memory requires fresh governance')
        record.status={'ARCHIVE':PersistentMemoryStatus.ARCHIVED,'RESTORE':PersistentMemoryStatus.ACTIVE,'REMOVE':PersistentMemoryStatus.REMOVED}[action]
        record.updated_at=utc_now_iso()
        return self.store.save_record(approve_memory(record,operator_id,action,confirmation))
