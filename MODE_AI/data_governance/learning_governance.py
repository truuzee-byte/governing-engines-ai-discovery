"""v2.0 admissibility artifacts; operator approval cannot supply prerequisites."""
from dataclasses import dataclass,asdict
from learning.contracts import digest,now

POLICY='MODE Data & Learning Governance v2.2 — 2026-09-27'

_ISSUER=object()

class _IssuedGovernance(dict):
    """Transient issuance binding; serialized dictionaries cannot issue decisions."""
    def __init__(self,value,issuer=None):
        if issuer is not _ISSUER:raise PermissionError('Governance issuance required')
        super().__init__(value);self._hash=digest(value)
    def verify(self):
        if digest(self)!=self._hash:raise PermissionError('Governance decision changed')
    def __deepcopy__(self,memo):
        from copy import deepcopy
        return deepcopy(dict(self),memo)

@dataclass(frozen=True)
class GovernanceDecision:
    decision_id: str
    subject_id: str
    operator_id: str
    decision: str
    scope: dict
    policy_basis: str
    evidence_refs: list
    prerequisite_refs: dict
    timestamp: str
    lineage: dict
    def to_dict(self):return asdict(self)
    def issued(self):return _IssuedGovernance(self.to_dict(),_ISSUER)

def candidate_binding(value):
    """Immutable evidence identity; lifecycle/review annotations are separate."""
    value=dict(value);value['lineage']=dict(value['lineage']);value.pop('candidate_status',None)
    for key in ('governance_decision','contradicts','revalidate_by','review','reviews'):
        value['lineage'].pop(key,None)
    return digest(value)

def verify_capture(runtime,candidate):
    """Re-evaluate existing governed prerequisites at the storage boundary."""
    from integration.learning_prerequisites import prepare_chain
    owner=candidate['scope']['operator_id'];lineage=candidate['lineage'];out=lineage['outcome']
    if runtime.context.identity.operator_id!=owner:raise PermissionError('Capture owner mismatch')
    rp=out['rp'];client=runtime.reality_acceptance_client
    result=client.verify_response(rp['request'],rp['response'])
    if (result['rp_state'] not in {'CONFIRMED','DISCONFIRMED'} or
        result['rp_state']!=rp['rp_state'] or result['decision_id']!=candidate['source_rp_decision_id']):
        raise PermissionError('Final RP capture required')
    governed=out['understanding']
    source=runtime.understanding_engine.store.get(owner,governed['understanding_id'],governed['version'])
    observation=runtime.runtime_observation_collector.store.load_record(owner,candidate['source_observation_ids'][-1])
    if lineage['observation']!=observation.to_dict():raise PermissionError('Observation custody mismatch')
    chain=prepare_chain(runtime,out,observation,source,governed,candidate['scope'])
    def stable(v):
        if isinstance(v,dict):return {k:stable(x) for k,x in v.items() if k not in {'created_at','timestamp'}}
        if isinstance(v,(list,tuple)):return [stable(x) for x in v]
        return v
    if chain['blocked_reasons'] or stable(chain)!=stable(lineage['canonical_v2']):
        raise PermissionError('Outcome Analysis/eligibility differs from governed evidence')
    claim=candidate['claim'];snapshot=rp['request']['evaluation']['resolution']['claim_snapshot']
    if (claim.get('rp_claim')!=snapshot or claim.get('rp_state')!=result['rp_state'] or
        claim.get('execution_authority',False) is not False or
        claim.get('learning_recommendation')!=chain['classification']['recommendation'] or
        candidate['source_understanding_ids']!=[source.understanding_id]):
        raise PermissionError('Learning claim or dimension substitution')
    authority=candidate['authority_source']
    if authority not in {'active_runtime:validated_build_capture','governed_interaction'}:
        raise PermissionError('Unknown governed capture source')
    build=out.get('build') if authority=='active_runtime:validated_build_capture' else None
    if authority=='active_runtime:validated_build_capture' and not build:
        raise PermissionError('Build capture requires an execution outcome')
    if authority=='governed_interaction' and (candidate['source_build_id'] is not None or candidate['source_spec_id'] is not None):
        raise PermissionError('Interaction capture cannot claim build identity')
    if build:
        failures=[check for check in build['validation_results'] if check.get('state')=='FAILED']
        success=build['validation_status']=='PASS';contradicted=success and rp['rp_state']=='DISCONFIRMED'
        statement=('External RP disconfirmed its exact claim in this captured execution' if contradicted else
            'Declared contract satisfied in this captured execution' if success else
            'Recorded checks failed in this captured execution')
        expected_claim={'statement':statement,'build_id':build['build_id'],'spec_id':build['spec_id'],
            'contract_hash':digest(out['operator_request']['request']),'failed_checks':failures,
            'rp_claim':snapshot,'generalization':'NONE','execution_authority':False,
            'rp_state':rp['rp_state'],'learning_recommendation':chain['classification']['recommendation']}
        if candidate['source_build_id']!=build['build_id'] or candidate['source_spec_id']!=build['spec_id']:
            raise PermissionError('Learning execution identity mismatch')
        expected_type=('EXECUTION_SUCCESS' if success and not contradicted else
            'OBLIGATION_FAILURE' if any(check.get('obligation') for check in failures) else 'VALIDATION_FAILURE')
    else:
        expected_claim={'statement':'Bounded governed interaction improvement','rp_claim':snapshot,
            'rp_state':rp['rp_state'],'learning_recommendation':chain['classification']['recommendation'],
            'generalization':'NONE','execution_authority':False}
        expected_type={'CORRECTNESS':'INTERPRETATION_CORRECTION','OPERATOR':'OPERATOR_CORRECTION',
            'OUTCOME':'EXECUTION_SUCCESS','SYSTEM':'CAPABILITY_GAP'}[chain['classification']['dimensions'][0]]
    if claim!=expected_claim:raise PermissionError('Learning claim differs from captured outcome')
    if candidate['candidate_type']!=expected_type:raise PermissionError('Learning classification differs from outcome')
    expected=(list(dict.fromkeys(build['evidence_references']+[build['receipt_path']])) if build
        else list(chain['outcome_analysis']['supporting_evidence']))
    if candidate['evidence_refs']!=expected:raise PermissionError('Evidence references differ from capture')
    if prerequisites(candidate):raise PermissionError('Incomplete governed candidate')
    return {'candidate_id':candidate['candidate_id'],'candidate_hash':candidate_binding(candidate),
        'rp_decision_id':result['decision_id'],'rp_receipt_id':result['receipt_id'],
        'outcome_analysis_id':chain['outcome_analysis']['analysis_id']}

