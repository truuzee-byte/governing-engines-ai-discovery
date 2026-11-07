from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from persistent_memory.persistent_memory_record import (
    PersistentMemoryCandidate,
    PersistentMemoryConsentStatus,
    PersistentMemoryOperation,
    PersistentMemoryRecord,
    PersistentMemoryStatus,
    PersistentMemoryStorageScope,
    PersistentMemoryType,
)


CREATE_TRIGGER_PHRASES = (
    "save this",
    "save that",
    "remember this",
    "remember that",
    "lock this",
    "lock that",
    "add this to memory",
    "add that to memory",
    "store this",
    "store that",
    "make this persistent",
    "make that persistent",
    "keep this",
    "keep that",
)

UPDATE_TRIGGER_PHRASES = (
    "update this memory",
    "update that memory",
    "change this memory",
    "change that memory",
    "replace this memory",
    "replace that memory",
)

DELETE_TRIGGER_PHRASES = (
    "delete this memory",
    "delete that memory",
    "forget this",
    "forget that",
    "remove this memory",
    "remove that memory",
)

QUERY_TRIGGER_PHRASES = (
    "what do you remember",
    "show my memory",
    "show memories",
    "list my memories",
    "list memory",
)


@dataclass
class PersistentMemoryPolicyResult:
    allowed: bool
    requires_confirmation: bool
    reason: str
    failure_code: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class MemoryIntentDetectionResult:
    detected: bool
    operation: PersistentMemoryOperation | None
    trigger_phrase: str | None
    requires_confirmation: bool
    reason: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "detected": self.detected,
            "operation": self.operation.value if self.operation is not None else None,
            "trigger_phrase": self.trigger_phrase,
            "requires_confirmation": self.requires_confirmation,
            "reason": self.reason,
        }


def detect_memory_intent(input_text: str) -> MemoryIntentDetectionResult:
    normalized = input_text.strip().lower()

    create_trigger = _find_trigger(normalized, CREATE_TRIGGER_PHRASES)
    if create_trigger is not None:
        return MemoryIntentDetectionResult(
            detected=True,
            operation=PersistentMemoryOperation.CREATE,
            trigger_phrase=create_trigger,
            requires_confirmation=True,
            reason="Operator used a Persistent Memory create trigger.",
        )

    update_trigger = _find_trigger(normalized, UPDATE_TRIGGER_PHRASES)
    if update_trigger is not None:
        return MemoryIntentDetectionResult(
            detected=True,
            operation=PersistentMemoryOperation.UPDATE,
            trigger_phrase=update_trigger,
            requires_confirmation=True,
            reason="Operator used a Persistent Memory update trigger.",
        )

    delete_trigger = _find_trigger(normalized, DELETE_TRIGGER_PHRASES)
    if delete_trigger is not None:
        return MemoryIntentDetectionResult(
            detected=True,
            operation=PersistentMemoryOperation.DELETE,
            trigger_phrase=delete_trigger,
            requires_confirmation=True,
            reason="Operator used a Persistent Memory delete trigger.",
        )

    query_trigger = _find_trigger(normalized, QUERY_TRIGGER_PHRASES)
    if query_trigger is not None:
        return MemoryIntentDetectionResult(
            detected=True,
            operation=None,
            trigger_phrase=query_trigger,
            requires_confirmation=False,
            reason="Operator requested Persistent Memory retrieval.",
        )

    return MemoryIntentDetectionResult(
        detected=False,
        operation=None,
        trigger_phrase=None,
        requires_confirmation=False,
        reason="No Persistent Memory trigger detected.",
    )


