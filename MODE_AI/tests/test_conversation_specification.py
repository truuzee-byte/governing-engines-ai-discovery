from tests.test_conversation_understanding import runtime
from types import SimpleNamespace as NS
from integration.conversation_understanding import prepare
from specs.conversation_specification import current, require_current
import pytest


def test_current_draft_accumulates_and_rejects_stale_projection(tmp_path):
    r=runtime(tmp_path)
    for i,text in enumerate(['Accept plain text.','Return JSON.','Reject empty input.']):
        r.context.active_thread.messages.append(NS(role='operator',content=text,message_id=str(i)))
        p={'subject_id':'local-tool','edits':[{'operation':'ADD','kind':'REQUIREMENT','quote':text,'target_id':None}]}
        result=prepare(r,text,interpreter=lambda *_:(p,{}))
        assert not result['result']['errors'], result
        view=current(r)[0]
        assert len(view['requirement_inventory'])==i+1
        assert view['specification']['authority_state']=='draft_only'
        assert not view['execution_attempted']
        if i==0:old=view['reference']
    with pytest.raises(PermissionError):require_current(r,old)
    assert require_current(r,view['reference'])['request']['construction_scope']==['Accept plain text.','Return JSON.','Reject empty input.']
