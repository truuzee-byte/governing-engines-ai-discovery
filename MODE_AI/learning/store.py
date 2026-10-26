"""Transactional append-only snapshots, with an operator-bound hash chain."""
from pathlib import Path
import sqlite3
import json
from copy import deepcopy
from collections.abc import Sequence,Mapping
from contextlib import contextmanager
from .contracts import digest, LearningCandidate, LearningRecord

class IntegrityError(ValueError): pass

class _HistoryView(Sequence):
    """Lazy detached snapshots: unused audit history need not be copied."""
    def __init__(self,history):self._rows=tuple(history)
    def __len__(self):return len(self._rows)
    def __getitem__(self,index):return deepcopy(self._rows[index])
    def __eq__(self,other):return list(self)==other

class _StateView(Mapping):
    def __init__(self,state):self._state=dict(state)
    def __iter__(self):return iter(self._state)
    def __len__(self):return len(self._state)
    def __getitem__(self,key):return deepcopy(self._state[key])

def _lineage(kind,value,history):
    from data_governance.learning_governance import candidate_binding
    if kind=='candidate' and value['candidate_status'] in {'ELIGIBLE','APPROVED'}:
        proof=next((h['value'] for h in reversed(history) if h['kind']=='capture_admission' and
            h['value']['candidate_id']==value['candidate_id']),None)
        if not proof or proof['candidate_hash']!=candidate_binding(value):
            raise IntegrityError('Candidate lacks governed capture admission')
    if kind!='record':return
    prior=next((h['value'] for h in reversed(history) if h['kind']=='record' and h['entity']==value['learning_id']),None)
    decision=value.get('lineage',{}).get('governance_decision',{})
    issued=next((h['value'] for h in reversed(history) if h['kind']=='governance' and h['entity']==decision.get('decision_id')),None)
    if not issued or issued!=decision or issued['decision']!='APPROVED':
        raise IntegrityError('Durable Learning lacks issued governance')
    candidate_id=decision.get('lineage',{}).get('new_candidate_id')
    if not candidate_id:
        # Lifecycle reviews retain the most recent admitted revalidation source.
        # Consult verified journal records, never a caller's replacement history.
        candidate_id=next((h['value']['lineage']['governance_decision']['lineage']['new_candidate_id']
            for h in reversed(history) if h['kind']=='record' and h['entity']==value['learning_id'] and
            h['value'].get('lineage',{}).get('governance_decision',{}).get('lineage',{}).get('new_candidate_id')),
            value['originating_candidate_id'])
    candidate=next((h['value'] for h in reversed(history) if h['kind']=='candidate' and h['entity']==candidate_id),None)
    if not candidate:raise IntegrityError('Durable Learning lacks source candidate')
    _lineage('candidate',dict(candidate,candidate_status='APPROVED'),history)
    chain=value['lineage'].get('canonical_v2',{});source=candidate['lineage']['canonical_v2']
    if (value['scope']!=candidate['scope'] or value['candidate_type']!=candidate['candidate_type'] or decision['operator_id']!=value['scope']['operator_id'] or
        decision['scope']!=value['scope'] or not set(candidate['evidence_refs']).issubset(value['evidence']) or
        any(chain.get(k)!=source.get(k) for k in ('rp_complete','observation_complete','understanding_complete',
            'semantic_continuity','reality_validation','outcome_analysis','classification','eligibility'))):
        raise IntegrityError('Durable Learning evidence binding mismatch')
    if value['lesson']!=candidate['claim'] and (not prior or value['lesson']!=prior['lesson']):
        raise IntegrityError('Durable Learning lesson substitution')
    if value['lineage'].get('outcome')!=(prior['lineage'].get('outcome') if prior else candidate['lineage']['outcome']):
        raise IntegrityError('Durable Learning outcome substitution')
    from datetime import datetime
    deadline=value['lineage'].get('revalidate_by')
    if not deadline or datetime.fromisoformat(deadline)>datetime.fromisoformat(candidate['lineage']['outcome']['rp']['authority_valid_until']):
        raise IntegrityError('Learning cannot extend RP validity')
    if prior is None and not decision.get('lineage',{}).get('action'):
        approval=value.get('approval_record',{})
        if (approval.get('operator_id')!=value['scope']['operator_id'] or approval.get('action')!='APPROVE' or
            approval.get('reviewed_hash')!=decision['lineage'].get('candidate_hash') or
            approval.get('reviewed_hash')!=digest(candidate)):
            raise IntegrityError('Learning approval does not bind source candidate')
        if value['learning_id']!='learning:'+digest([candidate['candidate_id'],approval['reviewed_hash']]):
            raise IntegrityError('Learning identity does not bind approval')
    active=value['status']=='APPROVED' and value['revocation_state']=='ACTIVE'
    action=decision.get('lineage',{}).get('action')
    if active and action in {'SUSPEND','DEPRECATE','ARCHIVE','REMOVE','REVOKE'}:
        raise IntegrityError('Inactive governance cannot activate Learning')
    if active and prior and (prior['status']!='APPROVED' or prior['revocation_state']!='ACTIVE'):
        prior_index=max(i for i,h in enumerate(history) if h['kind']=='record' and h['entity']==value['learning_id'])
        decision_index=max(i for i,h in enumerate(history) if h['kind']=='governance' and h['entity']==decision['decision_id'])
        if decision_index<=prior_index:
            raise IntegrityError('Reactivation requires a new governed transition')

