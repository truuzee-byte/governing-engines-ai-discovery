"""Operational import contamination at the normal System store/runtime boundary."""
import json
import sqlite3
from copy import deepcopy
from types import SimpleNamespace as NS
import pytest
from system_layer.service import SystemLayer
from system_layer.state.store import SystemStore
from system_layer.contracts import digest


@pytest.mark.parametrize('subject',['inventory:tool','operational-understanding:tool','operational-sources:tool'])
def test_exact_generic_import_reproduction(tmp_path,subject):
    runtime=NS(context=NS(identity=NS(operator_id='operator')))
    manager=SystemLayer(tmp_path/'system.db',runtime)
    with pytest.raises(PermissionError):
        with manager.store.transaction('operator') as (_,__,append):
            append(subject,{'operational_state':'OPERATIONAL','execution_authority':True},'LEGACY_IMPORT',{})
    assert manager.store.history('operator')==[]


def approve(action,value,owner='operator'):
    return dict(operator_id=owner,action=action,decision='APPROVE',hash=digest(value))


def governed(tmp_path, runtime=None):
    from system_layer.audit.operational_understanding_validator import FIELDS,LIST_FIELDS
    runtime=runtime or NS(context=NS(identity=NS(operator_id='operator')))
    underlying=getattr(getattr(runtime,'understanding_engine',None),'store',None)
    path=underlying.path.with_name('system_layer.sqlite3') if underlying else tmp_path/'system.db'
    manager=SystemLayer(path,runtime);runtime.system_layer=manager
    (tmp_path/'tool.py').write_text('def run(): return 1')
    owner=manager.owner
    request=dict(system_id='tool',system_version='1',root=str(tmp_path),files=['tool.py'],purpose='bounded inspection')
    inv=manager.inventory(request,approve('STRUCTURAL_INVENTORY',request,owner))
    model=dict(schema_version='OperationalUnderstanding/1.2',version=1,supersedes=None,
        inventory_hash=inv['value']['inventory_hash'],definition={k:['declared condition'] if k in LIST_FIELDS else 'declared condition' for k in FIELDS})
    model['definition'].update(capability_id='tool',system_version='1',operation_sequence=['Run'])
    model['model_hash']=digest(model)
    mdl=manager.operational_understanding(model,approve('OPERATIONAL_UNDERSTANDING',model,owner))
    request=dict(system_id='tool',model_receipt=mdl['receipt_id'],inventory_receipt=inv['receipt_id'],
        bindings=[dict(step_index=0,source_path='tool.py',source_sha256=inv['value']['entries'][0]['sha256'],symbol_kind='PYTHON_FUNCTION',symbol='run')])
    src=manager.operational_sources(request,approve('OPERATIONAL_SOURCES',request,owner))
    discovery=dict(system_id='tool',root=str(tmp_path),extensions=['.py'],limit=5,purpose='bounded discovery')
    discovered=manager.discover_sources(discovery,approve('STRUCTURAL_SOURCE_DISCOVERY',discovery,owner))
    return manager,{'inventory:tool':inv,'operational-understanding:tool':mdl,
        'operational-sources:tool':src,'source-discovery:tool':discovered}


FORGERIES=['capability_exists','capability_available','ready','healthy','provider_available','tool_available',
    'subsystem_registered','system_id','version','provider_binding','capability','provenance','owner',
    'authority','execution_authority']


@pytest.mark.parametrize('subject',['inventory:tool','operational-understanding:tool','operational-sources:tool','source-discovery:tool'])
@pytest.mark.parametrize('claim',FORGERIES)
def test_imported_operational_claims_cannot_reach_normal_status(tmp_path,subject,claim):
    from system_layer.runtime import command
    manager,records=governed(tmp_path);before=manager.store.history('operator')
    forged=deepcopy(records[subject]['value']);forged[claim]='FORGED_AVAILABLE_AUTHORITY'
    with pytest.raises(PermissionError):
        with manager.store.transaction('operator') as (_,__,append):
            append(subject,forged,records[subject]['action'],records[subject]['authorization'])
    manager.store=SystemStore(manager.store.path)
    assert manager.store.history('operator')==before
    assert command(manager.runtime,'/system show '+subject)==records[subject]
    assert 'FORGED_AVAILABLE_AUTHORITY' not in str(command(manager.runtime,'/system show '+subject))


@pytest.mark.parametrize('subject',['inventory:tool','operational-understanding:tool','operational-sources:tool','source-discovery:tool'])
@pytest.mark.parametrize('mutation',['value','provenance','owner','missing'])
def test_rehashed_import_fails_hydration_before_consumer(tmp_path,subject,mutation):
    from system_layer.runtime import command
    manager,records=governed(tmp_path)
    with sqlite3.connect(manager.store.path) as db:
        rows=db.execute('SELECT seq,subject,payload FROM events ORDER BY seq').fetchall();previous=''
        for seq,name,payload in rows:
            record=json.loads(payload)
            if name==subject:
                if mutation=='value':record['value']['execution_authority']=True
                elif mutation=='provenance':record['operational_admission']['request']={}
                elif mutation=='owner':record['operational_admission']['owner']='other'
                else:record.pop('operational_admission')
                record['receipt_id']='system-receipt:'+digest({k:v for k,v in record.items() if k!='receipt_id'})
            checksum=digest(['operator',name,record,previous])
            db.execute('UPDATE events SET payload=?,previous=?,hash=? WHERE seq=?',(json.dumps(record),previous,checksum,seq));previous=checksum
    manager.store=SystemStore(manager.store.path)
    with pytest.raises((ValueError,PermissionError)):
        command(manager.runtime,'/system show '+subject)


