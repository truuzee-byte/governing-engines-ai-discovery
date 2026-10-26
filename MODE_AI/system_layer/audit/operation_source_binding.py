"""Bind declared operation steps to inspected symbols, without importing tools.

System v1.2 §§8A,15–16 and Creative v1.2 §§43–53. Lexical native candidates
remain unresolved interfaces; a function declaration never proves runtime access.
"""
from copy import deepcopy
from ..contracts import digest
from .operational_understanding_validator import evaluate


def assess(model,inventory,bindings):
    assessment=evaluate(model,inventory,current_system_version=inventory['system_version'])
    if type(bindings) is not list or len(bindings)>256:raise ValueError('Bounded operation source bindings required')
    sequence=model['definition'].get('operation_sequence') or []
    entries={e['path']:e for e in inventory['entries']};mapped=[];seen=set()
    for binding in bindings:
        fields={'step_index','source_path','source_sha256','symbol_kind','symbol'}
        if type(binding) is not dict or set(binding)!=fields:raise ValueError('Exact operation/source/symbol binding required')
        index=binding['step_index']
        if type(index) is not int or not 0<=index<len(sequence):raise ValueError('Unknown operation step')
        if any(type(binding[k]) is not str or not binding[k] for k in fields-{'step_index'}):raise ValueError('Nonempty source identity required')
        key=tuple(binding[k] for k in sorted(fields))
        if key in seen:raise ValueError('Duplicate operation source binding')
        seen.add(key);entry=entries.get(binding['source_path'])
        if entry is None or entry['state']!='INSPECTED' or entry['sha256']!=binding['source_sha256']:
            raise ValueError('Operation source not present in the exact inspected inventory')
        structure=entry['structure'];kind=binding['symbol_kind'];symbol=binding['symbol'];state='SYMBOL_LOCATED';interface=None
        if kind=='PYTHON_INTERFACE':
            found=[v for v in structure.get('interfaces',[]) if v['qualified_name']==symbol]
            if len(found)!=1:raise ValueError('Python interface missing or ambiguous')
            interface=deepcopy(found[0])
        elif kind in {'PYTHON_FUNCTION','PYTHON_CLASS'}:
            names=structure.get('functions' if kind=='PYTHON_FUNCTION' else 'classes',[])
            if names.count(symbol)!=1:raise ValueError('Source symbol missing or ambiguous')
        elif kind in {'TYPE_CANDIDATE','STATIC_INTERFACE_CANDIDATE'}:
            candidates=[d for d in structure.get('declarations',[]) if d['kind']==kind and d['name']==symbol]
            if len(candidates)!=1:raise ValueError('Native source candidate missing or ambiguous')
            state='SIGNATURE_RESOLUTION_REQUIRED'
        else:raise ValueError('Unsupported operation symbol kind')
        mapped.append({'binding':deepcopy(binding),'operation':sequence[index],'state':state,'interface':interface,
            'argument_binding':'NOT_EVALUATED'})
    missing=[i for i in range(len(sequence)) if not any(m['binding']['step_index']==i for m in mapped)]
    unresolved=assessment['state']!='STRUCTURALLY_GROUNDED_MODEL' or missing or any(m['state']!='SYMBOL_LOCATED' for m in mapped)
    value={'contract':'OperationSourceBinding/1','model_hash':model['model_hash'],'inventory_hash':inventory['inventory_hash'],
        'bindings':deepcopy(bindings),'mapped':mapped,'unmapped_steps':missing,'assessment':assessment,
        'state':'REVIEW_REQUIRED' if unresolved else 'DECLARED_STEPS_SOURCE_BOUND',
        'execution_authority':False,'runtime_access':'NOT_ESTABLISHED','operability':'UNPROVEN'}
    value['binding_hash']=digest(value)
    return value
