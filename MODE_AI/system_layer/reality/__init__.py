"""Verify external findings; no capability adjudication inside Mode."""
import base64
from copy import deepcopy
from datetime import datetime, timezone
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey
from integration.reality_primacy import RealityAcceptanceClient
from ..contracts import digest


class CapabilityRealityClient:
    def __init__(self, transport, public_keys, clock=None):
        self.transport = transport
        self.keys = dict(public_keys)
        self.clock = clock or (lambda: datetime.now(timezone.utc))
        self.used = set()

    def verify_recorded(self, capability, result):
        """Recheck signed custody, exact declaration and freshness on reuse.

        A dictionary restored from storage is not an authenticated finding.
        Verification does not call RP or upgrade/renew the retained verdict.
        """
        result = deepcopy(result)
        reply = result['finding']
        body = reply['body']
        Ed25519PublicKey.from_public_bytes(self.keys[reply['key_id']]).verify(
            base64.b64decode(reply['signature'], validate=True), bytes.fromhex(digest(body)))
        request = result['acceptance']['request']
        outer = {'audit_id': body['audit_id'], 'capability_id': capability.capability_id,
            'capability_hash': digest(capability.declaration()), 'transition': request}
        if (body['contract'] != 'RPCapabilityFinding/1' or body['request_hash'] != digest(outer)
                or body['capability_hash'] != outer['capability_hash']
                or body['capability_id'] != capability.capability_id
                or body['scope'] != request['scope']
                or any(body['scope'].get(k) != v for k, v in capability.scope.items())):
            raise PermissionError('Recorded capability finding binding mismatch')
        stamp = self.clock()
        if isinstance(stamp, str): stamp = datetime.fromisoformat(stamp)
        start, end = (datetime.fromisoformat(body[k]) for k in ('evaluated_at', 'valid_until'))
        if start.tzinfo is None or end.tzinfo is None or not start <= stamp <= end:
            raise PermissionError('Recorded capability finding expired')
        accepted = RealityAcceptanceClient(None, self.keys, clock=self.clock).verify_response(
            request, body['canonical_response'])
        if any(body[k] != accepted[k] for k in ('rp_state', 'decision_id', 'chain_id', 'receipt_id')):
            raise PermissionError('Recorded finding differs from canonical RP decision')
        return {'finding': reply, 'acceptance': accepted}

    def audit(self, capability, transition, audit_id):
        if audit_id in self.used:
            raise PermissionError('Audit already consumed')
        self.used.add(audit_id)
        captured = {}
        def evaluate(request):
            outer = {'audit_id': audit_id, 'capability_id': capability.capability_id,
                'capability_hash': digest(capability.declaration()), 'transition': request}
            reply = deepcopy(self.transport(outer))
            body = reply['body']
            Ed25519PublicKey.from_public_bytes(self.keys[reply['key_id']]).verify(
                base64.b64decode(reply['signature'], validate=True), bytes.fromhex(digest(body)))
            if (body['contract'] != 'RPCapabilityFinding/1' or body['request_hash'] != digest(outer)
                    or body['capability_hash'] != outer['capability_hash']
                    or body['capability_id'] != capability.capability_id or body['audit_id'] != audit_id
                    or body['scope'] != request['scope']):
                raise PermissionError('External capability finding binding mismatch')
            if any(body['scope'].get(k) != v for k, v in capability.scope.items()):
                raise PermissionError('Capability finding scope mismatch')
            now = self.clock()
            if isinstance(now, str): now = datetime.fromisoformat(now)
            start, end = (datetime.fromisoformat(body[k]) for k in ('evaluated_at', 'valid_until'))
            if start.tzinfo is None or end.tzinfo is None or not start <= now <= end:
                raise PermissionError('Capability finding expired')
            if body['finding'] not in {'IMPLEMENTED', 'INTEGRATED', 'VALIDATED', 'OPERATIONAL',
                    'DEGRADED', 'FAILED', 'NOT_IMPLEMENTED', 'UNCONFIRMED', 'DISABLED', 'DEPRECATED', 'SUPERSEDED'}:
                raise PermissionError('Unknown capability finding')
            captured.update(reply=reply)
            return body['canonical_response']
        accepted = RealityAcceptanceClient(evaluate, self.keys, clock=self.clock).evaluate(transition)
        if accepted.get('rp_state') is None:
            raise PermissionError(accepted['reason'])
        body = captured['reply']['body']
        if any(body[k] != accepted[k] for k in ('rp_state', 'decision_id', 'chain_id', 'receipt_id')):
            raise PermissionError('Finding differs from canonical RP decision')
        if body['rp_state'] != 'CONFIRMED' and body['finding'] in {'IMPLEMENTED', 'INTEGRATED', 'VALIDATED', 'OPERATIONAL'}:
            raise PermissionError('Unconfirmed finding cannot strengthen capability')
        return {'finding': captured['reply'], 'acceptance': accepted}
