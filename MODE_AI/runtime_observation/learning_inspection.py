"""Fixed Learning-domain evidence routing in the existing inspection ledger.

Reads repository evidence only. No Learning service calls, store construction,
candidate generation, qualifications, or mutation. Source observations are not
independent validation of their claims. No gap/recommendation is precomputed.
"""
import ast
import json
import re
import hashlib
from pathlib import Path
from copy import deepcopy
from .transformation_provenance import digest
from learning.contracts import digest as objective_digest

WORKSPACE=Path(__file__).resolve().parents[1]
CLASSES=('SPECIFICATION','IMPLEMENTATION','INTEGRATION','TEST','LIVE','FAILURE',
         'STORE','PROVENANCE','CROSS_THREAD','REVISION')
DIAGNOSIS_POLICY='''
For the LEARNING objective: STATE-CONDITIONAL DIAGNOSIS CONTRACT.
At draft, critique and FINAL, emit ONLY JSON with ledger_id, statements and diagnosis.
Raw JSON only: no Markdown fences and no surrounding prose. Transport formatting is not evidence.
Always preserve ALL required coverage groups, including unavailable STORE evidence.
Choose status from the evidence before considering a repair. Use one exact shape:
1. EVIDENCE_BACKED_GAP: diagnosis has status, evidence_ids, gap (concrete string),
rationale, recommendation (exact inspected component, change, requires_operator_authorization:true,
execution_authority:false), verification. Cite current implementation and behavioral/failure evidence.
Do not select a repair from unavailable evidence or treat historical failure as proof of current recurrence.
2. INSUFFICIENT_EVIDENCE or UNAVAILABLE: diagnosis has status, evidence_ids,
gap:null, rationale (why diagnosis is blocked), recommendation:null, verification (inspection needed),
missing_evidence:[{evidence_id:selected unavailable entry ID,missing:what is missing,reason:why it prevents diagnosis}],
next_evidence:[{evidence_id:one of those missing IDs,inspection:read-only inspection request}].
Every non-gap response MUST use null for BOTH gap and recommendation. Do not recommend a repair.
Evidence classes are fixed by the ledger's source projection, not by your wording.
OBSERVED historical LIVE/TEST entries report existing scoped records, not current general qualification.
For missing generalized proof cite the UNAVAILABLE objective_unknowns entry; do not relabel a LIVE source as unavailable.
Inspection requests must start Inspect, Read, Locate, Collect, Compare, Measure or Verify;
they must not contain implement, repair, modify, rewrite, refactor, deploy, construct, build, create or add.
Do not invent missing IDs, new evidence, a defect or an authority grant. Missing records do not mean missing mechanisms.
Test definitions are not executions; deterministic transfer and memory retention are not general Learning.
Historical PASS/FAIL/PARTIAL/INCONCLUSIVE remain scoped. Your diagnosis is INFERRED, not validated truth.
MODE diagnoses; Operator authorizes; Builder constructs; Reality Primacy verifies.
'''
AUDIT='artifacts/full_behavioral_qualification_audit_20261021/'
# An explicit code-owned source catalogue; no arbitrary query-generated paths.
# Current store content has no diagnostic export yet: location is not permission.
SOURCES={
 'SPECIFICATION':[('learning/CONTRACT.md',None)],
 'IMPLEMENTATION':[('integration/interaction_learning.py','evaluate'),('learning/service.py','LearningService.understanding_candidate')],
 'INTEGRATION':[('learning/runtime.py','command'),('integration/conversation_understanding.py','prompt_context')],
 'TEST':[('tests/test_generalized_learning.py',None),('tests/test_architectural_learning_memory_repairs.py',None),
         ('artifacts/generalized_learning_completion_20261016/TEST_RESULTS_FINAL.json',None)],
 'LIVE':[(AUDIT+'BEHAVIORAL_CAPABILITY_MATRIX_20261021.json',None)],
 'FAILURE':[('artifacts/general_learning_memory_rerun_20261012/FINAL_QUALIFICATION_REPORT_20261012.md',None),(AUDIT+'FAILURE_HISTORY.json',None)],
 'STORE':[('learning/store.py','LearningStore.transaction'),('persistent_memory/learning_gateway.py','LearningMemoryGateway.available')],
 'PROVENANCE':[('integration/conversation_understanding.py','_learned_projection'),('understanding/understanding_engine.py','UnderstandingEngine.adopt_learning')],
 'CROSS_THREAD':[('tests/test_architectural_learning_memory_repairs.py','test_cross_thread_semantic_consumption_reaches_all_stages'),('learning/service.py','LearningService.apply_understanding')],
 'REVISION':[('learning/service.py','LearningService.revalidate'),('learning/service.py','LearningService.verify_application')],
}

