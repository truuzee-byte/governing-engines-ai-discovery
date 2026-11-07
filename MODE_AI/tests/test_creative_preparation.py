import pytest
from understanding.creative_production import CreativePreparation

@pytest.mark.parametrize('medium,required',[('GAME','ACTUAL_PLAY'),('ANIMATION','FRAME_CONTENT_INSPECTED')])
def test_shared_capabilities_require_actual_output(tmp_path,medium,required):
    request=dict(project_id='p',medium=medium,capabilities=['CHARACTER_CONSTRUCTION','ANIMATION'],assets=[],reuse_inventory_references=[],output_requirements=['operator specified output'])
    result=CreativePreparation(tmp_path/'store.db').prepare('op',request)
    assert required in result['required_observations']
    assert result['completion']=='UNPROVEN' and result['execution_authority'] is False
    assert result['missing']==['EXISTING_ASSET_INVENTORY_NOT_RETRIEVED']
    assert all(c['operational_understanding']=='NOT_ESTABLISHED' for c in result['capabilities'])
    request['assets']=[dict(object_id='missing-canon',version=1,expected_hash='hash')]
    with pytest.raises(FileNotFoundError):CreativePreparation(tmp_path/'store.db').prepare('op',request)
