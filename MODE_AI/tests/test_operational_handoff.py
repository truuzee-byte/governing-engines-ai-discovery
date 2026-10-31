import pytest
from understanding import UnderstandingEngine, UnderstandingStore
from understanding.tests.test_understanding_v12 import request_for, interpreted
from system_layer.audit.structural_inventory_auditor import inspect
from system_layer.audit.operational_understanding_validator import FIELDS, LIST_FIELDS
from system_layer.contracts import digest

def test_meaning_to_operation_preserves_governance(tmp_path):
    engine=UnderstandingEngine(UnderstandingStore(tmp_path/'meaning.db'))
    result=engine.process(request_for(interpreted('Project term means Alpha.','Alpha')))
    (tmp_path/'tool.py').write_text('def run(): pass')
    inventory=inspect(str(tmp_path),['tool.py'],system_id='project.term',system_version='1',scope={'operator_id':'operator','purpose':'inventory'})
    model=dict(schema_version='OperationalUnderstanding/1.2',version=1,supersedes=None,inventory_hash=inventory['inventory_hash'],
        definition={k:['explicit condition'] if k in LIST_FIELDS else 'explicit condition' for k in FIELDS})
    model['definition'].update(capability_id='project.term',system_version='1');model['model_hash']=digest(model)
    prepared=result.operational_handoff(model,inventory,current_system_version='1')
    assert prepared['state']=='ACCESS_AND_AUTHORITY_REQUIRED'
    assert prepared['execution_authority'] is False and prepared['validation']=='UNPROVEN'
    assert prepared['meaning']['understanding_id']==result.final_understanding.understanding_id
    (tmp_path/'tool.py').write_text('def changed(): pass')
    assert result.operational_handoff(model,inventory,current_system_version='1')['state']=='REVIEW_REQUIRED'
    result.review_required=True
    with pytest.raises(PermissionError):result.operational_handoff(model,inventory,current_system_version='1')
