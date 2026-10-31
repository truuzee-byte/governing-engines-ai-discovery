"""Atomic capability snapshots and append-only, hash-linked receipts."""
from contextlib import contextmanager
from copy import deepcopy
from pathlib import Path
import json
import sqlite3
from io import StringIO
from data_governance.custody_json import load as load_custody_json
from ..contracts import digest, now
from .operational_admission import family as operational_family, validate as validate_operational, _Issued

_IDENTITY_WRITER = object()


def _identity_lineage(owner, subject, record, current):
    if subject != 'identity':
        return
    from ..contracts import SystemIdentity, authorize
    from ..creation.service import SystemLayer
    if subject in current or record['action'] != 'SYSTEM_IDENTITY':
        raise PermissionError('Protected identity requires initial governed establishment')
    identity = SystemIdentity(**record['value']).to_dict()
    if identity != record['value']:
        raise PermissionError('Canonical System identity required')
    authorize(owner, 'SYSTEM_IDENTITY', identity, record['authorization'])
    SystemLayer._verify_method(None, identity)


def _material_lineage(owner, subject, record, current):
    """Validate historical binding without upgrading history to fresh authority.

    Receipt hashes establish reconstruction integrity, not external truth. A
    current transition still requires the live, sealed AdmissionDecision below.
    """
    if not subject.startswith('material:'):
        return
    try:
        value = record['value']
        audit = next(r for r in current.values()
                     if r['receipt_id'] == value['admission_receipt'])
        decision = audit['value']
        binding = decision['binding']
        previous = current.get(subject)
        prior = previous['value']['state'] if previous else None
        canonical = {k: v for k, v in decision.items() if k != 'admission_id'}
        valid = (
            audit['subject'] == 'admission:' + decision['admission_id']
            and audit['action'] == 'MATERIAL_ADMISSION_DECISION'
            and decision['admission_id'] == 'material-admission:' + digest(canonical)
            and decision['binding_hash'] == digest(binding)
            and decision['accepted'] is True and decision['decision'] == 'APPLY'
            and decision['rp_verdict'] == decision['rp_state'] == 'CONFIRMED'
            and decision['external_receipt_id'] and decision['external_chain_id']
            and decision['external_transition_id']
            and subject == 'material:' + binding['object_id']
            and binding['scope']['operator_id'] == owner
            and binding['prior_state'] == decision['prior_state'] == prior
            and value == dict(object_type=binding['object_type'],
                state=binding['candidate_state'], scope=binding['scope'],
                epistemic_state=binding['epistemic_state'], rp_state='CONFIRMED',
                admission_receipt=audit['receipt_id'])
            and decision['resulting_state'] == binding['candidate_state']
            and binding['epistemic_state'] == 'ESTABLISHED'
            and record['action'] == 'MATERIAL_STATE_APPLIED'
            and audit['receipt_id'] in record['references'])
        if not valid:
            raise ValueError('Invalid binding')
    except (KeyError, TypeError, StopIteration, ValueError) as exc:
        raise ValueError('System Layer material admission lineage failure') from exc


