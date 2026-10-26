from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from enum import Enum
import re
from typing import Any
from uuid import uuid4


class PersistentMemoryStatus(str, Enum):
    ACTIVE = "ACTIVE"
    UNDER_REVIEW = "UNDER_REVIEW"
    REJECTED = "REJECTED"
    DEPRECATED = "DEPRECATED"
    ARCHIVED = "ARCHIVED"
    REMOVED = "REMOVED"


class PersistentMemoryType(str, Enum):
    OPERATOR_PREFERENCE = "OPERATOR_PREFERENCE"
    OPERATOR_FACT = "OPERATOR_FACT"
    PROJECT_CONTEXT = "PROJECT_CONTEXT"
    WORKFLOW_PATTERN = "WORKFLOW_PATTERN"
    COMMUNICATION_PATTERN = "COMMUNICATION_PATTERN"
    SYSTEM_NOTE = "SYSTEM_NOTE"
    OTHER = "OTHER"


class PersistentMemoryOperation(str, Enum):
    CREATE = "CREATE"
    UPDATE = "UPDATE"
    DELETE = "DELETE"


class PersistentMemoryStorageScope(str, Enum):
    SESSION_ONLY = "SESSION_ONLY"
    PERSISTENT = "PERSISTENT"


class PersistentMemoryConsentStatus(str, Enum):
    NOT_REQUIRED = "NOT_REQUIRED"
    REQUESTED = "REQUESTED"
    APPROVED = "APPROVED"
    REJECTED = "REJECTED"
    REVOKED = "REVOKED"


def classify_memory_consent(response: str) -> str:
    """Closed vocabulary; refusal takes precedence over affirmative words."""
    if not isinstance(response, str):
        return "AMBIGUOUS"
    text = response.strip().lower().replace("’", "'").rstrip(".!")
    if re.search(r"\b(no|nope|nah|never|cancel|reject|rejected|deny|denied)\b|\bdo not\b|\bdon't\b", text):
        return "REJECTED"
    if text in {"session", "session only", "session-only", "session_only", "use for this session"}:
        return "SESSION_ONLY"
    if text in {"yes", "y", "confirm", "confirmed", "approve", "approved",
                "persistent", "persistent memory", "save persistent", "save to persistent memory"}:
        return "APPROVED"
    return "AMBIGUOUS"


class PersistentMemoryDomain(str, Enum):
    GENERAL = "GENERAL"
    HEALTH = "HEALTH"
    FINANCIAL = "FINANCIAL"
    EDUCATION = "EDUCATION"
    PROFESSIONAL = "PROFESSIONAL"
    LEGAL = "LEGAL"
    ENGINEERING = "ENGINEERING"
    ENTERPRISE_WORKFLOW = "ENTERPRISE_WORKFLOW"
    SYSTEM = "SYSTEM"
    PROJECT = "PROJECT"
    OTHER = "OTHER"


