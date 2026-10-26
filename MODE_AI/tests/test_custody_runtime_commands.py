import json
from types import SimpleNamespace as NS
import pytest
from integration.content_custody import command
from system_layer.contracts import digest

def test_explicit_runtime_commands_retrieve_exact_source(tmp_path):
    runtime=NS(context=NS(identity=NS(operator_id='op')),understanding_engine=NS(store=NS(path=tmp_path/'meaning.db')))
    request=dict(object_id='source',content='Exact operator canon.',source_reference='operator:turn',authority='operator',
                 kind='CANON',project_id='project',thread_id='thread',expected_previous=None,
                 visual_authority='CANONICAL_VISUAL_AUTHORITY',validation_references=[],knowledge_class='INTERNAL')
    payload=dict(request=request,approval=dict(operator_id='op',action='DOCUMENT_INTAKE',decision='APPROVE',hash=digest(request)))
    saved=command(runtime,'/documents intake '+json.dumps(payload))
    reference=dict(object_id='source',version=saved['version'],expected_hash=saved['record_hash'])
    retrieved=command(runtime,'/knowledge '+json.dumps([dict(reference,knowledge_class='INTERNAL')]))
    assert retrieved['entries'][0]['record']['content']==request['content']
    with pytest.raises(FileNotFoundError):command(runtime,'/vault get '+json.dumps(reference))
    preparation=command(runtime,'/creative '+json.dumps(dict(project_id='project',medium='ANIMATION',
        capabilities=['ANIMATION'],assets=[reference],reuse_inventory_references=[],output_requirements=['Visible motion'])))
    assert preparation['sources'][0]['record']['record_hash']==saved['record_hash']
    assert preparation['completion']=='UNPROVEN'
    assert command(runtime,'Here is generated text: /documents intake {}') is None
    with pytest.raises(TypeError):command(runtime,'/documents get '+json.dumps(dict(reference,owner='other')))


@pytest.mark.parametrize('body',['{"owner":"op","owner":"other"}','{"nested":{"decision":"REJECT","decision":"APPROVE"}}','{"version":NaN}'])
def test_malformed_command_does_not_silently_choose_a_value(tmp_path,body):
    runtime=NS(context=NS(identity=NS(operator_id='op')),understanding_engine=NS(store=NS(path=tmp_path/'meaning.db')))
    with pytest.raises(ValueError,match='Duplicate|Non-finite'):command(runtime,'/documents get '+body)
