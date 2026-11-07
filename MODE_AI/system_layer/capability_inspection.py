"""Scoped inventory evidence on existing Capability heads, never RP promotion."""
import hashlib
from copy import deepcopy
from pathlib import Path
from .contracts import Capability, authorize, digest
from .state.store import SystemStore

KINDS = {'CODE','INTEGRATION','TEST','RUNTIME','QUALIFICATION'}
AXES = ('implementation_state','integration_state','validation_state','operational_state')
WORKSPACE = Path(__file__).resolve().parents[1]

def inspect_sources(projection, authenticated_operator_id):
    """Bounded current reads of references on verified owned heads, not discovery by filename.

    Changed code is observed as current bytes, never as newly validated code.
    Non-code evidence is a historical receipt summary, not operational truth.
    """
    import ast,json
    if projection != inspect_capabilities(projection['store'],authenticated_operator_id,
                                          projection['operator_id'],projection['scope']):
        raise PermissionError('Owned current registry projection required')
    rows=[]
    for cap in projection['entries']:
        for ref in (cap.get('inventory') or {}).get('evidence',[]):
            row={'kind':ref['kind'],'reference':dict(ref),'status':'UNAVAILABLE','execution_authority':False}
            original=Path(ref['path']);path=original.resolve()
            safe=(path.is_relative_to(WORKSPACE) and path.suffix in {'.py','.json','.md'} and
                  not any(q.is_symlink() or getattr(q,'is_junction',lambda:False)()
                          for q in [original,*original.parents] if q.is_relative_to(WORKSPACE)))
            if not safe or not path.is_file() or path.stat().st_size>16*1024*1024:
                row['reason']='SOURCE_OUTSIDE_BOUND_OR_UNAVAILABLE';rows.append(row);continue
            raw=path.read_bytes();actual=hashlib.sha256(raw).hexdigest()
            row.update(actual_sha256=actual,freshness='CURRENT_HASH' if actual==ref['sha256'] else 'CHANGED_SINCE_REGISTRY')
            if path.suffix=='.py' and ref['kind'] in {'CODE','INTEGRATION'}:
                try:
                    text=raw.decode('utf-8-sig');tree=ast.parse(text);nodes=list(tree.body)
                    for name in ref['locator'].split('.'):
                        node=next(n for n in nodes if getattr(n,'name',None)==name)
                        nodes=getattr(node,'body',[])
                    lines=text.splitlines();excerpt='\n'.join(lines[node.lineno-1:node.end_lineno])
                    row.update(component=str(path)+'#'+ref['locator'],first_line=node.lineno,last_line=node.end_lineno)
                    if len(excerpt.encode())>8000:raise ValueError('Symbol exceeds bounded reader')
                    row.update(status='OBSERVED_CURRENT_SOURCE',source_excerpt=excerpt,statement_bounds=[])
                    variables={n.targets[0].id for n in ast.walk(node) if isinstance(n,ast.Assign) and
                        len(n.targets)==1 and isinstance(n.targets[0],ast.Name) and any(
                        isinstance(c,ast.Call) and isinstance(c.func,ast.Attribute) and c.func.attr=='get' and
                        c.args and isinstance(c.args[0],ast.Constant) and c.args[0].value=='statements' for c in ast.walk(n.value))}
                    for n in ast.walk(node):
                        if not isinstance(n,ast.Compare):continue
                        # Only a directly negated guard whose branch raises can
                        # establish an upper rejection bound; a passing compare
                        # or opposite-polarity branch is not a capacity fact.
                        guarded=False
                        for branch in ast.walk(node):
                            if not isinstance(branch,ast.If) or not any(isinstance(b,ast.Raise) for b in branch.body):continue
                            terms=branch.test.values if isinstance(branch.test,ast.BoolOp) and isinstance(branch.test.op,ast.Or) else [branch.test]
                            if any(isinstance(t,ast.UnaryOp) and isinstance(t.op,ast.Not) and t.operand is n for t in terms):guarded=True
                        if not guarded:continue
                        seq=[n.left,*n.comparators]
                        for left,op,right in zip(seq,n.ops,seq[1:]):
                            if (isinstance(left,ast.Call) and isinstance(left.func,ast.Name) and left.func.id=='len' and
                                len(left.args)==1 and isinstance(left.args[0],ast.Name) and left.args[0].id in variables and
                                isinstance(op,ast.LtE) and isinstance(right,ast.Constant) and type(right.value) is int):
                                row['statement_bounds'].append({'maximum':right.value,'line':n.lineno,'expression':ast.unparse(n)})
                except (ValueError,SyntaxError,UnicodeError,StopIteration,AttributeError):row.update(status='UNAVAILABLE',reason='SYMBOL_NOT_READABLE_WITHIN_BOUND')
            elif actual!=ref['sha256']:row['reason']='HISTORICAL_RECEIPT_HASH_CHANGED'
            elif path.suffix=='.json':
                try:
                    value=__import__('json').loads(raw)
                    row.update(status='OBSERVED_HISTORICAL_RECEIPT',summary={k:value[k] for k in
                        ('contract','exit_code','provider_calls','execution_authority','validation_state') if isinstance(value,dict) and k in value})
                    if isinstance(value,dict) and isinstance(value.get('events'),list):
                        from collections import Counter
                        row['summary']['test_call_outcomes']=dict(Counter(e.get('outcome') for e in value['events'] if e.get('phase')=='call'))
                except (ValueError,TypeError):row['reason']='RECEIPT_UNREADABLE'
            else:row['reason']='NO_BOUNDED_BODY_READER_FOR_THIS_REFERENCE'
            rows.append(row)
    if len(__import__('json').dumps(rows).encode())>24576:raise ValueError('Objective evidence projection exceeds bound')
    return rows