class SystemStore:
    @staticmethod
    def snapshot(path, owner):
        """Verified owned heads; read-only SQLite, no creation or write transaction.

        Hash integrity establishes recorded custody, never independent truth.
        """
        path = Path(path)
        if not owner: raise PermissionError('Owner required')
        if not path.is_file(): return {}
        current = {}; prior = ''
        with sqlite3.connect(path.resolve().as_uri()+'?mode=ro', uri=True) as db:
            for subject, payload, previous, checksum in db.execute(
                    'SELECT subject,payload,previous,hash FROM events WHERE owner=? ORDER BY seq', (owner,)):
                record = load_custody_json(StringIO(payload))
                fields = {'subject','value','action','previous_receipt','previous_value','authorization',
                          'references','timestamp','governed_metadata','receipt_id'}
                if operational_family(subject): fields.add('operational_admission')
                before = current.get(subject,{})
                if (previous != prior or checksum != digest([owner,subject,record,prior]) or
                        set(record) != fields or record['subject'] != subject or
                        record['receipt_id'] != 'system-receipt:'+digest({k:v for k,v in record.items() if k!='receipt_id'}) or
                        record['previous_receipt'] != before.get('receipt_id') or record['previous_value'] != before.get('value')):
                    raise ValueError('System Layer read-only receipt integrity failure')
                _material_lineage(owner,subject,record,current)
                _identity_lineage(owner,subject,record,current)
                validate_operational(owner,record,current)
                if record['action'] == 'CAPABILITY_EVIDENCE_RECORDED':
                    from ..capability_inspection import validate_record
                    validate_record(owner,record)
                current[subject] = record; prior = checksum
        return deepcopy(current)

    def __init__(self, path):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with sqlite3.connect(self.path) as connection:
            connection.execute('CREATE TABLE IF NOT EXISTS events (seq INTEGER PRIMARY KEY, owner TEXT, subject TEXT, payload TEXT, previous TEXT, hash TEXT)')

    @contextmanager
    def transaction(self, owner):
        if not owner:
            raise ValueError('Owner required')
        connection = sqlite3.connect(self.path, timeout=15)
        try:
            connection.execute('BEGIN IMMEDIATE')
            history, current, prior = [], {}, ''
            for subject, payload, previous, checksum in connection.execute(
                    'SELECT subject,payload,previous,hash FROM events WHERE owner=? ORDER BY seq', (owner,)):
                record = load_custody_json(StringIO(payload))
                if previous != prior or checksum != digest([owner, subject, record, prior]):
                    raise ValueError('System Layer history integrity failure')
                fields={'subject','value','action','previous_receipt','previous_value','authorization',
                        'references','timestamp','governed_metadata','receipt_id'}
                if operational_family(subject):fields.add('operational_admission')
                prior_subject=current.get(subject,{})
                if (type(record) is not dict or set(record)!=fields or record['subject']!=subject
                        or record['receipt_id']!='system-receipt:'+digest({k:v for k,v in record.items() if k!='receipt_id'})
                        or record['previous_receipt']!=prior_subject.get('receipt_id')
                        or record['previous_value']!=prior_subject.get('value')):
                    raise ValueError('System Layer receipt lineage integrity failure')
                _material_lineage(owner, subject, record, current)
                _identity_lineage(owner, subject, record, current)
                validate_operational(owner,record,current)
                if record['action'] == 'CAPABILITY_EVIDENCE_RECORDED':
                    from ..capability_inspection import validate_record
                    validate_record(owner,record)
                current[subject] = record
                history.append(record)
                prior = checksum
            identity_established = 'identity' in current
            def append(subject, value, action, authorization, references=(), *, material_decision=None, identity_admission=None, operational_admission=None):
                nonlocal prior, identity_established
                if operational_family(subject) and not isinstance(operational_admission,_Issued):
                    raise PermissionError('Operational import requires governed service admission')
                if subject == 'identity' and identity_admission is not _IDENTITY_WRITER:
                    raise PermissionError('Identity import must use governed System identity establishment')
                if subject == 'identity' and identity_established:
                    raise PermissionError('Protected identity is immutable')
                if subject.startswith('admission:'):
                    from data_governance.material_admission import AdmissionDecision
                    if not isinstance(value, AdmissionDecision):
                        raise PermissionError('Admission namespace requires a sealed gate decision')
                    value.verify()
                    if (subject != 'admission:' + value['admission_id'] or
                            action != 'MATERIAL_ADMISSION_DECISION' or
                            value['binding']['scope'].get('operator_id') != owner):
                        raise PermissionError('Admission record differs from gate decision')
                if subject.startswith('material:'):
                    from data_governance.material_admission import AdmissionDecision
                    from datetime import datetime, timezone
                    if not isinstance(material_decision, AdmissionDecision):
                        raise PermissionError('Material namespace requires external RP admission')
                    d = material_decision.verify()
                    binding = d['binding']
                    before = current.get(subject)
                    prior_state = before['value']['state'] if before else None
                    if (not d['accepted'] or d['decision'] != 'APPLY' or
                            action != 'MATERIAL_STATE_APPLIED' or
                            subject != 'material:' + d['object_id'] or
                            binding['scope'].get('operator_id') != owner or
                            value['state'] != d['resulting_state'] or
                            value['object_type'] != binding['object_type'] or
                            value['scope'] != binding['scope'] or
                            value['epistemic_state'] != binding['epistemic_state'] or
                            value['rp_state'] != d['rp_verdict'] or
                            prior_state != d['prior_state']):
                        raise PermissionError('Material write differs from admitted transition')
                    if datetime.fromisoformat(d['external_acceptance']['authority_valid_until']) < datetime.now(timezone.utc):
                        raise PermissionError('RP expired before material write')
                    audit = current.get('admission:' + d['admission_id'])
                    if not audit or audit['value'] != d or value['admission_receipt'] != audit['receipt_id']:
                        raise PermissionError('Material write lacks its persisted admission receipt')
                from data_governance.artifact_metadata import GovernedArtifactMetadata
                metadata = GovernedArtifactMetadata(subject, owner,
                    tuple(references) or ('SystemLayer/1:' + action,), action, 'SystemLayer',
                    'RUNTIME_DATA', 'NOT_REQUIRED', 'APPROVED', 'NOT_APPLICABLE', 'AUDIT_ONLY',
                    'ACTIVE', tuple(references)).to_dict()
                metadata = json.loads(json.dumps(metadata))
                from ..receipts import create_receipt
                record = deepcopy(create_receipt(subject, value, action, authorization,
                    current.get(subject, {}), references, metadata))
                if operational_family(subject):
                    record['operational_admission']=operational_admission.verify()
                    record['receipt_id']='system-receipt:'+digest({k:v for k,v in record.items() if k!='receipt_id'})
                    validate_operational(owner,record,current,live=True)
                _material_lineage(owner, subject, record, current)
                _identity_lineage(owner, subject, record, current)
                if record['action'] == 'CAPABILITY_EVIDENCE_RECORDED':
                    from ..capability_inspection import validate_record
                    validate_record(owner,record)
                checksum = digest([owner, subject, record, prior])
                connection.execute('INSERT INTO events(owner,subject,payload,previous,hash) VALUES(?,?,?,?,?)',
                    (owner, subject, json.dumps(record, sort_keys=True), prior, checksum))
                prior = checksum
                current[subject] = record
                history.append(record)
                if subject == 'identity':
                    identity_established = True
                return deepcopy(record)
            yield deepcopy(current), deepcopy(history), append
            connection.commit()
        except Exception:
            connection.rollback()
            raise
        finally:
            connection.close()

    def get(self, owner, subject):
        with self.transaction(owner) as (current, _, __):
            return current.get(subject)

    def history(self, owner):
        with self.transaction(owner) as (_, history, __):
            return history
