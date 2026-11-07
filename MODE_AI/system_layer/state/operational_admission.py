"""Operational provenance enforced by the existing SystemStore.

These records describe structure/procedures, never RP-validated operability.
The transient seal proves application writer provenance, not hostile-host custody.
"""
from copy import deepcopy
from pathlib import Path
from ..contracts import authorize, digest

PREFIXES={'inventory:':'STRUCTURAL_INVENTORY',
          'operational-understanding:':'OPERATIONAL_UNDERSTANDING',
          'operational-sources:':'OPERATIONAL_SOURCES',
          'source-discovery:':'STRUCTURAL_SOURCE_DISCOVERY'}
_ISSUER=object()


def family(subject):
    return next((p for p in PREFIXES if subject.startswith(p)),None)


class _Issued(dict):
    def __init__(self,value,issuer):
        if issuer is not _ISSUER:raise PermissionError('Operational producer required')
        super().__init__(deepcopy(value));self._hash=digest(value)
    def verify(self):
        if digest(dict(self))!=self._hash:raise PermissionError('Operational admission changed')
        return deepcopy(dict(self))


def issue(owner,subject,action,request,value,approval):
    authorize(owner,action,request,approval)
    if PREFIXES.get(family(subject))!=action:raise PermissionError('Operational namespace/action mismatch')
    return _Issued(dict(contract='SystemOperationalAdmission/1',owner=owner,subject=subject,
        action=action,request=deepcopy(request),value_hash=digest(value)),_ISSUER)


def validate(owner,record,current,*,live=False):
    prefix=family(record['subject'])
    if prefix is None:return
    proof=record.get('operational_admission')
    if type(proof) is not dict or set(proof)!={'contract','owner','subject','action','request','value_hash'}:
        raise PermissionError('Operational import lacks governed admission provenance')
    subject=record['subject'];identity=subject[len(prefix):];value=record['value'];request=proof['request']
    if (not identity or proof['contract']!='SystemOperationalAdmission/1' or proof['owner']!=owner or
        proof['subject']!=subject or proof['action']!=record['action'] or
        PREFIXES[prefix]!=record['action'] or proof['value_hash']!=digest(value)):
        raise PermissionError('Operational admission binding mismatch')
    authorize(owner,record['action'],request,record['authorization'])
    prior=current.get(subject)
    previous=prior['receipt_id'] if prior else None
    references=[previous] if previous else []
    if prefix=='inventory:':
        fields={'system_id','system_version','root','files','purpose'}
        if type(request) is not dict or set(request)!=fields:raise ValueError('Inventory request provenance required')
        from ..audit.structural_inventory_auditor import inspect
        if (value['system_id']!=identity or request['system_id']!=identity or
            value['system_version']!=request['system_version'] or value['root']!=str(Path(request['root'])) or
            value['selection']!=sorted(request['files']) or value['scope']!={'operator_id':owner,'purpose':request['purpose']} or
            value['version']!=(prior['value']['version']+1 if prior else 1) or value['supersedes']!=previous or
            value['operational_state']!='UNPROVEN' or value['execution_authority']!='NONE' or
            value['schema_version']!='StructuralInventory/1.2' or
            value['inventory_hash']!=digest({k:v for k,v in value.items() if k!='inventory_hash'})):
            raise PermissionError('Inventory cannot establish operational reality')
        if live:
            expected=inspect(request['root'],request['files'],system_id=identity,
                system_version=request['system_version'],scope=value['scope'],version=value['version'],supersedes=previous)
            clean=lambda v:{k:x for k,x in v.items() if k not in {'observed_at','inventory_hash'}}
            if clean(expected)!=clean(value):raise PermissionError('Inventory differs from observed source state')
    elif prefix=='source-discovery:':
        if type(request) is not dict or set(request)!={'system_id','root','extensions','limit','purpose'}:
            raise ValueError('Discovery request provenance required')
        if (request['system_id']!=identity or value['system_id']!=identity or value['operator_id']!=owner or
            value['root']!=str(Path(request['root'])) or any(value[k]!=request[k] for k in ('extensions','limit','purpose')) or
            value['execution_authority'] is not False or value['operability']!='UNPROVEN' or value['source_contents_read'] is not False or
            value['discovery_hash']!=digest({k:v for k,v in value.items() if k!='discovery_hash'})):
            raise PermissionError('Discovery cannot grant source authority')
        if live:
            from ..audit.source_discovery import discover
            expected=discover(request['root'],request['extensions'],request['limit'])
            expected.update(system_id=identity,purpose=request['purpose'],operator_id=owner)
            expected['discovery_hash']=digest({k:v for k,v in expected.items() if k!='discovery_hash'})
            if value!=expected:raise PermissionError('Discovery changed before admission')
    else:
        inventory=current.get('inventory:'+identity)
        if inventory is None:raise PermissionError('Governed inventory required')
        if prefix=='operational-understanding:':
            model=value['model'];assessment=value['assessment']
            if (set(value)!={'model','assessment'} or model!=request or model['definition']['capability_id']!=identity or
                model['inventory_hash']!=inventory['value']['inventory_hash'] or
                model['version']!=(prior['value']['model']['version']+1 if prior else 1) or model['supersedes']!=previous or
                assessment['runtime_operability']!='UNPROVEN' or assessment['execution_authority']!='NONE' or
                assessment['access']!='NOT_ESTABLISHED' or assessment['rp_verdict']!='NOT_REQUESTED'):
                raise PermissionError('Operational model is a governed declaration, not capability')
            references=[inventory['receipt_id'],*references]
            if live:
                from ..audit.operational_understanding_validator import evaluate
                if assessment!=evaluate(model,inventory['value'],current_system_version=inventory['value']['system_version']):
                    raise PermissionError('Operational assessment mismatch')
        else:
            model=current.get('operational-understanding:'+identity)
            if type(request) is not dict or set(request)!={'system_id','model_receipt','inventory_receipt','bindings'}:
                raise ValueError('Source binding request provenance required')
            if (model is None or request['system_id']!=identity or request['model_receipt']!=model['receipt_id'] or
                request['inventory_receipt']!=inventory['receipt_id'] or value['bindings']!=request['bindings'] or
                value['model_hash']!=model['value']['model']['model_hash'] or value['inventory_hash']!=inventory['value']['inventory_hash'] or
                value['execution_authority'] is not False or value['runtime_access']!='NOT_ESTABLISHED' or value['operability']!='UNPROVEN' or
                value['binding_hash']!=digest({k:v for k,v in value.items() if k!='binding_hash'})):
                raise PermissionError('Operational source cannot authorize itself')
            references=[model['receipt_id'],inventory['receipt_id']]
            if live:
                from ..audit.operation_source_binding import assess
                if value!=assess(model['value']['model'],inventory['value'],request['bindings']):
                    raise PermissionError('Operational source assessment mismatch')
    if record['references']!=references:raise PermissionError('Operational receipt lineage mismatch')
