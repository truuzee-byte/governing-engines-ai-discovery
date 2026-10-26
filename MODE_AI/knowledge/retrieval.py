"""Exact source custody; labels never confer execution or reality authority."""
from enum import Enum
from specs.document_service import DocumentService

class KnowledgeClass(str, Enum):
    SYSTEM='SYSTEM'
    INTERNAL='INTERNAL'
    EXTERNAL='EXTERNAL'

class KnowledgeState(str, Enum):
    CURRENT_AUTHORITY='CURRENT_AUTHORITY'
    HISTORY='HISTORY'
    SUPERSEDED_AUTHORITY='SUPERSEDED_AUTHORITY'
    CONFLICT='CONFLICT'
    MISSING_AUTHORITY='MISSING_AUTHORITY'
    UNAVAILABLE_SOURCE='UNAVAILABLE_SOURCE'
    NOT_RETRIEVED='NOT_RETRIEVED'
    NOT_SPECIFIED='NOT_SPECIFIED'
    DESIGNED_NOT_IMPLEMENTED='DESIGNED_NOT_IMPLEMENTED'
    UNPROVEN='UNPROVEN'

class KnowledgeRetrieval:
    def __init__(self,path):self.documents=DocumentService(path)

    def search(self,owner,query,project_id,limit=25,include_history=False):
        value=self.documents.search(owner,query,project_id,limit,include_history)
        for match in value['matches']:
            category=KnowledgeClass(match['knowledge_class']).value
            match['reference']['knowledge_class']=category
        return dict(value,contract='KnowledgeSearch/1',source_classes=[c.value for c in KnowledgeClass])

    def resolve_authority(self, owner, scope_id, version, expected_hash):
        from specs.document_authority import DocumentAuthority
        resolved = DocumentAuthority(self.documents).resolve(owner,scope_id,version,expected_hash)
        return dict(resolved, knowledge_sources=[{
            'knowledge_class':KnowledgeClass(source['metadata']['knowledge_class']).value,
            'source_reference':{'object_id':source['object_id'],'version':source['version'],'expected_hash':source['record_hash']},
            'project_id':source['metadata']['project_id'], 'kind':source['metadata']['kind'],
            'authority_state':resolved['state'],'claims_validated':False
        } for source in resolved['sources']])

    def retrieve(self,owner,references):
        if type(references) is not list or len(references)>256:raise ValueError('Bounded explicit references required')
        entries=[];seen=set()
        for ref in references:
            if type(ref) is not dict or set(ref)!={'object_id','version','expected_hash','knowledge_class'}:
                raise ValueError('Exact identity, version, hash and source class required')
            category=KnowledgeClass(ref['knowledge_class']).value
            identity=(category,ref['object_id'],ref['version'],ref['expected_hash'])
            if identity in seen:continue
            seen.add(identity)
            entry={'reference':dict(ref),'knowledge_class':category,'execution_authority':False}
            try:record=self.documents.retrieve(owner,ref['object_id'],ref['version'],ref['expected_hash'])
            except FileNotFoundError:entry.update(state='UNAVAILABLE_SOURCE',record=None)
            else:
                if record['metadata']['knowledge_class'] != category:
                    raise PermissionError('Knowledge provenance class cannot be changed on retrieval')
                kind=record['metadata']['kind']
                history=self.documents.store.history('DOCUMENT',owner,ref['object_id'])
                entry.update(state={'HISTORICAL':'HISTORY','SUPERSEDED':'SUPERSEDED_AUTHORITY'}.get(kind,'UNPROVEN'),
                    record=record,authority_status='DECLARED_SOURCE_AUTHORITY',
                    is_latest_version=record['version']==history[-1]['version'],
                    provenance={'source_reference':record['metadata']['source_reference'],
                        'authority':record['metadata']['authority'],'project_id':record['metadata']['project_id'],
                        'previous_hash':record['previous_hash'],'content_hash':record['content_hash']},
                    requires_authority_reconciliation=kind in {'AUTHORITATIVE','SPECIFICATION','CONTRACT','CANON'})
            entries.append(entry)
        return {'contract':'KnowledgeRetrieval/1','entries':entries,'execution_authority':False,
                'conflicting_versions':[key for key in sorted({e['reference']['object_id'] for e in entries})
                    if len({(e['reference']['version'],e['reference']['expected_hash']) for e in entries if e['reference']['object_id']==key})>1]}
