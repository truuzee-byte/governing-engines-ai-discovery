"""Material response admission. Trivial conversation does not acquire an RP obligation."""
from datetime import datetime,timezone
from learning.contracts import digest,now
from copy import deepcopy
import base64
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey
from integration.reality_primacy import digest as rp_digest

def _authenticate(runtime, rp):
    """Authenticate the retained external result without re-adjudicating its claim."""
    claim=getattr(runtime.context,'material_response_claim',None) or {}
    if claim.get('source')=='ObjectiveActionRP/1':
        from integration.objective_action_rp import consumer_client
        client=consumer_client(runtime,rp)
    else:client=runtime.reality_acceptance_client
    request=rp['request'];reply=rp['response'];body=reply['body']
    Ed25519PublicKey.from_public_bytes(client._keys[reply['key_id']]).verify(
        base64.b64decode(reply['signature'],validate=True),bytes.fromhex(rp_digest(body)))
    if request['request_id'] not in client._used or body['contract']!='RPTransitionResponse/1':raise ValueError('Unconsumed response')
    if body['request_hash']!=rp_digest(request) or body['request_id']!=request['request_id']:raise ValueError('Request mismatch')
    view=body['show_chain'];data=view['structured']
    if view['status']!='VERIFIED' or data['final_state']!='CONFIRMED':raise ValueError('Unconfirmed result')
    if data['scope']!=request['scope'] or data['outcome']['claim_id']!=request['claim_id']:raise ValueError('Scope mismatch')
    for field in ('decision_id','chain_id','receipt_id'):
        if rp[field]!=data[field]:raise ValueError('Lineage mismatch')
    if rp['outcome']!=data['outcome']:raise ValueError('Outcome mismatch')
    policy=request['evaluation']['authority']
    if rp['authority_valid_until']!=policy['valid_until']:raise ValueError('Validity mismatch')
    times=[datetime.fromisoformat(value) for value in (policy['valid_from'],body['evaluated_at'],policy['valid_until'])]
    if any(value.tzinfo is None for value in times):raise ValueError('Unzoned validity')
    if not times[0]<=times[1]<=datetime.now(timezone.utc)<=times[2]:raise ValueError('Expired result')

