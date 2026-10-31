"""Pressure tests for common admission storage and historical reconstruction."""
import json
import sqlite3
from copy import deepcopy

import pytest

from system_layer.contracts import digest
from tests.test_material_admission import proposal, external, manager, apply


@pytest.mark.parametrize('state', ['CONFIRMED', 'SUCCESS', 'READY', 'COMPLETE',
                                  'PENDING_VALIDATION', 'DISCONFIRMED'])
def test_plain_dictionary_cannot_issue_an_admission(tmp_path, state):
    m, _ = manager(tmp_path)
    with pytest.raises(PermissionError, match='sealed gate decision'):
        with m.store.transaction('operator') as (_, __, append):
            append('admission:forged', {'rp_state': state, 'accepted': True},
                   'MATERIAL_ADMISSION_DECISION', {})
    assert m.store.history('operator') == []


def rewrite_last(db_path, change):
    """Simulate a restore/import with internally recomputed receipt hashes."""
    with sqlite3.connect(db_path) as db:
        seq, owner, subject, payload, previous = db.execute(
            'SELECT seq,owner,subject,payload,previous FROM events ORDER BY seq DESC LIMIT 1').fetchone()
        record = json.loads(payload)
        change(record)
        record['receipt_id'] = 'system-receipt:' + digest(
            {k: v for k, v in record.items() if k != 'receipt_id'})
        db.execute('UPDATE events SET payload=?,hash=? WHERE seq=?',
                   (json.dumps(record), digest([owner, subject, record, previous]), seq))


@pytest.mark.parametrize('field,value', [
    ('state', {'location': 'invented'}), ('scope', {'operator_id': 'someone-else'}),
    ('object_type', 'DifferentClaim'), ('epistemic_state', 'PROPOSED'),
    ('rp_state', 'DISCONFIRMED'), ('admission_receipt', 'unbound'),
])
def test_rehashed_import_cannot_change_admitted_state(tmp_path, field, value):
    p = proposal(); client, request = external(tmp_path, p)
    m, _ = manager(tmp_path, client)
    assert apply(m, p, request)['applied']
    rewrite_last(m.store.path, lambda record: record['value'].__setitem__(field, value))
    with pytest.raises(ValueError, match='material admission lineage'):
        m.store.get('operator', 'material:object:1')


def test_forged_receipt_rolls_back_preceding_bookkeeping(tmp_path):
    m, _ = manager(tmp_path)
    with pytest.raises(PermissionError):
        with m.store.transaction('operator') as (_, __, append):
            append('bookkeeping', {'counter': 1}, 'COUNT', {})
            append('admission:forged', {}, 'MATERIAL_ADMISSION_DECISION', {})
    assert m.store.history('operator') == []


def test_non_claim_bookkeeping_remains_available(tmp_path):
    m, _ = manager(tmp_path)
    with m.store.transaction('operator') as (_, __, append):
        expected = append('bookkeeping', {'counter': 1}, 'COUNT', {})
    assert m.store.get('operator', 'bookkeeping') == expected


def test_gate_issued_admission_cannot_be_serialized_and_reissued(tmp_path):
    from data_governance.material_admission import MaterialAdmissionGate
    decision = MaterialAdmissionGate().evaluate(proposal())
    m, _ = manager(tmp_path)
    with pytest.raises(PermissionError, match='sealed gate decision'):
        with m.store.transaction('operator') as (_, __, append):
            append('admission:' + decision['admission_id'], json.loads(json.dumps(decision)),
                   'MATERIAL_ADMISSION_DECISION', {})


def test_successful_bound_admission_survives_restart(tmp_path):
    p = proposal(); client, request = external(tmp_path, p)
    m, _ = manager(tmp_path, client)
    result = apply(m, p, request)
    restarted, _ = manager(tmp_path)
    assert restarted.store.get('operator', 'material:object:1') == result['object']
