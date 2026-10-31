from dataclasses import dataclass, field
from enum import Enum
from typing import List


class KnowledgeDomain(str, Enum):
    RUNTIME = "RUNTIME"
    SESSION = "SESSION"
    PUBLIC = "PUBLIC"
    EXTERNAL_CURRENT = "EXTERNAL_CURRENT"
    PRIVATE_DOCUMENT = "PRIVATE_DOCUMENT"
    SYSTEM = "SYSTEM"
    INFERENCE = "INFERENCE"
    UNKNOWN = "UNKNOWN"
    MIXED = "MIXED"
    TEMPORAL = "TEMPORAL"

@dataclass(frozen=True)
class KnowledgeClassification:
    primary_domain: KnowledgeDomain
    secondary_domains: List[KnowledgeDomain] = field(default_factory=list)
    confidence: float = 0.0
    reason: str = ""