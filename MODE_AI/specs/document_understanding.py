"""Current document authority into the existing semantic-custody engine.

Operator submission authorizes processing, not truth of document claims. No
automatic prose/model interpretation, source replacement, or build approval.
"""
from copy import deepcopy
from .document_service import DocumentService
from .document_authority import DocumentAuthority
from system_layer.contracts import authorize,digest


def understand(runtime,request,approval):
    # A failed new selection must not leave the prior meaning available as the
    # current operational handoff. Its governed store history remains intact.
    runtime.context.understanding_result=None
    from understanding import UnderstandingRequest,AuthorityContext,AuthorityLevel
    from understanding.understanding_record import Evidence
    owner=runtime.context.identity.operator_id;thread=runtime.context.active_thread.thread_id
    if type(request) is not dict or set(request)!={'authority_reference','project_id','interpretation'}:
        raise ValueError('Exact document authority, project and interpretation required')
    authorize(owner,'DOCUMENT_UNDERSTANDING',request,approval)
    reference=request['authority_reference']
    if type(reference) is not dict or set(reference)!={'scope_id','version','expected_hash'}:
        raise ValueError('Exact current document authority reference required')
    docs=DocumentService(runtime.understanding_engine.store.path.with_name('content_custody.sqlite3'))
    resolved=DocumentAuthority(docs).resolve(owner,**reference)
    if resolved['state']!='CURRENT_AUTHORITY':raise PermissionError('Current document authority required: '+resolved['state'])
    source=resolved['sources'][0]
    if source['metadata']['project_id']!=request['project_id']:raise PermissionError('Document understanding project mismatch')
    data=deepcopy(request['interpretation'])
    if type(data) is not dict or data.get('semantic_domain') not in {'OPERATOR','SYSTEM','EXTERNAL','RUNTIME'}:
        raise ValueError('Explicit semantic domain required')
    if data.get('source_references')!=[source['record_hash']]:
        raise ValueError('Interpretation must identify the exact selected document hash')
    for requirement in data.get('requirements',[]):
        if isinstance(requirement,dict) and requirement.get('source_references',data['source_references'])!=data['source_references']:
            raise ValueError('Requirement source differs from selected document')
    selected=docs.text_source(owner,source['object_id'],source['version'],source['record_hash'])
    result=runtime.understanding_engine.process(UnderstandingRequest(owner,thread,selected['content'],
        project_id=request['project_id'],request_id='document-understanding:'+digest(request),
        interpreted_input=data,authoritative_document_context={'source_reference':source['record_hash'],'interpretation':data,
            'extraction':selected['extraction'],'knowledge_class':source['metadata']['knowledge_class']},
        authority_context=AuthorityContext(owner,AuthorityLevel.AUTHORIZED_OPERATOR,data['semantic_domain'],authenticated=True),
        evidence=(Evidence(source['record_hash'],'DOCUMENT',False,data['semantic_domain']),)))
    runtime.context.understanding_result=result
    return {'contract':'DocumentUnderstanding/1','source_reference':{'object_id':source['object_id'],'version':source['version'],'expected_hash':source['record_hash']},
        'source_record_hash':source['record_hash'],'authority_reference':deepcopy(reference),'understanding':result.to_dict(),
        'extraction':({k:v for k,v in selected['extraction'].items() if k!='segments'} if selected['extraction'] else None),
        'state':result.state,'errors':list(result.errors),'claims_validated':False,'execution_authority':False}
