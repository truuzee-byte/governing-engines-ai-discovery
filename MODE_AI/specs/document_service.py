"""Governed document intake/version custody. Rendered output is not its source spec."""
from data_governance.custody_store import CustodyStore
from system_layer.contracts import authorize
from data_governance.document_admission import _DOCUMENT_WRITER
          
KINDS={'AUTHORITATIVE','HISTORICAL','SUPERSEDED','DRAFT','FAILURE_ARTIFACT','AUDIT_ARTIFACT',
       'CANON','SPECIFICATION','CONTRACT','CONCEPT_ART','GENERATED_CANDIDATE','PRODUCTION_ASSET','RENDERED_EVIDENCE'}
VISUAL={'NOT_APPLICABLE','CANONICAL_VISUAL_AUTHORITY','APPROVED_CONCEPT_DIRECTION',
        'EXPLORATORY_CONCEPT','REFERENCE','GENERATED_CANDIDATE','PRODUCTION_ASSET','RENDERED_EVIDENCE'}


class DocumentService:
    def __init__(self,path):self.store=CustodyStore(path)

    def intake(self, owner, request, approval):
        self._validate_request(request)
        authorize(owner,'DOCUMENT_INTAKE',request,approval)
        return self._store(owner,request,approval)

    @staticmethod
    def _validate_request(request):
        fields={'object_id','content','kind','visual_authority','source_reference','authority',
                'project_id','thread_id','expected_previous','validation_references','knowledge_class'}
        if type(request) is not dict or set(request)!=fields:raise ValueError('Incomplete document contract')
        if request['kind'] not in KINDS or request['visual_authority'] not in VISUAL:
            raise ValueError('Unknown document classification')
        if request['knowledge_class'] not in {'SYSTEM','INTERNAL','EXTERNAL'}:
            raise ValueError('Explicit knowledge provenance class required')
        for key in ('source_reference','authority','project_id','thread_id'):
            if type(request[key]) is not str or not request[key].strip():raise ValueError('Missing document lineage: '+key)
        if type(request['validation_references']) is not list or any(type(v) is not str or not v for v in request['validation_references']):
            raise ValueError('Explicit validation references required')
    def _store(self,owner,request,approval,extra=None):
        return self.store.append('DOCUMENT',owner,request['object_id'],request['content'],
            {**{k:v for k,v in request.items() if k not in {'object_id','content','expected_previous'}},**(extra or {})},
            expected_previous=request['expected_previous'],authorization=approval,document_admission=_DOCUMENT_WRITER)

    def derive(self,owner,request,approval):
        if type(request) is not dict or set(request)!={'document','sources','derivation','mechanism_reference'}:
            raise ValueError('Complete document derivation required')
        authorize(owner,'DOCUMENT_DERIVATION',request,approval)
        self._validate_request(request['document'])
        if request['derivation'] not in {'EXTRACTION','MANUAL_REVISION','GENERATED_CANDIDATE'}:
            raise ValueError('Unsupported derivation; rendering needs observed output')
        if type(request['mechanism_reference']) is not str or not request['mechanism_reference'].strip():
            raise ValueError('Actual derivation mechanism reference required')
        if request['document']['kind'] not in {'DRAFT','GENERATED_CANDIDATE','FAILURE_ARTIFACT','AUDIT_ARTIFACT'}:
            raise PermissionError('Derived material must remain a candidate until separately governed')
        if type(request['sources']) is not list or not 0<len(request['sources'])<=256:
            raise ValueError('Explicit bounded source lineage required')
        sources=[];seen=set()
        for ref in request['sources']:
            if type(ref) is not dict or set(ref)!={'object_id','version','expected_hash'}:raise ValueError('Exact source required')
            source=self.retrieve(owner,**ref)
            if source['metadata']['project_id']!=request['document']['project_id']:raise PermissionError('Derivation project mismatch')
            if source['record_hash'] in seen:raise ValueError('Duplicate derivation source')
            seen.add(source['record_hash'])
            sources.append({'reference':dict(ref),'knowledge_class':source['metadata']['knowledge_class'],
                            'kind':source['metadata']['kind'],'content_hash':source['content_hash']})
        return self._store(owner,request['document'],approval,{'derivation':request['derivation'],
            'derivation_sources':sources,'mechanism_reference':request['mechanism_reference'],
            'claims_validated':False,'rendered_output_observed':False})

    def retrieve(self, owner, object_id, version, expected_hash):
        return self.store.retrieve('DOCUMENT',owner,object_id,version=version,expected_hash=expected_hash)

    def restore(self,owner,request,approval):
        """Document v2.0 §10: restore as a new version, never overwrite history."""
        if type(request) is not dict or set(request)!={'source','expected_previous','reason'}:
            raise ValueError('Pinned restoration source and current version required')
        if type(request['reason']) is not str or not request['reason'].strip():
            raise ValueError('Restoration reason required')
        source=request['source']
        if type(source) is not dict or set(source)!={'object_id','version','expected_hash'}:
            raise ValueError('Exact restoration source required')
        authorize(owner,'DOCUMENT_RESTORE',request,approval)
        record=self.retrieve(owner,**source)
        if request['expected_previous'] is None:raise ValueError('Existing current version required')
        metadata=dict(record['metadata'])
        metadata.update(restoration_source=dict(source),restoration_reason=request['reason'],
            claims_validated=False,rendered_output_observed=False)
        return self.store.append('DOCUMENT',owner,record['object_id'],record['content'],metadata,
            expected_previous=request['expected_previous'],authorization=approval,document_admission=_DOCUMENT_WRITER)

    def document_model(self, owner, object_id, version, expected_hash):
        """Source-bound model view; unavailable structure stays unavailable (§4)."""
        from system_layer.contracts import digest
        record = self.retrieve(owner, object_id, version, expected_hash)
        raw, binary_hash = self.source_bytes(owner, object_id, version, expected_hash)
        metadata = record['metadata']
        extraction = None
        missing = []
        try:
            source = self._text_record(record, require_text=False)
            extraction = source['extraction']
            segments = extraction['segments'] if extraction else [{'text': source['content']}]
        except ValueError:
            segments = []
            missing.append('TEXT_INTERPRETATION_UNAVAILABLE')
        segments = [dict(segment, segment_id=digest({'source':expected_hash,'index':index,'segment':segment}))
                    for index,segment in enumerate(segments)]
        paragraphs = ([{'paragraph_id':s['segment_id'],'source_locator':s['locator'],'text':s['text']}
                       for s in segments] if extraction and extraction['format']=='DOCX' else None)
        pages = ([{'page':int(s['locator'].split(':')[1]),'segment_id':s['segment_id'],
                   'reading_order_validated':False} for s in segments]
                 if extraction and extraction['format']=='PDF' else None)
        history = self.store.history('DOCUMENT', owner, object_id)
        structural = (extraction or {}).get('structure') or {}
        model = {'contract':'DocumentModel/1', 'document_id':object_id,
            'version_id':record['record_hash'], 'version':version, 'owner':owner,
            'source_reference':{'object_id':object_id,'version':version,'expected_hash':expected_hash},
            'binary_sha256':binary_hash, 'content_hash':record['content_hash'],
            'lifecycle':metadata['kind'], 'availability':'RETRIEVED',
            'processing':'PARTIAL_STRUCTURE', 'authority_state':'NOT_RECONCILED',
            'declared_authority':metadata['authority'], 'knowledge_class':metadata['knowledge_class'],
            'visual_authority':metadata['visual_authority'],
            'project_id':metadata['project_id'], 'thread_id':metadata['thread_id'],
            'permissions':{'owner':owner,'visibility':'OWNER_SCOPED'},
            'structure':{'segments':segments,'sections':structural.get('sections'),'paragraphs':paragraphs,'tables':structural.get('tables'),
                         'figures':None,'citations':None,'page_mappings':pages},
            'validation':{'state':'UNPROVEN','references':metadata['validation_references']},
            'claims':None,'rp_references':[],
            'lineage':{'source_reference':metadata['source_reference'],
                      'derivation_sources':metadata.get('derivation_sources',[]),
                      'previous_hash':record['previous_hash']},
            'custody_receipt':record['record_hash'], 'approval':record['authorization'],
            'finalization':'NOT_ESTABLISHED', 'is_latest_version':version==history[-1]['version'],
            'recovery_history':[{'version':r['version'],'record_hash':r['record_hash'],
                'source':r['metadata']['restoration_source'],'reason':r['metadata']['restoration_reason']}
                for r in history[:version] if 'restoration_source' in r['metadata']], 'extraction':extraction,
            'missing':missing+['STRUCTURED_LAYOUT_NOT_ESTABLISHED','CLAIM_EVIDENCE_NOT_INTERPRETED'],
            'rendered_output_observed':False,'execution_authority':False}
        model['model_hash'] = digest(model)
        return model

    def search(self,owner,query,project_id,limit=25,include_history=False):
        def content(record):
            source=self._text_record(record)
            return source['content'],({k:v for k,v in source['extraction'].items() if k!='segments'} if source['extraction'] else None)
        return self.store.search('DOCUMENT',owner,query,project_id,limit=limit,include_history=include_history,content_resolver=content)

    def passage(self,owner,object_id,version,expected_hash,segment_id):
        """Exact source passage; absence is not a claim that content is unspecified."""
        if type(segment_id) is not str or not segment_id:raise ValueError('Exact segment identity required')
        model=self.document_model(owner,object_id,version,expected_hash)
        matches=[s for s in model['structure']['segments'] if s['segment_id']==segment_id]
        if len(matches)!=1:raise FileNotFoundError('Selected source passage unavailable')
        return {'contract':'DocumentPassage/1','source_reference':model['source_reference'],
            'segment':matches[0],'binary_sha256':model['binary_sha256'],
            'knowledge_class':model['knowledge_class'],'lifecycle':model['lifecycle'],
            'authority_state':model['authority_state'],'validation':model['validation'],
            'extraction':({k:v for k,v in model['extraction'].items() if k not in {'segments','structure'}}
                if model['extraction'] else None),'state':'RETRIEVED','claims_validated':False,
            'execution_authority':False}

    def extract_text(self,owner,object_id,version,expected_hash,project_id):
        from .document_extraction import extract
        record=self.retrieve(owner,object_id,version,expected_hash)
        if record['metadata']['project_id']!=project_id:raise PermissionError('Document extraction project mismatch')
        result=extract(record['content'])
        return dict(result,source_reference={'object_id':object_id,'version':version,'expected_hash':expected_hash},
            source_record_hash=record['record_hash'],source_knowledge_class=record['metadata']['knowledge_class'],
            source_kind=record['metadata']['kind'],project_id=project_id,persisted=False)

    def text_source(self,owner,object_id,version,expected_hash):
        """Quoted source for context; decoding does not establish visual fidelity."""
        return self._text_record(self.retrieve(owner,object_id,version,expected_hash))

    @staticmethod
    def _text_record(record, require_text=True):
        import json
        try:encoded=json.loads(record['content'])
        except (ValueError,TypeError):encoded=None
        if isinstance(encoded,dict) and encoded.get('schema_version') in {'AudioSource/1','ImageSource/1'}:
            raise ValueError('Selected media has no admitted text interpretation; transcription/OCR not performed')
        if isinstance(encoded,dict) and encoded.get('schema_version')=='DocumentBinary/1':
            from .document_extraction import extract
            extraction=dict(extract(record['content']),source_record_hash=record['record_hash'],
                source_reference={'object_id':record['object_id'],'version':record['version'],'expected_hash':record['record_hash']},
                source_knowledge_class=record['metadata']['knowledge_class'],source_kind=record['metadata']['kind'],
                project_id=record['metadata']['project_id'],persisted=False)
            if require_text and (not extraction['segments'] or not any(segment['text'].strip() for segment in extraction['segments'])):
                raise ValueError('Selected document has no extracted source text; no substitute available')
            return {'content':'\n'.join(segment['text'] for segment in extraction['segments']),
                'extraction':extraction,'source_record_hash':record['record_hash'],'claims_validated':False}
        return {'content':record['content'],'extraction':None,'source_record_hash':record['record_hash'],'claims_validated':False}

    def source_bytes(self,owner,object_id,version,expected_hash):
        """Return exact preserved source bytes, never a regenerated document."""
        import json
        import hashlib
        record=self.retrieve(owner,object_id,version,expected_hash)
        try:encoded=json.loads(record['content'])
        except (ValueError,TypeError):encoded=None
        if isinstance(encoded,dict) and encoded.get('schema_version')=='DocumentBinary/1':
            from .document_extraction import decode_source
            _,raw=decode_source(record['content'])
        elif isinstance(encoded,dict) and encoded.get('schema_version') in {'AudioSource/1','ImageSource/1'}:
            from io import StringIO
            import base64
            from data_governance.custody_json import load
            encoded=load(StringIO(record['content']))
            required_encoding='BASE64_WAV' if encoded['schema_version']=='AudioSource/1' else 'BASE64'
            if set(encoded)!={'schema_version','encoding','data','sha256'} or encoded['encoding']!=required_encoding:
                raise ValueError('Exact media source envelope required')
            if type(encoded['data']) is not str or len(encoded['data'])>12*1024*1024:
                raise ValueError('Bounded media source required')
            raw=base64.b64decode(encoded['data'],validate=True)
            if len(raw)>8*1024*1024 or hashlib.sha256(raw).hexdigest()!=encoded['sha256']:
                raise ValueError('Media source size/hash mismatch')
        else:raw=record['content'].encode('utf-8')
        return raw,hashlib.sha256(raw).hexdigest()

    def specification_source(self, owner, object_id, version, expected_hash):
        record=self.retrieve(owner,object_id,version,expected_hash)
        if record['metadata']['kind'] not in {'AUTHORITATIVE','SPECIFICATION','CONTRACT'}:
            raise PermissionError('Document is not an authoritative specification source')
        # Source material only; no inferred Builder approval, parsed instructions or PASS.
        return {'contract':'DocumentSpecificationSource/1','record':record,
                'execution_authority':False,'specification_readiness':'NOT_EVALUATED'}

    def reconcile_authority(self, owner, request, approval):
        from .document_authority import DocumentAuthority
        return DocumentAuthority(self).reconcile(owner,request,approval)

    def prepare_specification(self, owner, scope_id, version, expected_hash, project_id):
        """Prepare a canonical draft from an explicitly selected structured source.

        Prose interpretation is not inferred here. Document approval establishes
        the source, never execution authority or specification readiness.
        """
        import copy
        import json
        from .document_authority import DocumentAuthority
        from .spec_engine import create_specification_object, REQUIRED_INTERPRETED_BUILD_REQUEST_FIELDS
        resolved=DocumentAuthority(self).resolve(owner,scope_id,version,expected_hash)
        if resolved['state']!='CURRENT_AUTHORITY':
            raise PermissionError('Current document authority required: '+resolved['state'])
        record=resolved['sources'][0]
        if record['metadata']['kind'] not in {'AUTHORITATIVE','SPECIFICATION','CONTRACT'}:
            raise PermissionError('Source is not a structured specification')
        if type(project_id) is not str or not project_id or record['metadata']['project_id']!=project_id:
            raise PermissionError('Document project scope mismatch')
        def unique(pairs):
            result={}
            for key,value in pairs:
                if key in result:raise ValueError('Duplicate structured source field')
                result[key]=value
            return result
        def invalid_constant(value):raise ValueError('Non-finite structured source value')
        request=json.loads(record['content'],object_pairs_hook=unique,parse_constant=invalid_constant)
        extraction=None
        if isinstance(request,dict) and request.get('schema_version')=='DocumentBinary/1':
            from .document_extraction import extract
            extracted=extract(record['content'])
            if extracted['state']!='TEXT_EXTRACTED' or len(extracted['segments'])!=1:
                raise PermissionError('Extracted document requires review before structured specification preparation')
            request=json.loads(extracted['segments'][0]['text'],object_pairs_hook=unique,parse_constant=invalid_constant)
            extraction={'mechanism_reference':extracted['mechanism_reference'],'binary_sha256':extracted['binary_sha256'],
                'format':extracted['format'],'source_record_hash':record['record_hash'],
                'transformation':'LOSSLESS_UTF8_DECODE','rendered_output_observed':False}
        states={'authority_state':'draft_only','validation_state':'incomplete','readiness_state':'needs_clarification',
                'save_ready_state':False,'clarification_required':True}
        allowed=set(REQUIRED_INTERPRETED_BUILD_REQUEST_FIELDS)|set(states)|{'artifact_structure','execution','validation','evidence','completion'}
        if type(request) is not dict or set(request)-allowed:
            raise ValueError('Source cannot be represented without field loss')
        draft=copy.deepcopy(request)
        transformations=[]
        for key,value in {**states,'execution_authority':'draft_only'}.items():
            transformations.append({'field':key,'source_value':request.get(key),'draft_value':value,
                                    'reason':'Source custody does not grant build authority or readiness'})
            draft[key]=value
        specification=create_specification_object(draft,draft_only=True)
        source={'object_id':record['object_id'],'version':record['version'],'expected_hash':record['record_hash']}
        authority={'scope_id':scope_id,'version':version,'expected_hash':expected_hash}
        specification['lineage']['document_source']=source
        specification['lineage']['document_authority']=authority
        if extraction is not None:specification['lineage']['document_extraction']=extraction
        specification['metadata']['project_id']=project_id
        return {'contract':'DocumentSpecificationPreparation/1','specification':specification,
                'source_reference':source,'authority_reference':authority,'transformations':transformations,
                'extraction':extraction,'execution_authority':False,'specification_readiness':'needs_clarification'}

    def export(self, owner, object_id, version, expected_hash, format):
        """Serialize an exact source; export is not observation of rendered output."""
        import hashlib
        import html
        import json
        record=self.retrieve(owner,object_id,version,expected_hash)
        source=self.text_source(owner,object_id,version,expected_hash) if format in {'TEXT','HTML'} else None
        if format=='MODEL_JSON':
            content=json.dumps(self.document_model(owner,object_id,version,expected_hash),sort_keys=True,ensure_ascii=False,allow_nan=False)
            media='application/json'
        elif format=='TEXT':
            content=source['content'];media='text/plain; charset=utf-8'
        elif format=='JSON':
            content=json.dumps(record,sort_keys=True,ensure_ascii=False,allow_nan=False);media='application/json'
        elif format=='HTML':
            content=('<!doctype html><html lang="en"><head><meta charset="utf-8">'
                '<meta http-equiv="Content-Security-Policy" content="default-src \'none\'">'
                '<title>'+html.escape(object_id)+'</title></head><body><pre>'+
                html.escape(source['content'])+'</pre></body></html>')
            media='text/html; charset=utf-8'
        else:raise ValueError('Unsupported export format')
        return {'contract':'DocumentExport/1','source_reference':{'object_id':object_id,'version':version,
                'expected_hash':expected_hash},'content':content,'media_type':media,
                'sha256':hashlib.sha256(content.encode('utf-8')).hexdigest(),
                'byte_length':len(content.encode('utf-8')),'format':format,
                'source_project_id':record['metadata']['project_id'],
                'source_knowledge_class':record['metadata']['knowledge_class'],
                'source_transformation':('DOCUMENT_MODEL' if format=='MODEL_JSON' else 'EXTRACTED_TEXT' if source and source['extraction'] else 'PRESERVED_RECORD' if format=='JSON' else 'SOURCE_TEXT'),
                'extraction':({k:v for k,v in source['extraction'].items() if k!='segments'} if source and source['extraction'] else None),
                'state':'SERIALIZED','rendered_output_observed':False,'execution_authority':False}
