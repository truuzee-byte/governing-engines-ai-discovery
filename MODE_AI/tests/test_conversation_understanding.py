from types import SimpleNamespace as NS
from understanding import UnderstandingEngine
from understanding.understanding_store import UnderstandingStore
from integration.conversation_understanding import prepare,prompt_context,current_records


def runtime(tmp_path, thread='t'):
    return NS(context=NS(identity=NS(operator_id='op'),active_thread=NS(thread_id=thread,messages=[])),
              understanding_engine=UnderstandingEngine(store=UnderstandingStore(tmp_path/'meaning.sqlite3')))


def test_current_governed_meaning_reaches_context_and_is_thread_scoped(tmp_path):
    r=runtime(tmp_path)
    def turn(text):
        r.context.active_thread.messages.append(NS(role='operator',content=text,message_id=str(len(r.context.active_thread.messages))))
        proposal={'subject_id':'scenario','edits':[{'operation':'ADD','kind':'FACT','quote':text,'target_id':None}]}
        result=prepare(r,text,interpreter=lambda *_:(proposal,{}))
        assert not result.get('error_type'), result
        assert not result['result']['errors'],result
    turn('A visitor arrives.')
    turn('The visitor did not ring the bell.')
    prompt=prompt_context(r)
    assert 'A visitor arrives.' in str(prompt) and 'did not ring' in str(prompt)
    assert len(current_records(r))==1 and current_records(r)[0].version==2
    fresh=runtime(tmp_path,'fresh')
    assert current_records(fresh)==[]
    assert 'visitor' not in str(prompt_context(fresh))


def test_model_cannot_invent_operator_evidence(tmp_path):
    r=runtime(tmp_path);text='A visitor arrives.'
    r.context.active_thread.messages.append(NS(role='operator',content=text,message_id='m'))
    proposal={'subject_id':'scenario','edits':[{'operation':'ADD','kind':'FACT','quote':'The visitor is an intruder.','target_id':None}]}
    result=prepare(r,text,interpreter=lambda *_:(proposal,{}))
    assert result['result']['errors']
    assert current_records(r)==[]