def evaluate_memory_candidate(
    candidate: PersistentMemoryCandidate,
) -> PersistentMemoryPolicyResult:
    if not isinstance(candidate, PersistentMemoryCandidate):
        return PersistentMemoryPolicyResult(
            allowed=False,
            requires_confirmation=True,
            reason="Invalid Persistent Memory candidate object.",
            failure_code="INVALID_MEMORY_CANDIDATE",
        )

    if candidate.operator_id.strip() == "":
        return PersistentMemoryPolicyResult(
            allowed=False,
            requires_confirmation=True,
            reason="Persistent Memory requires an operator_id.",
            failure_code="OPERATOR_ID_REQUIRED",
        )

    if candidate.proposed_content.strip() == "":
        return PersistentMemoryPolicyResult(
            allowed=False,
            requires_confirmation=True,
            reason="Persistent Memory content cannot be empty.",
            failure_code="EMPTY_MEMORY_CONTENT",
        )

    if candidate.source_thread_id.strip() == "":
        return PersistentMemoryPolicyResult(
            allowed=False,
            requires_confirmation=True,
            reason="Persistent Memory requires a source_thread_id.",
            failure_code="SOURCE_THREAD_REQUIRED",
        )

    if candidate.source_message_id.strip() == "":
        return PersistentMemoryPolicyResult(
            allowed=False,
            requires_confirmation=True,
            reason="Persistent Memory requires a source_message_id.",
            failure_code="SOURCE_MESSAGE_REQUIRED",
        )

    if candidate.original_operator_statement.strip() == "":
        return PersistentMemoryPolicyResult(
            allowed=False,
            requires_confirmation=True,
            reason="Persistent Memory requires the original operator statement.",
            failure_code="ORIGINAL_STATEMENT_REQUIRED",
        )

    if candidate.confidence < 0.0 or candidate.confidence > 1.0:
        return PersistentMemoryPolicyResult(
            allowed=False,
            requires_confirmation=True,
            reason="Persistent Memory confidence must be between 0.0 and 1.0.",
            failure_code="INVALID_CONFIDENCE",
        )

    if candidate.operation in (
        PersistentMemoryOperation.UPDATE,
        PersistentMemoryOperation.DELETE,
    ) and candidate.target_memory_id is None:
        return PersistentMemoryPolicyResult(
            allowed=False,
            requires_confirmation=True,
            reason="UPDATE and DELETE require target_memory_id.",
            failure_code="TARGET_MEMORY_ID_REQUIRED",
        )

    if candidate.storage_scope == PersistentMemoryStorageScope.SESSION_ONLY:
        return PersistentMemoryPolicyResult(
            allowed=True,
            requires_confirmation=False,
            reason="Session-only information may be used for current execution but shall not be persisted.",
            metadata={
                "storage_scope": candidate.storage_scope.value,
                "domain": candidate.domain.value,
                "data_category": candidate.data_category,
            },
        )

    if candidate.storage_scope == PersistentMemoryStorageScope.PERSISTENT:
        if candidate.consent_status != PersistentMemoryConsentStatus.APPROVED:
            return PersistentMemoryPolicyResult(
                allowed=True,
                requires_confirmation=True,
                reason="Persistent Memory operation is structurally valid but requires explicit operator approval before storage.",
                failure_code="PERSISTENT_MEMORY_CONFIRMATION_REQUIRED",
                metadata={
                    "storage_scope": candidate.storage_scope.value,
                    "consent_status": candidate.consent_status.value,
                    "domain": candidate.domain.value,
                    "data_category": candidate.data_category,
                },
            )

    return PersistentMemoryPolicyResult(
        allowed=True,
        requires_confirmation=True,
        reason="Persistent Memory operation is structurally valid. Operator confirmation is still required.",
        metadata={
            "storage_scope": candidate.storage_scope.value,
            "consent_status": candidate.consent_status.value,
            "domain": candidate.domain.value,
            "data_category": candidate.data_category,
        },
    )


def evaluate_memory_record(
    record: PersistentMemoryRecord,
) -> PersistentMemoryPolicyResult:
    if not isinstance(record, PersistentMemoryRecord):
        return PersistentMemoryPolicyResult(
            allowed=False,
            requires_confirmation=False,
            reason="Invalid Persistent Memory record object.",
            failure_code="INVALID_MEMORY_RECORD",
        )

    if record.operator_id.strip() == "":
        return PersistentMemoryPolicyResult(
            allowed=False,
            requires_confirmation=False,
            reason="Persistent Memory record requires operator_id.",
            failure_code="OPERATOR_ID_REQUIRED",
        )

    if record.content.strip() == "":
        return PersistentMemoryPolicyResult(
            allowed=False,
            requires_confirmation=False,
            reason="Persistent Memory record content cannot be empty.",
            failure_code="EMPTY_MEMORY_CONTENT",
        )

    if record.status not in PersistentMemoryStatus:
        return PersistentMemoryPolicyResult(
            allowed=False,
            requires_confirmation=False,
            reason="Invalid Persistent Memory status.",
            failure_code="INVALID_MEMORY_STATUS",
        )

    if record.memory_type not in PersistentMemoryType:
        return PersistentMemoryPolicyResult(
            allowed=False,
            requires_confirmation=False,
            reason="Invalid Persistent Memory type.",
            failure_code="INVALID_MEMORY_TYPE",
        )

    if record.storage_scope == PersistentMemoryStorageScope.SESSION_ONLY:
        return PersistentMemoryPolicyResult(
            allowed=False,
            requires_confirmation=False,
            reason="SESSION_ONLY information cannot exist as a Persistent Memory record.",
            failure_code="SESSION_ONLY_RECORD_NOT_ALLOWED",
        )

    if record.storage_scope == PersistentMemoryStorageScope.PERSISTENT:
        if record.consent_status != PersistentMemoryConsentStatus.APPROVED:
            return PersistentMemoryPolicyResult(
                allowed=False,
                requires_confirmation=False,
                reason="Persistent Memory record requires approved consent.",
                failure_code="PERSISTENT_RECORD_CONSENT_REQUIRED",
            )

    return PersistentMemoryPolicyResult(
        allowed=True,
        requires_confirmation=False,
        reason="Persistent Memory record is structurally valid.",
        metadata={
            "storage_scope": record.storage_scope.value,
            "consent_status": record.consent_status.value,
            "domain": record.domain.value,
            "data_category": record.data_category,
        },
    )


