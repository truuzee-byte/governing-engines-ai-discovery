"""Persisted operational labels cannot replace signed external dependency proof."""
from copy import deepcopy
from dataclasses import replace
from datetime import datetime, timezone, timedelta
from types import SimpleNamespace as NS
import pytest

from tests.test_system_layer import capability, external
from system_layer.creation.service import SystemLayer
from system_layer.reality import CapabilityRealityClient


def layer(tmp_path, client=None):
    return SystemLayer(tmp_path/'system.sqlite',
        NS(context=NS(identity=NS(operator_id='operator'))), client)


def store(m, value):
    with m.store.transaction('operator') as (_, __, append):
        return append('calculator', value, 'CAPABILITY_REGISTRATION', {})


def test_unsigned_dependency_cannot_satisfy_runtime_predicate(tmp_path):
    m = layer(tmp_path)
    store(m, {'control':'ACTIVE', 'capability':{'operational_state':'OPERATIONAL'},
        'reality':{'finding':{'body':{'rp_state':'CONFIRMED',
            'valid_until':(datetime.now(timezone.utc)+timedelta(minutes=5)).isoformat()}}}})
    assert not m._dependencies_current(NS(dependencies=['calculator']))


@pytest.mark.parametrize('observed,expected', [(True, True), (False, False), (None, False)])
def test_external_dependency_verdict_preserved_after_storage(tmp_path, observed, expected):
    cap = capability()
    request, endpoint, keys = external(tmp_path, cap, observed=observed)
    client = CapabilityRealityClient(endpoint.evaluate, keys)
    result = client.audit(cap, request, 'audit-dependency')
    m = layer(tmp_path, client)
    record = store(m, {'control':'ACTIVE', 'capability':replace(cap, operational_state='OPERATIONAL').to_dict(),
                      'reality':result})
    assert m._operational_current(record) is expected
    assert m._dependencies_current(NS(dependencies=['calculator'])) is expected


@pytest.mark.parametrize('tamper', ['signature', 'version', 'scope', 'claim', 'expired', 'finding'])
def test_retained_dependency_proof_cannot_be_substituted(tmp_path, tamper):
    cap = capability()
    request, endpoint, keys = external(tmp_path, cap)
    client = CapabilityRealityClient(endpoint.evaluate, keys)
    result = client.audit(cap, request, 'audit-dependency')
    value = {'control':'ACTIVE', 'capability':replace(cap, operational_state='OPERATIONAL').to_dict(),
             'reality':deepcopy(result)}
    if tamper == 'signature': value['reality']['finding']['signature'] = 'invalid'
    elif tamper == 'version': value['capability']['version'] += 1
    elif tamper == 'scope': value['capability']['scope']['deployment'] = 'other'
    elif tamper == 'claim': value['reality']['acceptance']['request']['claim_id'] = 'other'
    elif tamper == 'finding': value['reality']['finding']['body']['finding'] = 'IMPLEMENTED'
    elif tamper == 'expired': client.clock = lambda: datetime.now(timezone.utc)+timedelta(days=1)
    m = layer(tmp_path, client)
    record = store(m, value)
    assert not m._operational_current(record)
    assert not m._dependencies_current(NS(dependencies=['calculator']))


@pytest.mark.parametrize('tamper', ['signature', 'version', 'attempt', 'dimension', 'target', 'pending'])
def test_imported_validation_cannot_promote_registration(tmp_path, tamper):
    from tests.test_system_layer import validated, approval
    m, original = validated(tmp_path)
    value = deepcopy(original['value'])
    if tamper == 'signature': value['validations']['operational']['finding']['signature'] = 'invalid'
    elif tamper == 'version': value['capability']['version'] += 1
    elif tamper == 'attempt': value['build_outcome']['build']['build_id'] = 'substituted-attempt'
    elif tamper == 'dimension': value['validations']['dependency'] = deepcopy(value['validations']['functional'])
    elif tamper == 'target': value['target_state'] = 'DISABLED'
    elif tamper == 'pending': value['validations']['operational']['finding']['body']['rp_state'] = 'PENDING_VALIDATION'
    forged = store(m, value)
    before = m.store.history('operator')
    with pytest.raises(Exception):
        m.accept('calculator', forged['receipt_id'], approval('operator', 'OPERATOR_ACCEPTANCE',
            {'capability_receipt':forged['receipt_id']}))
    assert m.store.history('operator') == before
    assert m.store.get('operator', 'calculator')['value']['capability']['operational_state'] != 'OPERATIONAL'