@dataclass
class PersistentMemoryEvidence:
    source_thread_id: str
    source_message_id: str
    original_operator_statement: str
    reason: str
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class PersistentMemoryRecord:
    memory_id: str
    operator_id: str
    memory_type: PersistentMemoryType
    content: str
    source_thread_id: str
    source_message_id: str
    evidence: PersistentMemoryEvidence
    created_at: str
    updated_at: str
    last_confirmed_at: str
    confidence: float
    status: PersistentMemoryStatus

    domain: PersistentMemoryDomain = PersistentMemoryDomain.GENERAL
    data_category: str = "GENERAL"
    storage_scope: PersistentMemoryStorageScope = PersistentMemoryStorageScope.PERSISTENT
    consent_status: PersistentMemoryConsentStatus = PersistentMemoryConsentStatus.APPROVED
    expiration_policy: str | None = None
    operator_can_update: bool = True
    operator_can_delete: bool = True

    version: int = 0
    previous_hash: str | None = None
    governance_decision: dict = field(default_factory=dict)
    governed_metadata: dict = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        data = asdict(self)
        data["memory_type"] = self.memory_type.value
        data["status"] = self.status.value
        data["domain"] = self.domain.value
        data["storage_scope"] = self.storage_scope.value
        data["consent_status"] = self.consent_status.value
        data["evidence"] = self.evidence.to_dict()
        return data

    @staticmethod
    def from_dict(data: dict[str, Any]) -> "PersistentMemoryRecord":
        import math
        lineage={'version','previous_hash','governance_decision','governed_metadata'}
        fields=set(PersistentMemoryRecord.__dataclass_fields__)
        if type(data) is not dict or not (fields-lineage).issubset(data) or set(data)-fields:
            raise ValueError('MEMORY_INTEGRITY_FAILURE: incomplete or unknown persisted fields')
        for key in ('memory_id','operator_id','content','source_thread_id','source_message_id','created_at','updated_at','last_confirmed_at','data_category'):
            if type(data[key]) is not str:raise ValueError('MEMORY_INTEGRITY_FAILURE: malformed '+key)
        for key in ('operator_can_update','operator_can_delete'):
            if type(data[key]) is not bool:raise ValueError('MEMORY_INTEGRITY_FAILURE: explicit permission boolean required')
        if type(data['confidence']) not in {int,float} or not math.isfinite(data['confidence']):
            raise ValueError('MEMORY_INTEGRITY_FAILURE: malformed confidence')
        if type(data.get('version',0)) is not int or data.get('version',0)<0:
            raise ValueError('MEMORY_INTEGRITY_FAILURE: malformed version')
        if any(type(data.get(key,{})) is not dict for key in ('governance_decision','governed_metadata')):
            raise ValueError('MEMORY_INTEGRITY_FAILURE: malformed governance')
        evidence_data = data['evidence']
        if (type(evidence_data) is not dict or set(evidence_data)!=set(PersistentMemoryEvidence.__dataclass_fields__)
                or type(evidence_data['metadata']) is not dict
                or any(type(evidence_data[key]) is not str for key in ('source_thread_id','source_message_id','original_operator_statement','reason'))):
            raise ValueError('MEMORY_INTEGRITY_FAILURE: incomplete evidence')

        return PersistentMemoryRecord(
            memory_id=data["memory_id"],
            operator_id=data["operator_id"],
            memory_type=PersistentMemoryType(data["memory_type"]),
            content=data["content"],
            source_thread_id=data["source_thread_id"],
            source_message_id=data["source_message_id"],
            evidence=PersistentMemoryEvidence(
                source_thread_id=evidence_data.get("source_thread_id", ""),
                source_message_id=evidence_data.get("source_message_id", ""),
                original_operator_statement=evidence_data.get(
                    "original_operator_statement",
                    "",
                ),
                reason=evidence_data.get("reason", ""),
                metadata=evidence_data.get("metadata", {}),
            ),
            created_at=data["created_at"],
            updated_at=data["updated_at"],
            last_confirmed_at=data["last_confirmed_at"],
            confidence=data["confidence"],
            status=PersistentMemoryStatus(data["status"]),
            domain=PersistentMemoryDomain(data.get("domain", "GENERAL")),
            data_category=data.get("data_category", "GENERAL"),
            storage_scope=PersistentMemoryStorageScope(
                data["storage_scope"]
            ),
            consent_status=PersistentMemoryConsentStatus(
                data["consent_status"]
            ),
            expiration_policy=data.get("expiration_policy"),
            operator_can_update=data['operator_can_update'],
            operator_can_delete=data['operator_can_delete'],
            version=data.get('version',0),previous_hash=data.get('previous_hash'),
            governance_decision=data.get('governance_decision',{}),governed_metadata=data.get('governed_metadata',{}),
        )


@dataclass
class PersistentMemoryCandidate:
    operation: PersistentMemoryOperation
    operator_id: str
    memory_type: PersistentMemoryType
    proposed_content: str
    reason: str
    source_thread_id: str
    source_message_id: str
    original_operator_statement: str

    domain: PersistentMemoryDomain = PersistentMemoryDomain.GENERAL
    data_category: str = "GENERAL"
    storage_scope: PersistentMemoryStorageScope = PersistentMemoryStorageScope.PERSISTENT
    consent_status: PersistentMemoryConsentStatus = PersistentMemoryConsentStatus.REQUESTED
    expiration_policy: str | None = None
    operator_can_update: bool = True
    operator_can_delete: bool = True

    target_memory_id: str | None = None
    current_content: str | None = None
    confidence: float = 1.0
    metadata: dict[str, Any] = field(default_factory=dict)

    def confirmation_text(self) -> str:
        base = (
            "MEMORY OPERATION DETECTED\n\n"
            f"Operation:\n{self.operation.value}\n\n"
            f"Memory Type:\n{self.memory_type.value}\n\n"
            f"Domain:\n{self.domain.value}\n\n"
            f"Data Category:\n{self.data_category}\n\n"
            f"Storage Scope:\n{self.storage_scope.value}\n\n"
            f"Consent Status:\n{self.consent_status.value}\n\n"
        )

        if self.operation == PersistentMemoryOperation.CREATE:
            return (
                base
                + "Proposed Content:\n"
                f"{self.proposed_content}\n\n"
                "Reason:\n"
                f"{self.reason}\n\n"
                "Original Operator Statement:\n"
                f"{self.original_operator_statement}\n\n"
                "Do you want to create this Persistent Memory record?"
            )

        if self.operation == PersistentMemoryOperation.UPDATE:
            return (
                base
                + "Memory ID:\n"
                f"{self.target_memory_id}\n\n"
                "Current Value:\n"
                f"{self.current_content or ''}\n\n"
                "Proposed Value:\n"
                f"{self.proposed_content}\n\n"
                "Reason:\n"
                f"{self.reason}\n\n"
                "Original Operator Statement:\n"
                f"{self.original_operator_statement}\n\n"
                "Apply this Persistent Memory update?"
            )

        if self.operation == PersistentMemoryOperation.DELETE:
            return (
                base
                + "Memory ID:\n"
                f"{self.target_memory_id}\n\n"
                "Content:\n"
                f"{self.current_content or self.proposed_content}\n\n"
                "Reason:\n"
                f"{self.reason}\n\n"
                "Original Operator Statement:\n"
                f"{self.original_operator_statement}\n\n"
                "Delete this Persistent Memory record?"
            )

        raise ValueError(f"Unsupported memory operation: {self.operation}")

    def to_dict(self) -> dict[str, Any]:
        data = asdict(self)
        data["operation"] = self.operation.value
        data["memory_type"] = self.memory_type.value
        data["domain"] = self.domain.value
        data["storage_scope"] = self.storage_scope.value
        data["consent_status"] = self.consent_status.value
        return data


