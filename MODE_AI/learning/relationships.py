"""Bounded structural transfer derived from RP-validated operational contrasts.

These are revisable application hypotheses, not new facts, objectives, policy,
or execution grants. Examples alone do not establish universal causal laws.
"""
from copy import deepcopy
import json
from .contracts import digest

PROTECTED = {'operator_id', 'project', 'authority', 'approval', 'consent',
             'execution_authority', 'validation_state', 'governance_state'}


def _bounded(value):
    encoded = json.dumps(value, ensure_ascii=False, allow_nan=False)
    if len(encoded.encode('utf-8')) > 16384:
        raise ValueError('Relationship evidence/proposal bound exceeded')
    return value


def derive(contrast, evidence, scope):
    """Induce copy/literal fields only from at least two independently varied cases.

    The caller is OutcomeAnalysis, using admitted RP measurement content. No
    operator/model assertion can call this a governed Learning record.
    """
    _bounded(evidence)
    if type(evidence) is not dict or set(evidence) != {'contract', 'scope', 'signature', 'cases'}:
        raise ValueError('Exact relational evidence contract required')
    if evidence['contract'] != 'RelationalEvidence/1' or evidence['scope'] != scope:
        raise ValueError('Relationship cannot expand validated scope')
    signature = evidence['signature']; cases = evidence['cases']
    if (type(signature) is not dict or not signature or len(signature) > 8 or
            PROTECTED.intersection(signature) or type(cases) is not list or not 2 <= len(cases) <= 8):
        raise ValueError('Bounded positive relationship signature and multiple cases required')
    contexts = []; proposals = []
    for case in cases:
        if type(case) is not dict or set(case) != {'context', 'contrast', 'observation_kind'}:
            raise ValueError('Exact observed relational case required')
        context = case['context']; c = case['contrast']
        if case['observation_kind'] != 'OBSERVED' or type(context) is not dict:
            raise ValueError('Predictions cannot establish transfer')
        if not all(k in context and context[k] == v for k, v in signature.items()):
            raise ValueError('Signature not established by all observed contexts')
        if (type(c) is not dict or set(c) != set(contrast) or c['protocol'] != 'controlled_intervention/1' or
                c['variable'] != contrast['variable'] or c['unresolved'] or
                c['controls'].get('context_hash') != digest(context)):
            raise ValueError('Relationship case must bind its measured context')
        b, i, r = [c[k] for k in ('baseline', 'intervention', 'recovery')]
        if (any(type(a) is not dict or set(a) != {'input', 'output', 'controls'} or
                a['controls'] != c['controls'] for a in (b, i, r)) or b != r or b['input'] == i['input']):
            raise ValueError('Controlled intervention and recovery required in each context')
        if (any(type(a['output']) is not dict for a in (b, i, r)) or
                b['output'].get('accepted') is not False or i['output'].get('accepted') is not True):
            raise ValueError('Observed disconfirmation and successful intervention required')
        proposal = i['input']
        if type(proposal) is not dict or PROTECTED.intersection(proposal):
            raise ValueError('A learned proposal cannot carry authority or owner changes')
        for field in ('objective', 'conditions', 'constraints'):
            if field not in context or proposal.get(field) != context[field]:
                raise ValueError('Measured correction must preserve objective, conditions and constraints')
        contexts.append(context); proposals.append(proposal)
    if cases[0]['contrast'] != contrast or len({digest(c) for c in contexts}) != len(cases):
        raise ValueError('Primary contrast and independent contexts required')
    if len({digest(c['objective']) for c in contexts}) < 2:
        raise ValueError('A single objective cannot establish cross-context transfer')
    keys = set(proposals[0]); fields = {}
    if any(set(p) != keys for p in proposals):
        raise ValueError('Inconsistent proposal structures require review')
    for field in sorted(keys):
        # Protected semantics must always come from the CURRENT task, never an
        # old literal that accidentally matched the examples.
        if field in {'objective', 'conditions', 'constraints'}:
            fields[field] = {'copy': field}; continue
        candidates = [k for k in contexts[0] if all(k in c and p[field] == c[k]
                      for c, p in zip(contexts, proposals)) and
                      len({digest(c[k]) for c in contexts}) > 1]
        if field in candidates:
            fields[field] = {'copy': field}
        elif len(candidates) == 1:
            fields[field] = {'copy': candidates[0]}
        elif candidates:
            raise ValueError('Ambiguous structural binding requires more evidence')
        elif all(p[field] == proposals[0][field] for p in proposals):
            fields[field] = {'literal': deepcopy(proposals[0][field])}
        else:
            raise ValueError('No supported structural relationship; do not guess')
    return {'contract': 'OperationalRelationship/1', 'signature': deepcopy(signature),
            'fields': fields, 'scope': deepcopy(scope),
            'evidence_context_hashes': [digest(c) for c in contexts],
            'status': 'SUPPORTED_APPLICATION_HYPOTHESIS',
            'limits': ['Same owner/project/semantic domain', 'Exact signature and field bindings only',
                       'New application requires observed consequence verification',
                       'No universal fact, objective mutation or execution authority']}


def propose(relationship, context):
    """Negative structural relevance and safe instantiation, never keyword overlap."""
    if relationship.get('contract') != 'OperationalRelationship/1' or type(context) is not dict:
        return None
    if not all(k in context and context[k] == v for k, v in relationship['signature'].items()):
        return None
    proposal = {}
    for field, binding in relationship['fields'].items():
        if set(binding) == {'copy'}:
            if binding['copy'] not in context:
                return None
            proposal[field] = deepcopy(context[binding['copy']])
        elif set(binding) == {'literal'}:
            proposal[field] = deepcopy(binding['literal'])
        else:
            raise ValueError('Invalid stored relationship binding')
    if PROTECTED.intersection(proposal):
        raise PermissionError('Learned proposal attempts authority expansion')
    if any(proposal.get(k) != context.get(k) for k in ('objective', 'conditions', 'constraints')):
        raise PermissionError('Application changed protected task meaning')
    return _bounded(proposal)


def resolve_context(runtime, reference):
    """Use the current owner-issued semantic head, not caller-supplied task facts."""
    from understanding.understanding_record import digest as semantic_digest
    if type(reference) is not dict or set(reference) != {'understanding_id', 'version', 'hash'}:
        raise ValueError('Exact current task Understanding reference required')
    c = runtime.context
    state=getattr(c,'runtime_state',None)
    if getattr(runtime, '_halt_latch', None) or getattr(c.active_thread, 'halt', None) or getattr(state, 'value', state) == 'HALTED':
        raise PermissionError('HALT prevents learned adaptation')
    head = runtime.understanding_engine.store.get(c.identity.operator_id, reference['understanding_id'])
    if (head is None or head.version != reference['version'] or semantic_digest(head) != reference['hash'] or
            head.thread_id != c.active_thread.thread_id or not head.active or head.review_required or
            head.semantic_state.value != 'CONFIRMED' or head.semantic_domain != 'OPERATOR'):
        raise PermissionError('Current supported owner/thread task Understanding required')
    context = deepcopy(head.context.get('learning_application_context'))
    if type(context) is not dict or context.get('objective') != head.operator_objective:
        raise PermissionError('Application context must preserve the current objective')
    if context.get('constraints') != list(head.constraints):
        raise PermissionError('Application context must preserve all current constraints')
    _bounded(context)
    return head, context
