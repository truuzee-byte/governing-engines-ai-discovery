"""Explicit, content-bound context admission. Admission is not truth or durability."""
from dataclasses import dataclass, asdict
from copy import deepcopy
from datetime import datetime, timezone
from learning.contracts import digest

OUTCOMES={'ADMITTED','EXCLUDED','BLOCKED','REVIEW_REQUIRED','NOT_APPLICABLE'}
EPHEMERAL={'OPERATOR_INPUT','OPERATOR_PROFILE','THREAD','SESSION','TEMPORAL','RUNTIME','ROUTING','REQUIREMENTS','ORCHESTRATION','SYSTEM_POLICY','MODEL_PROPOSAL'}
GOVERNED={'MEMORY','LEARNING','UNDERSTANDING','KNOWLEDGE','SPECIFICATION','TOOL_RESULT','OBSERVATION','RP_RESULT','GOVERNANCE','RETRIEVED'}
_SEAL=object()

@dataclass(frozen=True)
class RuntimeContextArtifactAdmission:
    artifact_id: str
    artifact_type: str
    owner: str
    source: str
    purpose: str
    classification: str
    authority: str
    validation_state: str
    governance_state: str
    durability_state: str
    lifecycle_state: str
    lineage: tuple
    scope: dict
    freshness: str | None
    policy: str
    decision: str
    reason: str
    surface: str
    content_hash: str

    def to_dict(self):return asdict(self)

class AdmittedPrompt(str):
    def __new__(cls,text,decisions,scope,seal=None,sources=(),support_sources=(),support_loader=None):
        if seal is not _SEAL:raise PermissionError('Prompt must be issued by admission')
        obj=super().__new__(cls,text);obj._binding=digest([text,decisions,scope,list(sources),list(support_sources),id(support_loader) if support_loader else None])
        obj.decisions=deepcopy(decisions);obj.scope=deepcopy(scope)
        obj.sources=deepcopy(list(sources))
        obj.support_sources=deepcopy(list(support_sources))
        obj.support_loader=support_loader
        return obj

def verify(prompt,thread=None):
    if not isinstance(prompt,AdmittedPrompt) or prompt._binding!=digest([str(prompt),prompt.decisions,prompt.scope,prompt.sources,prompt.support_sources,id(prompt.support_loader) if prompt.support_loader else None]):
        raise PermissionError('Unadmitted or modified prompt augmentation')
    if thread is not None and prompt.scope.get('thread_id')!=thread:raise PermissionError('Prompt session mismatch')
    return prompt

