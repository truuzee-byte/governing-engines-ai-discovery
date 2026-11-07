"""Operational edges with provenance; representation does not assert existence."""
from dataclasses import dataclass, field, asdict
from enum import Enum
from .understanding_record import stable_id


class RelationshipType(str, Enum):
    DEPENDS_ON = "DEPENDS_ON"
    PRODUCES = "PRODUCES"
    CONSUMES = "CONSUMES"
    CONSTRAINS = "CONSTRAINS"
    AUTHORIZES = "AUTHORIZES"
    VALIDATES = "VALIDATES"
    PRESERVES = "PRESERVES"
    TRIGGERS = "TRIGGERS"
    BLOCKS = "BLOCKS"
    TRANSITIONS_TO = "TRANSITIONS_TO"
    REQUIRES = "REQUIRES"
    PROVES = "PROVES"
    SUPERSEDES = "SUPERSEDES"
    COORDINATES_WITH = "COORDINATES_WITH"
    PROPAGATES_TO = "PROPAGATES_TO"


@dataclass(frozen=True)
class SystemRelationship:
    relationship_id: str
    operator_id: str
    project_id: str
    system_id: str
    source_entity: str
    target_entity: str
    relationship_type: RelationshipType
    description: str
    governing_requirement_ids: tuple[str, ...]
    source_references: tuple[str, ...]
    governing_chain_ids: tuple[str, ...] = ()
    constraints: tuple[str, ...] = ()
    invariants: tuple[str, ...] = ()
    authority_requirements: tuple[str, ...] = ()
    evidence_requirements: tuple[str, ...] = ()
    failure_condition: str = ""
    confidence: float = 0.5
    validation_status: str = "PROVISIONAL"
    metadata: dict = field(default_factory=dict)

    def __post_init__(self):
        if not isinstance(self.relationship_type, RelationshipType):
            raise ValueError("canonical relationship type required")
        if not all((self.source_entity, self.target_entity, self.governing_requirement_ids, self.source_references)):
            raise ValueError("relationship requires endpoints, requirement and source provenance")
        if not 0 <= self.confidence <= 1:
            raise ValueError("invalid relationship confidence")

    @classmethod
    def create(cls, operator_id, project_id, system_id, source, target, kind,
               requirement_ids, source_references, **kwargs):
        kind = RelationshipType(kind)
        return cls(stable_id("rel", operator_id, project_id, system_id, source, target, kind),
                   operator_id, project_id, system_id, source, target, kind,
                   kwargs.pop("description", f"{source} {kind.value} {target}"),
                   tuple(requirement_ids), tuple(source_references), **kwargs)

    def to_dict(self):
        return asdict(self)
