"""Bounded build-experience policy. No model, code, specification or policy mutation."""
from copy import deepcopy
from dataclasses import replace
from pathlib import Path
import json
import hashlib
import base64
from uuid import uuid4
from learning.contracts import LearningCandidate, LearningRecord, CandidateType, Status, digest, now, validate_scope


def capture_build(self,runtime,outcome):
    """Called only by the active runtime after build completion; recheck custody."""
    out=deepcopy(outcome);operator=runtime.context.identity.operator_id
    if digest(out)!=digest(runtime.context.build_result):
        raise ValueError('Outcome differs from active runtime result')
    build=out.get('build')
    if not build: return None
    request=out['operator_request']['request']
    scope={'operator_id':operator,'project':request['execution']['repository_target'],
           'domain':out['operator_request']['understanding']['semantic_domain'],'capability':request['system_purpose']}
    validate_scope(scope)
    if out['operator_request']['authorization']['operator_id']!=operator: raise PermissionError('Source operator mismatch')
    observation=runtime.runtime_observation_collector.store.load_record(operator,out['observation_ids'][-1])
    if observation.thread_id!=runtime.context.active_thread.thread_id or observation.observed_outcome.get('build')!=build:
        raise ValueError('Observation/build lineage mismatch')
    governed=out['understanding'];source_id=governed['understanding_id']
    source=runtime.understanding_engine.store.get(operator,source_id,governed['version'])
    if source is None: raise ValueError('Missing canonical Understanding')
    # Consume the completed canonical meaning already governed by the build/RP
    # chain. Reinterpreting the raw build command here creates a different,
    # review-required proposal and cannot establish completion of this meaning.
    understood={'observation_id':observation.observation_id,'source_result':deepcopy(governed['result']),
                'mode':'GOVERNED_SOURCE_LINK','understanding_id':source_id}
    root=Path(build['artifact_root']).resolve()
    receipt_path=Path(build['receipt_path']).resolve()
    if not receipt_path.is_relative_to(root): raise ValueError('Receipt outside artifact scope')
    receipt=json.loads(receipt_path.read_text(encoding='utf-8'))
    checks=build['validation_results'];unresolved=[]
    if (receipt.get('build_id')!=build['build_id'] or receipt.get('final_status')!=build['validation_status'] or
        receipt.get('validation_results')!=checks): raise ValueError('Receipt/build mismatch')
    integrity=[c for c in checks if c.get('validation_type')=='final_artifact_integrity']
    if len(integrity)!=1 or integrity[0]['state']!='PASSED': unresolved.append('Final integrity not established')
    else:
        for path,expected in {**integrity[0]['final_hashes'],**integrity[0].get('final_obligation_hashes',{})}.items():
            target=(root/path).resolve()
            if not target.is_relative_to(root): raise ValueError('Evidence path escape')
            actual=hashlib.sha256(target.read_bytes()).hexdigest() if target.is_file() else 'DIRECTORY' if target.is_dir() else None
            if actual!=expected: unresolved.append('Artifact changed since validation: '+path)
    if observation.collection_errors: unresolved.append('Observation collection incomplete')
    for field in ('observed_outcome','validation_results','produced_receipts'):
        if not getattr(observation,field,None): unresolved.append('Missing observation evidence: '+field)
    failures=[c for c in checks if c.get('state')=='FAILED']
    success=build['validation_status']=='PASS'
    rp=out.get('rp',{});rp_claim=None
    if success:
        if not checks or any(c.get('state')!='PASSED' for c in checks): unresolved.append('Unresolved build contract')
        try:
            if rp.get('rp_state') not in {'CONFIRMED','DISCONFIRMED'}: raise ValueError('RP adjudication required')
            if rp['rp_state']=='CONFIRMED' and not rp.get('accepted'):raise ValueError('RP confirmation not accepted')
            from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey
            from integration.reality_primacy import digest as rp_digest
            client=runtime.reality_acceptance_client;reply=rp['response'];req=rp['request']
            if req['request_id'] not in client._used: raise ValueError('RP result was not consumed by runtime')
            Ed25519PublicKey.from_public_bytes(client._keys[reply['key_id']]).verify(
                base64.b64decode(reply['signature'],validate=True),bytes.fromhex(rp_digest(reply['body'])))
            if reply['body']['request_hash']!=rp_digest(req): raise ValueError('RP request changed')
            if reply['body']['show_chain']['structured']['final_state']!=rp['rp_state']:raise ValueError('RP state changed')
            if observation.observed_outcome.get('rp')!=rp: raise ValueError('RP Observation lineage mismatch')
            rp_claim=req['evaluation']['resolution']['claim_snapshot']
        except Exception as exc: unresolved.append('RP evidence unavailable: '+str(exc))
    elif build['validation_status']!='FAIL' or not failures:
        unresolved.append('No established bounded failure')
    contradicted=success and rp.get('rp_state')=='DISCONFIRMED'
    kind='EXECUTION_SUCCESS' if success and not contradicted else 'OBLIGATION_FAILURE' if any(c.get('obligation') for c in failures) else 'VALIDATION_FAILURE'
    claim={'statement':'Declared contract satisfied in this captured execution' if success else 'Recorded checks failed in this captured execution',
           'build_id':build['build_id'],'spec_id':build['spec_id'],'contract_hash':digest(request),
           'failed_checks':failures,'rp_claim':rp_claim,'generalization':'NONE','execution_authority':False}
    if contradicted:claim['statement']='External RP disconfirmed its exact claim in this captured execution'
    claim['rp_state']=rp.get('rp_state')
    lineage={'outcome':out,'observation':observation.to_dict(),'understanding_source':source.to_dict() if hasattr(source,'to_dict') else governed,
             'understanding_processing':understood,'receipt':receipt,'contradicts':[]}
    from integration.learning_prerequisites import prepare_chain
    canonical=prepare_chain(runtime,out,observation,source,governed,scope)
    lineage['canonical_v2']=canonical
    claim['learning_recommendation']=canonical['classification']['recommendation']
    unresolved.extend(canonical['blocked_reasons'])
    identity='candidate:'+digest([operator,build['build_id'],digest(claim)])
    ids=[source_id]
    candidate=LearningCandidate(identity,kind,claim,scope,out['observation_ids'],list(dict.fromkeys(ids)),build['build_id'],build['spec_id'],
        rp.get('decision_id'),list(dict.fromkeys(build['evidence_references']+[build['receipt_path']])),lineage,
        'active_runtime:validated_build_capture','UNESTABLISHED' if unresolved else 'BOUNDED_CAPTURE',unresolved,
        'RP_DISCONFIRMED' if contradicted else build['validation_status'],'UNESTABLISHED' if unresolved else 'VALIDATED_CAPTURE',now())
    with self.store.transaction(operator) as (state,_,append):
        if identity in state:return state[identity]
        append(canonical['outcome_analysis']['analysis_id'],'outcome_analysis',canonical['outcome_analysis'])
        if not unresolved and rp_claim:
            for old in state.values():
                old_claim=old.get('lesson',{}).get('rp_claim') or {}
                if ('learning_id' in old and old['status']=='APPROVED' and old['scope']==scope and
                    old_claim.get('claim_text')==rp_claim.get('claim_text') and
                    old['lesson'].get('rp_state') in {'CONFIRMED','DISCONFIRMED'} and
                    old['lesson']['rp_state']!=rp.get('rp_state')):
                    candidate.lineage['contradicts'].append({'learning_id':old['learning_id'],
                        'reason':'Opposing scoped RP outcomes; temporal/context adjudication required',
                        'evidence_refs':candidate.evidence_refs})
        append(identity,'candidate',candidate.to_dict())
        candidate=replace(candidate,candidate_status='PENDING_VALIDATION' if unresolved else 'ELIGIBLE')
        append(identity,'candidate',candidate.to_dict(),capture_runtime=runtime)
    return candidate.to_dict()

