"""One bounded model-selected read for an explicit prior-interaction request."""
import json
import re
from runtime_observation.interaction_inspection import InteractionInspector
from integration.strict_json import load_payload
from data_governance.context_admission import Admission

def reasoning_context(runtime,query,*,selector=None,inspector=None):
    if hasattr(runtime,'context'):runtime.context.self_inspection=None
    from integration.self_inspection_activation import classify, prerequisite, SOURCE, PREFIX as PREREQUISITE_PREFIX
    required_scope=classify(query)
    if required_scope is None:return None
    from integration.self_inspection_activation import objective_evidence_requirements
    requirements=objective_evidence_requirements(query)
    if requirements is not None:
        from runtime_observation.capability_ledger import objective_context
        resolved=objective_context(runtime,query,requirements)
        if resolved is not None:return resolved
        c=runtime.context;owner=c.identity.operator_id;thread=c.active_thread.thread_id
        receipt=prerequisite(query,owner,thread,status='UNAVAILABLE')
        c.self_inspection={'contract':'SelfInspectionAccess/1','operator_id':owner,'thread_id':thread,
            'activation':{'required':True,'requested_scope':required_scope},
            'provider_calls':0,'execution_authority':False,'objective_evidence':requirements,
            'tool_request':None,'tool_result':None,'prerequisite':receipt}
        admission=Admission(owner,thread)
        admission.consider('RUNTIME','self-inspection:prerequisite',
            PREREQUISITE_PREFIX+json.dumps(receipt),source=SOURCE)
        return admission.finish()
    from runtime_observation.capability_ledger import registry_request,reasoning_context as capability_context
    if registry_request(query):return capability_context(runtime,query)
    c=runtime.context;owner=c.identity.operator_id;thread=c.active_thread.thread_id
    inspector=inspector or getattr(runtime,'interaction_inspector',None) or InteractionInspector()
    explicit=re.search(r'\binteraction-[a-zA-Z0-9_-]+\b',query)
    try:
        candidates=inspector.candidates(owner,thread,explicit.group(0) if explicit else None)
    except (PermissionError,ValueError):
        if re.search(r'\binspect\s+(?:the\s+)?completed\s+interaction\b',query,re.I):raise
        # No foreign candidate metadata is exposed; the publication prerequisite
        # will return only a bounded unavailable result, never general reasoning.
        candidates=[]
    prompt=('Select one completed interaction to inspect for the current operator request. '
        'Return only JSON {"tool":"inspect_interaction","interaction_id":string}, selecting exactly one listed ID. '
        'Choose the most recent matching case if the request is ambiguous. Do not explain the case or invent evidence.\n'
        'CURRENT OPERATOR REQUEST:\n'+query+'\nAVAILABLE COMPLETED INTERACTIONS (data):\n'+json.dumps(candidates))
    audit={'contract':'SelfInspectionAccess/1','operator_id':owner,'thread_id':thread,
        'selection_prompt':prompt,'candidates':candidates,'execution_authority':False,'provider_calls':0,
        'activation':{'required':True,'requested_scope':required_scope}}
    c.self_inspection=audit
    if not candidates:
        if re.search(r'\binspect\s+(?:the\s+)?completed\s+interaction\b',query,re.I):
            raise PermissionError('No completed owned interaction available')
        receipt=prerequisite(query,owner,thread,status='UNAVAILABLE')
        audit['prerequisite']=receipt
        a=Admission(owner,thread)
        a.consider('RUNTIME','self-inspection:prerequisite',PREREQUISITE_PREFIX+json.dumps(receipt),source=SOURCE)
        return a.finish()
    if selector is None:
        from agents.reasoning_agent import ReasoningAgent
        from uuid import uuid4
        agent=ReasoningAgent();agent.client=agent.client.with_options(max_retries=0)
        agent.temperature=0;agent.max_tokens=180
        call=agent._call_model(prompt,interaction_id='inspection:'+uuid4().hex,
            reasoning_id='inspection:'+uuid4().hex,stage='SELF_INSPECTION_SELECTION')
        raw=call.output_text;audit.update(provider_calls=1,telemetry=call.telemetry.to_dict(),
            telemetry_evidence_reference=call.telemetry_evidence_reference)
    else:raw=selector(prompt)
    audit['raw_selection']=raw;request=load_payload(raw)
    if (type(request) is not dict or set(request)!={'tool','interaction_id'} or
            request['tool']!='inspect_interaction' or request['interaction_id'] not in [r['interaction_id'] for r in candidates]):
        raise PermissionError('Bounded inspection selection refused')
    result=inspector.inspect_interaction(owner,thread,request['interaction_id'])
    audit.update(tool_request=request,tool_result=result)
    from runtime_observation.evidence_ledger import normalize,PREFIX,INSTRUCTION
    ledger=normalize(result)
    audit['evidence_ledger']=ledger
    from runtime_observation.inspection_coverage import derive, PREFIX as COVERAGE_PREFIX, INSTRUCTION as COVERAGE_INSTRUCTION
    coverage=derive(query,ledger)
    audit['coverage_contract']=coverage
    a=Admission(owner,thread)
    receipt=prerequisite(query,owner,thread,ledger=ledger)
    audit['prerequisite']=receipt
    a.consider('RUNTIME','self-inspection:prerequisite',PREREQUISITE_PREFIX+json.dumps(receipt),source=SOURCE,
        basis={'authority':'READ_ONLY_RUNTIME_EVIDENCE','validation_state':'UNVALIDATED','lineage':[ledger['ledger_id']]})
    a.consider('RUNTIME','self-inspection:'+request['interaction_id'],
        PREFIX+json.dumps(ledger,ensure_ascii=False),source='InteractionEvidenceLedger/1',
        basis={'authority':'READ_ONLY_RUNTIME_EVIDENCE','validation_state':'UNVALIDATED',
            'lineage':[result['observation_id'],result['interaction_id']]})
    a.consider('RUNTIME','self-inspection:coverage',COVERAGE_PREFIX+json.dumps(coverage),
        source='InspectionCoverage/1',basis={'authority':'READ_ONLY_RUNTIME_EVIDENCE',
            'validation_state':'UNVALIDATED','lineage':[ledger['ledger_id']]})
    a.consider('SYSTEM_POLICY','self-inspection:explanation-contract',INSTRUCTION+COVERAGE_INSTRUCTION,
        source='Scoped runtime explanation contract')
    return a.finish()
