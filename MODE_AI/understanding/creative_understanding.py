"""Authored creative definitions into existing Understanding and Semantic Custody.

Approval establishes the Operator's selected creative intent only. It never
validates generated assets, operational capability, or external-world claims.
"""
import json
from .creative_models import SharedCreativeModels
from .understanding_engine import UnderstandingRequest
from .understanding_record import Evidence,normalize_meaning
from .semantic_custody_policy import AuthorityContext,AuthorityLevel
from system_layer.contracts import authorize,digest


def understand(runtime,request,approval):
    # Clear the active projection before resolving the newly selected source;
    # a rejected request cannot silently reuse a prior operational meaning.
    runtime.context.understanding_result=None
    if type(request) is not dict or set(request)!={'reference','project_id','medium'}:
        raise ValueError('Exact shared creative definition selection required')
    owner=runtime.context.identity.operator_id;thread=runtime.context.active_thread.thread_id
    authorize(owner,'CREATIVE_UNDERSTANDING',request,approval)
    resolver=SharedCreativeModels(runtime.understanding_engine.store.path.with_name('content_custody.sqlite3'))
    model=resolver.resolve(owner,request['reference'],request['project_id'],request['medium'])
    meaning=json.dumps({'authored_creative_intent':{'identity':model['identity'],'kind':model['kind'],
        'definition':model['definition'],'representations':model['representations']}},sort_keys=True,ensure_ascii=False)
    reference=request['reference']['expected_hash']
    interpreted={'subject_id':'creative:'+model['identity'],'subject_type':'AUTHORED_CREATIVE_INTENT','semantic_domain':'OPERATOR',
        'meaning':meaning,'scope':request['project_id'],'context':{'medium':request['medium']},
        'claim':{'predicate':'selected_authored_definition','value':model['definition_hash']},
        'requirements':model['use_requirements'] or [],'missing_requirements':model['unresolved'],
        'source_references':[reference]}
    result=runtime.understanding_engine.process(UnderstandingRequest(owner,thread,meaning,project_id=request['project_id'],
        request_id='creative-understanding:'+digest(request),interpreted_input=interpreted,
        authoritative_document_context={'source_reference':reference,'interpretation':interpreted},
        authority_context=AuthorityContext(owner,AuthorityLevel.AUTHORIZED_OPERATOR,'OPERATOR',authenticated=True,
            confirmation_reference='operator-approval:'+digest(approval)),
        evidence=(Evidence('operator-approval:'+digest(approval),'OPERATOR_STATEMENT',True,'OPERATOR',normalize_meaning(meaning)),
                  Evidence(reference,'DOCUMENT',False,'OPERATOR'))))
    runtime.context.understanding_result=result
    return {'contract':'CreativeUnderstanding/1','meaning_scope':'OPERATOR_AUTHORED_INTENT_ONLY',
        'source_record_hash':reference,'model':model,'understanding':result.to_dict(),'state':result.state,'errors':list(result.errors),
        'canon_document_updated':False,'asset_validated':False,'capability_proven':False,'execution_authority':False}
