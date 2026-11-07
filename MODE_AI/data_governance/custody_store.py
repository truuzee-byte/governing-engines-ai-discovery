"""Versioned content custody for document drafts and explicitly preserved Vault objects.

SQLite transactions prevent partial updates. Hash lineage detects accidental content
loss/substitution; it is not an independently protected anti-rollback trust anchor.
Namespaces remain distinct and retrieval never regenerates missing content.
"""
import json
import sqlite3
from io import StringIO
from pathlib import Path
from system_layer.contracts import digest, now
from .custody_json import load as load_custody_json


class CustodyStore:
    def __init__(self, path):
        self.path=Path(path)
        self.path.parent.mkdir(parents=True,exist_ok=True)
        with sqlite3.connect(self.path) as db:
            db.execute('CREATE TABLE IF NOT EXISTS objects(namespace TEXT, owner TEXT, identity TEXT, version INTEGER, payload TEXT, checksum TEXT, PRIMARY KEY(namespace,owner,identity,version))')

    @staticmethod
    def _knowledge(db,value,history):
        if value['namespace']!='KNOWLEDGE':return
        from system_layer.contracts import authorize
        body=load_custody_json(StringIO(value['content']));request=body['request']
        from knowledge.registry import validate_pending_record
        validate_pending_record(body)
        authorize(value['owner'],'KNOWLEDGE_REGISTER',request,value['authorization'])
        if (body.get('contract')!='KnowledgeRecord/1' or request['knowledge_id']!=value['object_id'] or
            request['expected_previous']!=value['previous_hash'] or
            value['metadata']!={'project_id':request['project_id'],'kind':request['knowledge_type'],
                'knowledge_class':request['pool'],'lifecycle':request['lifecycle']}):
            raise PermissionError('Knowledge import classification/custody mismatch')
        if history:
            prior=json.loads(history[-1]['content'])['request']
            if (prior['pool'],prior['project_id'])!=(request['pool'],request['project_id']):
                raise PermissionError('Knowledge import cannot promote source classification')
        if not request['sources'] or len(request['sources'])!=len(body['source_lineage']):
            raise PermissionError('Knowledge source provenance required')
        for ref,lineage in zip(request['sources'],body['source_lineage']):
            sources=CustodyStore._history(db,'DOCUMENT',value['owner'],ref['object_id'])
            if type(ref['version']) is not int or not 1<=ref['version']<=len(sources):
                raise PermissionError('Knowledge source unavailable')
            source=sources[ref['version']-1]
            if source['metadata']['knowledge_class']!=request['pool']:
                raise PermissionError('Knowledge import must retain source pool')
            if request['knowledge_type']=='GOVERNING_AUTHORITY' and (
                request['pool']!='SYSTEM' or source['metadata']['kind'] not in {'AUTHORITATIVE','SPECIFICATION','CONTRACT','CANON'}):
                raise PermissionError('Source is not governing authority')
            if request['knowledge_type']=='LEARNED_KNOWLEDGE' and request['pool']=='SYSTEM':
                raise PermissionError('Learned Knowledge is not governing System authority')
            expected={'reference':ref,'record_hash':source['record_hash'],
                'source_pool':source['metadata']['knowledge_class'],'source_kind':source['metadata']['kind'],
                'source_provenance':source['metadata']['source_reference']}
            if ref['expected_hash']!=source['record_hash'] or lineage!=expected or source['metadata']['project_id']!=request['project_id']:
                raise PermissionError('Knowledge import source provenance mismatch')

    @staticmethod
    def _history(db, namespace, owner, identity):
        rows=db.execute('SELECT version,payload,checksum FROM objects WHERE namespace=? AND owner=? AND identity=? ORDER BY version',(namespace,owner,identity)).fetchall()
        previous=None; result=[]
        for version,raw,checksum in rows:
            value=load_custody_json(StringIO(raw))
            fields={'schema_version','namespace','owner','object_id','version','previous_hash','content',
                    'content_hash','metadata','authorization','timestamp'}
            if (type(value) is not dict or set(value)!=fields or value['schema_version']!='CustodyObject/1'
                    or type(value['version']) is not int or type(value['content']) is not str
                    or type(value['metadata']) is not dict or type(value['authorization']) is not dict
                    or type(value['timestamp']) is not str or not value['timestamp']
                    or value['content_hash']!=digest(value['content'])
                    or version!=len(result)+1 or value['version']!=version or value['previous_hash']!=previous
                    or value['namespace']!=namespace or value['owner']!=owner or value['object_id']!=identity
                    or digest(value)!=checksum):
                raise ValueError('CUSTODY_INTEGRITY_FAILURE')
            CustodyStore._knowledge(db,value,result)
            from .document_admission import validate_document
            validate_document(db,value,result)
            result.append(dict(value,record_hash=checksum));previous=checksum
        return result

    def append(self, namespace, owner, identity, content, metadata, *, expected_previous, authorization, document_admission=None):
        from .document_admission import _DOCUMENT_WRITER
        if namespace in {'DOCUMENT','DOCUMENT_AUTHORITY'} and document_admission is not _DOCUMENT_WRITER:
            raise PermissionError('Document import must use governed Document service admission')
        if namespace not in {'DOCUMENT','VAULT','DOCUMENT_AUTHORITY','KNOWLEDGE'} or any(type(v) is not str or not v.strip() for v in (owner,identity,content)):
            raise ValueError('Explicit object namespace, owner, identity and content required')
        if type(metadata) is not dict or type(authorization) is not dict:
            raise ValueError('Explicit custody metadata and authorization objects required')
        with sqlite3.connect(self.path,timeout=15) as db:
            db.execute('BEGIN IMMEDIATE')
            history=self._history(db,namespace,owner,identity)
            previous=history[-1]['record_hash'] if history else None
            if previous!=expected_previous:raise ValueError('STALE_CUSTODY_VERSION')
            value={'schema_version':'CustodyObject/1','namespace':namespace,'owner':owner,'object_id':identity,
                'version':len(history)+1,'previous_hash':previous,'content':content,'content_hash':digest(content),
                'metadata':metadata,'authorization':authorization,'timestamp':now()}
            checksum=digest(value)
            self._knowledge(db,value,history)
            from .document_admission import validate_document
            validate_document(db,value,history)
            db.execute('INSERT INTO objects VALUES(?,?,?,?,?,?)',(namespace,owner,identity,value['version'],json.dumps(value,sort_keys=True),checksum))
        return dict(value,record_hash=checksum)

    def retrieve(self, namespace, owner, identity, *, version, expected_hash):
        if type(version) is not int or version<1 or not expected_hash:
            raise ValueError('Exact version and hash required; latest is not authoritative retrieval')
        with sqlite3.connect(self.path) as db:history=self._history(db,namespace,owner,identity)
        if version>len(history):raise FileNotFoundError('AUTHORITATIVE_OBJECT_UNAVAILABLE')
        record=history[version-1]
        if record['record_hash']!=expected_hash:raise ValueError('CUSTODY_REFERENCE_MISMATCH')
        return record

    def history(self, namespace, owner, identity):
        with sqlite3.connect(self.path) as db:
            return self._history(db,namespace,owner,identity)

    def search(self,namespace,owner,query,project_id,*,limit=25,include_history=False,content_resolver=None):
        """Bounded literal discovery of pinned records, never authority selection.

        Search covers at most 256 object histories in the requested namespace.
        A partial window is explicit; a missing match is not global absence.
        """
        if namespace not in {'DOCUMENT','VAULT','KNOWLEDGE'}:raise ValueError('Searchable custody namespace required')
        if any(type(v) is not str or not v.strip() for v in (owner,query,project_id)) or len(query)>1024:
            raise ValueError('Explicit bounded search text and project scope required')
        if type(limit) is not int or not 1<=limit<=100 or type(include_history) is not bool:
            raise ValueError('Bounded search options required')
        matches=[];count=0;examined=0;unavailable=[]
        with sqlite3.connect(self.path) as db:
            db.execute('BEGIN')
            identities=db.execute('SELECT DISTINCT identity FROM objects WHERE namespace=? AND owner=? ORDER BY identity LIMIT 257',
                                  (namespace,owner)).fetchall()
            for (identity,) in identities[:256]:
                history=self._history(db,namespace,owner,identity)
                records=history if include_history else history[-1:]
                for record in records:
                    examined+=1
                    if record['metadata'].get('project_id')!=project_id:continue
                    fields=['object_id'] if query.casefold() in record['object_id'].casefold() else []
                    source_info=None
                    try:
                        content,source_info=content_resolver(record) if content_resolver else (record['content'],None)
                        if query.casefold() in content.casefold():fields.append('extracted_content' if source_info else 'content')
                    except Exception as exc:
                        unavailable.append({'reference':{'object_id':identity,'version':record['version'],'expected_hash':record['record_hash']},
                            'state':'CONTENT_UNAVAILABLE','error_type':type(exc).__name__})
                    if not fields:continue
                    count+=1
                    if len(matches)<limit:
                        matches.append({'reference':{'object_id':identity,'version':record['version'],'expected_hash':record['record_hash']},
                            'kind':record['metadata'].get('kind'),'knowledge_class':record['metadata'].get('knowledge_class'),
                            'matched_fields':fields,'timestamp':record['timestamp'],'content_extraction':source_info,
                            'record_position':'LATEST_STORED_VERSION' if record['version']==history[-1]['version'] else 'HISTORICAL_VERSION',
                            'authority_status':'NOT_RECONCILED','claims_validated':False})
        return {'contract':'CustodySearch/1','namespace':namespace,'project_id':project_id,'query':query,
            'match_method':'LITERAL_CASEFOLD_SUBSTRING','include_history':include_history,'matches':matches,
            'examined_records':examined,'matching_records_in_window':count,'results_limited':count>limit,
            'search_completeness':'PARTIAL_CONTENT_UNAVAILABLE' if unavailable else 'PARTIAL_OBJECT_WINDOW' if len(identities)>256 else 'COMPLETE_FOR_SELECTED_NAMESPACE',
            'object_window_limited':len(identities)>256,'unavailable_content':unavailable,
            'execution_authority':False,'automatically_selected':False}
