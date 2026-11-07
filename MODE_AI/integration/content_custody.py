"""Explicit Operator command surfaces; never called from generated model text."""
from integration.strict_json import load_payload
from memory.vault import Vault
from specs.document_service import DocumentService


def execute(runtime,text):
    """Observe the actual command attempt without logging preserved private content."""
    from uuid import uuid4
    from system_layer.contracts import digest
    identity='custody-operation:'+uuid4().hex
    payload={'operation_id':identity,'command':text.partition(' ')[0],
             'request_hash':digest(text),'state':'STARTED','execution_authority':False}
    try:
        result=command(runtime,text)
    except Exception as exc:
        payload.update(state='REJECTED' if isinstance(exc,PermissionError) else 'FAILED',error_type=type(exc).__name__)
        if isinstance(exc,PermissionError):payload['authorization_state']='REJECTED'
        runtime._observe_runtime_event('custody_operation',payload,runtime_error=type(exc).__name__)
        raise
    payload.update(state='COMPLETED',result_hash=digest(result))
    if isinstance(result,dict):
        payload['result_state']=result.get('state')
        if result.get('errors'):payload.update(state='FAILED',error_type='RESULT_ERRORS')
        payload['record_references']=[result[k] for k in ('record_hash','source_record_hash','preparation_hash','observation_id','thread_hash') if isinstance(result.get(k),str)]
        if result.get('contract') in {'ThreadCreation/1','ThreadFork/1'}:
            payload['thread_reference']={'operator_id':result['thread']['operator_id'],
                'thread_id':result['thread']['thread_id'],'expected_hash':result['thread_hash']}
        payload['result_contract']=result.get('contract',result.get('schema_version'))
        if str(result.get('contract','')).startswith('Cinematic') or result.get('contract')=='StoryInterpretation/1':
            # Preserve exact source/intermediate/specification/evidence linkage;
            # command text and story content are not copied into Observation.
            payload['cinematic_lineage']={key:result[key] for key in (
                'selected_source','references','reference','specification_reference',
                'specification_hash','requirement_id','observation_id','observation_hash') if key in result}
        if result.get('contract')=='DocumentTextExtraction/1':
            from hashlib import sha256
            payload['extraction_evidence']={key:result[key] for key in (
                'source_reference','source_record_hash','binary_sha256','format','mechanism_reference',
                'project_id','source_knowledge_class','state','unresolved','rendered_output_observed')}
            payload['extraction_evidence']['segments']=[{'locator':segment['locator'],
                'sha256':sha256(segment['text'].encode('utf-8')).hexdigest(),
                'byte_length':len(segment['text'].encode('utf-8'))} for segment in result['segments']]
            payload['extraction_evidence']['content_representation']='SEGMENT_HASHES_ONLY'
        if result.get('contract')=='DocumentExport/1':
            payload['output_artifacts']=[{'kind':'SERIALIZED_DOCUMENT','sha256':result['sha256'],
                'byte_length':result['byte_length'],'media_type':result['media_type'],
                'source_reference':result['source_reference'],'project_id':result['source_project_id'],
                'knowledge_class':result['source_knowledge_class'],'rendered_output_observed':False,
                'source_transformation':result['source_transformation'],'extraction':result['extraction']}]
    observation=runtime._observe_runtime_event('custody_operation',payload,runtime_error=payload.get('error_type'))
    if observation is not None and observation.collection_errors:
        observation=None
    if isinstance(result,dict) and result.get('contract')=='DocumentExport/1':
        result=dict(result,observation_reference=({'observation_id':observation.observation_id,
            'expected_hash':digest(observation.to_dict()),'result_payload_hash':payload['result_hash']}
            if observation is not None else None),observation_state='RECORDED' if observation is not None else 'UNAVAILABLE')
    return result


