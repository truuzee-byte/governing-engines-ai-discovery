"""Knowledge v1.0 §§6–9,16,20: versioned meaning, never duplicated source truth."""
import json
from datetime import datetime, timezone
from system_layer.contracts import authorize, digest
from specs.document_service import DocumentService
from .retrieval import KnowledgeClass

LIFECYCLES={'CANDIDATE','ACTIVE','ARCHIVED','DEPRECATED','SUPERSEDED','REVOKED'}
TYPES={'GOVERNING_AUTHORITY','SYSTEM_STATE_REFERENCE','INTERNAL_FACT','DECISION','DEFINITION',
       'PROCEDURE','PROJECT_KNOWLEDGE','LEARNED_KNOWLEDGE','EXTERNAL_REFERENCE','HISTORICAL',
       'INFERENCE','HYPOTHESIS','UNKNOWN'}

def validate_pending_record(body):
    pending={'contract':'KnowledgeRecord/1','authority_state':'NOT_RECONCILED',
        'authority_tier':None,'validation_state':'UNPROVEN','rp_state':'PENDING_VALIDATION',
        'rp_references':[],'last_verified_at':None,'support_state':'NOT_EVALUATED',
        'claims_validated':False,'execution_authority':False}
    if any(key not in body or type(body[key]) is not type(value) or body[key]!=value
           for key,value in pending.items()):
        raise PermissionError('Knowledge custody cannot establish reality or authority')


def timestamp(value):
    if value is None: return None
    if type(value) is not str: raise ValueError('Explicit UTC timestamp or null required')
    parsed=datetime.fromisoformat(value.replace('Z','+00:00'))
    if parsed.tzinfo is None: raise ValueError('Timezone required')
    return parsed


