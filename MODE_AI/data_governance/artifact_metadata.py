"""Governed pipeline metadata. State labels confer no authority."""
from dataclasses import dataclass, asdict, replace
from learning.contracts import digest

STATES = {
    'classification': {'OPERATOR_DATA','RUNTIME_DATA','UNDERSTANDING_DATA','REALITY_DATA','OUTCOME_DATA','LEARNING_DATA','PERSISTENT_DATA'},
    'validation_status': {'NOT_REQUIRED','UNVALIDATED','OPERATOR_ATTESTED','VALIDATED','INVALID','PENDING'},
    'governance_status': {'PENDING','APPROVED','REJECTED','REVOKED'},
    'learning_status': {'NOT_APPLICABLE','PENDING','ELIGIBLE','APPROVED','INACTIVE'},
    'durability_status': {'TRANSIENT','AUDIT_ONLY','CANDIDATE','DURABLE','RETIRED'},
    'lifecycle_status': {'CANDIDATE','ACTIVE','SUSPENDED','ARCHIVED','REMOVED'},
}
FIELD_AUTHORITIES={'validation_status':'RealityPrimacy','governance_status':'Governance','learning_status':'Learning',
    'durability_status':'PersistentMemory','lifecycle_status':'Governance','classification':'DataGovernance'}

@dataclass(frozen=True)
class GovernedArtifactMetadata:
    artifact_id: str
    operator_id: str
    source: tuple
    purpose: str
    authority: str
    classification: str
    validation_status: str
    governance_status: str
    learning_status: str
    durability_status: str
    lifecycle_status: str
    lineage: tuple = ()
    schema_version: str = '2.0'

    def __post_init__(self):
        if self.schema_version!='2.0' or not all(isinstance(v,str) and v.strip() for v in (self.artifact_id,self.operator_id,self.purpose,self.authority)):
            raise ValueError('Incomplete governed metadata')
        if not isinstance(self.source,tuple) or not self.source or not isinstance(self.lineage,tuple) or not all(isinstance(v,str) and v for v in self.source+self.lineage):
            raise ValueError('Explicit source/lineage references required')
        for field, allowed in STATES.items():
            if getattr(self,field) not in allowed:raise ValueError('Unknown '+field)
        if self.durability_status=='DURABLE' and self.governance_status!='APPROVED':raise ValueError('Durability requires governance approval')

    def to_dict(self):return asdict(self)

    @classmethod
    def from_dict(cls,value):
        value=dict(value)
        if not isinstance(value.get('source'),(list,tuple)) or not isinstance(value.get('lineage',()),(list,tuple)):
            raise ValueError('Malformed source/lineage')
        value['source']=tuple(value['source']);value['lineage']=tuple(value.get('lineage',()))
        return cls(**value)

    def transition(self,changes,decision):
        if set(changes)-set(STATES):raise PermissionError('Identity/source/authority changes require a distinct governed artifact')
        if 'classification' in changes and changes['classification']!=self.classification:
            raise PermissionError('Reclassification requires a distinct governed artifact')
        if any(decision.get('lineage',{}).get('field_authorities',{}).get(field)!=FIELD_AUTHORITIES[field] for field in changes):
            raise PermissionError('Owning field authority required')
        if (decision.get('decision')!='APPROVED' or decision.get('operator_id')!=self.operator_id or
            decision.get('subject_id')!=self.artifact_id or decision.get('lineage',{}).get('metadata_hash')!=digest(self.to_dict()) or
            decision.get('lineage',{}).get('metadata_changes')!=changes):
            raise PermissionError('Exact governed metadata transition required')
        return replace(self,**changes,lineage=self.lineage+(decision['decision_id'],))
