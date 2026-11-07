from types import SimpleNamespace as NS
import pytest
from system_layer.audit.structural_inventory_auditor import inspect
from system_layer.audit.operational_understanding_validator import FIELDS,LIST_FIELDS
from system_layer.audit.operation_source_binding import assess
from system_layer.service import SystemLayer
from system_layer.contracts import digest


def test_steps_bind_to_actual_symbols_without_import_or_execution(tmp_path):
    (tmp_path/'tool.py').write_text('raise RuntimeError("must not import")\ndef setup(): pass\ndef run(): pass')
    inventory=inspect(str(tmp_path),['tool.py'],system_id='tool',system_version='1',scope={'operator_id':'op','purpose':'inspect'})
    model=dict(schema_version='OperationalUnderstanding/1.2',version=1,supersedes=None,inventory_hash=inventory['inventory_hash'],
        definition={k:['Explicit condition'] if k in LIST_FIELDS else 'Explicit condition' for k in FIELDS})
    model['definition'].update(capability_id='tool',system_version='1',operation_sequence=['Set up','Run']);model['model_hash']=digest(model)
    bindings=[dict(step_index=i,source_path='tool.py',source_sha256=inventory['entries'][0]['sha256'],symbol_kind='PYTHON_FUNCTION',symbol=name) for i,name in enumerate(('setup','run'))]
    value=assess(model,inventory,bindings)
    assert value['state']=='DECLARED_STEPS_SOURCE_BOUND' and value['operability']=='UNPROVEN'
    assert assess(model,inventory,bindings[:1])['unmapped_steps']==[1]
    with pytest.raises(ValueError,match='missing'):assess(model,inventory,[dict(bindings[0],symbol='invented')])
    service=SystemLayer(tmp_path/'system.db',NS(context=NS(identity=NS(operator_id='op'))))
    req=dict(system_id='tool',system_version='1',root=str(tmp_path),files=['tool.py'],purpose='inspect')
    approve=lambda action,value:dict(operator_id='op',action=action,decision='APPROVE',hash=digest(value))
    inv=service.inventory(req,approve('STRUCTURAL_INVENTORY',req));inventory=inv['value']
    model['inventory_hash']=inventory['inventory_hash'];model['model_hash']=digest({k:v for k,v in model.items() if k!='model_hash'})
    mdl=service.operational_understanding(model,approve('OPERATIONAL_UNDERSTANDING',model))
    value=assess(model,inventory,bindings)
    request=dict(system_id='tool',model_receipt=mdl['receipt_id'],inventory_receipt=inv['receipt_id'],bindings=bindings)
    approved=dict(operator_id='op',action='OPERATIONAL_SOURCES',decision='APPROVE',hash=digest(request))
    stored=service.operational_sources(request,approved)
    assert stored['value']['binding_hash']==value['binding_hash']
    from understanding.creative_production import CreativePreparation
    creative=CreativePreparation(tmp_path/'docs.db')
    prep=creative.prepare('op',dict(project_id='p',medium='ANIMATION',capabilities=['ANIMATION'],assets=[],reuse_inventory_references=[],output_requirements=['Visible motion']))
    selected=[dict(capability_id='ANIMATION',system_id='tool',model_receipt=mdl['receipt_id'],inventory_receipt=inv['receipt_id'])]
    linked=creative.operational_models('op',prep,selected,system_store=service.store)
    assert linked['capabilities'][0]['source_receipt']==stored['receipt_id']
    assert linked['capabilities'][0]['source_map']['mapped'][1]['binding']['symbol']=='run'
    (tmp_path/'tool.py').write_text('def different(): pass')
    assert assess(model,inventory,bindings)['state']=='REVIEW_REQUIRED'
