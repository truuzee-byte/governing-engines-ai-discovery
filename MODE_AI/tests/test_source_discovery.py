import pytest
from system_layer.audit.source_discovery import discover
from system_layer.audit.structural_inventory_auditor import inspect


def test_discovery_preserves_partial_selection_then_exact_inventory(tmp_path):
    (tmp_path/'module').mkdir()
    (tmp_path/'module'/'a.py').write_text("raise RuntimeError('must not import')\ndef available(): pass\n")
    (tmp_path/'module'/'b.h').write_text('class Actor {};')
    (tmp_path/'ignored.txt').write_text('not selected')
    result=discover(str(tmp_path),['.py','.h'],1)
    assert result['state']=='PARTIAL' and result['results_limited']
    assert result['discovered_matches_in_window']==2 and not result['source_contents_read']
    paths=[entry['path'] for entry in result['files']]
    inventory=inspect(str(tmp_path),paths,system_id='s',system_version='1',scope={'operator_id':'op','purpose':'source review'})
    assert inventory['entries'][0]['sha256'] is not None
    assert result['files'][0]['sha256'] is None and not result['execution_authority']


def test_discovery_requires_bounded_explicit_selection(tmp_path):
    with pytest.raises(ValueError):discover(str(tmp_path),['*'],1)
    with pytest.raises(ValueError):discover(str(tmp_path),['.py'],True)
    assert discover(str(tmp_path),['.py'],4)['files']==[]


def test_discovery_receipt_uses_existing_system_store_and_exact_scope(tmp_path):
    from types import SimpleNamespace as NS
    from system_layer.service import SystemLayer
    from system_layer.contracts import digest
    service=SystemLayer(tmp_path/'system.db',NS(context=NS(identity=NS(operator_id='op'))))
    request=dict(system_id='tool',root=str(tmp_path),extensions=['.py'],limit=10,purpose='Locate tool source')
    with pytest.raises(PermissionError):service.discover_sources(request,{})
    approval=dict(operator_id='op',action='STRUCTURAL_SOURCE_DISCOVERY',decision='APPROVE',hash=digest(request))
    record=service.discover_sources(request,approval);value=record['value']
    assert value['discovery_hash']==digest({k:v for k,v in value.items() if k!='discovery_hash'})
    assert service.store.get('op','inventory:tool') is None
    assert service.store.get('op','source-discovery:tool')['receipt_id']==record['receipt_id']
