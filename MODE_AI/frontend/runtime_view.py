"""Explicit presentation projection; excludes private context and reasoning internals."""
STATES = {'IDLE','LISTENING','INTERPRETING','CLARIFYING','BUILDING','VALIDATING','HALTED','COMPLETE','ERROR'}
NAVIGATION = ['Chat Mode','Build Mode','Past Builds','Chat Threads','Operator Onboarding']


def operation_export(runtime,view_hash,*,expected_owner):
    """Download retained export bytes, never regenerate an unavailable result."""
    from copy import deepcopy
    from hashlib import sha256
    from system_layer.contracts import digest
    context=runtime.context
    operation=deepcopy(getattr(context,'operation_view',None))
    if (context.identity.operator_id!=expected_owner or not isinstance(operation,dict)
            or operation.get('operator_id')!=expected_owner or operation.get('thread_id')!=context.active_thread.thread_id
            or operation.get('view_hash')!=view_hash or digest({k:v for k,v in operation.items() if k!='view_hash'})!=view_hash):
        raise PermissionError('Retained export selection changed')
    result=operation.get('result')
    if not isinstance(result,dict) or result.get('contract')!='DocumentExport/1' or result.get('state')!='SERIALIZED':
        raise ValueError('No retained serialized export')
    raw=result['content'].encode('utf-8')
    if sha256(raw).hexdigest()!=result['sha256'] or len(raw)!=result['byte_length']:
        raise ValueError('Retained export bytes changed')
    return raw,result['sha256']


def observation_view(runtime,observation_id,expected_hash,*,expected_owner):
    from system_layer.contracts import digest
    if runtime.context.identity.operator_id!=expected_owner:raise PermissionError('Presentation owner changed')
    record=runtime.runtime_observation_collector.store.load_record(expected_owner,observation_id)
    value=record.to_dict()
    if record.operator_id!=expected_owner or digest(value)!=expected_hash:
        raise PermissionError('Observation scope/hash changed')
    return {'contract':'ModeObservationView/1','source':'STORED_OBSERVATION','observation':value,
        'observation_hash':expected_hash,'current_validity':'NOT_REVALIDATED','execution_authority':False}


def thread_view(runtime,thread_id,*,expected_owner):
    from system_layer.contracts import digest
    if runtime.context.identity.operator_id!=expected_owner:
        raise PermissionError('Presentation owner changed')
    thread=runtime.thread_store.load_thread(expected_owner,thread_id)
    return {'contract':'ModeThreadView/1','source':'STORED_THREAD','thread_id':thread.thread_id,'operator_id':expected_owner,
            'title':thread.title,'updated_at':thread.updated_at,'execution_authority':False,
            'active_thread_changed':False,'thread_hash':digest(thread.to_dict()),'continuity':thread.continuity,
            'messages':[{'role':m.role,'content':m.content,'message_id':m.message_id}
                        for m in thread.messages if m.role in {'operator','user','assistant','mode'}]}