class Admission:
    def __init__(self,owner,thread):
        if not owner or not thread:raise ValueError('Context ownership required')
        self.scope={'operator_id':owner,'thread_id':thread};self.decisions=[];self.parts=[];self.sources=[];self.support_sources=[];self.support_loader=None

    def consider(self,kind,identity,content,*,source,owner=None,basis=None,selected=True):
        owner=self.scope['operator_id'] if owner is None else owner;basis=deepcopy(basis or {})
        outcome='ADMITTED';reason='Class policy satisfied'
        if not selected:outcome='NOT_APPLICABLE';reason='Not selected for this context surface'
        elif owner!=self.scope['operator_id']:outcome='BLOCKED';reason='Owner mismatch'
        elif any(basis.get('scope',{}).get(k,v)!=v for k,v in self.scope.items()):
            outcome='BLOCKED';reason='Artifact scope mismatch'
        elif kind not in EPHEMERAL|GOVERNED:outcome='REVIEW_REQUIRED';reason='Unknown artifact class'
        elif kind in EPHEMERAL and basis.get('governance_state','EPHEMERAL_CONTEXT') not in {'EPHEMERAL_CONTEXT','APPROVED'}:
            outcome='REVIEW_REQUIRED';reason='Unknown explicit governance state'
        elif kind in GOVERNED and (basis.get('governance_state')!='APPROVED' or basis.get('verified') is not True or not basis.get('lineage')):
            outcome='EXCLUDED';reason='Verified governed source required'
        elif kind in GOVERNED and (basis.get('classification') not in {'OPERATOR_DATA','RUNTIME_DATA','UNDERSTANDING_DATA','REALITY_DATA','OUTCOME_DATA','LEARNING_DATA','PERSISTENT_DATA'} or
                basis.get('validation_state') not in {'NOT_REQUIRED','OPERATOR_ATTESTED','VALIDATED'} or not basis.get('authority')):
            outcome='REVIEW_REQUIRED';reason='Incomplete governed metadata'
        elif kind in {'LEARNING','RP_RESULT'} and not basis.get('freshness'):
            outcome='REVIEW_REQUIRED';reason='Governed validity boundary required'
        elif basis.get('lifecycle_state','ACTIVE')!='ACTIVE':outcome='EXCLUDED';reason='Inactive artifact'
        if outcome=='ADMITTED' and basis.get('freshness'):
            try:
                deadline=datetime.fromisoformat(basis['freshness'])
                if deadline.tzinfo is None or deadline<=datetime.now(timezone.utc):raise ValueError()
            except (ValueError,TypeError):outcome='EXCLUDED';reason='Expired or malformed validity'
        record=RuntimeContextArtifactAdmission(identity,kind,owner,source,'Current response context',
            basis.get('classification','OPERATOR_DATA' if kind in {'OPERATOR_INPUT','OPERATOR_PROFILE','SESSION'} else 'RUNTIME_DATA' if kind in EPHEMERAL else 'UNKNOWN'),
            basis.get('authority','OPERATOR' if kind in {'OPERATOR_INPUT','OPERATOR_PROFILE','SESSION','THREAD'} else 'RUNTIME'),
            basis.get('validation_state','NOT_REQUIRED' if kind in EPHEMERAL else 'UNKNOWN'),
            basis.get('governance_state','EPHEMERAL_CONTEXT' if kind in EPHEMERAL else 'UNKNOWN'),
            basis.get('durability_state','TRANSIENT'),basis.get('lifecycle_state','ACTIVE'),
            tuple(basis.get('lineage',[source])),{**deepcopy(self.scope),**deepcopy(basis.get('scope',{}))},basis.get('freshness'),
            'RuntimeContextAdmission/1:'+kind,outcome,reason,'reasoning_prompt',digest(content))
        self.decisions.append(record.to_dict())
        if outcome=='ADMITTED':
            self.parts.append(content)
            self.sources.append({'record':record.to_dict(),'content':content})
        return outcome=='ADMITTED'

    def support(self,kind,identity,content,*,source,owner=None,basis=None):
        """Verified evidence-only availability, never rendered semantic context."""
        if kind not in GOVERNED:raise PermissionError('Governed evidence owner required')
        if len(self.support_sources)>=8 or len(content.encode('utf-8'))>8192:
            return False
        gate=Admission(self.scope['operator_id'],self.scope['thread_id'])
        allowed=gate.consider(kind,identity,content,source=source,owner=owner,basis=basis)
        for decision in gate.decisions:
            decision['purpose']='Attribution verification only; not semantic inference'
            if allowed:decision['reason']='PROVENANCE_ONLY_AVAILABLE'
        self.decisions.extend(gate.decisions)
        if allowed:
            row=gate.sources[0];row['record']=gate.decisions[0]
            self.support_sources.append(row)
        return allowed

    def include(self,prompt):
        verify(prompt,self.scope['thread_id'])
        if prompt.scope!=self.scope:raise PermissionError('Context owner mismatch')
        self.decisions.extend(deepcopy(prompt.decisions));self.parts.append(str(prompt))
        self.sources.extend(deepcopy(prompt.sources))
        if prompt.support_loader:
            if self.support_loader is not None and self.support_loader is not prompt.support_loader:
                raise PermissionError('Ambiguous evidence owner')
            self.support_loader=prompt.support_loader
        for row in prompt.support_sources:
            if row not in self.support_sources:
                if len(self.support_sources)>=8:raise PermissionError('Bounded provenance support exceeded')
                self.support_sources.append(deepcopy(row))

    def finish(self):return AdmittedPrompt(''.join(self.parts),self.decisions,self.scope,_SEAL,self.sources,self.support_sources,self.support_loader)

def basis_for_memory(record):
    from persistent_memory.persistent_memory_manager import memory_is_eligible
    return {'verified':memory_is_eligible(record,record.operator_id),'governance_state':record.governance_decision.get('decision','UNKNOWN'),
        'lineage':[record.governance_decision['decision_id']] if record.governance_decision.get('decision_id') else [],
        'validation_state':'OPERATOR_ATTESTED','classification':'PERSISTENT_DATA','authority':'OPERATOR',
        'scope':{'operator_id':record.operator_id,'domain':record.domain.value,
                 'source_thread_id':record.source_thread_id,'source_message_id':record.source_message_id,
                 'record_version':record.version,'previous_version_hash':record.previous_hash,
                 'supersession_state':'CURRENT_RETRIEVED_VERSION'},
        'durability_state':'DURABLE','lifecycle_state':record.status.value,
        'freshness':record.expiration_policy}
