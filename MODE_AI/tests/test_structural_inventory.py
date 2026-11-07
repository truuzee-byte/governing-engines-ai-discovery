import json
from types import SimpleNamespace as NS
import pytest
from system_layer.audit.structural_inventory_auditor import inspect, freshness
from system_layer.audit.operational_understanding_validator import evaluate, FIELDS, LIST_FIELDS
from system_layer.contracts import digest
from system_layer.service import SystemLayer


def snapshot(tmp_path, files=None):
    return inspect(str(tmp_path), files or ['tool.py'], system_id='tool', system_version='v1',
                   scope={'operator_id': 'operator', 'purpose': 'Inspect tool interface'})


def test_inventory_reads_structure_without_running_code(tmp_path):
    (tmp_path / 'tool.py').write_text("raise RuntimeError('must not execute')\nclass Tool:\n def run(self): pass\n")
    before = (tmp_path / 'tool.py').read_bytes()
    record = snapshot(tmp_path)
    assert record['entries'][0]['structure']['classes'] == ['Tool']
    assert record['entries'][0]['structure']['functions'] == ['run']
    assert record['completeness'] == 'COMPLETE_FOR_SELECTION'
    assert record['operational_state'] == 'UNPROVEN' and record['execution_authority'] == 'NONE'
    assert record == json.loads(json.dumps(record))
    assert (tmp_path / 'tool.py').read_bytes() == before


@pytest.mark.parametrize('content',['{"setting":1,"setting":2}','{"setting":NaN}'])
def test_ambiguous_json_inventory_remains_uninspectable(tmp_path,content):
    import hashlib
    raw=content.encode();(tmp_path/'tool.json').write_bytes(raw)
    record=snapshot(tmp_path,['tool.json']);entry=record['entries'][0]
    assert entry['state']=='UNINSPECTABLE' and entry['structure'] is None
    assert entry['sha256']==hashlib.sha256(raw).hexdigest()
    assert record['completeness']=='PARTIAL'
    assert freshness(record)['state']=='REVALIDATION_REQUIRED'


@pytest.mark.parametrize('files', [[], ['../outside'], ['C:/secret'], ['/secret'], ['x:stream'], ['x','X'], ['a/./b']])
def test_unbounded_or_escaping_selection_rejected(tmp_path, files):
    with pytest.raises(ValueError):
        inspect(str(tmp_path), files, system_id='tool', system_version='v1', scope={'operator_id':'op','purpose':'audit'})


def test_missing_and_invalid_sources_remain_visible(tmp_path):
    (tmp_path/'tool.py').write_text('def invalid(')
    record = snapshot(tmp_path, ['tool.py', 'missing.py'])
    assert [e['state'] for e in record['entries']] == ['MISSING','UNINSPECTABLE']
    assert record['completeness'] == 'PARTIAL'
    assert freshness(record)['state'] == 'REVALIDATION_REQUIRED'


def test_implementation_change_invalidates_inventory(tmp_path):
    (tmp_path/'tool.py').write_text('def old(): pass')
    record = snapshot(tmp_path)
    assert freshness(record)['state'] == 'CURRENT_FOR_SELECTION'
    (tmp_path/'tool.py').write_text('def new(): pass')
    assert freshness(record)['changed_paths'] == ['tool.py']
    record['entries'][0]['sha256'] = 'forged'
    with pytest.raises(ValueError): freshness(record)


def test_inventory_service_requires_exact_approval_and_keeps_history(tmp_path):
    runtime = NS(context=NS(identity=NS(operator_id='operator')))
    service = SystemLayer(tmp_path/'system.sqlite', runtime)
    (tmp_path/'tool.py').write_text('x=1')
    request = {'system_id':'tool','system_version':'v1','root':str(tmp_path),'files':['tool.py'],'purpose':'audit'}
    with pytest.raises(PermissionError): service.inventory(request, {})
    approval = {'operator_id':'operator','action':'STRUCTURAL_INVENTORY','decision':'APPROVE','hash':digest(request)}
    first = service.inventory(request, approval)
    (tmp_path/'tool.py').write_text('x=2')
    second = service.inventory(request, approval)
    assert second['value']['version'] == 2
    assert second['value']['supersedes'] == first['receipt_id']
    assert len(service.store.history('operator')) == 2
    assert service.store.get('operator','tool') is None  # no capability promotion