def snapshot(runtime, *, expected_owner=None):
    from datetime import datetime, timezone
    import json
    from system_layer.contracts import digest
    context = runtime.context
    owner = context.identity.operator_id
    if expected_owner is not None and owner != expected_owner:
        raise PermissionError('Presentation owner changed')
    thread = context.active_thread
    if thread.operator_id != owner:
        raise PermissionError('Presentation thread owner mismatch')
    baseline=getattr(thread,'_custody_baseline',None)
    retention={'state':'NOT_VERIFIED','current_disk_state':'NOT_RECHECKED'}
    if baseline is not None:
        retention.update(state='WRITE_CONFLICT' if getattr(thread,'_custody_conflict',False) else
            'LOCAL_CHANGES_NOT_PERSISTED' if digest(thread.to_dict())!=baseline else 'MATCHES_LAST_LOADED_OR_SAVED_VERSION',
            last_loaded_or_saved_hash=baseline)
    state = getattr(context.runtime_state, 'value', context.runtime_state)
    if state not in STATES:
        raise ValueError('Unknown runtime presentation state')
    pending=getattr(runtime,'pending_action',None)
    pending_view=None
    if pending is not None:
        pending_view={'action_id':pending.action_id,'action_type':pending.action_type,'awaiting':pending.awaiting}
        if pending.action_type=='SAVE_MEMORY':pending_view['memory_text']=pending.payload['memory_text']
    onboarding=getattr(context,'onboarding_state',None)
    onboarding_view={'state':'NOT_RETRIEVED'}
    if onboarding is not None:
        if onboarding.operator_id!=owner:raise PermissionError('Onboarding owner mismatch')
        onboarding_view={'state':'COMPLETE' if onboarding.onboarding_complete else 'REQUIRED',
                         'onboarding_required':onboarding.onboarding_required,
                         'temporal_initialized':onboarding.temporal_initialized}
        profile=getattr(context,'profile',None)
        if profile is not None:
            if profile.operator_id!=owner:raise PermissionError('Profile owner mismatch')
            onboarding_view.update(operator_id=owner,profile_hash=digest(profile.to_dict()),answers={
                key:getattr(profile.operator_managed,key) for key in ('preferred_name','timezone','language')})
        else:onboarding_view['answers_state']='NOT_RETRIEVED'
    build = getattr(context, 'build_result', None)
    operation=getattr(context,'operation_view',None)
    if operation is not None:
        if (operation.get('operator_id')!=owner or operation.get('thread_id')!=thread.thread_id
                or operation.get('view_hash')!=digest({k:v for k,v in operation.items() if k!='view_hash'})):
            raise PermissionError('Operation presentation scope/integrity mismatch')
        if len(json.dumps(operation,ensure_ascii=False).encode())>65536:
            result=operation.get('result')
            export_reference=({'view_hash':operation['view_hash'],'sha256':result['sha256'],'byte_length':result['byte_length'],'format':result['format']}
                if isinstance(result,dict) and result.get('contract')=='DocumentExport/1' else None)
            reference=({k:result[k] for k in ('namespace','owner','object_id','version','record_hash','content_hash')}
                if isinstance(result,dict) and all(k in result for k in ('namespace','owner','object_id','version','record_hash','content_hash')) else None)
            if reference and reference['namespace']=='DOCUMENT':
                reference['project_id']=result['metadata']['project_id']
                try:encoded=json.loads(result['content'])
                except (ValueError,TypeError):encoded=None
                reference['declared_source_schema']=encoded.get('schema_version') if isinstance(encoded,dict) else None
            operation={k:operation[k] for k in ('contract','command','state','error_type','view_hash','execution_authority')}
            operation.update(result=None,result_reference=reference,export_reference=export_reference,display_state='RESULT_EXCEEDS_DISPLAY_LIMIT',content_omitted=True)
    build_view = None
    if isinstance(build, dict):
        build_view = {k:build[k] for k in ('request_id','state','reasons','observation_ids') if k in build}
        result = build.get('build') or {}
        build_view['artifact'] = {k:result[k] for k in ('validation_status','receipt_path','artifact_root') if k in result}
        rp = build.get('rp') or {}
        build_view['reality'] = {k:rp[k] for k in ('accepted','rp_state','reason') if k in rp}
    return {'contract':'ModePresentation/1','navigation':list(NAVIGATION),'state':state,
            'operator_id':owner,
            'captured_at':datetime.now(timezone.utc).isoformat(),
            'thread_id':thread.thread_id,'title':thread.title,
            'thread_retention':retention,
            'messages':[{'role':m.role,'content':m.content,'message_id':m.message_id}
                        for m in thread.messages if m.role in {'operator','user','assistant','mode'}],
            'build':build_view,'operation':operation,'pending_action':pending_view,'past_builds':{'state':'NOT_RETRIEVED'},
            'threads':[{'thread_id':thread.thread_id,'title':thread.title,'active':True}],
            'onboarding':onboarding_view,
            'execution_authority':False,'source':'ACTIVE_RUNTIME_SNAPSHOT'}


def history(runtime, *, expected_owner):
    """Explicit historical view, never revalidates or upgrades a past build."""
    if runtime.context.identity.operator_id!=expected_owner:
        raise PermissionError('Presentation owner changed')
    from system_layer.contracts import digest
    result={'contract':'ModeHistory/1','execution_authority':False}
    try:
        threads=runtime.thread_store.list_threads(expected_owner)
        result['threads']={'state':'RETRIEVED','items':[{'thread_id':t.thread_id,'title':t.title,
            'updated_at':t.updated_at,'active':t.thread_id==runtime.context.active_thread.thread_id} for t in threads]}
    except Exception as exc:
        result['threads']={'state':'UNAVAILABLE','error_type':type(exc).__name__,'items':[]}
    try:
        records=runtime.runtime_observation_collector.store.load_records_for_operator(expected_owner)
        groups={};builds=[]
        for record in sorted(records,key=lambda r:r.created_at,reverse=True):
            if record.metadata.get('runtime_component')!='integration.build_runtime':continue
            outcome=record.metadata.get('observed_outcome',{})
            identity=outcome.get('request_id')
            if not identity:continue
            attempt=outcome.get('attempt_id')
            # Legacy records without attempt identity cannot prove grouping.
            key=(record.thread_id,attempt or record.observation_id)
            reference={'observation_id':record.observation_id,'observation_hash':digest(record.to_dict()),
                'observed_state':outcome.get('state','UNAVAILABLE'),'created_at':record.created_at}
            if key in groups:
                if groups[key]['request_id']!=identity:raise ValueError('Build attempt identity conflict')
                groups[key]['observations'].append(reference)
                continue
            item={'request_id':identity,'attempt_id':attempt,'observed_state':outcome.get('state','UNAVAILABLE'),
                'observation_id':record.observation_id,'created_at':record.created_at,'thread_id':record.thread_id,
                'observation_hash':digest(record.to_dict()),
                'observations':[reference],'attempt_grouping':'EXPLICIT' if attempt else 'LEGACY_UNRESOLVED',
                'current_validity':'NOT_REVALIDATED','receipt_references':record.metadata.get('produced_receipts',[])}
            groups[key]=item;builds.append(item)
        result['past_builds']={'state':'RETRIEVED','items':builds[:100],'total':len(builds),'limited':len(builds)>100}
    except Exception as exc:
        result['past_builds']={'state':'UNAVAILABLE','error_type':type(exc).__name__,'items':[]}
    return result


def export(runtime):
    """Explicit local export; never runs automatically or serves a network endpoint."""
    import json
    path = runtime.understanding_engine.store.path.with_name('presentation.json')
    value = snapshot(runtime)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2), encoding='utf-8')
    return {'path':str(path),'source':'ACTIVE_RUNTIME_SNAPSHOT','execution_authority':False}