def read_source(relative,symbol):
    row={'path':relative,'component':relative+('#'+symbol if symbol else ''),
         'status':'UNAVAILABLE','validation_state':'NOT_INDEPENDENTLY_VALIDATED','execution_authority':False}
    try:
        root=WORKSPACE.resolve();p=root/relative
        if not p.resolve().is_relative_to(root) or any(x.is_symlink() or x.is_junction() for x in [p,*p.parents] if x.is_relative_to(root)):
            raise ValueError('Source boundary')
        if not p.is_file() or p.stat().st_size>2*1024*1024:raise ValueError('Missing or oversized source')
        raw=p.read_bytes();text=raw.decode('utf-8-sig');row['sha256']=hashlib.sha256(raw).hexdigest()
        if p.suffix=='.py':
            tree=ast.parse(text);lines=text.splitlines()
            if symbol:
                nodes=tree.body
                for part in symbol.split('.'):
                    node=next(n for n in nodes if isinstance(n,(ast.FunctionDef,ast.ClassDef)) and n.name==part)
                    nodes=getattr(node,'body',[])
                excerpt='\n'.join(lines[node.lineno-1:node.end_lineno])
                row.update(first_line=node.lineno,last_line=node.end_lineno)
            else:
                # Test bodies are not proof of execution. Preserve names only.
                excerpt=json.dumps([{'name':n.name,'line':n.lineno} for n in ast.walk(tree) if isinstance(n,ast.FunctionDef) and n.name.startswith('test_')])
            row['source_excerpt']=excerpt[:3200]
            row['excerpt_truncated']=len(excerpt)>3200
        elif p.suffix=='.json':
            data=json.loads(text)
            if relative.endswith('BEHAVIORAL_CAPABILITY_MATRIX_20261021.json'):
                data=[r for r in data['rows'] if any(t in r['capability'].lower() for t in ('learning','understanding','memory','preference','composition'))]
                data=[{k:v for k,v in r.items() if k!='engineering_proof'} for r in data]
            elif relative.endswith('TEST_RESULTS_FINAL.json'):
                data={name:{k:v for k,v in receipt.items() if k in ('exit_code','call_results','passed_tests','provider_calls','errors','skipped_tests')}
                      for name,receipt in data.items() if isinstance(receipt,dict)}
            elif relative.endswith('FAILURE_HISTORY.json'):
                # Keep every historical verdict; no PASS-only filter.
                data=data
            row['recorded_excerpt']=json.dumps(data,ensure_ascii=False)[:8500]
            row['excerpt_truncated']=len(json.dumps(data,ensure_ascii=False))>8500
        else:
            row['recorded_excerpt']=text[:6500];row['excerpt_truncated']=len(text)>6500
        row['status']='OBSERVED_REPOSITORY_SOURCE' if p.suffix=='.py' else 'OBSERVED_RECORDED_DOCUMENT'
    except (OSError,ValueError,StopIteration,SyntaxError,UnicodeError,KeyError) as exc:
        row['reason']=type(exc).__name__+': source absent, unsupported or outside bounded read'
    return row

