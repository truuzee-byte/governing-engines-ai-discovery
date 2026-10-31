from understanding.creative_production import CreativePreparation
from system_layer.audit.structural_inventory_auditor import inspect
from system_layer.audit.operational_understanding_validator import FIELDS,LIST_FIELDS
from system_layer.state.store import SystemStore
from system_layer.contracts import digest
import pytest


def test_creative_uses_current_existing_operational_model_without_grant(tmp_path):
    creative=CreativePreparation(tmp_path/'docs.db')
    preparation=creative.prepare('op',dict(project_id='p',medium='ANIMATION',capabilities=['ANIMATION','VOICE_PERFORMANCE'],
        assets=[],reuse_inventory_references=[],output_requirements=['Observed motion']))
    tool=tmp_path/'tool.py';tool.write_text('def animate(): return 1')
    inventory=inspect(str(tmp_path),['tool.py'],system_id='tool',system_version='1',scope={'operator_id':'op','purpose':'fixture'})
    model=dict(schema_version='OperationalUnderstanding/1.2',version=1,supersedes=None,inventory_hash=inventory['inventory_hash'],
        definition={k:['fixture requirement'] if k in LIST_FIELDS else 'fixture requirement' for k in FIELDS})
    model['definition'].update(capability_id='tool',system_version='1');model['model_hash']=digest(model)
    from types import SimpleNamespace as NS
    from system_layer.service import SystemLayer
    service=SystemLayer(tmp_path/'system.db',NS(context=NS(identity=NS(operator_id='op'))));store=service.store
    request=dict(system_id='tool',system_version='1',root=str(tmp_path),files=['tool.py'],purpose='fixture')
    approve=lambda action,value:dict(operator_id='op',action=action,decision='APPROVE',hash=digest(value))
    a=service.inventory(request,approve('STRUCTURAL_INVENTORY',request));inventory=a['value']
    model['inventory_hash']=inventory['inventory_hash'];model['model_hash']=digest({k:v for k,v in model.items() if k!='model_hash'})
    b=service.operational_understanding(model,approve('OPERATIONAL_UNDERSTANDING',model))
    binding=dict(capability_id='ANIMATION',system_id='tool',model_receipt=b['receipt_id'],inventory_receipt=a['receipt_id'])
    result=creative.operational_models('op',preparation,[binding],system_store=store)
    assert result['capabilities'][0]['state']=='STRUCTURALLY_GROUNDED_MODEL'
    assert result['unbound']==['VOICE_PERFORMANCE'] and result['execution_authority'] is False
    tool.write_text('def changed(): return 2')
    assert creative.operational_models('op',preparation,[binding],system_store=store)['capabilities'][0]['state']=='REVIEW_REQUIRED'
    with pytest.raises(ValueError):creative.operational_models('op',preparation,[dict(binding,model_receipt='stale')],system_store=store)
