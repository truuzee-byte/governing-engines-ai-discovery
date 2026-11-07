"""Transient source-backed target bindings in the existing inspection pipeline.

Not capability enrollment, execution authority, an evidence comparator or a
free-text entailment oracle. Model results use typed semantic relations; prose
or echoed IDs alone cannot acquire target-scope publication acceptance.
"""
import ast
import hashlib
import json
import re
from pathlib import Path
from copy import deepcopy
from learning.contracts import digest as objective_digest
from .transformation_provenance import digest

WORKSPACE=Path(__file__).resolve().parents[1]
# Explicit implementation bindings, not name-similarity source discovery. These
# describe inspected functions, not a declaration that general comparison works.
TARGETS=(
    {'path':'runtime_observation/materiality_contract.py','symbol':'evaluate',
     'sources':('_identity','evaluate'),
     'questions':(
         r'What\b[^?\n]*\bwhether (?:one|an?) evidence (?:item|record) can safely (?:represent|substitute for) (?:another|an? other)(?: for this objective)?\?',
         r'What prevents safe representative-evidence decisions\?',
     ),
     'question_scope':{'operation':'REPRESENT_EVIDENCE_WITHOUT_LOSS',
                       'subject_role':'evidence_item','object_role':'other_evidence_item',
                       'constraint':'current_operator_objective'}},
)
POLICY='''
TARGET-SCOPED DIAGNOSIS: diagnose the operative question in the runtime-issued
target binding, not its enclosing subject. Return JSON only with ledger_id,
statements, diagnosis. Diagnosis is exactly {binding_id,status,assessment,
evidence_ids,gap:null,recommendation:null}. Status is INSUFFICIENT_EVIDENCE or
UNAVAILABLE. Assessment is exactly {subject,predicate,result}; subject is the
bound implementation symbol, predicate is the structured question_scope, and
result is NOT_ESTABLISHED_BY_INSPECTED_EVIDENCE. Cite inspected implementation
entries and target_unknowns. Source inspection does not establish a missing
general capability or current target-level behavioral qualification.
No prose substitution, domain-wide diagnosis, repair or authority grant is
permitted. This is a deliberately bounded semantic contract: unsupported
arbitrary prose is refused, not labeled semantically verified. Preserve unknowns.
MODE diagnoses; Operator authorizes; Builder constructs; Reality Primacy verifies.
'''

def questions(query):
    return list(re.finditer(r'\b(?:What|Which) (?:capability|component|mechanism|prevents)\b[^\n?]*\?',query,re.I))

def requested(query):
    matches=questions(query)
    own=re.search(r'\b(?:you|your|yourself|MODE)\b',query,re.I)
    declared=any(re.fullmatch(pattern,m.group(),re.I) for m in matches
                 for d in TARGETS for pattern in d['questions'])
    return bool(matches) and bool(own or declared)

def _read(definition):
    # Reuse the existing exact-selection, no-linked-path structural reader.
    from system_layer.audit.structural_inventory_auditor import validate_selection,_read as read
    root,_=validate_selection(WORKSPACE,[definition['path']])
    raw=read(root,definition['path']);text=raw.decode('utf-8-sig')
    nodes=ast.parse(text).body;rows=[]
    for symbol in definition['sources']:
        children=nodes
        for part in symbol.split('.'):
            node=next(n for n in children if isinstance(n,(ast.ClassDef,ast.FunctionDef)) and n.name==part)
            children=node.body
        excerpt='\n'.join(text.splitlines()[node.lineno-1:node.end_lineno])
        if len(excerpt.encode('utf-8'))>8000:raise ValueError('Target symbol exceeds bounded reader')
        rows.append({'path':definition['path'],'symbol':symbol,'sha256':hashlib.sha256(raw).hexdigest(),
                     'first_line':node.lineno,'last_line':node.end_lineno,'source_excerpt':excerpt})
    return rows

