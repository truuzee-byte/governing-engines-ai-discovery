import json
import sqlite3
import pytest
from system_layer.state.store import SystemStore
from system_layer.contracts import digest


@pytest.mark.parametrize('field,value',[
    ('receipt_id','system-receipt:wrong'),('previous_receipt','absent'),
    ('previous_value',{'invented':True}),('subject','other'),
])
def test_receipt_reconstruction_rejects_inconsistent_inner_lineage(tmp_path,field,value):
    store=SystemStore(tmp_path/'system.db')
    with store.transaction('op') as (_,__,append):append('capability',{'state':'DECLARED'},'DECLARE',{})
    with sqlite3.connect(store.path) as db:
        record=json.loads(db.execute('SELECT payload FROM events').fetchone()[0]);record[field]=value
        if field!='receipt_id':record['receipt_id']='system-receipt:'+digest({k:v for k,v in record.items() if k!='receipt_id'})
        db.execute('UPDATE events SET payload=?,hash=?',(json.dumps(record),digest(['op','capability',record,''])))
    with pytest.raises(ValueError,match='receipt lineage integrity'):store.get('op','capability')


def test_interleaved_subjects_reconstruct_their_own_receipts(tmp_path):
    store=SystemStore(tmp_path/'system.db')
    with store.transaction('op') as (_,__,append):
        first=append('one',{'state':'DECLARED'},'DECLARE',{})
        append('two',{'state':'DECLARED'},'DECLARE',{})
        final=append('one',{'state':'UNPROVEN'},'INSPECT',{},[first['receipt_id']])
    assert store.get('op','one')==final
    assert final['previous_receipt']==first['receipt_id']
    assert len(store.history('op'))==3
