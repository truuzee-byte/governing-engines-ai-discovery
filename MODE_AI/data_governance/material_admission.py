"""Consumer-side material admission; external RP alone adjudicates evidence.

This module binds an existing canonical external decision to one exact proposed
mutation. It does not resolve evidence, run validators, or issue RP receipts.
Local admission receipts refer to the external decision/chain/receipt unchanged.
"""
from copy import deepcopy
from dataclasses import dataclass
from datetime import datetime, timezone

from integration.reality_primacy import RealityAcceptanceClient, digest


EPISTEMIC_STATES = frozenset({'ESTABLISHED', 'INFERRED', 'UNKNOWN', 'CONFLICTED', 'PROPOSED'})
TRANSITION_CLASSES = frozenset({
    'CLAIM_ADMISSION', 'OBJECT_STATE', 'UNDERSTANDING', 'MEMORY_ADMISSION',
    'KNOWLEDGE_ADMISSION', 'STORY_STATE', 'CINEMATIC_STATE', 'SPECIFICATION',
    'EXECUTION_READINESS', 'EXECUTION_AUTHORIZATION', 'ARTIFACT_ACCEPTANCE',
    'CAPABILITY_STATE', 'SYSTEM_STATE', 'LEARNING_UPDATE', 'REVALIDATION', 'ROLLBACK',
})
_SEAL = object()


class AdmissionDecision(dict):
    """In-process integrity capability, not a replacement for Kernel isolation."""
    def __init__(self, value, seal=None):
        if seal is not _SEAL:
            raise PermissionError('Admission decision must be issued by the gate')
        super().__init__(deepcopy(value))
        self._issued_hash = digest(value)

    def verify(self):
        if digest(self) != self._issued_hash:
            raise PermissionError('Admission decision changed after evaluation')
        return self


@dataclass(frozen=True)
class MaterialProposal:
    object_id: str
    object_type: str
    claim_id: str
    claim_text: str
    transition_class: str
    scope: dict
    source: dict
    authority: dict
    prior_state: object
    candidate_state: object
    epistemic_state: str
    preconditions: dict

    def binding(self):
        # Round-trip copies keep a caller mutation from altering the evaluated
        # binding. Finite canonical JSON validation is supplied by digest.
        from dataclasses import asdict
        value = asdict(self)
        digest(value)
        return value

    def validate(self):
        for name in ('object_id', 'object_type', 'claim_id', 'claim_text'):
            if type(getattr(self, name)) is not str or not getattr(self, name).strip():
                raise ValueError('MISSING_' + name.upper())
        if self.transition_class not in TRANSITION_CLASSES:
            raise ValueError('UNKNOWN_TRANSITION_CLASS')
        if self.epistemic_state not in EPISTEMIC_STATES:
            raise ValueError('UNKNOWN_EPISTEMIC_STATE')
        if type(self.scope) is not dict or not self.scope.get('operator_id'):
            raise ValueError('MISSING_OWNER_SCOPE')
        if type(self.source) is not dict or not self.source.get('references'):
            raise ValueError('SOURCE_UNBOUND')
        refs = self.source['references']
        if type(refs) is not list or any(type(x) is not str or not x for x in refs):
            raise ValueError('SOURCE_UNBOUND')
        if type(self.authority) is not dict or not self.authority.get('reference'):
            raise ValueError('AUTHORITY_UNBOUND')
        if self.authority.get('operator_id') != self.scope['operator_id']:
            raise ValueError('AUTHORITY_OWNER_MISMATCH')
        if self.authority.get('scope') != self.scope:
            raise ValueError('AUTHORITY_SCOPE_MISMATCH')
        if type(self.preconditions) is not dict or not self.preconditions:
            raise ValueError('PRECONDITIONS_UNRESOLVED')
        if any(type(v) is not bool or not v for v in self.preconditions.values()):
            raise ValueError('PRECONDITIONS_NOT_SATISFIED')
        self.binding()