def resolve(query):
    """A bounded declared phrase-to-source mapping; ambiguity is never guessed."""
    matches=questions(query)
    if not matches:return None
    subject=re.search(r'\binspect\s+your\s+(?:current\s+)?([\w -]{1,64}?)\s+(?:system|subsystem)\b',query,re.I)
    b={'query_hash':objective_digest(query),'operative_question':None,'question_span':None,
       'enclosing_subject':subject.group(1).strip() if subject else None,
       'resolution':'AMBIGUOUS' if len(matches)!=1 else 'UNKNOWN',
       'target':None,'implementation_references':[],'question_scope':None,
       'execution_authority':False}
    if len(matches)==1:
        m=matches[0];text=m.group();start=m.start()+len(text)-len(text.lstrip())
        b.update(operative_question=query[start:m.end()],question_span=[start,m.end()])
        # Unsupported polarity/negation is ambiguous rather than silently
        # interpreted by the bounded positive-relation grammar.
        uncertain=re.search(r'\b(?:not|never|instead|except)\b',b['operative_question'],re.I)
        found=[] if uncertain else [d for d in TARGETS if any(re.fullmatch(p,b['operative_question'],re.I) for p in d['questions'])]
        if len(found)==1:
            d=found[0]
            try:
                rows=_read(d)
                b.update(resolution='RESOLVED',target={'path':d['path'],'symbol':d['symbol'],
                    'kind':'SOURCE_BOUND_IMPLEMENTATION'},implementation_references=[{k:v for k,v in r.items() if k!='source_excerpt'} for r in rows],
                    question_scope=deepcopy(d['question_scope']))
            except (OSError,ValueError,StopIteration,SyntaxError,UnicodeError):b['resolution']='UNAVAILABLE'
    b['binding_id']='inspection-target:'+digest(b)
    return b

def requirements(query):
    if not requested(query):return None
    b=resolve(query)
    if b is None:return None
    return {'contract':'ObjectiveEvidenceRequirements/2','subject':b['enclosing_subject'] or 'UNRESOLVED',
            'target_binding':b,'required_classes':['TARGET_IMPLEMENTATION','TARGET_EVIDENCE_LIMITS'],
            'resolution':'UNAVAILABLE','execution_authority':False,
            'limits':'Supported source-bound inspection only; unknown target is not an absent capability.'}

def verify(query,binding):
    if binding!=resolve(query) or binding.get('resolution')!='RESOLVED':
        raise PermissionError('Inspection target binding missing, changed, stale or unresolved')
    return binding

def context(runtime,query,requirements):
    from .capability_ledger import normalize,SOURCE
    from .evidence_ledger import PREFIX,INSTRUCTION
    from .inspection_coverage import derive,PREFIX as CP,INSTRUCTION as CI
    from integration.self_inspection_activation import prerequisite,SOURCE as PS,PREFIX as PP
    from data_governance.context_admission import Admission
    b=requirements['target_binding']
    if b['resolution']!='RESOLVED':return None
    verify(query,b);c=runtime.context;owner=c.identity.operator_id;thread=c.active_thread.thread_id
    projection={'contract':'CapabilityInspection/1','operator_id':owner,'scope':[b['target']],
        'inspection_id':b['binding_id'],'store':None,'entries':[],
        'limitations':['Source mapping is not a governed capability declaration or qualification.'],
        'execution_authority':False}
    ledger=normalize(projection,thread)
    ledger['objective']={**deepcopy(requirements),'query_hash':objective_digest(query),'resolution':'BOUNDED_SOURCES_INSPECTED'}
    sid='bound-target';ledger['sources'][sid]={'source_type':'OBJECTIVE_INSPECTION','source_identifier':sid,
        'reference':{'binding_id':b['binding_id'],'implementation_references':b['implementation_references']},
        'transition_id':None,'producer':'runtime_observation.inspection_target.context','stage':'READ_ONLY_BOUND_TARGET',
        'sequence':None,'operator_id':owner,'thread_id':thread}
    def add(field,value,cls='OBSERVED'):
        ledger['entries'].append({'entry_id':f'E{len(ledger["entries"])+1:03d}','field':field,'value':value,
            'evidence_class':cls,'source_id':sid,'scope':b['binding_id']+':'+field,
            'allowed_attribution_target':b['binding_id'],'directly_recorded':cls=='OBSERVED','derived':False,
            'confidence':'UNAVAILABLE','support':[],'recorded_alternatives':[],'conflicts':[]})
    add('operator_objective',query);add('inspection_target',b)
    definition=next(d for d in TARGETS if d['path']==b['target']['path'] and d['symbol']==b['target']['symbol'])
    rows=_read(definition)
    if [{k:v for k,v in r.items() if k!='source_excerpt'} for r in rows]!=b['implementation_references']:
        raise PermissionError('Source changed during target inspection')
    for row in rows:add('target_implementation',row)
    add('target_unknowns',{'question_scope':b['question_scope'],
        'missing':'No objective-specific target consequence/validation proof or current behavioral qualification is supplied by these source reads.',
        'limits':'Missing in this admitted inspection only; not a global absence finding or permission to acquire evidence.'},'UNAVAILABLE')
    ledger.pop('ledger_id');ledger['ledger_id']='ledger-'+digest(ledger)[:16]
    from .materiality_contract import evaluate
    c.diagnostic_materiality=evaluate(ledger);ledger=c.diagnostic_materiality['ledger']
    if c.diagnostic_materiality['receipt']['size_gate']=='BLOCK':raise PermissionError('Target diagnostic evidence bound exceeded')
    coverage=derive(query,ledger);receipt=prerequisite(query,owner,thread,ledger=ledger)
    c.self_inspection={'contract':'SelfInspectionAccess/1','operator_id':owner,'thread_id':thread,
        'provider_calls':0,'execution_authority':False,'objective_evidence':ledger['objective'],
        'tool_request':{'tool':'inspect_target_sources','target':b['target']},'tool_result':rows,
        'evidence_ledger':ledger,'coverage_contract':coverage,'prerequisite':receipt}
    a=Admission(owner,thread)
    for name,prefix,value,source in [('prerequisite',PP,receipt,PS),('target',PREFIX,ledger,SOURCE),('coverage',CP,coverage,'InspectionCoverage/1')]:
        a.consider('RUNTIME','self-inspection:'+name,prefix+json.dumps(value),source=source,
            basis={'authority':'READ_ONLY_RUNTIME_EVIDENCE','validation_state':'UNVALIDATED','lineage':[b['binding_id']]})
    a.consider('SYSTEM_POLICY','self-inspection:explanation-contract',INSTRUCTION+CI+POLICY,source='Bound target diagnosis contract')
    return a.finish()

