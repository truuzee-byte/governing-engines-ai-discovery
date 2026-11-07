"""
Persistent Memory Package

Purpose
-------
Persistent Memory preserves approved long-term information across
sessions.

Thread Memory records conversation history.

Persistent Memory records information Mode is explicitly authorized
to retain beyond the current conversation.

Hard Line
---------
Mode may propose memory.

The operator approves memory.

Session-only information may be used for current execution.

Session-only information shall never become Persistent Memory.

Persistent Memory shall never be created, updated, or deleted without
explicit operator confirmation.
"""

from persistent_memory.persistent_memory_manager import (
    PersistentMemoryManager,
    PersistentMemoryOperationResult,
)

from persistent_memory.persistent_memory_policy import (
    CREATE_TRIGGER_PHRASES,
    DELETE_TRIGGER_PHRASES,
    QUERY_TRIGGER_PHRASES,
    UPDATE_TRIGGER_PHRASES,
    MemoryIntentDetectionResult,
    PersistentMemoryPolicyResult,
    confirm_memory_operation,
    detect_memory_intent,
    evaluate_memory_candidate,
    evaluate_memory_record,
)

from persistent_memory.persistent_memory_record import (
    PersistentMemoryCandidate,
    PersistentMemoryConsentStatus,
    PersistentMemoryDomain,
    PersistentMemoryEvidence,
    PersistentMemoryOperation,
    PersistentMemoryReceipt,
    PersistentMemoryRecord,
    PersistentMemoryStatus,
    PersistentMemoryStorageScope,
    PersistentMemoryType,
    create_memory_record_from_candidate,
    generate_memory_id,
    generate_receipt_id,
    utc_now_iso,
)

from persistent_memory.persistent_memory_store import (
    PersistentMemoryStore,
)

__all__ = [
    # Manager
    "PersistentMemoryManager",
    "PersistentMemoryOperationResult",

    # Store
    "PersistentMemoryStore",

    # Policy
    "PersistentMemoryPolicyResult",
    "MemoryIntentDetectionResult",
    "detect_memory_intent",
    "evaluate_memory_candidate",
    "evaluate_memory_record",
    "confirm_memory_operation",

    # Trigger phrases
    "CREATE_TRIGGER_PHRASES",
    "UPDATE_TRIGGER_PHRASES",
    "DELETE_TRIGGER_PHRASES",
    "QUERY_TRIGGER_PHRASES",

    # Models
    "PersistentMemoryRecord",
    "PersistentMemoryCandidate",
    "PersistentMemoryEvidence",
    "PersistentMemoryReceipt",

    # Enums
    "PersistentMemoryStatus",
    "PersistentMemoryType",
    "PersistentMemoryOperation",
    "PersistentMemoryStorageScope",
    "PersistentMemoryConsentStatus",
    "PersistentMemoryDomain",

    # Helpers
    "create_memory_record_from_candidate",
    "generate_memory_id",
    "generate_receipt_id",
    "utc_now_iso",
]