"""System registry namespace in the existing ledger/selection pipeline."""
from copy import deepcopy
import json
from .transformation_provenance import digest
from learning.contracts import digest as objective_digest

SOURCE='CapabilityEvidenceLedger/1'
CAPABILITIES=('self-inspection-activation','interaction-inspection','transition-provenance',
    'evidence-normalization','evidence-selection','coverage-validation','evidence-bound-publication',
    'system-capability-inspection')

def registry_request(query):
    import re
    return bool(re.search(r'capabilit',query,re.I) and re.search(r'inspect',query,re.I) and
                re.search(r'system layer|registry|recorded',query,re.I) and not re.search(r'build.ready|gap diagnosis',query,re.I))

def objective_context(runtime,query,requirements):
    """Resolve a declared subject against existing owned inventory; unknowns stay closed.

    First supported readiness predicate is an explicit independent-statement
    capacity. This is not a general semantic objective parser or gap generator.
    """
    import re
    if requirements.get('contract')=='ObjectiveEvidenceRequirements/2':
        from .inspection_target import context
        return context(runtime,query,requirements)
    if requirements.get('subject','').casefold()=='learning' and hasattr(runtime,'understanding_engine'):
        from .learning_inspection import context
        return context(runtime,query,requirements)
    from system_layer.capability_inspection import inspect_capabilities,inspect_sources
    from integration.self_inspection_activation import prerequisite,SOURCE as PS,PREFIX as PP
    from data_governance.context_admission import Admission
    from .evidence_ledger import PREFIX,INSTRUCTION
    from .inspection_coverage import derive,PREFIX as CP,INSTRUCTION as CI
    if not hasattr(runtime,'understanding_engine'):return None
    wanted=re.search(r'\b(\d{1,2})\s+independent required statements\b',query,re.I)
    subject=set(re.findall(r'[a-z0-9]+',requirements['subject'].lower()))
    if not wanted or not 1<=int(wanted.group(1))<=64 or not subject or requirements['subject']=='UNRESOLVED':return None
    c=runtime.context;owner=c.identity.operator_id;thread=c.active_thread.thread_id
    path=runtime.understanding_engine.store.path.with_name('system_layer.sqlite3')
    projection=inspect_capabilities(path,owner,owner,list(CAPABILITIES))
    matches=[e['capability_id'] for e in projection['entries'] if e.get('inventory') and
             subject<=set(re.findall(r'[a-z0-9]+',(e['capability_id']+' '+e['name']).lower()))]
    if len(matches)!=1:return None
    projection=inspect_capabilities(path,owner,owner,matches);reads=inspect_sources(projection,owner)
    ledger=normalize(projection,thread)
    ledger['objective']={**requirements,'required_capacity':int(wanted.group(1)),
        'query_hash':objective_digest(query),'resolution':'BOUNDED_SOURCES_INSPECTED',
        'limits':'Only registered subject references and explicit independent-statement capacity; not arbitrary objective diagnosis.'}
    def add(field,value,cls='OBSERVED'):
        sid='objective';ledger['sources'][sid]={'source_type':'OBJECTIVE_INSPECTION','source_identifier':sid,
            'reference':{'inspection_id':projection['inspection_id'],'store':projection['store']},
            'transition_id':None,'producer':'system_layer.capability_inspection.inspect_sources',
            'stage':'BOUNDED_CURRENT_READ','sequence':None,'operator_id':owner,'thread_id':thread}
        ledger['entries'].append({'entry_id':f'E{len(ledger["entries"])+1:03d}','field':field,'value':value,
            'evidence_class':cls,'source_id':sid,'scope':sid+':'+field,'allowed_attribution_target':sid+':'+field,
            'directly_recorded':cls=='OBSERVED','derived':False,'confidence':'UNAVAILABLE',
            'support':[],'recorded_alternatives':[],'conflicts':[]})
    add('operator_objective',{'query':query,'subject':requirements['subject'],'required_capacity':int(wanted.group(1))})
    for kind in ('CODE','INTEGRATION','TEST','RUNTIME','QUALIFICATION'):
        rows=[r for r in reads if r['kind']==kind]
        add('evidence_class_'+kind,rows or 'No owned reference for this evidence class',
            'OBSERVED' if rows and any(r['status'].startswith('OBSERVED') for r in rows) else 'UNAVAILABLE')
    for row in reads:
        for bound in row.get('statement_bounds',[]):
            add('inspected_capacity',{**bound,'component':row['component'],'actual_sha256':row['actual_sha256'],
                'freshness':row['freshness'],'limits':'Observed source predicate only, not operational validation.'})
    add('objective_unknowns','Current operational satisfaction and generalized diagnosis are UNAVAILABLE; historical receipt summaries do not prove this new objective.', 'UNAVAILABLE')
    ledger.pop('ledger_id');ledger['ledger_id']='ledger-'+digest(ledger)[:16]
    if len(json.dumps(ledger).encode())>49152:raise ValueError('Objective ledger bound exceeded')
    coverage=derive(query,ledger);receipt=prerequisite(query,owner,thread,ledger=ledger)
    c.self_inspection={'contract':'SelfInspectionAccess/1','operator_id':owner,'thread_id':thread,
        'provider_calls':0,'execution_authority':False,'objective_evidence':ledger['objective'],
        'tool_request':{'tool':'inspect_objective_sources','scope':matches},'tool_result':{'registry':projection,'reads':reads},
        'evidence_ledger':ledger,'coverage_contract':coverage,'prerequisite':receipt}
    a=Admission(owner,thread)
    for name,prefix,value,source in [('prerequisite',PP,receipt,PS),('objective',PREFIX,ledger,SOURCE),('coverage',CP,coverage,'InspectionCoverage/1')]:
        a.consider('RUNTIME','self-inspection:'+name,prefix+json.dumps(value),source=source,
            basis={'authority':'READ_ONLY_RUNTIME_EVIDENCE','validation_state':'UNVALIDATED','lineage':[projection['inspection_id']]})
    a.consider('SYSTEM_POLICY','self-inspection:explanation-contract',INSTRUCTION+CI+'''
For a ledger with objective, FINAL JSON additionally requires "diagnosis": {
"status":"BLOCKED_BY_INSPECTED_BOUND" or "BOUND_SUFFICIENT_ONLY",
"required_capacity":integer,"observed_capacity":integer,"evidence_ids":[inspected_capacity entry IDs],
"gap":your evidence-derived explanation,"rationale":why the inspected bound does or does not block this objective,
"recommendation":{"component":exact inspected component,"change":your smallest specific recommendation,
"requires_operator_authorization":true,"execution_authority":false}}.
Do not select a gap from missing evidence. If no unique inspected capacity exists, do not invent a diagnosis.
Choose the supporting objective, inspected evidence classes and unavailable limitations.
Your diagnosis/rationale/recommendation are INFERRED, never observed truth or approval.
Operator authorizes, Builder constructs, Reality Primacy verifies. No self-modification.
''',source='Scoped runtime explanation contract')
    return a.finish()