def required_scope(proposal):
    """Exact immutable binding an independently governed RP request must cover."""
    return {**deepcopy(proposal.scope), 'material_binding_hash': digest(proposal.binding())}


class MaterialAdmissionGate:
    def __init__(self, client=None, *, clock=None):
        self.client = client
        self.clock = clock or (lambda: datetime.now(timezone.utc))

    def evaluate(self, proposal, request=None):
        if not isinstance(proposal, MaterialProposal):
            raise TypeError('MaterialProposal required')
        proposal = deepcopy(proposal)
        binding = proposal.binding()
        result = {'contract': 'MaterialAdmission/1', 'binding': binding,
            'binding_hash': digest(binding), 'claim_id': proposal.claim_id,
            'object_id': proposal.object_id, 'scope': deepcopy(proposal.scope),
            'epistemic_state': proposal.epistemic_state, 'rp_state': 'PENDING_VALIDATION',
            'rp_verdict': None, 'decision': 'HOLD_PENDING_VALIDATION',
            'reason_code': 'EXTERNAL_RP_REQUIRED', 'accepted': False,
            'prior_state': deepcopy(proposal.prior_state),
            'proposed_state': deepcopy(proposal.candidate_state),
            'resulting_state': deepcopy(proposal.prior_state),
            'timestamp': self.clock().isoformat(), 'external_acceptance': None,
            'external_receipt_id': None, 'external_chain_id': None,
            'external_transition_id': None}
        try:
            proposal.validate()
            if request is not None:
                request = deepcopy(request)
                claim = request['evaluation']['resolution']['claim_snapshot']
                if (request['claim_id'] != proposal.claim_id or
                        request['scope'] != required_scope(proposal) or
                        request['source_state'] != digest(proposal.prior_state) or
                        request['target_state'] != digest(proposal.candidate_state) or
                        claim['claim_text'] != proposal.claim_text or
                        claim['source_authority'] != proposal.authority):
                    raise ValueError('MATERIAL_REQUEST_BINDING_MISMATCH')
                if not isinstance(self.client, RealityAcceptanceClient):
                    raise ValueError('AUTHENTICATED_EXTERNAL_RP_CLIENT_REQUIRED')
                acceptance = self.client.evaluate(request)
                result['external_acceptance'] = deepcopy(acceptance)
                state = acceptance.get('rp_state')
                if state not in {'CONFIRMED', 'DISCONFIRMED', 'PENDING_VALIDATION'}:
                    raise ValueError('EXTERNAL_RP_RESPONSE_UNAVAILABLE_OR_INVALID')
                result.update(rp_state=state, rp_verdict=state,
                    external_receipt_id=acceptance['receipt_id'],
                    external_chain_id=acceptance['chain_id'],
                    external_transition_id=acceptance['decision_id'])
                if state == 'DISCONFIRMED':
                    result.update(decision='DENY', reason_code='EXTERNAL_RP_DISCONFIRMED')
                elif state == 'PENDING_VALIDATION':
                    result['reason_code'] = 'EXTERNAL_RP_PENDING_VALIDATION'
                elif proposal.epistemic_state != 'ESTABLISHED':
                    # A supported inference/proposal remains an inference/proposal;
                    # a new explicitly evidenced proposal is needed for promotion.
                    result['reason_code'] = 'EPISTEMIC_PROMOTION_NOT_AUTHORIZED'
                else:
                    result.update(decision='APPLY', reason_code='SCOPED_EXTERNAL_RP_CONFIRMED',
                        accepted=True, resulting_state=deepcopy(proposal.candidate_state))
        except (ValueError, TypeError, KeyError) as exc:
            result.update(decision='GOVERNANCE_BLOCK', reason_code=str(exc))
        result['admission_id'] = 'material-admission:' + digest(result)
        return AdmissionDecision(result, _SEAL)


def uncertainty_disclosure(value):
    """A no-value UNKNOWN disclosure neither admits a fact nor grants a mutation."""
    return (type(value) is dict and set(value) == {'epistemic_state', 'value'} and
            value == {'epistemic_state': 'UNKNOWN', 'value': None})
