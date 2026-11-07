"""Bounded preference assertions, not an open-domain personal-fact verifier.

Only sealed, admitted operator statements and eligible memory can establish a
preference. Hypotheses remain hypotheses. Scope does not widen by implication.
No persistent storage, model calls, RP decisions or execution authority here.
"""
import re
from data_governance.context_admission import verify
from learning.contracts import digest

GROUNDING_INSTRUCTION = (
    'Preference grounding: use only admitted operator statements or eligible '
    'operator-attested memory as preference evidence. Model drafts and critiques '
    'are unvalidated suggestions, not user facts. Keep today/session-only '
    'preferences within that scope. A session-only change does not imply an '
    'outside-session default or revive an earlier preference. Preserve explicit '
    'current corrections; keep unresolved conflicts unknown. Label hypotheses '
    'as hypotheses, never as established continuity. If no default is established, '
    'say so rather than inventing one. A preference applies only to its stated subject: '
    'a system-evaluation preference does not change facts in a fictional scenario or '
    'establish an epistemic rule for unrelated topics. Memory persistence is opt-in: '
    'absence of a thread-only instruction is never permission to save other information. '
    'Distinguish explicit save requests, current eligible saved records, and ordinary '
    'thread context; do not describe all unspecified content as eligible for long-term memory.'
)

LIMITED = re.compile(r'\b(today|tonight|this evening|session.only|conversation only|this session|this conversation|do not save|don.t (?:save|remember))\b', re.I)
UNCERTAIN = re.compile(r'\b(may|might|perhaps|hypothesis|possibly|if|unclear|unknown|not know|don.t know|no established)\b', re.I)
CORRECTION = re.compile(r'\b(actually|instead|no longer|now prefer|changed my|correction)\b', re.I)
SOURCE = re.compile(r'(?:^|[.!?\n:]\s*)(?:actually,?\s*)?(?:I (?:now )?prefer|my (?:favorite|preferred|default)\s+\w+\s+is)\s+([^.!?\n]+)', re.I)
CLAIM = re.compile(r'\byou (?:still |now |always |usually )?prefer\s+([^.!?;\n]+)|\byour (?:favorite|preferred|default)\s+\w+\s+is\s+([^.!?;\n]+)', re.I)
DEFAULT = re.compile(r'\b(?:your default|remains (?:the|your) default)\b', re.I)

def value(text):
    text = re.split(r'\b(?:today|tonight|for now|for this|this evening|outside|within|in this|not|but|because|and|over)\b|[,;]', text, maxsplit=1, flags=re.I)[0]
    return ' '.join(re.findall(r'[a-z0-9]+', text.lower())).strip()

def operator_sources(raw_input, admitted=None):
    rows=[]
    if admitted is not None:
        verify(admitted)
        for source in admitted.sources:
            record=source['record']
            kind=record['artifact_type']
            if record['authority']!='OPERATOR' or kind not in {'THREAD','MEMORY','OPERATOR_INPUT','SESSION'}:
                continue
            # Aggregate JSON transcript metadata is not a second operator source.
            if record['source'].startswith('ContextAssembler:'):
                continue
            rows.append((0 if kind=='MEMORY' else 1,record['artifact_id'],source['content'],kind))
    rows.sort(key=lambda r:r[0])  # current-session evidence follows retrieved memory
    rows.append((2,'input:current',raw_input,'OPERATOR_INPUT'))
    return rows

def assess(response, raw_input='', admitted=None):
    """Return inspectable recognized claims and source IDs, with no authority grant."""
    facts=[]
    defaults=[]
    for _,identity,text,kind in operator_sources(raw_input,admitted):
        for withdrawal in re.finditer(r'\bI (?:no longer|do not|don.t) prefer\s+([^.!?\n]+)',text,re.I):
            removed=value(withdrawal.group(1))
            facts=[f for f in facts if f['value']!=removed]
            if not LIMITED.search(text):
                defaults=[f for f in defaults if f['value']!=removed]
        for match in SOURCE.finditer(text):
            item=value(match.group(1))
            if not item or UNCERTAIN.search(match.group(0)):
                continue
            if CORRECTION.search(text):
                facts=[]
            facts.append({'value':item,'id':identity,'limited':bool(LIMITED.search(text)),
                          'default':bool(re.search(r'\bmy default\b',match.group(0),re.I))})
            if facts[-1]['default'] and not facts[-1]['limited']:
                if CORRECTION.search(text):defaults=[]
                defaults.append(facts[-1])
    claims=[]
    for sentence in re.split(r'(?<=[.!?;])\s+|\n+',response):
        matches=list(CLAIM.finditer(sentence))
        default=bool(DEFAULT.search(sentence))
        hypothesis = re.search(r'\byou (?:may|might|possibly) prefer\b',sentence,re.I)
        if not matches and not default and not hypothesis:
            continue
        if sentence.rstrip().endswith('?'):
            continue
        # Uncertainty must qualify the personal assertion, not an unrelated
        # clause ("Coffee might help; your default is tea" is not a hypothesis).
        qualified_default = default and re.search(r'\b(?:may|might) (?:be|remain) (?:your|the) default\b',sentence,re.I)
        if (hypothesis and not default and not matches) or qualified_default:
            claims.append({'text':sentence,'state':'INFERENCE_OR_UNKNOWN','source_ids':[]})
            continue
        for match in matches or [None]:
            item=value(next(g for g in match.groups() if g is not None)) if match else None
            candidates=[f for f in facts if item==f['value']] if item else [f for f in facts if f['default'] and f['value'] in sentence.lower()]
            if default:
                candidates=[f for f in defaults if item==f['value']] if item else [f for f in defaults if f['value'] in sentence.lower()]
            if re.search(r'\b(always|usually|outside this (?:conversation|session))\b',sentence,re.I):
                candidates=[f for f in candidates if not f['limited']]
            values={f['value'] for f in (defaults if default else facts)}
            # Conflicting plain statements do not acquire precedence merely by order.
            supported=bool(candidates) and len(values)==1
            claims.append({'text':sentence,'state':'SUPPORTED' if supported else 'UNSUPPORTED',
                           'source_ids':[f['id'] for f in candidates] if supported else []})
    return {'allowed':all(c['state']!='UNSUPPORTED' for c in claims),
            'coverage':'BOUNDED_PREFERENCE_DEFAULT_LANGUAGE', 'claims':claims,
            'response_hash':digest(response)}