def normalize(projection,thread):
    if projection.get('contract')!='CapabilityInspection/1' or projection['execution_authority'] is not False:
        raise PermissionError('Read-only capability inspection required')
    owner=projection['operator_id']; sources={}; entries=[]
    def add(sid,namespace,field,value,cls='OBSERVED'):
        sources[sid]={'source_type':namespace,'source_identifier':sid,
            'reference':{'inspection_id':projection['inspection_id'],'store':projection['store']},
            'transition_id':None,'producer':'system_layer.capability_inspection.inspect_capabilities',
            'stage':'READ_ONLY_REGISTRY','sequence':None,'operator_id':owner,'thread_id':thread}
        entries.append({'entry_id':f'E{len(entries)+1:03d}','field':field,'value':value,
            'evidence_class':cls,'source_id':sid,'namespace':namespace,'scope':sid+':'+field,
            'allowed_attribution_target':sid+':'+field,'directly_recorded':cls=='OBSERVED',
            'derived':cls=='INFERRED','confidence':'UNAVAILABLE','support':[],
            'recorded_alternatives':[],'conflicts':[]})
    for record in projection['entries']:
        add(record['capability_id'],'SYSTEM_CAPABILITY','registry_record',deepcopy(record),
            'UNAVAILABLE' if record.get('state')=='UNKNOWN' else 'OBSERVED')
    add('qualification','QUALIFICATION','qualification_limits',
        'This inspection does not independently requalify any capability or change Learning Expression, memory, Objective Continuity, Pass 3, Frozen60 or Development Program state. Qualification generalization is unavailable.', 'UNAVAILABLE')
    add('vocabulary','SYSTEM_CAPABILITY','status_distinctions',{
        'SPECIFIED':'Declaration or contract only; not implementation.',
        'IMPLEMENTED':'Code evidence only; not validation.', 'INTEGRATED':'Recorded runtime wiring; not operational proof.',
        'VALIDATED':'Passed scoped tests; not generalized runtime qualification.',
        'OPERATIONAL':'Recorded runtime success only within the cited target scope; not RP authorization.',
        'DEGRADED':'Selected evidence records a material failure; no qualification rewritten.',
        'UNKNOWN_UNAVAILABLE':'Insufficient or missing selected evidence; not proof of absence.',
        'authoritative_axes':'UNCONFIRMED/PENDING_VALIDATION remain unchanged by evidence inventory.'})
    conflicts=[{'capability_id':r['capability_id'],'conflict':r.get('conflict')}
               for r in projection['entries'] if r.get('conflict') not in (None,'NONE_OBSERVED_IN_SELECTED_EVIDENCE')]
    add('conflicts','SYSTEM_CAPABILITY','registry_runtime_conflicts',
        {'observed_conflicts':conflicts,'limit':'Comparison covers selected hashes and recorded evidence only; uninspected runtime conflicts remain unavailable.'})
    add('limits','INFERENCE','scope_inference',
        'Recorded scoped evidence can support a bounded status assessment; it cannot establish generalized self-diagnosis or authorize construction.', 'INFERRED')
    add('unknown','SYSTEM_CAPABILITY','unavailable_capability_evidence',projection['limitations']+[
        'Unregistered capabilities, whole-system completeness, fresh independent RP validation and generalized operational ability remain unavailable.'], 'UNAVAILABLE')
    ledger={'contract':SOURCE,'operator_id':owner,'thread_id':thread,
        'interaction_id':projection['inspection_id'],'observation_id':None,
        'sources':sources,'entries':entries,'conflicts':[],'execution_authority':False,
        'validation_state':'RECORDED_NOT_INDEPENDENTLY_VALIDATED','limits':projection['limitations']}
    ledger['ledger_id']='ledger-'+digest(ledger)[:16]
    if len(json.dumps(ledger).encode())>49152: raise ValueError('Capability ledger bound exceeded')
    return ledger