class KnowledgeRegistry:
    def __init__(self,path,understanding_store):
        self.documents=DocumentService(path)
        self.store=self.documents.store
        self.understanding_store=understanding_store

    def register(self,owner,request,approval):
        fields={'knowledge_id','pool','knowledge_type','semantic_domain','project_id','thread_id',
            'sources','understanding_reference','author','organization','authority_scope','visibility',
            'lifecycle','temporal_scope','fresh_until','applicability','exclusions','unresolved',
            'related_knowledge','conflicts','expected_previous'}
        if type(request) is not dict or set(request)!=fields: raise ValueError('Complete Knowledge registration required')
        authorize(owner,'KNOWLEDGE_REGISTER',request,approval)
        KnowledgeClass(request['pool'])
        if request['knowledge_type'] not in TYPES or request['lifecycle'] not in LIFECYCLES:
            raise ValueError('Unknown Knowledge type/lifecycle')
        if request['visibility']!='OWNER_SCOPED': raise PermissionError('Shared access has not been authorized')
        for key in ('knowledge_id','semantic_domain','project_id','thread_id','author','organization','authority_scope'):
            if type(request[key]) is not str or not request[key].strip():raise ValueError('Missing Knowledge identity: '+key)
        if type(request['temporal_scope']) is not dict or set(request['temporal_scope'])!={'from','until'}:
            raise ValueError('Explicit temporal scope required')
        start=timestamp(request['temporal_scope']['from']);end=timestamp(request['temporal_scope']['until'])
        if start and end and start>end:raise ValueError('Reversed temporal scope')
        timestamp(request['fresh_until'])
        for key in ('applicability','exclusions','unresolved'):
            if type(request[key]) is not list or any(type(x) is not str or not x for x in request[key]):
                raise ValueError('Explicit Knowledge scope list required')
        sources=self._sources(owner,request['sources'],request['project_id'])
        ref=request['understanding_reference']
        if type(ref) is not dict or set(ref)!={'understanding_id','version','expected_hash'} or type(ref['version']) is not int:
            raise ValueError('Pinned Understanding reference required')
        meaning=self.understanding_store.get(owner,ref['understanding_id'],ref['version'])
        if meaning is None:raise FileNotFoundError('Understanding unavailable; meaning cannot be invented')
        canonical=meaning.to_dict()
        if digest(canonical)!=ref['expected_hash']:raise ValueError('Understanding changed')
        if (meaning.project_id,meaning.thread_id,meaning.semantic_domain)!=(request['project_id'],request['thread_id'],request['semantic_domain']):
            raise PermissionError('Understanding scope mismatch')
        evidence={e.reference for e in meaning.supporting_evidence}
        if any(s['record_hash'] not in evidence for s in sources):
            raise ValueError('Understanding does not preserve the selected documentary lineage')
        for field in ('related_knowledge','conflicts'):
            if type(request[field]) is not list or len(request[field])>256:raise ValueError('Bounded relationships required')
            for linked in request[field]:
                if type(linked) is not dict or set(linked)!={'knowledge_id','version','expected_hash'}:
                    raise ValueError('Pinned Knowledge relationship required')
                related=self.store.retrieve('KNOWLEDGE',owner,linked['knowledge_id'],version=linked['version'],expected_hash=linked['expected_hash'])
                if related['metadata']['project_id']!=request['project_id']:raise PermissionError('Relationship project mismatch')
        previous=self.store.history('KNOWLEDGE',owner,request['knowledge_id'])
        if previous:
            old=json.loads(previous[-1]['content'])
            if (old['request']['pool'],old['request']['project_id'])!=(request['pool'],request['project_id']):
                raise PermissionError('Knowledge identity cannot silently cross pool/project')
        body={'contract':'KnowledgeRecord/1','request':request,
            'canonical_meaning':meaning.canonical_meaning,'understanding_state':meaning.semantic_state.value,
            'source_lineage':[{'reference':ref,'record_hash':source['record_hash'],
                'source_pool':source['metadata']['knowledge_class'],'source_kind':source['metadata']['kind'],
                'source_provenance':source['metadata']['source_reference']} for ref,source in zip(request['sources'],sources)],
            'authority_state':'NOT_RECONCILED','authority_tier':None,'validation_state':'UNPROVEN',
            'rp_state':'PENDING_VALIDATION','rp_references':[], 'last_verified_at':None,
            'support_state':'NOT_EVALUATED','claims_validated':False,'execution_authority':False}
        return self.store.append('KNOWLEDGE',owner,request['knowledge_id'],json.dumps(body,sort_keys=True),
            {'project_id':request['project_id'],'kind':request['knowledge_type'],'knowledge_class':request['pool'],
             'lifecycle':request['lifecycle']},expected_previous=request['expected_previous'],authorization=approval)

    def _sources(self,owner,refs,project):
        if type(refs) is not list or not 0<len(refs)<=256:raise ValueError('Explicit bounded documentary lineage required')
        values=[];seen=set()
        for ref in refs:
            if type(ref) is not dict or set(ref)!={'object_id','version','expected_hash'}:raise ValueError('Exact documentary source required')
            value=self.documents.retrieve(owner,**ref)
            if value['metadata']['project_id']!=project:raise PermissionError('Knowledge source project mismatch')
            if value['record_hash'] in seen:raise ValueError('Repeated source is not additional evidence')
            seen.add(value['record_hash']);values.append(value)
        return values

    def retrieve(self,owner,knowledge_id,version,expected_hash):
        record=self.store.retrieve('KNOWLEDGE',owner,knowledge_id,version=version,expected_hash=expected_hash)
        body=json.loads(record['content']);request=body['request']
        # Custody hashes establish byte identity, not RP adjudication. This
        # contract has no RP admission transition; imports cannot invent one.
        validate_pending_record(body)
        ref=request['understanding_reference']
        meaning=self.understanding_store.get(owner,ref['understanding_id'],ref['version'])
        missing_meaning=meaning is None
        if meaning is not None and digest(meaning.to_dict())!=ref['expected_hash']:
            raise ValueError('Knowledge Understanding lineage changed')
        if meaning is not None and (body['canonical_meaning']!=meaning.canonical_meaning or
                body['understanding_state']!=meaning.semantic_state.value):
            raise ValueError('Knowledge meaning differs from pinned Understanding')
        unavailable=[]
        for ref in request['sources']:
            try:self.documents.retrieve(owner,**ref)
            except FileNotFoundError:unavailable.append(ref)
        current=datetime.now(timezone.utc)
        end=timestamp(request['fresh_until'])
        freshness='NOT_ESTABLISHED' if end is None else 'EXPIRED' if current>end else 'WITHIN_DECLARED_INTERVAL'
        return {'contract':'KnowledgeRecordRetrieval/1','record':record,'knowledge':body,
            'unavailable_sources':unavailable,'freshness':freshness,
            'unavailable_understanding':missing_meaning,
            'state':'UNAVAILABLE_SOURCE' if unavailable or missing_meaning else 'REVIEW_REQUIRED' if request['conflicts'] or request['unresolved'] else 'RETRIEVED',
            'claims_validated':False,'execution_authority':False}

    def search(self,owner,query,project_id,limit=25,include_history=False):
        result=self.store.search('KNOWLEDGE',owner,query,project_id,limit=limit,include_history=include_history)
        for match in result['matches']:
            ref=match['reference']
            resolved=self.retrieve(owner,ref['object_id'],ref['version'],ref['expected_hash'])
            request=resolved['knowledge']['request']
            match.update(lifecycle=request['lifecycle'],freshness=resolved['freshness'],
                availability=resolved['state'],applicability=request['applicability'],
                exclusions=request['exclusions'],rp_state=resolved['knowledge']['rp_state'])
        return result

    def relationships(self,owner,knowledge_id,version,expected_hash):
        """Resolve authored edges only; proximity or repetition creates no relation."""
        source=self.retrieve(owner,knowledge_id,version,expected_hash)
        edges=[]
        for kind in ('related_knowledge','conflicts'):
            for reference in source['knowledge']['request'][kind]:
                target=self.retrieve(owner,**reference)
                edges.append({'kind':kind,'reference':reference,'state':target['state'],
                    'pool':target['knowledge']['request']['pool'],
                    'lifecycle':target['knowledge']['request']['lifecycle'],
                    'freshness':target['freshness'],'authority_state':target['knowledge']['authority_state']})
        return {'contract':'KnowledgeRelationships/1','source_reference':{
            'knowledge_id':knowledge_id,'version':version,'expected_hash':expected_hash},
            'edges':edges,'scope':'EXPLICIT_OUTGOING_EDGES','conflicts_resolved':False,
            'claims_validated':False,'execution_authority':False}

    def meaning_lookup(self,owner,meaning,semantic_domain,project_id,pool,limit=25,include_history=False):
        """Reconstruct a bounded semantic-key index from verified custody records.

        This uses Understanding's existing exact normalization, not similarity,
        inferred equivalence, authority ranking or an external embedding provider.
        """
        import sqlite3
        from understanding.understanding_record import normalize_meaning
        if any(type(x) is not str or not x.strip() for x in (owner,meaning,semantic_domain,project_id)):
            raise ValueError('Explicit meaning and scope required')
        if len(meaning)>65536 or type(limit) is not int or not 1<=limit<=100 or type(include_history) is not bool:
            raise ValueError('Bounded meaning lookup required')
        KnowledgeClass(pool)
        key=normalize_meaning(meaning)
        if not key:raise ValueError('Nonempty normalized meaning required')
        matches=[];count=0
        with sqlite3.connect(self.store.path) as db:
            db.execute('BEGIN')
            identities=db.execute('SELECT DISTINCT identity FROM objects WHERE namespace=? AND owner=? ORDER BY identity LIMIT 257',
                ('KNOWLEDGE',owner)).fetchall()
            for (identity,) in identities[:256]:
                history=self.store._history(db,'KNOWLEDGE',owner,identity)
                for record in history if include_history else history[-1:]:
                    body=json.loads(record['content']);request=body['request']
                    if (request['pool'],request['semantic_domain'],request['project_id'])!=(pool,semantic_domain,project_id):continue
                    if normalize_meaning(body['canonical_meaning'])!=key:continue
                    count+=1
                    if len(matches)<limit:
                        matches.append({'knowledge_id':identity,'version':record['version'],'expected_hash':record['record_hash']})
        # Re-resolve source custody before exposing the located meanings.
        values=[self.retrieve(owner,**ref) for ref in matches]
        return {'contract':'KnowledgeMeaningLookup/1','normalized_meaning':key,'pool':pool,
            'semantic_domain':semantic_domain,'project_id':project_id,'references':matches,'records':values,
            'match_method':'UNDERSTANDING_NORMALIZED_EXACT','include_history':include_history,
            'matching_records_in_window':count,'results_limited':count>limit,
            'index_completeness':'PARTIAL_OBJECT_WINDOW' if len(identities)>256 else 'COMPLETE_FOR_SELECTED_NAMESPACE',
            'automatically_selected':False,'claims_validated':False,'execution_authority':False}
