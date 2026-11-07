"""Operator selection of governing sources, distinct from validation of their claims."""
import json
from system_layer.contracts import authorize
from data_governance.document_admission import _DOCUMENT_WRITER

STATES={'CURRENT_AUTHORITY','CONFLICT','MISSING_AUTHORITY','NOT_SPECIFIED','DESIGNED_NOT_IMPLEMENTED','UNPROVEN'}

class DocumentAuthority:
    def __init__(self, documents):
        self.documents=documents
        self.store=documents.store

    def reconcile(self, owner, request, approval):
        if type(request) is not dict or set(request)!={'scope_id','state','references','rationale','expected_previous'}:
            raise ValueError('Complete authority decision required')
        authorize(owner,'DOCUMENT_AUTHORITY',request,approval)
        if request['state'] not in STATES:raise ValueError('Unknown authority state')
        if type(request['rationale']) is not str or not request['rationale'].strip():raise ValueError('Decision rationale required')
        refs=request['references']
        if type(refs) is not list or len(refs)>256:raise ValueError('Bounded exact source references required')
        count={'CURRENT_AUTHORITY':1,'MISSING_AUTHORITY':0,'NOT_SPECIFIED':0}.get(request['state'])
        if count is not None and len(refs)!=count:raise ValueError('Authority state/source count mismatch')
        if request['state']=='CONFLICT' and len(refs)<2:raise ValueError('Conflicting sources must remain explicit')
        seen=set()
        for ref in refs:
            if type(ref) is not dict or set(ref)!={'object_id','version','expected_hash'}:raise ValueError('Exact source reference required')
            key=(ref['object_id'],ref['version'],ref['expected_hash'])
            if key in seen:raise ValueError('Duplicate source is not a conflict')
            seen.add(key)
            record=self.documents.retrieve(owner,**ref)
            if request['state']=='CURRENT_AUTHORITY' and record['metadata']['kind'] not in {'AUTHORITATIVE','SPECIFICATION','CONTRACT','CANON'}:
                raise PermissionError('Candidate/draft cannot be selected as governing authority')
        body={'contract':'DocumentAuthorityDecision/1',**request,'claims_validated':False,'execution_authority':False}
        return self.store.append('DOCUMENT_AUTHORITY',owner,request['scope_id'],json.dumps(body,sort_keys=True),
            {'kind':'DOCUMENT_AUTHORITY_DECISION'},expected_previous=request['expected_previous'],authorization=approval,
            document_admission=_DOCUMENT_WRITER)

    def resolve(self, owner, scope_id, version, expected_hash):
        history=self.store.history('DOCUMENT_AUTHORITY',owner,scope_id)
        if type(version) is not int or version<1 or version>len(history):
            raise FileNotFoundError('Authority decision unavailable')
        decision=history[version-1]
        if decision['record_hash']!=expected_hash:raise ValueError('Authority decision hash mismatch')
        body=json.loads(decision['content']);sources=[];missing=[]
        for ref in body['references']:
            try:sources.append(self.documents.retrieve(owner,**ref))
            except FileNotFoundError:missing.append(ref)
        state='SUPERSEDED_AUTHORITY' if version!=history[-1]['version'] else body['state']
        if missing:state='UNAVAILABLE_SOURCE'
        return {'contract':'ResolvedDocumentAuthority/1','state':state,'decision':decision,'sources':sources,
                'missing_references':missing,'claims_validated':False,'execution_authority':False}