def validate(ledger,value,selected):
    b=ledger['objective']['target_binding']
    query=next(e['value'] for e in ledger['entries'] if e['field']=='operator_objective')
    verify(query,b)
    keys={'binding_id','status','assessment','evidence_ids','gap','recommendation'}
    if type(value) is not dict or set(value)!=keys:raise PermissionError('Typed target-scope diagnosis required; no freeform substitution')
    if value['binding_id']!=b['binding_id'] or value['status'] not in {'INSUFFICIENT_EVIDENCE','UNAVAILABLE'}:
        raise PermissionError('Wrong inspection binding or unsupported capability claim')
    expected={'subject':b['target']['symbol'],'predicate':b['question_scope'],'result':'NOT_ESTABLISHED_BY_INSPECTED_EVIDENCE'}
    if value['assessment']!=expected:raise PermissionError('Semantic relation/roles do not answer bound question')
    if value['gap'] is not None or value['recommendation'] is not None:raise PermissionError('No repair from unavailable target evidence')
    ids=value['evidence_ids'];entries={e['entry_id']:e for e in ledger['entries']}
    if type(ids) is not list or any(type(i) is not str or i not in selected or i not in entries for i in ids) or len(ids)!=len(set(ids)):
        raise PermissionError('Known selected target evidence required')
    fields={entries[i]['field'] for i in ids}
    if not {'target_implementation','target_unknowns'}<=fields or any(entries[i]['source_id']!='bound-target' for i in ids):
        raise PermissionError('Target obligations cannot be discharged by enclosing-domain context')
    return deepcopy(value)

def output_format(ledger):
    b=ledger['objective']['target_binding']
    def fixed(v):
        if isinstance(v,dict):return obj({k:fixed(x) for k,x in v.items()})
        return {'type':'string','enum':[v]}
    def obj(p):return {'type':'object','properties':p,'required':list(p),'additionalProperties':False}
    ids=[e['entry_id'] for e in ledger['entries']]
    enumeration=lambda values:{'type':'string','enum':values}
    array=lambda values:{'type':'array','items':enumeration(values)}
    diagnosis=obj({'binding_id':enumeration([b['binding_id']]),'status':enumeration(['INSUFFICIENT_EVIDENCE','UNAVAILABLE']),
        'assessment':obj({'subject':enumeration([b['target']['symbol']]),'predicate':fixed(b['question_scope']),
            'result':enumeration(['NOT_ESTABLISHED_BY_INSPECTED_EVIDENCE'])}),
        'evidence_ids':array(ids),'gap':{'type':'null'},'recommendation':{'type':'null'}})
    return {'type':'json_schema','name':'target_scoped_diagnosis','strict':True,
        'schema':obj({'ledger_id':enumeration([ledger['ledger_id']]),'statements':array(ids),'diagnosis':diagnosis})}