def confirm_memory_operation(
    candidate: PersistentMemoryCandidate,
    operator_confirmation: str,
) -> PersistentMemoryPolicyResult:
    normalized = operator_confirmation.strip().lower()

    if normalized in ("yes", "y", "confirm", "confirmed", "approved", "approve"):
        candidate.consent_status = PersistentMemoryConsentStatus.APPROVED

        return PersistentMemoryPolicyResult(
            allowed=True,
            requires_confirmation=False,
            reason="Operator confirmed Persistent Memory operation.",
            metadata={
                "operation": candidate.operation.value,
                "memory_type": candidate.memory_type.value,
                "target_memory_id": candidate.target_memory_id,
                "storage_scope": candidate.storage_scope.value,
                "consent_status": candidate.consent_status.value,
                "domain": candidate.domain.value,
                "data_category": candidate.data_category,
            },
        )

    if normalized in ("no", "n", "reject", "rejected", "deny", "denied"):
        candidate.consent_status = PersistentMemoryConsentStatus.REJECTED

        return PersistentMemoryPolicyResult(
            allowed=False,
            requires_confirmation=False,
            reason="Operator rejected Persistent Memory operation.",
            failure_code="OPERATOR_REJECTED_MEMORY_OPERATION",
            metadata={
                "operation": candidate.operation.value,
                "memory_type": candidate.memory_type.value,
                "target_memory_id": candidate.target_memory_id,
                "storage_scope": candidate.storage_scope.value,
                "consent_status": candidate.consent_status.value,
                "domain": candidate.domain.value,
                "data_category": candidate.data_category,
            },
        )

    if normalized in ("session", "session only", "use for this session"):
        candidate.storage_scope = PersistentMemoryStorageScope.SESSION_ONLY
        candidate.consent_status = PersistentMemoryConsentStatus.NOT_REQUIRED

        return PersistentMemoryPolicyResult(
            allowed=True,
            requires_confirmation=False,
            reason="Operator selected session-only use. No Persistent Memory record shall be created.",
            metadata={
                "operation": candidate.operation.value,
                "memory_type": candidate.memory_type.value,
                "target_memory_id": candidate.target_memory_id,
                "storage_scope": candidate.storage_scope.value,
                "consent_status": candidate.consent_status.value,
                "domain": candidate.domain.value,
                "data_category": candidate.data_category,
            },
        )

    if normalized in ("persistent", "save persistent", "save to persistent memory"):
        candidate.storage_scope = PersistentMemoryStorageScope.PERSISTENT
        candidate.consent_status = PersistentMemoryConsentStatus.APPROVED

        return PersistentMemoryPolicyResult(
            allowed=True,
            requires_confirmation=False,
            reason="Operator selected Persistent Memory storage.",
            metadata={
                "operation": candidate.operation.value,
                "memory_type": candidate.memory_type.value,
                "target_memory_id": candidate.target_memory_id,
                "storage_scope": candidate.storage_scope.value,
                "consent_status": candidate.consent_status.value,
                "domain": candidate.domain.value,
                "data_category": candidate.data_category,
            },
        )

    return PersistentMemoryPolicyResult(
        allowed=False,
        requires_confirmation=True,
        reason="Operator confirmation was not recognized.",
        failure_code="CONFIRMATION_REQUIRED",
    )


def _find_trigger(
    normalized_text: str,
    trigger_phrases: tuple[str, ...],
) -> str | None:
    for phrase in trigger_phrases:
        if phrase in normalized_text:
            return phrase

    return None