def model(record):
    value = {'schema_version':'OperationalUnderstanding/1.2','version':1,'supersedes':None,
             'inventory_hash':record['inventory_hash'],
             'definition':{key: ['explicit test definition'] if key in LIST_FIELDS else 'explicit test definition' for key in FIELDS}}
    value['definition'].update(capability_id='tool',system_version='v1')
    value['model_hash'] = digest(value)
    return value


def test_grounded_model_does_not_prove_operation_or_authority(tmp_path):
    (tmp_path/'tool.py').write_text('x=1')
    record = snapshot(tmp_path)
    result = evaluate(model(record), record, current_system_version='v1')
    assert result['state'] == 'STRUCTURALLY_GROUNDED_MODEL'
    assert result['runtime_operability'] == 'UNPROVEN' and result['execution_authority'] == 'NONE'
    assert evaluate(model(record),record,current_system_version='v2')['state']=='REVIEW_REQUIRED'
    (tmp_path/'tool.py').write_text('x=2')
    assert evaluate(model(record),record,current_system_version='v1')['state']=='REVIEW_REQUIRED'


def test_missing_operation_information_is_not_invented(tmp_path):
    (tmp_path/'tool.py').write_text('x=1')
    record = snapshot(tmp_path)
    value = model(record)
    del value['definition']['operation_sequence']
    value['model_hash'] = digest({k:v for k,v in value.items() if k!='model_hash'})
    assert 'UNRESOLVED:operation_sequence' in evaluate(value,record,current_system_version='v1')['reasons']


@pytest.mark.parametrize('change',['missing','duplicate','renamed'])
def test_freshness_cannot_omit_selected_sources_even_with_recomputed_digest(tmp_path,change):
    (tmp_path/'tool.py').write_text('x=1')
    record=snapshot(tmp_path)
    if change=='missing':record['entries']=[]
    elif change=='duplicate':record['entries']*=2
    else:record['entries'][0]['path']='unselected.py'
    record['inventory_hash']=digest({k:v for k,v in record.items() if k!='inventory_hash'})
    with pytest.raises(ValueError,match='exactly one entry'):freshness(record)


def test_whitespace_validation_mechanism_is_unresolved(tmp_path):
    (tmp_path/'tool.py').write_text('x=1')
    record=snapshot(tmp_path);value=model(record)
    value['definition']['validation_mechanism']=' \t '
    value['model_hash']=digest({k:v for k,v in value.items() if k!='model_hash'})
    assert 'UNRESOLVED:validation_mechanism' in evaluate(value,record,current_system_version='v1')['reasons']


def test_operational_model_uses_existing_receipt_chain(tmp_path):
    runtime = NS(context=NS(identity=NS(operator_id='operator')))
    service = SystemLayer(tmp_path/'system.sqlite', runtime)
    (tmp_path/'tool.py').write_text('x=1')
    request = {'system_id':'tool','system_version':'v1','root':str(tmp_path),'files':['tool.py'],'purpose':'audit'}
    approve = lambda action,value: {'operator_id':'operator','action':action,'decision':'APPROVE','hash':digest(value)}
    inv = service.inventory(request, approve('STRUCTURAL_INVENTORY', request))
    value = model(inv['value'])
    with pytest.raises(PermissionError): service.operational_understanding(value, {})
    first = service.operational_understanding(value, approve('OPERATIONAL_UNDERSTANDING', value))
    assert first['value']['assessment']['runtime_operability']=='UNPROVEN'
    value['version']=2
    value['supersedes']=first['receipt_id']
    value['model_hash']=digest({k:v for k,v in value.items() if k!='model_hash'})
    second=service.operational_understanding(value,approve('OPERATIONAL_UNDERSTANDING',value))
    assert second['value']['model']['supersedes']==first['receipt_id']
    assert len(service.store.history('operator'))==3


