"""Governed causal analysis; no truth, Learning or durability decisions."""
from dataclasses import dataclass,asdict
from copy import deepcopy
from learning.contracts import digest,now

@dataclass(frozen=True)
class OutcomeAnalysisRecord:
    analysis_id: str
    operator_id: str
    scope: dict
    outcome_classification: str
    success_analysis: dict
    failure_analysis: dict
    recovery_analysis: dict
    root_cause_state: str
    root_cause: dict
    supporting_evidence: list
    contradicting_evidence: list
    unresolved_causal_conditions: list
    prerequisite_refs: dict
    lineage: dict
    created_at: str
    status: str
    schema_version: str = '2.0'
    def __post_init__(self):
        if self.root_cause_state not in {'PROVEN','SUPPORTED','UNRESOLVED','UNKNOWN'}:raise ValueError('Unknown cause state')
        if self.status not in {'COMPLETE','PENDING'}:raise ValueError('Unknown analysis status')
        if self.root_cause_state in {'PROVEN','SUPPORTED'} and (not self.root_cause or not self.supporting_evidence):
            raise ValueError('Root cause requires structured evidence')
    def to_dict(self):return deepcopy(asdict(self))

class OutcomeAnalysisEngine:
    def analyze(self,*,operator,scope,observation,understanding,validated_reality,measurements,attempt_chain=None):
        refs={'observation_id':observation.get('observation_id'),
              'understanding_id':understanding.get('understanding_id'),
              'rp_decision_id':validated_reality.get('decision_id')}
        unresolved=[];support=[];contradictions=[];cause={};recovery={}
        if attempt_chain is not None:
            if (not attempt_chain or len(attempt_chain) > 2 or
                    any(a.get('attempt_number') != n for n,a in enumerate(attempt_chain,1)) or
                    len({a.get('claim_binding') for a in attempt_chain}) != 1 or
                    len({a.get('specification_hash') for a in attempt_chain}) != 1):
                unresolved.append('Corrective attempt chain incomplete or inconsistent')
        if not all(refs.values()) or not validated_reality.get('completed'):
            unresolved.append('Governed upstream chain incomplete')
        outcome=observation.get('observed_outcome',{}).get('build',{}).get('validation_status','UNKNOWN')
        state='UNKNOWN'
        # A bounded controlled intervention is a supported causal hypothesis,
        # never a universal/proven cause. Measurements must come from RP's
        # validated evidence export, not an operator/model-supplied root string.
        for measurement in measurements:
            check=measurement.get('rp_check',{})
            if check.get('admissible') is not True or (check.get('valid') is not True and check.get('contradiction_detected') is not True):
                unresolved.append('Measurement lacks admitted RP validation');continue
            if measurement.get('rp_check',{}).get('contradiction_detected') is True:
                contradictions.append(measurement['evidence_id']);continue
            contrast=measurement.get('content',{}).get('properties',{}).get('causal_contrast')
            if not isinstance(contrast,dict):continue
            required={'protocol','variable','baseline','intervention','recovery','controls','unresolved'}
            if set(contrast)!=required or contrast['protocol']!='controlled_intervention/1':
                unresolved.append('Unsupported causal evidence protocol');continue
            arms=[contrast[k] for k in ('baseline','intervention','recovery')]
            if (not isinstance(contrast['variable'],str) or not contrast['variable'].strip() or
                not isinstance(contrast['controls'],dict) or not contrast['controls'] or
                any(not isinstance(a,dict) or set(a)!={'input','output','controls'} for a in arms)):
                unresolved.append('Incomplete controlled intervention');continue
            if contrast['unresolved'] or any(a['controls']!=contrast['controls'] for a in arms):
                unresolved.append('Causal controls or alternatives unresolved');continue
            b,i,r=arms
            if b['input']==i['input'] or b!=r:
                unresolved.append('Intervention or recovery not established');continue
            if b['output']==i['output']:
                contradictions.append(measurement['evidence_id']);state='UNRESOLVED';continue
            support.append(measurement['evidence_id'])
            if cause and cause['contrast']!=contrast:
                unresolved.append('Multiple causal explanations require adjudication');continue
            cause={'variable':contrast['variable'],'contrast':deepcopy(contrast),
                   'scope':deepcopy(scope),'method':'controlled_intervention/1',
                   'limits':['Supported within measured controls only','No unmeasured/general causal claim']}
            relational=measurement.get('content',{}).get('properties',{}).get('relational_evidence')
            if relational is not None:
                from learning.relationships import derive
                try:
                    cause['relationship']=derive(contrast,relational,scope)
                except (ValueError,TypeError,KeyError,AttributeError) as exc:
                    unresolved.append('Relational evidence requires review: '+str(exc))
            recovery=deepcopy(r);state='SUPPORTED'
        if contradictions:state='UNRESOLVED';unresolved.append('Contradictory causal measurements')
        if not cause:unresolved.append('Root cause not identified from validated causal evidence')
        if unresolved and state=='SUPPORTED':state='UNRESOLVED'
        payload={'scope':scope,'refs':refs,'cause':cause,'support':support,'contradictions':contradictions,'unresolved':unresolved,
                 'attempt_chain_hash':digest(attempt_chain) if attempt_chain is not None else None}
        return OutcomeAnalysisRecord('outcome-analysis:'+digest(payload),operator,deepcopy(scope),outcome,
            {'observed':outcome=='PASS','source':refs['observation_id']},
            {'observed':outcome=='FAIL','source':refs['observation_id']},recovery,state,cause,support,contradictions,unresolved,refs,
            {'validated_reality':deepcopy(validated_reality),'measurement_hashes':{x['evidence_id']:digest(x) for x in measurements},
             'attempt_chain':deepcopy(attempt_chain)},
            now(),'COMPLETE' if not unresolved and state in {'PROVEN','SUPPORTED'} else 'PENDING')
