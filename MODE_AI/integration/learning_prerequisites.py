"""Governed artifact adapter. Verification belongs here, not in Learning."""
import base64
from copy import deepcopy
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey
from integration.reality_primacy import digest
from outcome_analysis import OutcomeAnalysisEngine
from data_governance.learning_governance import POLICY


def prepare_chain(runtime,out,observation,source,governed,scope):
    blocked=[];rp=out.get('rp',{});measurements=[];reality={'completed':False}
    continuity='UNKNOWN';semantic_ref=None
    try:
        client=runtime.reality_acceptance_client;req=rp['request'];reply=rp['response']
        Ed25519PublicKey.from_public_bytes(client._keys[reply['key_id']]).verify(
            base64.b64decode(reply['signature'],validate=True),bytes.fromhex(digest(reply['body'])))
        body=reply['body'];data=body['show_chain']['structured']
        if (req['request_id'] not in client._used or body['request_hash']!=digest(req) or
            body['show_chain']['status']!='VERIFIED' or data['final_state']!=rp['rp_state'] or
            rp['rp_state'] not in {'CONFIRMED','DISCONFIRMED'} or data['scope']!=req['scope'] or
            req['scope']['operator_id']!=scope['operator_id']):raise ValueError('Reality chain incomplete')
        # Mode already accepted/recorded the temporal boundary; retain it, never
        # renew an old result by changing timestamps or replaying a receipt.
        if not rp.get('acceptance_checked_at') or not rp.get('authority_valid_until'):raise ValueError('Acceptance time absent')
        from datetime import datetime
        if datetime.fromisoformat(rp['acceptance_checked_at'])>datetime.fromisoformat(rp['authority_valid_until']):raise ValueError('Expired acceptance')
        claim=data['source_decision']['chain']['provenance']['input_snapshots']['resolution']['claim_snapshot']
        if digest(claim)!=digest(req['evaluation']['resolution']['claim_snapshot']):raise ValueError('Claim substitution')
        if digest(governed)!=digest(claim['source_understanding']):raise ValueError('Governed Understanding substitution')
        from pathlib import Path
        signed_scope=req['scope']
        scope_matches=(all(signed_scope.get(k)==v for k,v in scope.items()) if 'project' in signed_scope else
            str(Path(signed_scope['artifact_root']).resolve())==str(Path(scope['project']).resolve()) and
            scope['domain']==source.semantic_domain and scope['capability']==claim['source_specification']['structure']['system_purpose'])
        if not scope_matches:
            raise ValueError('Learning scope exceeds signed evidence scope')
        from understanding.understanding_record import UnderstandingRecord,digest as semantic_hash
        from understanding.meaning_continuity_validator import MeaningContinuityValidator
        snapshot=UnderstandingRecord.from_dict(claim['source_understanding']['result']['final_understanding'])
        comparison=MeaningContinuityValidator().validate(source,snapshot)
        if semantic_hash(source)!=claim['source_understanding']['understanding_hash']:raise ValueError('Semantic snapshot mismatch')
        semantic_ref=source.understanding_id
        if comparison.continuity_preserved and not comparison.requires_review and not comparison.meaning_changed:
            continuity='STABLE'
        reality={'completed':True,'decision_id':rp['decision_id'],'claim_id':req['claim_id'],'scope':deepcopy(req['scope']),
                 'state':rp['rp_state'],'receipt_id':rp['receipt_id'],'acceptance_checked_at':rp['acceptance_checked_at']}
        batch=req['evaluation']['batch']
        admitted={x.get('evidence_id'):x for x in batch['checks'] if x.get('admissible') is True and (x.get('valid') is True or x.get('contradiction_detected') is True)}
        measurements=[{**deepcopy(e),'rp_check':deepcopy(admitted[e['evidence_id']])} for e in batch['evidence_snapshots'] if e['evidence_id'] in admitted]
    except Exception as exc:blocked.append('Reality/semantic prerequisite: '+str(exc))
    obs=observation.to_dict()
    observation_complete=not observation.collection_errors and all(getattr(observation,k,None) for k in ('observed_outcome','validation_results','produced_receipts'))
    result=governed.get('result',{})
    understanding_complete=bool(source and semantic_ref and governed.get('contract')=='GovernedUnderstanding/1.2' and
        result.get('final_understanding') and result.get('review_required') is False and not result.get('errors'))
    analysis=OutcomeAnalysisEngine().analyze(operator=scope['operator_id'],scope=scope,observation=obs,
        understanding={'understanding_id':semantic_ref if understanding_complete else None},validated_reality=reality,
        measurements=measurements,attempt_chain=out.get('attempts')).to_dict()
    if not observation_complete:blocked.append('Observation incomplete')
    if not understanding_complete:blocked.append('Understanding incomplete')
    if continuity not in {'STABLE','RESTORED'}:blocked.append('Semantic continuity not STABLE/RESTORED')
    if analysis['status']!='COMPLETE':blocked.extend(analysis['unresolved_causal_conditions'])
    from learning.canonical import eligibility,classify,confidence
    eligible=eligibility(observation_complete=observation_complete,understanding_complete=understanding_complete,
        rp_complete=reality['completed'],semantic_continuity=continuity,analysis=analysis)
    classification=classify(analysis,measurements if eligible['status']=='ELIGIBLE' else [])
    support=confidence(analysis['supporting_evidence'],analysis['contradicting_evidence'])
    if not classification['dimensions']:blocked.append('No supported Learning dimension')
    from data_governance.artifact_metadata import GovernedArtifactMetadata
    metadata={}
    for name,identity,authority,category,status in (
        ('observation',observation.observation_id,'RuntimeObservation','RUNTIME_DATA','UNVALIDATED'),
        ('understanding',semantic_ref,'SemanticCustody','UNDERSTANDING_DATA','NOT_REQUIRED'),
        ('reality',reality.get('decision_id'),'RealityPrimacy','REALITY_DATA','VALIDATED' if reality['completed'] else 'PENDING'),
        ('outcome_analysis',analysis['analysis_id'],'OutcomeAnalysis','OUTCOME_DATA','NOT_REQUIRED')):
        if identity:metadata[name]=GovernedArtifactMetadata(identity,scope['operator_id'],(identity,),
            'Governed Learning input: '+name,authority,category,status,'PENDING','NOT_APPLICABLE','AUDIT_ONLY','CANDIDATE').to_dict()
    return {'policy':POLICY,'observation_complete':observation_complete,'understanding_complete':understanding_complete,
        'rp_complete':reality['completed'],'semantic_continuity':continuity,'semantic_reference':semantic_ref,
        'reality_validation':reality,'outcome_analysis':analysis,'classification':classification,
        'eligibility':eligible,'confidence':support,'artifact_metadata':metadata,'blocked_reasons':list(dict.fromkeys(blocked))}
