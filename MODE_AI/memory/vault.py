"""Intentional preservation only. Thread context is never silently promoted."""
from data_governance.custody_store import CustodyStore
from system_layer.contracts import authorize


class Vault:
    def __init__(self, path):self.store=CustodyStore(path)

    def preserve(self, owner, request, approval):
        if set(request)!={'object_id','content','source_reference','authority','kind','project_id','thread_id','expected_previous'}:
            raise ValueError('Complete preservation and lineage request required')
        if any(not isinstance(request[k],str) or not request[k].strip() for k in ('source_reference','authority','kind','project_id','thread_id')):
            raise ValueError('Vault provenance and scope must be explicit')
        authorize(owner,'VAULT_PRESERVE',request,approval)
        return self.store.append('VAULT',owner,request['object_id'],request['content'],
            {k:v for k,v in request.items() if k not in {'object_id','content','expected_previous'}},
            expected_previous=request['expected_previous'],authorization=approval)

    def retrieve(self, owner, object_id, version, expected_hash):
        return self.store.retrieve('VAULT',owner,object_id,version=version,expected_hash=expected_hash)

    def search(self,owner,query,project_id,limit=25,include_history=False):
        return self.store.search('VAULT',owner,query,project_id,limit=limit,include_history=include_history)

    def preserve_thread(self, owner, request, approval, *, thread_store):
        """Preserve an explicit snapshot; never promote a thread automatically."""
        import json
        from system_layer.contracts import digest
        fields={'object_id','thread_id','expected_thread_hash','project_id','expected_previous'}
        if type(request) is not dict or set(request)!=fields:
            raise ValueError('Exact thread snapshot request required')
        authorize(owner,'VAULT_PRESERVE_THREAD',request,approval)
        thread=thread_store.load_thread(owner,request['thread_id']).to_dict()
        if digest(thread)!=request['expected_thread_hash']:
            raise ValueError('Thread changed since preservation was proposed')
        if type(request['project_id']) is not str or not request['project_id'].strip():
            raise ValueError('Explicit project scope required')
        return self.store.append('VAULT',owner,request['object_id'],
            json.dumps(thread,sort_keys=True,ensure_ascii=False,allow_nan=False),
            {'kind':'THREAD_SNAPSHOT','thread_id':request['thread_id'],'project_id':request['project_id'],
             'source_reference':'thread:'+request['thread_id'],'source_hash':request['expected_thread_hash'],
             'authority':'OPERATOR_PRESERVED_HISTORY','claims_validated':False},
            expected_previous=request['expected_previous'],authorization=approval)

    def thread_snapshot(self, owner, object_id, version, expected_hash):
        import json
        from system_layer.contracts import digest
        record=self.retrieve(owner,object_id,version,expected_hash)
        if record['metadata'].get('kind')!='THREAD_SNAPSHOT':
            raise ValueError('Preserved thread snapshot required')
        thread=json.loads(record['content'])
        if (thread.get('operator_id')!=owner or thread.get('thread_id')!=record['metadata']['thread_id']
                or digest(thread)!=record['metadata']['source_hash']):
            raise ValueError('Thread snapshot provenance mismatch')
        return {'contract':'PreservedThread/1','record_hash':record['record_hash'],
                'version':record['version'],'thread':thread,'claims_validated':False}
