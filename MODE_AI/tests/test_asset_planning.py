import json
import pytest
from understanding.creative_production import CreativePreparation
from understanding.creative_models import FIELDS
from understanding.asset_planning import search,plan
from system_layer.contracts import digest


def test_asset_choice_is_bound_to_actual_search_and_prepared_definition(tmp_path):
    creative=CreativePreparation(tmp_path/'docs.db')
    def intake(identity,content,kind):
        req=dict(object_id=identity,content=content,kind=kind,visual_authority='NOT_APPLICABLE',knowledge_class='INTERNAL',
            source_reference='operator:asset',authority='operator',project_id='p',thread_id='t',expected_previous=None,validation_references=[])
        record=creative.documents.intake('op',req,dict(operator_id='op',action='DOCUMENT_INTAKE',decision='APPROVE',hash=digest(req)))
        return dict(object_id=identity,version=1,expected_hash=record['record_hash'])
    asset=intake('oak-model','Oak geometry source','PRODUCTION_ASSET')
    definition={k:'Explicit authored requirement' for k in FIELDS['ASSET']};definition['reuse_modify_create']='MODIFY'
    model=dict(schema_version='SharedCreativeDefinition/1',identity='asset-plan',kind='ASSET',definition=definition,
        representations={},use_requirements={'GAME':['Interactive scene'],'ANIMATION':['Rendered scene']},source_references=[asset])
    modelref=intake('asset-plan',json.dumps(model),'DRAFT')
    prep=creative.prepare('op',dict(project_id='p',medium='GAME',capabilities=['ASSET_CONSTRUCTION'],assets=[asset],
        reuse_inventory_references=[],model_references=[modelref],output_requirements=['Integrated authored tree']))
    found=search(creative,'op',prep,'Oak')
    assert len(found['candidates'])==1 and found['candidates'][0]['reference']==asset
    request=dict(preparation_hash=prep['preparation_hash'],model_reference=modelref,query='Oak',search_hash=found['search_hash'],choice='MODIFY',asset_reference=asset,rationale='Adapt the existing model')
    approval=lambda r:dict(operator_id='op',action='CREATIVE_ASSET_PLAN',decision='APPROVE',hash=digest(r))
    result=plan(creative,'op',prep,request,approval(request))
    assert result['selected_source']['record_hash']==asset['expected_hash'] and result['completion']=='UNPROVEN'
    assert result['licensing']=='NOT_VALIDATED' and not result['execution_authority']
    with pytest.raises(PermissionError):plan(creative,'op',prep,request,{})
    intake('new-oak','Oak alternative','PRODUCTION_ASSET')
    with pytest.raises(ValueError,match='search changed'):plan(creative,'op',prep,request,approval(request))
