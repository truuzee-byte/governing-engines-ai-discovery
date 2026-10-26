"""Domain-specific authority rules; enforcement is in the custody engine."""
from dataclasses import dataclass
from enum import Enum


class AuthorityLevel(str, Enum):
    SYSTEM_LAW = "SYSTEM_LAW"
    AUTHORIZED_OPERATOR = "AUTHORIZED_OPERATOR"
    AUTHORIZED_ORGANIZATION = "AUTHORIZED_ORGANIZATION"
    VALIDATED_EXTERNAL_AUTHORITY = "VALIDATED_EXTERNAL_AUTHORITY"
    DIRECT_OPERATOR_STATEMENT = "DIRECT_OPERATOR_STATEMENT"
    VALIDATED_RUNTIME_EVIDENCE = "VALIDATED_RUNTIME_EVIDENCE"
    INFERRED_CONTEXT = "INFERRED_CONTEXT"
    MODEL_INFERENCE = "MODEL_INFERENCE"
    UNVERIFIED_INPUT = "UNVERIFIED_INPUT"


@dataclass(frozen=True)
class AuthorityContext:
    holder: str
    level: AuthorityLevel
    domain: str
    authenticated: bool = False
    confirmation_reference: str = ""
    may_replace_protected: bool = False
    may_delete: bool = False

    def __post_init__(self):
        if not isinstance(self.level, AuthorityLevel):
            raise ValueError("authority level must use canonical enum")
        for value in (self.authenticated, self.may_replace_protected, self.may_delete):
            if type(value) is not bool:
                raise ValueError("authority flags must be booleans")


@dataclass(frozen=True)
class SemanticCustodyPolicy:
    version: str = "1.2"
    qualifying_source_types: tuple = ("OPERATOR_STATEMENT", "DOCUMENT", "AUTHORITATIVE_DOCUMENT",
        "SYSTEM_POLICY", "EXTERNAL_AUTHORITY", "RUNTIME_OBSERVATION", "REALITY_VALIDATION")
    # Domain owners outrank model inference; no universal authority ladder.
    domain_owners: tuple = (
        ("OPERATOR", ("AUTHORIZED_OPERATOR", "DIRECT_OPERATOR_STATEMENT")),
        ("SYSTEM", ("SYSTEM_LAW", "AUTHORIZED_ORGANIZATION")),
        ("EXTERNAL", ("VALIDATED_EXTERNAL_AUTHORITY", "AUTHORIZED_ORGANIZATION")),
        ("RUNTIME", ("VALIDATED_RUNTIME_EVIDENCE", "SYSTEM_LAW")),
    )
    same_state_actions: tuple = ("CREATE", "NO_CHANGE", "ADD_EVIDENCE", "REFINE", "EXPAND", "REDUCE")

    def rank(self, domain, level):
        owners = dict(self.domain_owners).get(domain, ())
        if str(level) in owners or getattr(level, "value", None) in owners:
            return 3
        if level in {"MODEL_INFERENCE", "INFERRED_CONTEXT"}:
            return 1
        return 0
