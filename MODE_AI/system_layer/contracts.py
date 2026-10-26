"""System Layer v1.0 contracts. Operator decisions are exact-content bound."""
from dataclasses import dataclass, asdict, field
from enum import Enum
from datetime import datetime, timezone
import hashlib
import json


def digest(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(',', ':'),
        ensure_ascii=False, allow_nan=False).encode()).hexdigest()


def now():
    return datetime.now(timezone.utc).isoformat()


def authorize(owner, action, value, approval):
    if approval != {'operator_id': owner, 'action': action, 'decision': 'APPROVE', 'hash': digest(value)}:
        raise PermissionError('Exact current operator approval required: ' + action)


class CapabilityState(str, Enum):
    DECLARED = 'DECLARED'
    PROPOSED = 'PROPOSED'
    SPECIFICATION_REQUIRED = 'SPECIFICATION_REQUIRED'
    SPECIFICATION_IN_DEVELOPMENT = 'SPECIFICATION_IN_DEVELOPMENT'
    SPECIFICATION_APPROVED = 'SPECIFICATION_APPROVED'
    READY_FOR_BUILD = 'READY_FOR_BUILD'
    IN_DEVELOPMENT = 'IN_DEVELOPMENT'
    IMPLEMENTED = 'IMPLEMENTED'
    INTEGRATED = 'INTEGRATED'
    VALIDATION_PENDING = 'VALIDATION_PENDING'
    VALIDATED = 'VALIDATED'
    OPERATIONAL = 'OPERATIONAL'
    DEGRADED = 'DEGRADED'
    FAILED = 'FAILED'
    DISABLED = 'DISABLED'
    DEPRECATED = 'DEPRECATED'
    SUPERSEDED = 'SUPERSEDED'
    NOT_IMPLEMENTED = 'NOT_IMPLEMENTED'
    UNCONFIRMED = 'UNCONFIRMED'


STAGES = ('CAPABILITY_UPDATE', 'QUICK_SPEC', 'DECLARED', 'RP_AUDIT',
    'EXISTING_CAPABILITY_SEARCH', 'GAP', 'CHAIN_RECOGNITION', 'CHAIN_RELATIONSHIP_MAPPING',
    'MECHANISM_DERIVATION', 'DEPENDENCY_ANALYSIS', 'SPECIFICATION_SUFFICIENCY',
    'CLARIFICATION', 'CREATION_COMPONENT', 'GOVERNING_SPEC_CHAIN', 'OPERATOR_APPROVAL',
    'TARGET_EXECUTION_SPEC', 'EXECUTION_APPROVAL', 'BUILDER', 'CONSTRUCTION',
    'INTEGRATION', 'TESTING', 'RP_VALIDATION', 'GOVERNANCE_VALIDATION',
    'OPERATOR_ACCEPTANCE', 'CAPABILITY_REGISTRATION', 'SYSTEM_LAYER_STATE_UPDATE', 'OPERATIONAL')

PRINCIPLES = ('Operator Authority', 'Reality Primacy', 'Mechanism Primacy',
    'Interpretation Before Execution', 'Understanding Before Automation',
    'Governance Before Capability Expansion', 'Validation Before Deployment',
    'Evidence Before Completion', 'Knowledge Does Not Imply Authority',
    'Reference Is Not Authority', 'Authority Must Be Current', 'Execution Requires Custody',
    'Unsupported Claims Remain Pending Validation')

PRINCIPLES_V12 = PRINCIPLES[:5] + ('Structure Before Description',) + PRINCIPLES[5:]

IDENTITY_FIELDS = {
    'name': {'name', 'abbreviation', 'runtime_identity', 'public_identity', 'internal_identity', 'versioned_reference'},
    'system_type': {'classification'},
    'version': {'release_state', 'effective_date', 'supersession', 'capability_profile', 'deployment_profile', 'validation_references', 'audit_references'},
    'creator': {'creator_identity', 'authorship', 'architectural_ownership', 'approval_relationship', 'governing_role'},
    'organization': {'ownership', 'operational_authority', 'governance_authority', 'deployment_authority', 'maintenance_authority'},
    'purpose': {'problem_addressed', 'function', 'operators_or_systems_served', 'intended_outcomes', 'failures_to_prevent'},
    'operational_boundaries': {'deployment', 'authority', 'execution', 'knowledge', 'memory', 'self_modification',
        'builder', 'governance_mutation', 'external_action', 'privacy_data_custody', 'human_approval',
        'halt_conditions', 'runtime_profile', 'mutable_roots', 'protected_paths'},
}


def strings(values, field_name, required=False):
    if type(values) is not list or any(type(v) is not str or not v.strip() for v in values):
        raise ValueError('String list required: ' + field_name)
    if required and not values:
        raise ValueError('Missing ' + field_name)


