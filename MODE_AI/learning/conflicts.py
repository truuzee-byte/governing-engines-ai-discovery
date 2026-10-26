"""Explicit, version-bound conflict adjudication; no inferred semantic merge."""
from copy import deepcopy
from learning.contracts import digest,now
from data_governance.learning_governance import GovernanceDecision,POLICY

def resolve(manager,owner,left_id,right_id,left_hash,right_hash,action):
    actions={'MAINTAIN_EXISTING','SUPERSEDE','REPLACE','MERGE_COMPATIBLE','COEXIST','SUSPEND_BOTH','REQUEST_ADDITIONAL_EVIDENCE'}
    if action not in actions or left_id==right_id:raise ValueError('Invalid conflict request')
    with manager.store.transaction(owner) as (state,_,append):
        left=deepcopy(state[left_id]);right=deepcopy(state[right_id])
        if digest(left)!=left_hash or digest(right)!=right_hash:raise ValueError('Stale conflict review')
        if not all(manager._canonical_active(v) for v in (left,right)):raise PermissionError('Active governed records required')
        if action=='COEXIST' and left['scope']==right['scope']:raise PermissionError('Coexistence requires differentiated scope')
        if action not in {'COEXIST','SUSPEND_BOTH','REQUEST_ADDITIONAL_EVIDENCE'} and left['scope']!=right['scope']:
            raise PermissionError('Replacement/merge requires exact matching scope')
        decision=GovernanceDecision('governance:'+digest([left_hash,right_hash,action,now()]),left_id,owner,'APPROVED',left['scope'],POLICY,
            list(dict.fromkeys(left['evidence']+right['evidence'])),left['lineage']['canonical_v2']['outcome_analysis']['prerequisite_refs'],now(),
            {'action':action,'sources':[left_id,right_id],'source_hashes':[left_hash,right_hash]}).to_dict()
        changed=[]
        if action=='MERGE_COMPATIBLE':
            a=left['lineage']['canonical_v2'];b=right['lineage']['canonical_v2']
            if ((left['lesson'].get('rp_claim') or {}).get('claim_text')!=(right['lesson'].get('rp_claim') or {}).get('claim_text') or
                a['outcome_analysis']['root_cause']!=b['outcome_analysis']['root_cause']):
                raise PermissionError('Semantic compatibility not established; request additional evidence')
            merged=deepcopy(left);merged['learning_id']='learning:'+digest([left_hash,right_hash,action])
            merged['lineage'].pop('dependency_graph',None)
            decision['subject_id']=merged['learning_id'];merged['lineage']['governance_decision']=decision
            merged['lineage']['merge_sources']=deepcopy([left,right]);merged['evidence']=decision['evidence_refs']
            merged['supersedes']=[left_id,right_id];merged['updated_at']=now()
            from learning.canonical import confidence
            merged['lineage']['canonical_v2']['confidence']=confidence(a['confidence']['supporting']+b['confidence']['supporting'],
                a['confidence']['contradicting']+b['confidence']['contradicting'],a['confidence']['history']+b['confidence']['history'])
            changed.append(merged)
            for old in (left,right):old.update(status='SUPERSEDED',superseded_by=merged['learning_id'])
        elif action in {'SUPERSEDE','REPLACE'}:
            left.update(status='SUPERSEDED',superseded_by=right_id);right['supersedes']=list(dict.fromkeys(right['supersedes']+[left_id]))
        elif action=='MAINTAIN_EXISTING':right.update(status='SUSPENDED',revocation_state='SUSPENDED')
        elif action in {'SUSPEND_BOTH','REQUEST_ADDITIONAL_EVIDENCE'}:
            for record in (left,right):record.update(status='SUSPENDED',revocation_state='SUSPENDED')
        for record in (left,right):
            record['lineage'].setdefault('conflict_decisions',[]).append(decision);record['updated_at']=now();changed.append(record)
        append(decision['decision_id'],'governance',GovernanceDecision(**decision).issued())
        for record in changed:append(record['learning_id'],'record',record)
    return {'decision':decision,'records':changed,'resolution_state':'PENDING' if action=='REQUEST_ADDITIONAL_EVIDENCE' else 'RESOLVED'}
