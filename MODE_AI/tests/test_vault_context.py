import json
from types import SimpleNamespace as NS
import pytest
from integration.content_custody import command
from memory.vault_context import prompt_context
from system_layer.contracts import digest


def test_vault_context_exact_once_and_failed_selection_clears_previous(tmp_path):
    runtime=NS(context=NS(identity=NS(operator_id='op'),active_thread=NS(thread_id='t')),
        understanding_engine=NS(store=NS(path=tmp_path/'meaning.db')))
    req=dict(object_id='canon',content='Original preserved wording.',kind='CANON',project_id='p',thread_id='t',
        source_reference='operator:1',authority='operator',expected_previous=None)
    saved=command(runtime,'/vault preserve '+json.dumps(dict(request=req,approval=dict(operator_id='op',action='VAULT_PRESERVE',decision='APPROVE',hash=digest(req)))))
    ref=dict(object_id='canon',version=1,expected_hash=saved['record_hash'])
    def select(refs):return command(runtime,'/vault context '+json.dumps(dict(references=refs,project_id='p')))
    select([ref,ref]);prompt=prompt_context(runtime)
    assert str(prompt).count(req['content'])==1 and len(prompt.decisions)==1
    assert prompt_context(runtime) is None
    select([ref])
    with pytest.raises(FileNotFoundError):select([dict(ref,object_id='missing')])
    assert prompt_context(runtime) is None