def prerequisites(candidate):
    chain=candidate.get('lineage',{}).get('canonical_v2',{})
    reasons=[]
    for name in ('observation_complete','understanding_complete','rp_complete'):
        if chain.get(name) is not True:reasons.append(name+' not established')
    if chain.get('semantic_continuity') not in {'STABLE','RESTORED'}:reasons.append('Semantic continuity unresolved')
    analysis=chain.get('outcome_analysis',{})
    if (analysis.get('status')!='COMPLETE' or analysis.get('root_cause_state') not in {'PROVEN','SUPPORTED'} or
        not analysis.get('root_cause') or not analysis.get('supporting_evidence') or analysis.get('unresolved_causal_conditions')):
        reasons.append('Outcome Analysis/root cause incomplete')
    if chain.get('policy')!=POLICY:reasons.append('Canonical policy missing')
    if not chain.get('classification',{}).get('dimensions'):reasons.append('Learning classification missing')
    if chain.get('confidence',{}).get('state') not in {'SUPPORTED','CORROBORATED'}:reasons.append('Learning confidence unsupported')
    from datetime import datetime,timezone
    try:
        deadline=candidate['lineage']['outcome']['rp']['authority_valid_until']
        if datetime.fromisoformat(deadline)<=datetime.now(timezone.utc):reasons.append('Fresh revalidation required')
    except (KeyError,TypeError,ValueError):reasons.append('Revalidation boundary unavailable')
    reasons.extend(candidate.get('unresolved_states',[]))
    return list(dict.fromkeys(reasons))

def decide(candidate,operator,approved):
    reasons=prerequisites(candidate)
    if candidate['scope']['operator_id']!=operator:reasons.append('Operator mismatch')
    if not approved:reasons.append('Operator rejected durability')
    chain=candidate.get('lineage',{}).get('canonical_v2',{})
    refs=chain.get('outcome_analysis',{}).get('prerequisite_refs',{})
    stamp=now();subject=candidate['candidate_id']
    return GovernanceDecision('governance:'+digest([subject,digest(candidate),approved,stamp]),subject,operator,
        'APPROVED' if not reasons else 'REJECTED',candidate['scope'],POLICY,candidate['evidence_refs'],refs,stamp,
        {'candidate_hash':digest(candidate),'reasons':reasons,'outcome_analysis_id':chain.get('outcome_analysis',{}).get('analysis_id')})
