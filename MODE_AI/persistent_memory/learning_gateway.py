"""Governance-approved Learning exports; distinct from ordinary operator memory."""
from pathlib import Path
import sqlite3
import json
from learning.contracts import digest,now
from data_governance.learning_governance import POLICY

class LearningMemoryGateway:
    def __init__(self,path,source_loader):
        self.path=Path(path);self.source_loader=source_loader
        self.path.parent.mkdir(parents=True,exist_ok=True)
        with sqlite3.connect(self.path) as db:
            db.execute('CREATE TABLE IF NOT EXISTS learning_versions (operator TEXT, learning_id TEXT, version INTEGER, payload TEXT, checksum TEXT, PRIMARY KEY(operator,learning_id,version))')

    def _source(self,operator,identity):
        if not isinstance(identity,str):raise PermissionError('Canonical Learning identity required; raw data rejected')
        record=self.source_loader(operator,identity)
        if not record or record.get('scope',{}).get('operator_id')!=operator or record.get('learning_id')!=identity:
            raise PermissionError('Unknown or cross-operator Learning')
        decision=record.get('lineage',{}).get('governance_decision',{})
        chain=record.get('lineage',{}).get('canonical_v2',{})
        if (decision.get('decision')!='APPROVED' or decision.get('policy_basis')!=POLICY or
            decision.get('subject_id') not in {record['originating_candidate_id'],identity} or decision.get('operator_id')!=operator or
            decision.get('scope')!=record['scope'] or set(decision.get('prerequisite_refs',{}))!={'observation_id','understanding_id','rp_decision_id'} or not all(decision['prerequisite_refs'].values()) or
            not decision.get('evidence_refs') or not set(decision['evidence_refs']).issubset(record.get('evidence',[])) or
            chain.get('outcome_analysis',{}).get('status')!='COMPLETE' or not record.get('evidence')):
            raise PermissionError('Governance or lineage inadmissible')
        return record

    def publish(self,operator,identity):
        record=self._source(operator,identity)
        payload={'memory_type':'GOVERNED_LEARNING_EXPORT','operator_id':operator,'learning_id':identity,
            'scope':record['scope'],'lesson':record['lesson'],'source_hash':digest(record),
            'governance_decision_id':record['lineage']['governance_decision']['decision_id'],
            'lineage':record['lineage']['canonical_v2'],'status':record['status'],'timestamp':now()}
        with sqlite3.connect(self.path,timeout=10) as db:
            db.execute('BEGIN IMMEDIATE')
            row=db.execute('SELECT version,payload,checksum FROM learning_versions WHERE operator=? AND learning_id=? ORDER BY version DESC LIMIT 1',(operator,identity)).fetchone()
            if row:
                old=json.loads(row[1])
                if digest(old)!=row[2]:raise ValueError('Memory integrity failure')
                if old['source_hash']==payload['source_hash']:return old
            version=1 if not row else row[0]+1
            payload['version']=version
            payload['previous_hash']=row[2] if row else None
            db.execute('INSERT INTO learning_versions VALUES(?,?,?,?,?)',(operator,identity,version,json.dumps(payload,sort_keys=True),digest(payload)))
        return payload

    def available(self,operator,identity):
        try:record=self._source(operator,identity)
        except PermissionError:return False
        if record['status']!='APPROVED' or record['revocation_state']!='ACTIVE':return False
        from datetime import datetime,timezone
        deadline=record.get('lineage',{}).get('revalidate_by')
        if not deadline or datetime.fromisoformat(deadline)<=datetime.now(timezone.utc):return False
        with sqlite3.connect(self.path) as db:
            rows=db.execute('SELECT payload,checksum FROM learning_versions WHERE operator=? AND learning_id=? ORDER BY version',(operator,identity)).fetchall()
        previous=None;last=None
        for raw,checksum in rows:
            payload=json.loads(raw)
            if digest(payload)!=checksum or payload['previous_hash']!=previous:raise ValueError('Memory lineage integrity failure')
            if payload['operator_id']!=operator or payload['learning_id']!=identity:raise ValueError('Memory identity mismatch')
            previous=checksum;last=payload
        return bool(last and last['status']=='APPROVED' and last['source_hash']==digest(record))

    def history(self,operator,identity):
        with sqlite3.connect(self.path) as db:
            rows=db.execute('SELECT payload,checksum FROM learning_versions WHERE operator=? AND learning_id=? ORDER BY version',(operator,identity)).fetchall()
        previous=None;values=[]
        for raw,checksum in rows:
            value=json.loads(raw)
            if digest(value)!=checksum or value['previous_hash']!=previous:raise ValueError('Memory export history integrity failure')
            previous=checksum;values.append(value)
        return values