@dataclass
class PersistentMemoryReceipt:
    receipt_id: str
    memory_id: str
    operator_id: str
    operation: PersistentMemoryOperation
    status: str
    created_at: str
    previous_content: str | None
    new_content: str | None
    trace_reference: str | None = None
    memory_version: int | None = None
    governance_reference: str | None = None

    domain: PersistentMemoryDomain = PersistentMemoryDomain.GENERAL
    data_category: str = "GENERAL"
    storage_scope: PersistentMemoryStorageScope = PersistentMemoryStorageScope.PERSISTENT
    consent_status: PersistentMemoryConsentStatus = PersistentMemoryConsentStatus.APPROVED

    def to_dict(self) -> dict[str, Any]:
        data = asdict(self)
        data["operation"] = self.operation.value
        data["domain"] = self.domain.value
        data["storage_scope"] = self.storage_scope.value
        data["consent_status"] = self.consent_status.value
        return data

    def evidence_projection(self) -> dict[str, Any]:
        """Trace this receipt without copying private or session-only content.

        Persistent content is resolved through the exact owner/memory/version;
        refused and session-only content is never made durable by this view.
        """
        from hashlib import sha256
        value=self.to_dict()
        for field in ('previous_content','new_content'):
            content=value.pop(field)
            value[field+'_sha256']=sha256(content.encode('utf-8')).hexdigest() if content is not None else None
        return dict(value,content_representation='HASH_ONLY',receipt_projection='PersistentMemoryReceiptEvidence/1')


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def generate_memory_id() -> str:
    return f"pm-{uuid4().hex}"


def generate_receipt_id() -> str:
    return f"pmr-{uuid4().hex}"


def create_memory_record_from_candidate(
    candidate: PersistentMemoryCandidate,
) -> PersistentMemoryRecord:
    if candidate.operation != PersistentMemoryOperation.CREATE:
        raise ValueError("Only CREATE candidates can create memory records.")

    if candidate.storage_scope != PersistentMemoryStorageScope.PERSISTENT:
        raise ValueError("SESSION_ONLY candidates cannot create Persistent Memory records.")

    if candidate.consent_status != PersistentMemoryConsentStatus.APPROVED:
        raise ValueError("Persistent Memory creation requires approved consent.")

    now = utc_now_iso()

    evidence = PersistentMemoryEvidence(
        source_thread_id=candidate.source_thread_id,
        source_message_id=candidate.source_message_id,
        original_operator_statement=candidate.original_operator_statement,
        reason=candidate.reason,
        metadata=candidate.metadata,
    )

    return PersistentMemoryRecord(
        memory_id=generate_memory_id(),
        operator_id=candidate.operator_id,
        memory_type=candidate.memory_type,
        content=candidate.proposed_content,
        source_thread_id=candidate.source_thread_id,
        source_message_id=candidate.source_message_id,
        evidence=evidence,
        created_at=now,
        updated_at=now,
        last_confirmed_at=now,
        confidence=candidate.confidence,
        status=PersistentMemoryStatus.ACTIVE,
        domain=candidate.domain,
        data_category=candidate.data_category,
        storage_scope=candidate.storage_scope,
        consent_status=candidate.consent_status,
        expiration_policy=candidate.expiration_policy,
        operator_can_update=candidate.operator_can_update,
        operator_can_delete=candidate.operator_can_delete,
    )