def test_legitimate_restart_and_runtime_drift_remain_nonoperational(tmp_path):
    from system_layer.audit.structural_inventory_auditor import freshness
    from system_layer.audit.operational_understanding_validator import evaluate
    from system_layer.audit.operation_source_binding import assess
    manager,records=governed(tmp_path);manager.store=SystemStore(manager.store.path)
    inv=manager.store.get('operator','inventory:tool')['value']
    model=manager.store.get('operator','operational-understanding:tool')['value']['model']
    src=manager.store.get('operator','operational-sources:tool')['value']
    assert freshness(inv)['state']=='CURRENT_FOR_SELECTION'
    assert evaluate(model,inv,current_system_version='1')['runtime_operability']=='UNPROVEN'
    (tmp_path/'tool.py').write_text('def unavailable(): pass')
    assert freshness(inv)['state']=='REVALIDATION_REQUIRED'
    assert evaluate(model,inv,current_system_version='1')['state']=='REVIEW_REQUIRED'
    assert assess(model,inv,src['bindings'])['state']=='REVIEW_REQUIRED'
    assert manager.store.get('operator','tool') is None  # no capability registration


def test_model_provider_claim_and_wrong_version_are_only_declarations(tmp_path):
    from system_layer.audit.operational_understanding_validator import evaluate
    manager,records=governed(tmp_path)
    model=deepcopy(records['operational-understanding:tool']['value']['model'])
    model.update(version=2,supersedes=records['operational-understanding:tool']['receipt_id'])
    model['definition'].update(system_version='nonexistent',tools=['UNAVAILABLE_PROVIDER'],capability_status='READY',operational_state='AVAILABLE')
    model['model_hash']=digest({k:v for k,v in model.items() if k!='model_hash'})
    stored=manager.operational_understanding(model,approve('OPERATIONAL_UNDERSTANDING',model))
    assert stored['value']['assessment']['state']=='REVIEW_REQUIRED'
    assert stored['value']['assessment']['runtime_operability']=='UNPROVEN'
    assert stored['value']['assessment']['execution_authority']=='NONE'
    assert not hasattr(manager.runtime,'model_provider')


def test_serialized_admission_and_mutated_transaction_view_cannot_issue_authority(tmp_path):
    manager,records=governed(tmp_path);before=manager.store.history('operator')
    record=records['inventory:tool']
    with pytest.raises(PermissionError):
        with manager.store.transaction('operator') as (current,history,append):
            current['inventory:tool']['value']['operational_state']='OPERATIONAL';history.clear()
            append('inventory:tool',record['value'],record['action'],record['authorization'],
                operational_admission=record['operational_admission'])
    assert manager.store.history('operator')==before


@pytest.mark.parametrize('field',['system_id','model_receipt','inventory_receipt'])
def test_source_substitution_rejected_atomically(tmp_path,field):
    manager,records=governed(tmp_path);before=manager.store.history('operator')
    request=deepcopy(records['operational-sources:tool']['operational_admission']['request']);request[field]='unrelated'
    with pytest.raises((ValueError,PermissionError)):
        manager.operational_sources(request,approve('OPERATIONAL_SOURCES',request))
    assert manager.store.history('operator')==before


@pytest.mark.parametrize('subject',['inventory:tool','operational-understanding:tool','operational-sources:tool'])
def test_normal_boot_restart_query_excludes_import_contamination(tmp_path,monkeypatch,subject):
    from interactive_mode_ai import ModeRuntime
    from mode_operator.operator_identity import OperatorIdentity
    from mode_operator.operator_store import OperatorStore
    from memory.thread_store import ThreadStore
    from system_layer.runtime import command
    from tests.test_system_layer import setup,declare,capability
    from dataclasses import replace
    monkeypatch.chdir(tmp_path)
    operators=OperatorStore(str(tmp_path/'operators'));identity=OperatorIdentity.create('operator')
    profile=operators.create_profile(identity)
    profile.update_operator_managed_info(preferred_name='Operator',timezone='UTC',language='English')
    thread=ThreadStore(str(tmp_path/'threads')).create_thread('operator');profile.active_thread_id=thread.thread_id
    operators.save_profile(identity,profile)
    def boot():
        runtime=ModeRuntime('operator',str(tmp_path/'operators'),str(tmp_path/'threads'));runtime.boot();return runtime
    runtime=boot()
    try:
        manager,records=governed(tmp_path,runtime)
        template_path=tmp_path/'template';template_path.mkdir()
        template=setup(template_path,runtime_profile='PUBLIC').store.get('operator','identity')['value']
        manager.identity(template,approve('SYSTEM_IDENTITY',template))
        declare(manager,replace(capability(),capability_id='tool'))
        before=manager.store.history('operator')
        forged=deepcopy(records[subject]['value']);forged['operational_state']='FORGED_PIPELINE_PROVIDER_READY'
        with pytest.raises(PermissionError):
            with manager.store.transaction('operator') as (_,__,append):append(subject,forged,'LEGACY_IMPORT',{})
        assert manager.store.history('operator')==before
    finally:runtime.shutdown()
    runtime=boot()
    try:
        command(runtime,'/system context tool')
        prompt=runtime._build_engine_input('Describe the declared tool and its current evidence limits.')
        assert 'FORGED_PIPELINE_PROVIDER_READY' not in str(prompt)
        assert 'UNPROVEN' in str(prompt) and 'grants_execution_authority' in str(prompt)
        assert runtime.handle_build_request('Is Pipeline available?') is None
        with pytest.raises(PermissionError):runtime.system_layer.require_internal_execution()
        assert command(runtime,'/system show '+subject)==records[subject]
        assert 'FORGED_PIPELINE_PROVIDER_READY' not in str(runtime._build_engine_input('Explain the evidence limits again.'))
    finally:runtime.shutdown()
