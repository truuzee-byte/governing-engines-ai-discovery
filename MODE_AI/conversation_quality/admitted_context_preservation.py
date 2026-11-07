"""Bounded downstream admission preservation; never a source-validation owner.

Model suggestions cannot revoke sealed admission. Evidence challenges are
returned for source-owner revalidation, not committed as state transitions.
The language guard is deliberately bounded, not a general truth verifier.
"""
import json
import re
from datetime import datetime, timezone
from data_governance.context_admission import verify, GOVERNED
from learning.contracts import digest

PRESERVATION_RULE = (
    'Governed context preservation: admission is assigned by the runtime, not by '
    'the draft, critique or final model. An admitted source remains usable within '
    'its stated scope and validation level unless an authorized source-validation '
    'path supplies an invalidation, expiry, disconfirmation or supersession. '
    'Operator-attested data is not independently validated external truth. '
    'Question the reasoning or flag contradictory evidence with source IDs for '
    'authorized revalidation; do not silently revoke eligibility, infer ineligibility '
    'from missing metadata, or replace an admitted value with unknown merely on '
    'critique uncertainty. Model proposals have no admission authority. '
    'A pending review does not itself invalidate a source. Historical model answers '
    'do not outrank current admitted data. Do not invent validation receipts.'
)

def records(prompt):
    verify(prompt)
    rows = {}
    for source in prompt.sources:
        r = source['record']
        if r['artifact_type'] in GOVERNED and r['decision'] == 'ADMITTED':
            if r['freshness']:
                deadline = datetime.fromisoformat(r['freshness'].replace('Z', '+00:00'))
                if deadline.tzinfo is None or deadline <= datetime.now(timezone.utc):
                    raise PermissionError('Admitted source expired; origin owner must reassemble/revalidate context')
            rows[(r['artifact_id'], r['content_hash'])] = r
    return list(rows.values())

def metadata_context(prompt):
    """Render only existing sealed selected-source metadata, not provenance bodies."""
    rows = []
    for r in records(prompt):
        scope = r['scope']
        rows.append({
            'record_id': r['artifact_id'], 'kind': r['artifact_type'],
            'source': r['source'], 'evidence_refs': r['lineage'],
            'admissibility': r['decision'], 'approval': r['governance_state'],
            'downstream_use_eligible': True, 'surface': r['surface'],
            'validation': r['validation_state'], 'authority': r['authority'],
            'lifecycle': r['lifecycle_state'], 'freshness': r['freshness'],
            'source_thread_id': scope.get('source_thread_id'),
            'source_message_id': scope.get('source_message_id'),
            'record_version': scope.get('record_version'),
            'previous_version_hash': scope.get('previous_version_hash'),
            'supersession_state': scope.get('supersession_state', 'ADMITTED_FOR_THIS_REQUEST'),
            'scope': scope, 'content_hash': r['content_hash'],
        })
    return '\n\n' + PRESERVATION_RULE + '\nADMITTED SOURCE METADATA (runtime-issued):\n' + json.dumps(rows, ensure_ascii=False, separators=(',', ':')) if rows else ''

# Recognize explicit source-eligibility denials. No arbitrary answer changes or
# mere critique disagreement are treated as revocation. Do not claim NLP completeness.
DENIAL = re.compile(
    r'(?:memory|record|source|context|evidence|persistent)[^.!?\n]{0,200}'
    r'(?:not (?:confirmed|eligible|admitted|approved|valid)|ineligible|unapproved|'
    r'unusable|unverified|unconfirmed|(?:is|has been) (?:invalid|stale|expired|superseded)|'
    r'cannot be (?:used|trusted)|should not be used|'
    r'lacks? (?:eligibility|approval|admission)|do(?:es)? not confirm|'
    r'no (?:eligible|admitted)|eligibility (?:is|remains) (?:unknown|uncertain))'
    r'|(?:no|lack of|without)[^.!?\n]{0,60}(?:eligible|admitted|approved)[^.!?\n]{0,80}'
    r'(?:memory|record|source|evidence|context)', re.I)
CHALLENGE = re.compile(r'\b(?:contradict\w*|disconfirm\w*|supersed\w*|expired|stale|invalidat\w*)\b', re.I)

def assess_preservation(text, prompt):
    admitted = records(prompt)
    from .source_grounding import _clauses,scoped_unknown
    # Decode JSON strings before distinguishing scoped unknowns from revocation;
    # do not allow a disclaimer in another field/sentence to mask a denial.
    cleaned=re.sub(r'^```(?:json)?\s*|\s*```$', '', text.strip())
    try:parsed=json.loads(cleaned)
    except ValueError:parsed=None
    def strings(v):
        if isinstance(v,str):return [v]
        if isinstance(v,dict):return [s for x in v.values() for s in strings(x)]
        if isinstance(v,list):return [s for x in v for s in strings(x)]
        return []
    values=strings(parsed) if isinstance(parsed,(dict,list)) else [text]
    denial=bool(admitted and any(DENIAL.search(s) and not scoped_unknown(s,prompt)
                                for value in values for s in _clauses(value)))
    challenges = []
    if admitted and CHALLENGE.search(text):
        # Named evidence remains a proposal: only the source validation owner
        # can authorize a state change. Never fabricate a new validation grant.
        cited = [s['record']['artifact_id'] for s in prompt.sources
                 if s['record']['artifact_id'] in text]
        challenges.append({'status': 'PENDING_AUTHORIZED_REVALIDATION',
                           'source_ids': [r['artifact_id'] for r in admitted],
                           'cited_admitted_evidence_ids': cited,
                           'proposal_hash': digest(text),
                           'route': 'ORIGIN_SOURCE_VALIDATION_AND_CONTEXT_ADMISSION',
                           'admissibility_changed': False})
    return {'allowed': not denial, 'unsupported_readjudication': denial,
            'coverage': 'BOUNDED_ADMISSION_DENIAL_LANGUAGE',
            'protected_source_ids': [r['artifact_id'] for r in admitted],
            'validation_review_requests': challenges, 'response_hash': digest(text)}