def context(runtime,query,requirements):
    from .capability_ledger import normalize,SOURCE
    from .evidence_ledger import PREFIX,INSTRUCTION
    from .inspection_coverage import derive,PREFIX as CP,INSTRUCTION as CI
    from integration.self_inspection_activation import prerequisite,SOURCE as PS,PREFIX as PP
    from data_governance.context_admission import Admission
    c=runtime.context;owner=c.identity.operator_id;thread=c.active_thread.thread_id
    if not owner or not thread:raise PermissionError('Authenticated runtime scope required')
    projection={'contract':'CapabilityInspection/1','operator_id':owner,'scope':['Learning repository evidence'],
        'inspection_id':'learning-inspection:'+digest([owner,thread,query]),'store':None,'entries':[],
        'limitations':['Repository evidence does not confer RP, execution, durability or qualification authority.'],
        'execution_authority':False}
    ledger=normalize(projection,thread)
    ledger['objective']={**requirements,'domain':'LEARNING','query_hash':objective_digest(query),
        'resolution':'BOUNDED_SOURCES_INSPECTED','required_classes':list(CLASSES),
        'reason':'FIXED_LEARNING_SOURCE_MAP_CURRENT_READS_AND_EXPLICIT_UNAVAILABLE',
        'limits':'Learning domain only; evidence availability and coverage are not behavioral qualification.'}
    sid='learning-domain';ledger['sources'][sid]={'source_type':'OBJECTIVE_INSPECTION','source_identifier':sid,
        'reference':{'catalogue':'runtime_observation.learning_inspection.SOURCES'},'transition_id':None,
        'producer':'runtime_observation.learning_inspection.context','stage':'READ_ONLY_LEARNING_SOURCE_MAP',
        'sequence':None,'operator_id':owner,'thread_id':thread}
    def add(field,value,cls):
        ledger['entries'].append({'entry_id':f'E{len(ledger["entries"])+1:03d}','field':field,'value':value,
            'evidence_class':cls,'source_id':sid,'scope':sid+':'+field,'allowed_attribution_target':sid+':'+field,
            'directly_recorded':cls=='OBSERVED','derived':False,'confidence':'UNAVAILABLE','support':[],
            'recorded_alternatives':[],'conflicts':[]})
    add('operator_objective',query,'OBSERVED')
    reads={}
    for kind in CLASSES:
        rows=[read_source(*ref) for ref in SOURCES[kind]];reads[kind]=rows
        if kind=='STORE':
            add('learning_class_'+kind,{'rows':rows,'state_content':'UNAVAILABLE_NO_OWNER_SCOPED_DIAGNOSTIC_STORE_EXPORT',
                'limits':'Store implementation inspected; no governed journal values read or inferred.'},'UNAVAILABLE')
        else:
            add('learning_class_'+kind,{'rows':rows,'limits':'Code/test presence and historical outcomes do not prove current generalized Learning.'},
                'OBSERVED' if any(r['status'].startswith('OBSERVED') for r in rows) else 'UNAVAILABLE')
    add('objective_unknowns','Current general behavioral competence, exact post-repair recurrence, private governed-state values and arbitrary-domain readiness are UNAVAILABLE. Memory retention is not behavior change. Historical failures remain historical, not proof of their persistence after repair.','UNAVAILABLE')
    ledger.pop('ledger_id');ledger['ledger_id']='ledger-'+digest(ledger)[:16]
    from .materiality_contract import evaluate as assess_materiality
    c.diagnostic_materiality=assess_materiality(ledger)
    ledger=c.diagnostic_materiality['ledger']
    if len(json.dumps(ledger).encode())>90000:raise PermissionError('Learning diagnostic evidence bound exceeded')
    coverage=derive(query,ledger);receipt=prerequisite(query,owner,thread,ledger=ledger)
    c.self_inspection={'contract':'SelfInspectionAccess/1','operator_id':owner,'thread_id':thread,
        'provider_calls':0,'execution_authority':False,'objective_evidence':ledger['objective'],
        'tool_request':{'tool':'inspect_learning_sources','scope':['LEARNING'],'required_classes':list(CLASSES)},
        'tool_result':reads,'evidence_ledger':ledger,'coverage_contract':coverage,'prerequisite':receipt}
    a=Admission(owner,thread)
    for name,prefix,value,source in [('prerequisite',PP,receipt,PS),('learning',PREFIX,ledger,SOURCE),('coverage',CP,coverage,'InspectionCoverage/1')]:
        a.consider('RUNTIME','self-inspection:'+name,prefix+json.dumps(value),source=source,
            basis={'authority':'READ_ONLY_RUNTIME_EVIDENCE','validation_state':'UNVALIDATED','lineage':[projection['inspection_id']]})
    a.consider('SYSTEM_POLICY','self-inspection:explanation-contract',INSTRUCTION+CI+DIAGNOSIS_POLICY,
        source='Scoped runtime explanation contract')
    return a.finish()