def test_runtime_command_exposes_inventory_without_execution(tmp_path):
    from system_layer.runtime import command
    runtime = NS(context=NS(identity=NS(operator_id='operator')))
    runtime.system_layer=SystemLayer(tmp_path/'system.sqlite',runtime)
    (tmp_path/'tool.py').write_text('x=1')
    request={'system_id':'tool','system_version':'v1','root':str(tmp_path),'files':['tool.py'],'purpose':'audit'}
    approval={'operator_id':'operator','action':'STRUCTURAL_INVENTORY','decision':'APPROVE','hash':digest(request)}
    receipt=command(runtime,'/system inventory '+json.dumps({'request':request,'approval':approval}))
    assert receipt['value']['execution_authority']=='NONE'


def test_unreadable_source_is_not_omitted(tmp_path, monkeypatch):
    import system_layer.audit.structural_inventory_auditor as inventory
    def denied(*args): raise PermissionError('fixture denial')
    monkeypatch.setattr(inventory,'_read',denied)
    record=snapshot(tmp_path)
    assert record['entries'][0]['state']=='UNINSPECTABLE'
    assert record['entries'][0]['error_type']=='PermissionError'
    assert record['completeness']=='PARTIAL'


def test_v12_identity_adds_law_without_rewriting_v10(tmp_path):
    from tests.test_system_layer import setup
    from system_layer.contracts import SystemIdentity, PRINCIPLES_V12
    manager=setup(tmp_path)
    original=manager.store.get('operator','identity')['value']
    assert 'communication_identity' not in original
    assert SystemIdentity(**original).to_dict()==original
    new=dict(original,schema_version='1.2',governing_principles=list(PRINCIPLES_V12),
        communication_identity={'authority_reference':'synthetic operator decision','version':'1',
                                'baseline_character':'precise and calm'})
    assert SystemIdentity(**new).to_dict()==new
    assert 'Structure Before Description' in new['governing_principles']
    assert manager.store.get('operator','identity')['value']==original
    with pytest.raises(PermissionError):
        manager.identity(new,{'operator_id':'operator','action':'SYSTEM_IDENTITY','decision':'APPROVE','hash':digest(new)})
    new['governing_principles']=original['governing_principles']
    with pytest.raises(ValueError): SystemIdentity(**new)


def test_selected_capability_prompt_exposes_missing_and_stale_inventory(tmp_path):
    from tests.test_system_layer import setup, declare
    from system_layer.runtime import prompt_context,command
    manager=setup(tmp_path)
    declare(manager)
    runtime=manager.runtime
    runtime.system_layer=manager
    command(runtime,'/system context calculator')
    prompt=prompt_context(runtime)
    assert 'NOT_RETRIEVED' in prompt
    (tmp_path/'calculator.py').write_text('def add(a,b): return a+b')
    request={'system_id':'calculator','system_version':'v1','root':str(tmp_path),
             'files':['calculator.py'],'purpose':'inspect calculator'}
    approve={'operator_id':'operator','action':'STRUCTURAL_INVENTORY','decision':'APPROVE','hash':digest(request)}
    manager.inventory(request,approve)
    command(runtime,'/system context calculator')
    assert 'CURRENT_FOR_SELECTION' in prompt_context(runtime)
    (tmp_path/'calculator.py').write_text('def add(a,b): return a-b')
    command(runtime,'/system context calculator')
    prompt=prompt_context(runtime)
    assert 'REVALIDATION_REQUIRED' in prompt and 'UNPROVEN' in prompt


def test_system_context_selection_cannot_substitute_changed_receipt(tmp_path,monkeypatch):
    from tests.test_system_layer import setup,declare
    from system_layer.runtime import command,prompt_context
    manager=setup(tmp_path);declare(manager)
    runtime=manager.runtime;runtime.system_layer=manager
    selected=command(runtime,'/system context calculator')
    original=manager._record('calculator')
    assert selected['selected_receipt_id']==original['receipt_id']
    monkeypatch.setattr(manager,'_record',lambda identity:dict(original,receipt_id='changed'))
    with pytest.raises(PermissionError,match='Selected capability changed'):prompt_context(runtime)
    assert runtime._system_context_selection is None
    runtime._system_context_selection=('thread','calculator',original['receipt_id'])
    def unavailable(identity):raise FileNotFoundError('Unavailable capability')
    monkeypatch.setattr(manager,'_record',unavailable)
    with pytest.raises(FileNotFoundError):command(runtime,'/system context missing')
    assert runtime._system_context_selection is None