def evaluate(runtime,text,generated_text=None,*,reasoning_input=None):
    context=runtime.context
    domain=getattr(getattr(context,'knowledge_classification',None),'primary_domain',None)
    domain=getattr(domain,'value',domain)
    claim=getattr(context,'material_response_claim',None)
    from data_governance.response_claims import extract, consequential
    scope={'operator_id':getattr(getattr(context,'identity',None),'operator_id',None),
           'thread_id':getattr(getattr(context,'active_thread',None),'thread_id',None)}
    rp_evidence_receipt=None
    assessment_text=generated_text if generated_text is not None else text
    if generated_text is None:
        from cryptography.exceptions import InvalidSignature
        try:
            from integration.rp_evidence_state import claim_projection
            assessment_text=claim_projection(runtime,text,reasoning_input)
            state=getattr(context,"rp_evidence_state",None)
            if state is not None and assessment_text!=text:
                import json
                rp_evidence_receipt=json.loads(state.response_json)
        except (ValueError,KeyError,TypeError,PermissionError,InvalidSignature):
            assessment_text=text  # Invalid/missing RP state cannot relax any claim check.
    extraction=extract(assessment_text,scope)
    material=bool(claim) or domain=='EXTERNAL_CURRENT' or consequential(assessment_text)
    # A request for discussion is not a claim made by Mode. The resulting
    # answer still passes the full structural gate, even when drafting is allowed.
    if generated_text is None and not claim and domain!='EXTERNAL_CURRENT':
        from data_governance.response_claims import is_conversation_request
        if is_conversation_request(assessment_text):
            material=False
    syntax_analysis=extraction
    if not material:
        # A grammatical assertion is not itself a consequential claim. Retain
        # analysis for diagnostics without manufacturing RP obligations for it.
        extraction={'state':'NON_MATERIAL','claims':[],'coverage':'CONVERSATION_ONLY'}
    reasons=[]
    from integration.self_inspection_activation import assess as inspection_prerequisite
    inspection=inspection_prerequisite(text,reasoning_input,generated_text)
    if inspection is not None and not inspection['allowed']:
        reasons.append(inspection['reason'])
    recorded_capability_observation=None
    if (generated_text is not None and not claim and domain!='EXTERNAL_CURRENT'
            and inspection is not None and inspection['allowed']):
        from runtime_observation.evidence_ledger import from_prompt,assess_rendered
        ledger=from_prompt(reasoning_input)
        if ledger is not None and ledger['contract']=='CapabilityEvidenceLedger/1':
            quoted=assess_rendered(generated_text,reasoning_input)
            if quoted is not None and quoted['allowed']:
                # Exact, scoped statements report what owned records contain.
                # They do not affirm the referenced outcomes as current truth.
                # Freeform text, incomplete coverage, explicit material claims
                # and external-current assertions retain the original RP gate.
                material=False
                extraction={'state':'NON_MATERIAL','claims':[],
                    'coverage':'BOUNDED_OBJECTIVE_DIAGNOSIS_NOT_VALIDATED' if ledger.get('objective') else 'EXACT_SCOPED_CAPABILITY_RECORD_OBSERVATION'}
                recorded_capability_observation={'ledger_id':ledger['ledger_id'],
                    'coverage_id':inspection['coverage_id'],
                    'model_diagnosis_class':'INFERRED_NOT_REPAIR_APPROVAL' if ledger.get('objective') else None,
                    'recorded_not_independently_validated':True,'execution_authority':False}
    preference_grounding=None
    if generated_text is not None:
        from conversation_quality.preference_grounding import assess
        if reasoning_input is not None:
            from data_governance.context_admission import verify
            verify(reasoning_input,scope['thread_id'])
            if reasoning_input.scope!=scope:raise PermissionError('Preference evidence owner mismatch')
        preference_grounding=assess(generated_text,text,reasoning_input)
        if not preference_grounding['allowed']:
            reasons.append('UNSUPPORTED_PREFERENCE: clarify the preference or its scope; no outside-session default is established by a session-only change')
        import re
        memory_attribution=False
        for clause in re.split(r'(?<=[.!?;])\s+|\n+|\bbut\b',generated_text,flags=re.I):
            attribution=re.search(r'\b(?:stored|saved|retained) in (?:your |the )?persistent memory\b|\bfrom (?:your |the )?persistent memory\b',clause,re.I)
            if not attribution or clause.rstrip().endswith('?'):
                continue
            before=clause[:attribution.start()].replace('\u2019',"'")
            if re.search(r"\b(?:not|never|no|don't|doesn't|isn't|wasn't|can't|cannot)\b",before,re.I):
                continue
            memory_attribution=True
        if memory_attribution:
            sources=getattr(reasoning_input,'sources',[]) if reasoning_input is not None else []
            if not any(s['record']['artifact_type']=='MEMORY' and s['record']['decision']=='ADMITTED' for s in sources):
                reasons.append('UNSUPPORTED_MEMORY_ATTRIBUTION: no eligible persistent record admitted for this response')
    if material and generated_text is not None and extraction['state']=='UNKNOWN_MATERIALITY':
        reasons.append('UNKNOWN_MATERIALITY: consequential continuation requires review')
    if not getattr(getattr(context,'identity',None),'operator_id',None):reasons.append('Operator authority unavailable')
    profile=getattr(context,'profile',None)
    if profile and profile.operator_id!=context.identity.operator_id:reasons.append('Operator scope mismatch')
    if material:
        assembled=getattr(context,'assembled_context',None)
        if not assembled or not assembled.runtime.context_ready:reasons.append('Governed context unavailable')
        meaning=getattr(context,'understanding_result',None)
        if not meaning or meaning.review_required or not meaning.final_understanding or meaning.errors:
            reasons.append('Semantic continuity incomplete')
        rp=getattr(context,'reality_primacy_result',{}) or {}
        try:
            request=rp['request'];scope=request['scope']
            exact=(claim and claim['operator_input_hash']==digest(text) and claim['claim_id']==request['claim_id'] and
                scope['operator_id']==context.identity.operator_id and scope['thread_id']==context.active_thread.thread_id)
            if not exact or rp.get('accepted') is not True or rp.get('rp_state')!='CONFIRMED':raise ValueError()
            _authenticate(runtime,rp)
            if generated_text is not None and scope.get('response_hash')!=digest(generated_text):
                raise ValueError('Generated response is outside the signed RP scope')
            if generated_text is not None and scope.get('response_claims_hash')!=digest(extraction['claims']):
                raise ValueError('Response propositions are outside the signed RP scope')
            if generated_text is not None and request['evaluation']['resolution']['claim_snapshot']['claim_text']!=generated_text:
                raise ValueError('RP adjudicated a different proposition')
        except Exception:reasons.append('Required scoped current RP confirmation unavailable')
    disclosure=[]
    previous=getattr(runtime,'_response_governance_scope',None)
    meaning=getattr(getattr(context,'understanding_result',None),'final_understanding',None)
    current={'domain':domain,'claim':claim,'definitions':getattr(meaning,'canonical_meaning',None),
        'assumptions':getattr(context,'runtime_assumptions',None)}
    if previous is not None and previous!=current:disclosure.append('Governed response scope or claim assumptions changed.')
    runtime._response_governance_scope=deepcopy(current)
    if getattr(context,'learning_influence',{}):disclosure.append('Governed historical Learning was considered for this response; it grants no execution authority.')
    result={'material':material,'materiality':extraction,'syntax_analysis':syntax_analysis,'execution_authority_granted':False,
            'publication_scope':'GOVERNED' if material else 'CONVERSATION_ONLY',
            'decision':'REVIEW_REQUIRED' if material and extraction['state']=='UNKNOWN_MATERIALITY' and reasons else 'BLOCK' if reasons else 'ALLOW',
            'allowed':not reasons,'reasons':reasons,'disclosures':disclosure,'timestamp':now(),
            'preference_grounding':preference_grounding,'self_inspection_prerequisite':inspection,
            'recorded_capability_observation':recorded_capability_observation,'rp_evidence_state':rp_evidence_receipt}
    context.response_governance=result
    return result