def assess(evidence):
    """No promotion across evidence kinds; runtime scope remains mandatory."""
    present = {e['kind'] for e in evidence if e['result'] == 'PASS'}
    failed = any(e['result'] == 'FAIL' for e in evidence)
    return {'specified':'SPECIFIED',
        'implemented':'IMPLEMENTED' if 'CODE' in present else 'UNKNOWN',
        'integrated':'INTEGRATED' if {'CODE','INTEGRATION'} <= present else 'UNKNOWN',
        'validated':'VALIDATED' if 'TEST' in present else 'UNKNOWN',
        'operational':'OPERATIONAL' if 'RUNTIME' in present else 'UNKNOWN',
        'health':'DEGRADED' if failed else 'NO_RECORDED_FAILURE_IN_SELECTED_EVIDENCE',
        'authority':'EVIDENCE_INVENTORY_ONLY_NOT_RP_OR_QUALIFICATION_PROMOTION'}

def validate_payload(owner, value):
    if set(value) != {'capability','evidence_inventory','control','target_state'}:
        raise ValueError('Exact capability evidence inventory required')
    cap = Capability(**value['capability'])
    if cap.operator_id != owner or cap.declared_state != 'DECLARED' or any(getattr(cap,k) != 'UNCONFIRMED' for k in AXES) or cap.rp_state != 'PENDING_VALIDATION':
        raise PermissionError('Evidence inventory cannot promote governed reality axes')
    inventory = value['evidence_inventory']
    if set(inventory) != {'contract','evidence','assessment','limitations','component_ownership'} or inventory['contract'] != 'CapabilityEvidenceInventory/1':
        raise ValueError('Typed capability evidence required')
    if value['control'] != 'EVIDENCE_ONLY' or value['target_state'] != 'UNCONFIRMED':
        raise PermissionError('Evidence inventory has no transition authority')
    if not isinstance(inventory['limitations'],list) or not inventory['limitations']:
        raise ValueError('Explicit scope limitations required')
    evidence=inventory['evidence']
    if not isinstance(evidence,list) or len(evidence)>16: raise ValueError('Bounded evidence required')
    for e in evidence:
        if (set(e) != {'kind','path','sha256','locator','scope','result'} or e['kind'] not in KINDS or
                e['result'] not in {'PASS','FAIL','UNKNOWN'} or not e['scope'] or not e['locator'] or
                not Path(e['path']).is_absolute() or len(e['sha256']) != 64):
            raise ValueError('Typed exact evidence reference required')
    if inventory['assessment'] != assess(evidence): raise PermissionError('Invented assessment')
    return cap