def command(runtime, text):
    prefix=next((p for p in ('/vault ','/documents ','/knowledge ','/creative ','/thread ','/onboarding ') if text.startswith(p)),None)
    if prefix is None:return None
    owner=runtime.context.identity.operator_id
    if prefix=='/onboarding ':
        from onboarding.runtime import update
        return update(runtime,**load_payload(text[len(prefix):]))
    if prefix=='/thread ':
        action,_,body=text[len(prefix):].partition(' ')
        if action=='create':
            return runtime.thread_store.create_from_request(owner,**load_payload(body))
        if action=='activate':
            from memory.thread_runtime import activate
            return activate(runtime,**load_payload(body))
        if action!='fork':raise ValueError('Unsupported continuity operation')
        return runtime.thread_store.fork_thread(owner,**load_payload(body))
    if prefix=='/creative ':
        from understanding.creative_production import CreativePreparation
        creative=CreativePreparation(runtime.understanding_engine.store.path.with_name('content_custody.sqlite3'))
        body=text[len(prefix):]
        if body.startswith('cinematic '):
            from understanding.cinematic_runtime import execute as cinematic_execute
            action,_,payload=body[len('cinematic '):].partition(' ')
            return cinematic_execute(runtime,action,**load_payload(payload))
        if body.startswith('understand '):
            from understanding.creative_understanding import understand
            return understand(runtime,**load_payload(body[len('understand '):]))
        if body.startswith('asset_search '):
            from understanding.asset_planning import search
            return search(creative,owner=owner,**load_payload(body[len('asset_search '):]))
        if body.startswith('asset_plan '):
            from understanding.asset_planning import plan
            return plan(creative,owner=owner,**load_payload(body[len('asset_plan '):]))
        if body.startswith('inspect_frames '):
            return creative.inspect_frames(owner=owner,**load_payload(body[len('inspect_frames '):]),
                collector=runtime.runtime_observation_collector,thread_id=runtime.context.active_thread.thread_id)
        if body.startswith('inspect_audio '):
            return creative.inspect_audio(owner=owner,**load_payload(body[len('inspect_audio '):]),
                collector=runtime.runtime_observation_collector,thread_id=runtime.context.active_thread.thread_id)
        if body.startswith('model '):
            from understanding.creative_models import SharedCreativeModels
            return SharedCreativeModels(creative.documents.store.path).resolve(owner=owner,**load_payload(body[len('model '):]))
        if body.startswith('operations '):
            from system_layer.runtime import service
            return creative.operational_models(owner=owner,**load_payload(body[len('operations '):]),system_store=service(runtime).store)
        if body.startswith('evidence '):
            return creative.locate_observations(owner=owner,**load_payload(body[len('evidence '):]),
                observation_store=runtime.runtime_observation_collector.store)
        return creative.prepare(owner,load_payload(body))
    if prefix=='/knowledge ':
        from knowledge.retrieval import KnowledgeRetrieval
        retrieval=KnowledgeRetrieval(runtime.understanding_engine.store.path.with_name('content_custody.sqlite3'))
        body=text[len(prefix):]
        if body.startswith('record_context '):
            from knowledge.runtime_context import select_records
            return select_records(runtime,**load_payload(body[len('record_context '):]))
        if body.startswith(('register ','record ','records ','relationships ','meaning ')):
            from knowledge.registry import KnowledgeRegistry
            registry=KnowledgeRegistry(retrieval.documents.store.path,runtime.understanding_engine.store)
            action,_,payload=body.partition(' ')
            method={'register':registry.register,'record':registry.retrieve,'records':registry.search,
                    'relationships':registry.relationships,'meaning':registry.meaning_lookup}[action]
            return method(owner=owner,**load_payload(payload))
        if body.startswith('search '):return retrieval.search(owner=owner,**load_payload(body[len('search '):]))
        if body.startswith('authority_context '):
            from knowledge.runtime_context import select_authority
            return select_authority(runtime,**load_payload(body[len('authority_context '):]))
        if body.startswith('context '):
            from knowledge.runtime_context import select
            return select(runtime,load_payload(body[len('context '):]))
        if body.startswith('resolve '):return retrieval.resolve_authority(owner=owner,**load_payload(body[len('resolve '):]))
        return retrieval.retrieve(owner,load_payload(body))
    service=(Vault if prefix=='/vault ' else DocumentService)(
        runtime.understanding_engine.store.path.with_name('content_custody.sqlite3'))
    action,_,body=text[len(prefix):].partition(' ')
    if prefix=='/documents ' and action=='understand':
        from specs.document_understanding import understand
        return understand(runtime,**load_payload(body))
    methods={'get':service.retrieve,'search':service.search}
    if prefix=='/vault ':
        if action=='context':
            from memory.vault_context import select
            return select(runtime,**load_payload(body))
        methods['preserve']=service.preserve
        methods['thread_snapshot']=service.thread_snapshot
        methods['preserve_thread']=lambda owner,request,approval:service.preserve_thread(
            owner,request,approval,thread_store=runtime.thread_store)
    else:methods.update(intake=service.intake,derive=service.derive,restore=service.restore,model=service.document_model,passage=service.passage,extract_text=service.extract_text,specification_source=service.specification_source,
                        prepare_specification=service.prepare_specification,authority=service.reconcile_authority,export=service.export)
    if action not in methods:raise ValueError('Unsupported custody operation')
    result=methods[action](owner=owner,**load_payload(body))
    if prefix=='/documents ' and action=='intake':
        from knowledge.runtime_context import remember_intake_reference
        remember_intake_reference(runtime,result)
    return result