def validate(ledger,value,selected):
    if type(value) is not dict:raise PermissionError('Exact Learning diagnosis required')
    base={'status','evidence_ids','gap','rationale','recommendation','verification'}
    nongap=value.get('status') in {'INSUFFICIENT_EVIDENCE','UNAVAILABLE'}
    if set(value)!=(base|{'missing_evidence','next_evidence'} if nongap else base):
        raise PermissionError('Exact Learning diagnosis required')
    if value['status'] not in {'INSUFFICIENT_EVIDENCE','UNAVAILABLE','EVIDENCE_BACKED_GAP'}:raise PermissionError('No qualification promotion')
    ids=value['evidence_ids'];entries={e['entry_id']:e for e in ledger['entries']}
    if type(ids) is not list or any(type(i) is not str or i not in selected or i not in entries for i in ids) or len(set(ids))!=len(ids):
        raise PermissionError('Diagnosis citations must be selected evidence')
    for text in (value['rationale'],value['verification'],*([value['gap']] if not nongap else [])):
        if type(text) is not str or not 12<=len(text)<=1800:raise PermissionError('Substantive bounded inference required')
    rec=value['recommendation']
    if nongap:
        if rec is not None:raise PermissionError('No recommendation before an evidence-backed gap')
        if value['gap'] is not None:raise PermissionError('No diagnosed gap from insufficient or unavailable evidence')
        missing=value['missing_evidence'];next_steps=value['next_evidence']
        if type(missing) is not list or not 1<=len(missing)<=8 or type(next_steps) is not list or not 1<=len(next_steps)<=8:
            raise PermissionError('Explicit missing evidence and next inspection required')
        missing_ids=[]
        for row in missing:
            if (type(row) is not dict or set(row)!={'evidence_id','missing','reason'} or
                type(row['evidence_id']) is not str or row['evidence_id'] not in ids or
                entries[row['evidence_id']]['evidence_class']!='UNAVAILABLE' or
                any(type(row[k]) is not str or not 12<=len(row[k])<=1200 for k in ('missing','reason'))):
                raise PermissionError('Missing-evidence requirements must cite selected unavailable evidence')
            missing_ids.append(row['evidence_id'])
        if len(set(missing_ids))!=len(missing_ids):raise PermissionError('Duplicate missing-evidence requirement')
        for row in next_steps:
            if (type(row) is not dict or set(row)!={'evidence_id','inspection'} or row['evidence_id'] not in missing_ids or
                type(row['inspection']) is not str or not 12<=len(row['inspection'])<=1200 or
                not re.match(r'^(Inspect|Read|Locate|Collect|Compare|Measure|Verify)\b',row['inspection'],re.I) or
                re.search(r'\b(implement|repair|modify|rewrite|refactor|deploy|construct|build|create|add)\b',row['inspection'],re.I)):
                raise PermissionError('Next evidence is inspection only, never repair guidance')
    else:
        fields={entries[i]['field'] for i in ids if entries[i]['evidence_class']=='OBSERVED'}
        if 'learning_class_IMPLEMENTATION' not in fields or not fields.intersection({'learning_class_FAILURE','learning_class_LIVE'}):
            raise PermissionError('Code, tests or memory alone cannot establish behavioral gap')
        targets={r['component'] for i in ids if isinstance(entries[i].get('value'),dict) for r in entries[i]['value'].get('rows',[])
                 if r['status'].startswith('OBSERVED') and '#' in r['component']}
        if (type(rec) is not dict or set(rec)!={'component','change','requires_operator_authorization','execution_authority'} or
            rec['component'] not in targets or rec['requires_operator_authorization'] is not True or rec['execution_authority'] is not False or
            type(rec['change']) is not str or not 12<=len(rec['change'])<=1800):raise PermissionError('Bound inspected recommendation with no authority required')
    texts=[value['rationale'],value['verification']]+([value['gap']] if not nongap else [])+([rec['change']] if rec else [])
    if nongap:texts += [row[k] for row in missing for k in ('missing','reason')]+[row['inspection'] for row in next_steps]
    if any(re.search(r'\bI\s+(?:hereby\s+)?(?:authoriz|approv|will (?:implement|modify|deploy|execut))',t,re.I) for t in texts):
        raise PermissionError('No self-authorization')
    return deepcopy(value)

def output_format(ledger):
    """Provider representation of the existing contract; local validation stays mandatory.

    IDs/classes come only from a verified admitted ledger in ReasoningAgent.
    This neither chooses the diagnosis nor normalizes or repairs model output.
    """
    if ledger.get('objective',{}).get('domain')!='LEARNING':
        raise PermissionError('Learning diagnosis contract required')
    entries=ledger['entries'];ids=[e['entry_id'] for e in entries]
    unavailable=[e['entry_id'] for e in entries if e['evidence_class']=='UNAVAILABLE']
    if not ids or not unavailable:raise PermissionError('Bounded known citation classes required')
    def obj(properties):
        return {'type':'object','properties':properties,'required':list(properties),'additionalProperties':False}
    def arr(item):return {'type':'array','items':item}
    def enum(values):return {'type':'string','enum':values}
    string={'type':'string'}
    nongap=obj({'status':enum(['INSUFFICIENT_EVIDENCE','UNAVAILABLE']),
        'evidence_ids':arr(enum(ids)),'gap':{'type':'null'},'rationale':string,
        'recommendation':{'type':'null'},'verification':string,
        'missing_evidence':arr(obj({'evidence_id':enum(unavailable),'missing':string,'reason':string})),
        'next_evidence':arr(obj({'evidence_id':enum(unavailable),'inspection':string}))})
    branches=[nongap]
    targets=sorted({r['component'] for e in entries if isinstance(e.get('value'),dict)
        for r in e['value'].get('rows',[]) if r['status'].startswith('OBSERVED') and '#' in r['component']})
    if targets:
        branches.append(obj({'status':enum(['EVIDENCE_BACKED_GAP']),'evidence_ids':arr(enum(ids)),
            'gap':string,'rationale':string,'recommendation':obj({'component':enum(targets),'change':string,
                'requires_operator_authorization':{'type':'boolean','enum':[True]},
                'execution_authority':{'type':'boolean','enum':[False]}}),'verification':string}))
    schema=obj({'ledger_id':enum([ledger['ledger_id']]),'statements':arr(enum(ids)),
                'diagnosis':{'anyOf':branches}})
    return {'type':'json_schema','name':'learning_diagnosis','strict':True,'schema':schema}