class LearningStore:
    def __init__(self,path='runtime_data/learning/learning.sqlite3'):
        self._lineage_verified=set()
        self.path=Path(path);self.path.parent.mkdir(parents=True,exist_ok=True)
        with sqlite3.connect(self.path) as c:
            c.execute('CREATE TABLE IF NOT EXISTS journal (seq INTEGER PRIMARY KEY AUTOINCREMENT, operator TEXT NOT NULL, entity TEXT NOT NULL, kind TEXT NOT NULL, payload TEXT NOT NULL, previous TEXT NOT NULL, checksum TEXT NOT NULL)')
            c.execute('CREATE TABLE IF NOT EXISTS artifact_metadata (checksum TEXT PRIMARY KEY, payload TEXT NOT NULL, metadata_hash TEXT NOT NULL)')

    @contextmanager
    def transaction(self,operator):
        if not isinstance(operator,str) or not operator.strip(): raise ValueError('Operator required')
        c=sqlite3.connect(self.path,timeout=10)
        try:
            c.execute('BEGIN IMMEDIATE')
            state={};previous='';history=[]
            for seq,owner,entity,kind,payload,prior,checksum in c.execute('SELECT * FROM journal WHERE operator=? ORDER BY seq',(operator,)):
                value=json.loads(payload)
                if prior!=previous or checksum!=digest([owner,entity,kind,value,prior]): raise IntegrityError('Learning journal integrity failure')
                if kind=='governance' and any(h['kind']=='governance' and h['entity']==entity for h in history):
                    raise IntegrityError('Governance decision replay')
                if kind in {'candidate','record'}:
                    obj=(LearningCandidate if kind=='candidate' else LearningRecord)(**value)
                    identity=value['candidate_id' if kind=='candidate' else 'learning_id']
                    if obj.scope['operator_id']!=operator or identity!=entity: raise IntegrityError('Learning identity mismatch')
                    if checksum not in self._lineage_verified:
                        _lineage(kind,value,history)
                        self._lineage_verified.add(checksum)
                    state[entity]=value
                metadata=c.execute('SELECT payload,metadata_hash FROM artifact_metadata WHERE checksum=?',(checksum,)).fetchone()
                governed=None
                if metadata:
                    governed=json.loads(metadata[0])
                    if digest(governed)!=metadata[1]:raise IntegrityError('Governed metadata integrity failure')
                    from data_governance.artifact_metadata import GovernedArtifactMetadata
                    GovernedArtifactMetadata.from_dict(governed)
                    expected='LEARNING_DATA' if kind in {'record','candidate'} else 'OUTCOME_DATA' if kind=='outcome_analysis' else 'RUNTIME_DATA'
                    if governed['artifact_id']!=entity or governed['operator_id']!=owner or governed['classification']!=expected:
                        raise IntegrityError('Governed metadata identity/classification mismatch')
                history.append({'entity':entity,'kind':kind,'value':value,'hash':checksum,'governed_metadata':governed})
                previous=checksum
            def write(entity,kind,value):
                nonlocal previous
                checksum=digest([operator,entity,kind,value,previous])
                c.execute('INSERT INTO journal(operator,entity,kind,payload,previous,checksum) VALUES(?,?,?,?,?,?)',
                    (operator,entity,kind,json.dumps(value,sort_keys=True),previous,checksum))
                from data_governance.artifact_metadata import GovernedArtifactMetadata
                decision=value.get('lineage',{}).get('governance_decision',{})
                approved=decision.get('decision')=='APPROVED' or (kind=='governance' and value.get('decision')=='APPROVED')
                status=value.get('status',value.get('candidate_status','PENDING'))
                active=kind=='record' and status=='APPROVED' and approved
                classification='LEARNING_DATA' if kind in {'record','candidate'} else 'OUTCOME_DATA' if kind=='outcome_analysis' else 'RUNTIME_DATA'
                sources=tuple(value.get('evidence',value.get('evidence_refs',[]))) or ('journal:'+previous if previous else 'runtime:Learning',)
                meta=GovernedArtifactMetadata(entity,operator,sources,kind,'Governance' if kind=='governance' else 'Learning',classification,
                    'VALIDATED' if value.get('lineage',{}).get('canonical_v2',{}).get('rp_complete') else 'UNVALIDATED',
                    'APPROVED' if approved else 'REJECTED' if status=='REJECTED' else 'PENDING',
                    'APPROVED' if active else 'ELIGIBLE' if status=='ELIGIBLE' else 'PENDING' if kind=='candidate' else 'INACTIVE' if kind=='record' else 'NOT_APPLICABLE',
                    'DURABLE' if active else 'RETIRED' if kind=='record' else 'CANDIDATE' if kind=='candidate' else 'AUDIT_ONLY',
                    'ACTIVE' if active else 'REMOVED' if status=='REMOVED' else 'ARCHIVED' if status=='ARCHIVED' else 'SUSPENDED' if kind=='record' else 'CANDIDATE',
                    tuple([decision['decision_id']]) if decision.get('decision_id') else ()).to_dict()
                prior=next((h for h in reversed(history) if h['entity']==entity),None)
                if prior and prior['kind']!=kind:raise IntegrityError('Artifact classification cannot silently change')
                c.execute('INSERT INTO artifact_metadata VALUES(?,?,?)',(checksum,json.dumps(meta,sort_keys=True),digest(meta)))
                previous=checksum
                if kind in {'candidate','record'}:state[entity]=value
                history.append({'entity':entity,'kind':kind,'value':value,'hash':checksum,'governed_metadata':meta})
            def append(entity,kind,value,*,capture_runtime=None):
                if kind=='capture_admission':raise PermissionError('Capture admission is internal')
                if kind=='governance':
                    from data_governance.learning_governance import _IssuedGovernance
                    if not isinstance(value,_IssuedGovernance):raise PermissionError('Issued governance required')
                    value.verify()
                    if any(h['kind']=='governance' and h['entity']==entity for h in history):
                        raise IntegrityError('Governance decision replay')
                value=deepcopy(dict(value))
                if kind in {'candidate','record'}:
                    obj=(LearningCandidate if kind=='candidate' else LearningRecord)(**value)
                    if obj.scope['operator_id']!=operator or value['candidate_id' if kind=='candidate' else 'learning_id']!=entity:
                        raise IntegrityError('Learning write identity mismatch')
                if kind=='candidate' and value['candidate_status'] in {'ELIGIBLE','APPROVED'}:
                    from data_governance.learning_governance import candidate_binding,verify_capture
                    proof=next((h['value'] for h in reversed(history) if h['kind']=='capture_admission' and h['value']['candidate_id']==entity),None)
                    if not proof:
                        if capture_runtime is None:raise PermissionError('Governed capture required before eligibility')
                        proof=verify_capture(capture_runtime,value)
                        write('capture:'+entity,'capture_admission',proof)
                _lineage(kind,value,history)
                write(entity,kind,value)
            # Callers may inspect snapshots; mutation of returned dictionaries
            # cannot fabricate the admission history used by append.
            yield _StateView(state),_HistoryView(history),append
            c.commit()
        except Exception:
            c.rollback();raise
        finally:c.close()

    def history(self,operator):
        with self.transaction(operator) as (_,history,_): return list(history)

    def get(self,operator,identity):
        with self.transaction(operator) as (state,_,__): return state.get(identity)