@dataclass(frozen=True)
class SystemIdentity:
    name: dict
    system_type: dict
    version: dict
    creator: dict
    organization: dict
    purpose: dict
    construction_method: dict
    operational_boundaries: dict
    governing_principles: list
    schema_version: str = '1.0'
    communication_identity: dict | None = None

    def __post_init__(self):
        expected = {'1.0': PRINCIPLES, '1.2': PRINCIPLES_V12}.get(self.schema_version)
        if expected is None or self.governing_principles != list(expected):
            raise ValueError('Protected governing principles must match authority')
        if self.schema_version == '1.2':
            communication = self.communication_identity
            if (type(communication) is not dict or not communication.get('authority_reference')
                    or not communication.get('version') or not communication.get('baseline_character')):
                raise ValueError('Versioned operator-governed communication identity required')
        elif self.communication_identity is not None:
            raise ValueError('Communication identity requires the explicit v1.2 contract')
        for key in ('name', 'system_type', 'version', 'creator', 'organization', 'purpose',
                    'construction_method', 'operational_boundaries'):
            value = getattr(self, key)
            if type(value) is not dict or not value or not value.get('authority_reference'):
                raise ValueError('Explicit identity authority required: ' + key)
            if not IDENTITY_FIELDS.get(key, set()) <= set(value):
                raise ValueError('Incomplete identity contract: ' + key)
        if self.operational_boundaries['runtime_profile'] not in {'PUBLIC', 'INTERNAL'}:
            raise ValueError('Unknown runtime deployment profile')
        strings(self.operational_boundaries['mutable_roots'], 'mutable_roots')
        strings(self.operational_boundaries['protected_paths'], 'protected_paths')
        if not all(self.construction_method.get(k) for k in ('version', 'reference', 'sha256')):
            raise ValueError('Versioned construction method integrity reference required')

    def to_dict(self):
        value = asdict(self)
        if self.schema_version == '1.0':
            value.pop('communication_identity')  # preserve prior approved serialized identity
        return json.loads(json.dumps(value, allow_nan=False))


@dataclass(frozen=True)
class QuickSpecification:
    requested_capability: str
    purpose: str
    required_outcome: str
    known_boundaries: list
    deployment_target: str
    priority: str
    exclusions: list

    def __post_init__(self):
        for key in ('requested_capability', 'purpose', 'required_outcome', 'deployment_target', 'priority'):
            if type(getattr(self, key)) is not str or not getattr(self, key).strip():
                raise ValueError('Unresolved Quick Specification: ' + key)
        strings(self.known_boundaries, 'known_boundaries', True)
        strings(self.exclusions, 'exclusions')

    def to_dict(self):
        return json.loads(json.dumps(asdict(self), allow_nan=False))


@dataclass(frozen=True)
class Capability:
    capability_id: str
    name: str
    category: str
    purpose: str
    description: str
    operator_id: str
    scope: dict
    expected_behavior: list
    authorized_behavior: list
    prohibited_behavior: list
    required_inputs: list
    required_outputs: list
    required_components: list
    dependencies: list
    interfaces: list
    required_chains: list
    chain_relationships: list
    mechanisms: list
    invariants: list
    required_evidence: list
    validation_requirements: list
    authority_requirements: list
    approval_requirements: list
    builder_support: dict
    creation_support: dict
    limitations: list
    failures: list
    evidence_references: list
    version: int
    supersedes: str | None
    declared_state: str = 'DECLARED'
    implementation_state: str = 'UNCONFIRMED'
    integration_state: str = 'UNCONFIRMED'
    validation_state: str = 'UNCONFIRMED'
    operational_state: str = 'UNCONFIRMED'
    rp_state: str = 'PENDING_VALIDATION'
    last_audit_at: str | None = None
    last_validation_at: str | None = None
    schema_version: str = '1.0'

    def __post_init__(self):
        if self.schema_version != '1.0' or type(self.version) is not int or self.version < 1:
            raise ValueError('Unsupported capability version')
        for key in ('capability_id', 'name', 'category', 'purpose', 'description', 'operator_id'):
            if type(getattr(self, key)) is not str or not getattr(self, key).strip():
                raise ValueError('Missing capability identity: ' + key)
        if (type(self.scope) is not dict or self.scope.get('operator_id') != self.operator_id
                or self.scope.get('profile') not in {'PUBLIC', 'INTERNAL'} or not self.scope.get('deployment')):
            raise ValueError('Explicit operator and deployment profile required')
        for key in ('expected_behavior', 'authorized_behavior', 'prohibited_behavior', 'required_inputs',
                    'required_outputs', 'required_components', 'dependencies', 'interfaces', 'required_chains',
                    'invariants', 'required_evidence', 'validation_requirements', 'authority_requirements',
                    'approval_requirements', 'limitations', 'failures', 'evidence_references'):
            strings(getattr(self, key), key)
        for key in ('chain_relationships', 'mechanisms'):
            if type(getattr(self, key)) is not list:
                raise ValueError('Explicit list required: ' + key)
        for key in ('declared_state', 'implementation_state', 'integration_state', 'validation_state', 'operational_state'):
            CapabilityState(getattr(self, key))
        if self.rp_state not in {'CONFIRMED', 'DISCONFIRMED', 'PENDING_VALIDATION'}:
            raise ValueError('Unknown RP verdict')

    def to_dict(self):
        return json.loads(json.dumps(asdict(self), allow_nan=False))

    def declaration(self):
        return {k: v for k, v in self.to_dict().items() if k not in {
            'implementation_state', 'integration_state', 'validation_state', 'operational_state',
            'rp_state', 'last_audit_at', 'last_validation_at', 'evidence_references', 'failures'}}