def reasoning_context(runtime,query):
    from system_layer.capability_inspection import inspect_capabilities
    from data_governance.context_admission import Admission
    from integration.self_inspection_activation import prerequisite,SOURCE as PS,PREFIX as PP
    from .evidence_ledger import PREFIX,INSTRUCTION
    from .inspection_coverage import derive,PREFIX as CP,INSTRUCTION as CI
    c=runtime.context; owner=c.identity.operator_id;thread=c.active_thread.thread_id
    path=runtime.understanding_engine.store.path.with_name('system_layer.sqlite3')
    projection=inspect_capabilities(path,owner,owner,list(CAPABILITIES))
    ledger=normalize(projection,thread); coverage=derive(query,ledger)
    receipt=prerequisite(query,owner,thread,ledger=ledger)
    c.self_inspection={'contract':'SelfInspectionAccess/1','operator_id':owner,'thread_id':thread,
        'provider_calls':0,'execution_authority':False,'tool_request':{'tool':'inspect_capabilities','scope':list(CAPABILITIES)},
        'tool_result':projection,'evidence_ledger':ledger,'coverage_contract':coverage,'prerequisite':receipt}
    a=Admission(owner,thread)
    for name,prefix,value,source in [('prerequisite',PP,receipt,PS),('capabilities',PREFIX,ledger,SOURCE),('coverage',CP,coverage,'InspectionCoverage/1')]:
        a.consider('RUNTIME','self-inspection:'+name,prefix+json.dumps(value),source=source,
            basis={'authority':'READ_ONLY_RUNTIME_EVIDENCE','validation_state':'UNVALIDATED','lineage':[projection['inspection_id']]})
    a.consider('SYSTEM_POLICY','self-inspection:explanation-contract',INSTRUCTION+CI+
        '\nCapability records report scoped inventory assessments separately from authoritative RP axes. Select every requested capability, status distinctions, conflicts, qualification limits and unavailable evidence. No objective-gap diagnosis or build specification is supported here.',source='Scoped runtime explanation contract')
    return a.finish()