def governed_interaction(runtime,operator_input,reasoning_input,processor):
    """Shared admission for interactive and supervisor response publication."""
    from data_governance.context_admission import verify
    from models.runtime_models import InteractionProcessingResult
    verify(reasoning_input,operator_input.session_id)
    gate=evaluate(runtime,operator_input.raw_input,reasoning_input=reasoning_input)
    result=None
    if gate['allowed']:
        result=processor(operator_input,reasoning_input=reasoning_input)
        released=evaluate(runtime,operator_input.raw_input,generated_text=result.response_text or '',reasoning_input=reasoning_input)
        released['disclosures']=list(dict.fromkeys(gate['disclosures']+released['disclosures']))
        released['rp_evidence_state']=gate.get('rp_evidence_state')
        gate=released
    if not gate['allowed']:
        fields=('interaction_id','reasoning_id','raw_input','pressure_state','conversation_quality_state',
                'provider_request_telemetry','telemetry_evidence_references','telemetry_persistence_errors','context_admission')
        retained={key:getattr(result,key) for key in fields if result is not None and hasattr(result,key)}
        from integration.self_inspection_activation import bounded_result
        blocked_text=(bounded_result(operator_input.raw_input) if gate.get('self_inspection_prerequisite') and not gate['self_inspection_prerequisite']['allowed']
                      else 'PENDING_VALIDATION: '+ '; '.join(gate['reasons']))
        return InteractionProcessingResult(False,None,getattr(result,'trace_reference',''),
            {**(getattr(result,'failure_state',{}) or {}),'governance':gate['reasons']},True,getattr(result,'halt_required',False),
            blocked_text,**retained)
    return result
