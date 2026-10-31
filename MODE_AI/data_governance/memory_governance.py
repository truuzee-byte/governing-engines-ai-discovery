"""Ordinary memory approval preserves operator attestation, never RP truth."""
from .learning_governance import GovernanceDecision,POLICY
from .artifact_metadata import GovernedArtifactMetadata
from learning.contracts import digest,now

def memory_payload(record):
    data=record.to_dict()
    return {k:v for k,v in data.items() if k not in {'version','previous_hash','governance_decision','governed_metadata'}}

def approve_memory(record,operator,action,confirmation):
    from persistent_memory.persistent_memory_record import classify_memory_consent
    from persistent_memory.operator_requests import bound_create_authorization,removal_matches
    explicit=(classify_memory_consent(confirmation)=='APPROVED' or
        action=='CREATE' and bound_create_authorization(confirmation,record.evidence.original_operator_statement,record.content) or
        action=='REMOVE' and removal_matches(confirmation,record.content))
    if record.operator_id!=operator or not explicit:
        raise PermissionError('Explicit owner authorization required')
    if record.evidence.metadata.get('source_kind','OPERATOR_DECLARATION')!='OPERATOR_DECLARATION':
        raise PermissionError('Raw upstream artifacts require their own governed admission path')
    if not all((record.source_thread_id,record.source_message_id,record.evidence.original_operator_statement,record.content)):
        raise PermissionError('Source custody incomplete')
    refs=[record.source_thread_id,record.source_message_id]
    payload_hash=digest(memory_payload(record))
    decision=GovernanceDecision('governance:'+digest([record.memory_id,payload_hash,action,now()]),record.memory_id,operator,
        'APPROVED',{'operator_id':operator,'domain':record.domain.value},POLICY,refs,
        {'source_message_id':record.source_message_id},now(),{'action':action,'payload_hash':payload_hash,
        'validation':'OPERATOR_ATTESTED','truth_claim':False,'operator_confirmation':confirmation,
        'rp_state':'PENDING_VALIDATION','material_claim_admitted':False}).to_dict()
    record.governance_decision=decision
    record.governed_metadata=GovernedArtifactMetadata(record.memory_id,operator,tuple(refs),'Operator continuity',
        'operator:'+operator,'PERSISTENT_DATA','OPERATOR_ATTESTED','APPROVED','NOT_APPLICABLE',
        'DURABLE' if record.status.value=='ACTIVE' else 'RETIRED',
        record.status.value if record.status.value in {'ACTIVE','ARCHIVED','REMOVED'} else 'SUSPENDED',
        (decision['decision_id'],)).to_dict()
    decision['lineage']['metadata_hash']=digest(record.governed_metadata)
    return record

def admissible(record):
    d=record.governance_decision
    return bool(d.get('decision')=='APPROVED' and d.get('subject_id')==record.memory_id and
        d.get('operator_id')==record.operator_id and d.get('policy_basis')==POLICY and
        d.get('lineage',{}).get('payload_hash')==digest(memory_payload(record)) and
        d.get('lineage',{}).get('validation')=='OPERATOR_ATTESTED' and record.governed_metadata and
        d.get('lineage',{}).get('metadata_hash')==digest(record.governed_metadata))
