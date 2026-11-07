from copy import deepcopy
import pytest
from understanding.creative_production import CreativePreparation
from system_layer.contracts import digest


@pytest.mark.parametrize('field,value',[('completion','PASS'),('execution_authority',True),
    ('capabilities',[{'capability_id':'ANIMATION','operational_understanding':'ESTABLISHED'}])])
def test_rehashed_embedded_claims_cannot_replace_source_resolution(tmp_path,field,value):
    creative=CreativePreparation(tmp_path/'custody.db')
    original=creative.prepare('op',dict(project_id='p',medium='ANIMATION',capabilities=['ANIMATION'],assets=[],
        reuse_inventory_references=[],output_requirements=['Visible motion']))
    altered=deepcopy(original);altered[field]=value
    altered['preparation_hash']=digest({k:v for k,v in altered.items() if k!='preparation_hash'})
    with pytest.raises(ValueError,match='canonical source resolution'):creative._check_preparation('op',altered)
    creative._check_preparation('op',original)
