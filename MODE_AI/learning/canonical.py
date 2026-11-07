"""Evidence-derived classification/support. No truth or authority inference."""
from .contracts import now
DIMENSIONS={'CORRECTNESS','OUTCOME','OPERATOR','SYSTEM'}

def eligibility(*,observation_complete,understanding_complete,rp_complete,semantic_continuity,analysis):
    reasons=[]
    for name,value in [('Observation',observation_complete),('Understanding',understanding_complete),('Reality Primacy',rp_complete)]:
        if value is not True:reasons.append(name+' incomplete')
    if semantic_continuity not in {'STABLE','RESTORED'}:reasons.append('Semantic continuity unresolved')
    if (analysis.get('status')!='COMPLETE' or analysis.get('root_cause_state') not in {'PROVEN','SUPPORTED'} or
        not analysis.get('supporting_evidence') or not analysis.get('root_cause') or analysis.get('unresolved_causal_conditions')):
        reasons.append('Outcome Analysis/root cause incomplete')
    return {'status':'ELIGIBLE' if not reasons else 'PENDING_VALIDATION','reasons':reasons,
        'outcome_analysis_id':analysis['analysis_id'],'durability_authority':False}

def classify(analysis,measurements):
    dimensions=[]
    targets={'INTERPRETATION_CORRECTNESS':'CORRECTNESS','RUNTIME_OUTCOME':'OUTCOME',
             'OPERATOR_CONTINUITY':'OPERATOR','RUNTIME_ARCHITECTURE':'SYSTEM'}
    if analysis['status']=='COMPLETE':
        for m in measurements:
            dimension=targets.get(m.get('content',{}).get('properties',{}).get('improvement_target'))
            if (m['evidence_id'] in analysis['supporting_evidence'] and dimension in DIMENSIONS and
                (dimension!='OPERATOR' or analysis['scope'].get('operator_id'))):
                dimensions.append(dimension)
    return {'dimensions':sorted(set(dimensions)),'evidence_refs':analysis['supporting_evidence'],
        'scope':analysis['scope'],'applicability':'Exact controlled conditions only',
        'exclusions':['No generalization','No execution authority'],
        'lineage':{'outcome_analysis_id':analysis['analysis_id']},
        'recommendation':({'action':'Review the validated controlled variable before relying on this outcome',
            'variable':analysis['root_cause'].get('variable'),'controls':analysis['root_cause'].get('contrast',{}).get('controls'),
            'execution_authority':False} if dimensions else None),
        'unresolved_conditions':[] if dimensions else ['No governed dimension established']}

def confidence(supporting,contradicting,history=()):
    support=sorted(set(supporting));opposition=sorted(set(contradicting))
    state='CONTRADICTED' if opposition else 'CORROBORATED' if len(support)>1 else 'SUPPORTED' if support else 'UNSUPPORTED'
    event={'state':state,'supporting':support,'contradicting':opposition,'timestamp':now()}
    return {**event,'history':[*history,event],'truth_authority':False}
