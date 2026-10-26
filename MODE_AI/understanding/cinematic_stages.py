"""Incremental provider-candidate boundary. This module performs no API calls.

Stages depend on pinned prior outputs; incomplete content is retained as a failed
candidate and cannot become a domain object. Exact local deterministic derivation
is the active implementation; future provider orchestration uses these envelopes.
"""
from .cinematic_models import loads
from system_layer.contracts import digest

STAGES = ('SCENE', 'AUDIENCE', 'REQUIREMENTS', 'MECHANISMS', 'SPECIFICATION')
MAX_STAGE_BYTES = 64_000


def inspect_candidate(stage, provider_status, output_text, source_reference, prior_references):
    if stage not in STAGES or type(source_reference) is not str or not source_reference:
        raise ValueError('Known stage and source required')
    if type(prior_references) is not dict or any(type(v) is not str or not v for v in prior_references.values()):
        raise ValueError('Pinned prior stages required')
    required = set(STAGES[:STAGES.index(stage)])
    if set(prior_references) != required: raise ValueError('Stage lineage missing or unexpected')
    if type(output_text) is not str: raise ValueError('Exact provider text required')
    envelope = {'contract': 'CinematicProviderCandidate/1', 'stage': stage, 'source_reference': source_reference,
        'prior_references': dict(prior_references), 'provider_status': provider_status,
        'output_hash': digest(output_text), 'output_byte_length': len(output_text.encode('utf-8')),
        'state': 'REJECTED', 'reason': None, 'candidate': None, 'canon_accepted': False,
        'execution_authority': False, 'retry': False}
    if provider_status != 'completed': envelope['reason'] = 'PROVIDER_NOT_COMPLETED'
    elif envelope['output_byte_length'] > MAX_STAGE_BYTES: envelope['reason'] = 'STAGE_BOUND_EXCEEDED'
    else:
        try:
            value = loads(output_text)
            if type(value) is not dict or set(value) != {'stage', 'source_reference', 'prior_references', 'payload'}:
                raise ValueError('Stage envelope required')
            if value['stage'] != stage or value['source_reference'] != source_reference or value['prior_references'] != prior_references:
                raise ValueError('Stage lineage mismatch')
            if type(value['payload']) not in (dict, list): raise ValueError('Structured stage payload required')
            envelope.update(state='CANDIDATE_REQUIRES_GROUNDING', candidate=value['payload'])
        except (ValueError, TypeError): envelope['reason'] = 'INVALID_STAGE_OR_LINEAGE'
    return envelope
