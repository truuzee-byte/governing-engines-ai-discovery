"""Current canonical draft view over governed, thread-scoped declarations.

Understanding owns versioned requirements. This projection does not create a
second requirement store, approve a draft, choose files, or execute a build.
"""
from copy import deepcopy
from specs.spec_engine import create_specification_object
from understanding.understanding_record import digest


def project(record):
    if (record.context.get('declaration_contract')!='OperatorDeclarations/1'
            or record.semantic_state.value!='CONFIRMED'
            or record.validation_status!='SUPPORTED_DECLARATION'):
        raise PermissionError('Current governed operator declarations required')
    items=record.context['declarations']
    requirements=[v for v in items if v['kind'] in {'REQUIREMENT','CONSTRAINT'}]
    if not requirements:
        return None
    reference={'understanding_id':record.understanding_id,'version':record.version,'hash':digest(record)}
    request={'request_id':record.understanding_id,'system_name':record.subject_id,
        'system_purpose':record.canonical_meaning,'tool_type':'',
        'construction_scope':[v['quote'] for v in requirements],
        'approved_components':[], 'governance_constraints':[v['quote'] for v in requirements if v['kind']=='CONSTRAINT'],
        'execution_authority':'draft_only','receipt_requirements':[], 'runtime_target':None,
        'source_trace_reference':'understanding:'+digest(reference),
        'artifact_structure':{'files':[],'directories':[]}}
    specification=create_specification_object(request,draft_only=True)
    specification['spec_version']=str(record.version)
    specification['metadata']['created_at']=record.updated_at
    specification['metadata']['governed_declaration_reference']=reference
    specification['structure']['understanding_requirements']={
        'requirements':[{'requirement_id':v['id'],'text':v['quote'],'source_references':v['source_references']} for v in requirements]}
    specification['lineage']['current_version']=str(record.version)
    specification['lineage']['source_refs']=sorted({r for v in requirements for r in v['source_references']})
    return {'specification':specification,'request':request,'reference':reference,
        'requirement_inventory':deepcopy(requirements),
        'state':'SPECIFICATION_NOT_READY','execution_attempted':False,
        'missing_fields':['artifact_structure.files','execution.repository_target','validation.requirements','validation.commands','authorization'],
        'readiness_basis':'Requirements accumulated; concrete artifact, validation and execution authority remain unspecified.'}


def current(runtime):
    from integration.conversation_understanding import current_records
    return [view for record in current_records(runtime) if (view:=project(record)) is not None]


def require_current(runtime, reference):
    for view in current(runtime):
        if view['reference']==reference:
            return view
    raise PermissionError('Stale or unrelated conversation specification reference')


def synchronize_pending(runtime):
    pending=getattr(runtime.context,'build_clarification',None)
    if not pending or pending['thread_id']!=runtime.context.active_thread.thread_id:
        return
    views=current(runtime)
    old=(pending.get('conversation_specification_reference') or
         pending.get('envelope',{}).get('understanding',{}).get('conversation_specification_reference'))
    if old:
        views=[v for v in views if v['reference']['understanding_id']==old['understanding_id']]
    if len(views)!=1:
        return
    view=views[0]
    if old==view['reference']:
        return
    # Changed meaning invalidates the old pending approval. Never carry an
    # authorization across a new requirement version.
    envelope=deepcopy(pending.get('envelope',{}))
    envelope.pop('authorization',None)
    request=envelope.setdefault('request',{})
    prior_owned={}
    if old:
        prior_record=runtime.understanding_engine.store.get(
            runtime.context.identity.operator_id,old['understanding_id'],old['version'])
        if prior_record is None or digest(prior_record)!=old['hash']:
            raise PermissionError('Pending specification source lineage changed')
        prior_owned=project(prior_record)['request']
    for key in ('construction_scope','governance_constraints'):
        values=request.get(key,[])
        if not isinstance(values,list):
            raise ValueError('Collected scope and constraints must be lists')
        retained=[v for v in values if v not in prior_owned.get(key,[])]
        request[key]=list(dict.fromkeys(retained+view['request'][key]))
    for key,value in view['request'].items():
        request.setdefault(key,deepcopy(value))
    # Only the declaration-derived fields change. Explicit artifact targets,
    # validation commands and other collected fields remain available for review.
    for key in ('system_purpose','source_trace_reference'):
        request[key]=deepcopy(view['request'][key])
    request['operator_input']=pending['operator_input']
    request['execution_authority']='draft_only'
    for key,value in {'authority_state':'draft_only','validation_state':'incomplete',
                      'readiness_state':'needs_clarification','save_ready_state':False,
                      'clarification_required':True}.items():
        if key in request:request[key]=value
    understanding=envelope.setdefault('understanding',{})
    understanding.update({'subject_id':view['specification']['spec_name'],'semantic_domain':'OPERATOR',
            'meaning':view['request']['system_purpose'],'objective':view['request']['system_purpose'],
            'requirements':deepcopy(view['specification']['structure']['understanding_requirements']['requirements']),
            'conversation_specification_reference':view['reference']})
    pending['envelope']=envelope
    pending['conversation_specification_reference']=view['reference']