def validate_record(owner, record):
    cap=validate_payload(owner,record['value'])
    authorize(owner,'CAPABILITY_EVIDENCE',{'value':record['value'],'expected_receipt':record['previous_receipt']},record['authorization'])
    if record['subject'] != cap.capability_id: raise PermissionError('Capability subject mismatch')

def record_evidence(service, value, expected_receipt, approval):
    """Operator-only inventory population. No identity or execution grant implied."""
    value=deepcopy(value); cap=validate_payload(service.owner,value)
    authorize(service.owner,'CAPABILITY_EVIDENCE',{'value':value,'expected_receipt':expected_receipt},approval)
    for e in value['evidence_inventory']['evidence']:
        if hashlib.sha256(Path(e['path']).read_bytes()).hexdigest() != e['sha256']:
            raise PermissionError('Evidence source changed before recording')
    with service.store.transaction(service.owner) as (heads,_,append):
        previous=heads.get(cap.capability_id)
        if (previous or {}).get('receipt_id') != expected_receipt: raise PermissionError('Stale capability head')
        if previous and previous['value'].get('control') != 'EVIDENCE_ONLY':
            raise PermissionError('Cannot overwrite operational workflow with inventory')
        if cap.version != (previous['value']['capability']['version']+1 if previous else 1) or cap.supersedes != expected_receipt:
            raise PermissionError('Explicit inventory version lineage required')
        return append(cap.capability_id,value,'CAPABILITY_EVIDENCE_RECORDED',approval,
                      [e['path']+'#'+e['locator'] for e in value['evidence_inventory']['evidence']])

def inspect_capabilities(path, authenticated_operator_id, operator_id, scope):
    """Only the already authenticated operator can read its bounded registry.

    No arbitrary file reads: freshness hashes only references inside this workspace.
    """
    if not authenticated_operator_id or authenticated_operator_id != operator_id:
        raise PermissionError('Capability custody mismatch')
    if type(scope) is not list or not 1<=len(scope)<=8 or any(type(s) is not str for s in scope) or len(set(scope))!=len(scope):
        raise ValueError('Explicit bounded capability IDs required')
    heads=SystemStore.snapshot(path,operator_id); entries=[]
    root=Path(__file__).resolve().parents[1]
    for cid in scope:
        r=heads.get(cid)
        if r is None or 'capability' not in r['value']:
            entries.append({'capability_id':cid,'state':'UNKNOWN','reason':'NO_OWNED_REGISTRY_ENTRY'});continue
        cap=Capability(**r['value']['capability'])
        if cap.operator_id != operator_id: raise PermissionError('Stored capability owner mismatch')
        inventory=r['value'].get('evidence_inventory')
        checks=[]
        if inventory:
            for e in inventory['evidence']:
                original=Path(e['path']);p=original.resolve()
                # Disallow symlinks/reparse escapes and unrelated private files.
                allowed=p.is_relative_to(root) and not any(q.is_symlink() for q in [original,*original.parents] if q.is_relative_to(root))
                actual=hashlib.sha256(p.read_bytes()).hexdigest() if allowed and p.is_file() and p.stat().st_size<=16*1024*1024 else None
                checks.append({'path':e['path'],'kind':e['kind'],'state':'CURRENT_HASH' if actual==e['sha256'] else 'CHANGED_OR_UNAVAILABLE'})
        entries.append({'capability_id':cid,'name':cap.name,'receipt_id':r['receipt_id'],
            'authoritative_states':{k:getattr(cap,k) for k in ('declared_state',*AXES,'rp_state')},
            'dependencies':cap.dependencies,'version':cap.version,'supersedes':cap.supersedes,
            'inventory':inventory,'freshness':checks,
            'conflict':'REVALIDATION_REQUIRED' if any(c['state']!='CURRENT_HASH' for c in checks) else 'NONE_OBSERVED_IN_SELECTED_EVIDENCE',
            'execution_authority':False})
    result={'contract':'CapabilityInspection/1','operator_id':operator_id,'scope':scope,'entries':entries,
        'store':str(Path(path).resolve()),'validation_state':'RECORDED_NOT_INDEPENDENTLY_VALIDATED',
        'execution_authority':False,'limitations':['Selected registry evidence is not a whole-system capability audit.',
        'Scoped runtime success does not prove generalized capability. RP axes and qualification remain unchanged.']}
    result['inspection_id']='capability-inspection:'+digest(result)
    return result
