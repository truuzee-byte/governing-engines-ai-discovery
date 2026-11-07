import json
from system_layer.audit.structural_inventory_auditor import inspect,freshness


def test_descriptor_relationships_are_structure_not_runtime_state(tmp_path):
    value={'EngineAssociation':'5.7','Modules':[{'Name':'Game','Type':'Runtime','AdditionalDependencies':['Engine']}],
           'Plugins':[{'Name':'ControlRig','Enabled':True,'PlatformAllowList':['Win64']}]}
    path=tmp_path/'Game.uproject';path.write_text(json.dumps(value))
    inventory=inspect(str(tmp_path),['Game.uproject'],system_id='game',system_version='1',scope={'operator_id':'op','purpose':'structure'})
    structure=inventory['entries'][0]['structure']
    assert structure['modules']==value['Modules'] and structure['plugins']==value['Plugins']
    assert structure['operability']=='UNPROVEN' and inventory['execution_authority']=='NONE'
    value['Plugins'][0]['Enabled']=False;path.write_text(json.dumps(value))
    assert freshness(inventory)['state']=='REVALIDATION_REQUIRED'


def test_malformed_or_missing_descriptor_structure_is_explicit(tmp_path):
    (tmp_path/'Bad.uplugin').write_text('{"Modules":42}')
    (tmp_path/'Empty.uproject').write_text('{}')
    result=inspect(str(tmp_path),['Bad.uplugin','Empty.uproject'],system_id='game',system_version='1',scope={'operator_id':'op','purpose':'structure'})
    assert result['entries'][0]['state']=='UNINSPECTABLE'
    assert result['entries'][1]['structure']['unresolved']==['Modules','Plugins']


def test_native_index_does_not_turn_lexical_names_into_callable_proof():
    from system_layer.audit.unreal_structure import native_candidates
    value=native_candidates(b'// class FalseType;\n#include "Source.h"\nclass TOOL_API ActualType {\n static void Execute(int x);\n};')
    assert value['includes']==['Source.h']
    assert [v['name'] for v in value['declarations']]==['ActualType','Execute']
    assert value['interpretation']=='LEXICAL_CANDIDATES_ONLY' and 'OPERATIONAL_VALIDATION' in value['unresolved']


def test_unreal_array_trailing_comma_dialect_preserves_strings_and_rejects_missing_values():
    import pytest
    from system_layer.audit.unreal_structure import parse
    result=parse(b'{"Plugins":[{"Name":"Literal,]","Enabled":true},],"Modules":[]}', 'PLUGIN')
    assert result['plugins'][0]['Name']=='Literal,]'
    assert len(result['parse_transformations'])==1 and result['operability']=='UNPROVEN'
    for malformed in (b'{"Plugins":[,]}',b'{"Plugins":[{},,]}',b'{"Plugins":[],}',b'{"Plugins":NaN}'):
        with pytest.raises(ValueError):parse(malformed,'PLUGIN')
