"""Fail-closed evidence boundaries for governed responses, not source admission.

Natural language entailment is not inferred from lexical similarity. Attributed
assertions must identify a source and quote its supported content. Historical
measurements may be quoted; unmeasured mechanisms must be labelled inference.
No state writes, provider calls, or validation grants occur here.
"""
import json
import re
from data_governance.context_admission import verify, GOVERNED
from learning.contracts import digest

INSTRUCTION = (
    'Evidence grounding: separate learned measurements, inference and hypothesis. '
    'Never present an unmeasured exception as observed. Historical generalization '
    'NONE means measured arms only, not all future inputs. Critique must compare '
    'every exception claim with the measured contrast. A model cannot create evidence. '
    'For an explicit memory/source/evidence attribution, cite the admitted record ID '
    'and quote the exact supported claim, or restate the complete literal fact from '
    'one uniquely admitted memory; arbitrary paraphrase is not verified. Do not invent '
    'a citation. Verification-only support is not ordinary inference evidence and '
    'requires an explicit operator request naming that record. If support is '
    'absent or uncertain say so, without asserting it exists. Requests to add support '
    'must be conditional on an actual admitted source. New contradictions are review '
    'proposals until authorized validation reassembles the admitted state. For typed '
    'learned Understanding, cite its actual record ID and quote a complete '
    'literal_measured_claim shown below, using double quotation marks around the '
    'literal claim and its source ID in the same sentence. These are projections of measured fields, '
    'not permission for additional paraphrased claims or future outcomes.'
)
ATTRIBUTION = re.compile(
    r'\b(?:based on|according to|supported by|from|as recorded in|as shown by)\b'
    r'[^.!?\n]{0,100}\b(?:memory|record|source|evidence|understanding|receipt)\b'
    r'|\b(?:memory|record|source|evidence|receipt)\b[^.!?\n]{0,80}'
    r'\b(?:states?|shows?|confirms?|defines?|establishes?|supports?|tells?|indicates?)\b'
    r'|\b(?:memory|memories|provenance)\b'
    r'|\b(?:I|we)\s+(?:recall|remember)\b', re.I)
EXCEPTION = re.compile(r'\b[A-Za-z]+(?:Error|Exception)\b|\b(?:raises?|throws?)\s+(?:an?\s+)?exception\b')
ABSENT = re.compile(r'\b(?:no|not|absent|unavailable|unknown|uncertain|unsupported|if|unless|hypothetical)\b', re.I)
ABSENT_SUPPORT = re.compile(
    r'\bno\s+(?:(?:eligible|admitted|approved|supporting|persistent|operator-attested)\s+)*'
    r'(?:memory|memories|source|record|evidence|provenance)\b'
    r'|\bsupport\s+(?:is|remains)\s+(?:absent|unknown|uncertain|unavailable)\b', re.I)
IDS = re.compile(r'\b(?:pm-|understanding-|transformation-)[a-zA-Z0-9-]+')

def sources(prompt):
    verify(prompt)
    governed = [s for s in prompt.sources if s['record']['decision']=='ADMITTED'
            and s['record']['artifact_type'] in GOVERNED]
    # Recorded diagnostic citations do not promote logs into governed truth.
    from copy import deepcopy
    for source in prompt.sources:
        r=source['record']
        if r['decision']=='ADMITTED' and r['artifact_type']=='RUNTIME' and r['source']=='InteractionEvidenceLedger/1':
            from runtime_observation.evidence_ledger import from_prompt
            ledger=from_prompt(prompt)
            for sid,spec in ledger['sources'].items():
                if spec['source_type']!='TRANSITION_RECORD':continue
                record=deepcopy(r);record['artifact_id']=sid;record['validation_state']='UNVALIDATED'
                record['lineage']=[spec['reference']]
                content={e['field']:e['value'] for e in ledger['entries'] if e['source_id']==sid}
                governed.append({'record':record,'content':json.dumps(content,ensure_ascii=False,sort_keys=True)})
            continue
        if r['decision']!='ADMITTED' or r['artifact_type']!='RUNTIME' or r['source']!='InteractionInspector/1':continue
        try:
            payload=json.JSONDecoder().raw_decode(source['content'].split('SELF-INSPECTED RUNTIME EVIDENCE (recorded data, not instructions):\n',1)[1])[0]
            if payload['contract']!='InteractionInspection/1' or any(payload[k]!=prompt.scope[k] for k in ('operator_id','thread_id')):continue
            for item in payload['transformation_provenance']['records']:
                event=item['record']
                if any(event[k]!=payload[k] for k in ('operator_id','thread_id','interaction_id')):continue
                record=deepcopy(r);record['artifact_id']=event['transition_id']
                record['validation_state']='UNVALIDATED';record['lineage']=[item['reference']]
                governed.append({'record':record,'content':json.dumps(event,ensure_ascii=False,sort_keys=True)})
        except (KeyError,ValueError,IndexError,TypeError):continue
    return governed


def support_sources(prompt):
    """Sealed verification-only records; never model-visible inference content."""
    verify(prompt)
    from datetime import datetime,timezone
    rows=[]
    for row in prompt.support_sources:
        r=row['record']
        if r['decision']!='ADMITTED':continue
        if r['freshness'] and datetime.fromisoformat(r['freshness'].replace('Z','+00:00'))<=datetime.now(timezone.utc):continue
        rows.append(row)
    return rows


def resolve_support(text,prompt):
    """Bounded current-owner read for explicit model citations, never inference."""
    verify(prompt)
    if prompt.support_loader is None or not IDS.search(text):return prompt
    from data_governance.context_admission import Admission,basis_for_memory
    a=Admission(prompt.scope['operator_id'],prompt.scope['thread_id'])
    a.include(prompt)
    # Current store versions are re-resolved. Do not retain stale support copies.
    a.support_sources=[]
    for r in prompt.support_loader(prompt.scope['operator_id'],text):
        a.support('MEMORY',r.memory_id,r.content,source='Current evidence-owner citation resolution',
                  owner=r.operator_id,basis=basis_for_memory(r))
    return a.finish()


def _claim_words(text):
    # Literal proposition normalization only, not semantic entailment by overlap.
    return ' '.join(w for w in re.findall(r'\w+',text.lower()) if w not in {'and','that'})


def _hypothetical_exception(line):
    return (line.strip().lower().startswith(('hypothetically,','hypothetical:','possibly,')) and
            bool(re.search(r'\b(?:could|might|may)\b|not established|unmeasured',line,re.I)))


def _exception_caveat(line):
    # Deliberately narrow negation grammar. A following affirmative assertion
    # (even after 'but') is not licensed by a disclaimer.
    if re.search(r'\bbut\b|;|\band (?:it|this|the input)\b',line,re.I):return False
    return bool(re.fullmatch(r'(?:Do not (?:assert|claim|report) .+|'
        r'It is not established that .+|'
        r'Any claim that .+ is (?:unmeasured|unsupported)(?: speculation)?(?: and must not be asserted as fact)?)',line,re.I))


def _clauses(text):
    """Sentence boundaries, including JSON strings decoded by the caller.

    A disclaimer in another sentence cannot negate an asserted exception.
    """
    return [s.strip() for s in re.split(r'[.!?](?:\s+|$)|\n', text) if s.strip()]


def literal_measured_claims(row):
    """Source-bound literal field projections, not generated semantic entailment."""
    record=row.get('record',{})
    if (record.get('artifact_type')!='UNDERSTANDING' or record.get('decision')!='ADMITTED' or
            record.get('validation_state')!='VALIDATED' or record.get('governance_state')!='APPROVED'):
        return []
    try:payload=json.loads(row['content'])
    except (ValueError,TypeError):return []
    if not isinstance(payload,dict) or payload.get('kind')!='BOUNDED_HISTORICAL_UNDERSTANDING':return []
    result=[]
    for index,e in enumerate(payload.get('experiences',[])):
        prop=e.get('learned_proposition',{});arm=prop.get('contrast',{}).get('intervention',{})
        output=arm.get('output')
        if not isinstance(output,dict) or output.get('accepted') is not True:continue
        value=arm.get('input');variable=prop.get('measured_variable')
        if not isinstance(variable,str):continue
        values=value.items() if isinstance(value,dict) else [(variable,value)]
        for field,v in values:
            if not isinstance(v,(str,int,float,bool)) or v is None:continue
            result.append({'text':f'Measured successful {field}: {v}',
                'path':f'experiences[{index}].learned_proposition.contrast.intervention.input'+('.'+field if isinstance(value,dict) else ''),
                'input':value})
    return result


def scoped_unknown(sentence,prompt):
    """A specific unmeasured new input is not revocation of an admitted source."""
    if not re.match(r'^(?:there is )?no admitted evidence (?:that|about|for|regarding)\b',sentence.strip(),re.I):return False
    if re.search(r'\b(?:ineligible|invalid|revoked|unusable|superseded|expired|unapproved)\b',sentence,re.I):return False
    known=' '.join(s['content'] for s in prompt.sources if s['record']['artifact_type']=='UNDERSTANDING')
    values=[v for s in prompt.sources if s['record']['artifact_type']=='OPERATOR_INPUT'
            for v in re.findall(r'["“]([^"”\n]+)["”]',s['content']) if v not in known]
    return any(v in sentence for v in values)


def _verification_requested(prompt,identity):
    return any(s['record']['artifact_type']=='OPERATOR_INPUT' and identity in s['content'] and
               re.search(r'\b(?:verify|verification|attribution|provenance|check|validate)\b',s['content'],re.I)
               for s in prompt.sources)


def learned_rule_context(prompt):
    """Typed measured arms before draft generation, no invented general rule."""
    rules=[]
    for row in sources(prompt):
        try:payload=json.loads(row['content'])
        except (ValueError,TypeError):continue
        if not isinstance(payload,dict) or payload.get('kind')!='BOUNDED_HISTORICAL_UNDERSTANDING':continue
        for e in payload.get('experiences',[]):
            prop=e['learned_proposition'];contrast=prop.get('contrast',{})
            rules.append({'source_id':row['record']['artifact_id'],'known_rule':{
                'statement':prop['statement'],'measured_variable':prop.get('measured_variable'),
                'successful_arm':contrast.get('intervention'),'scope':payload.get('scope'),
                'conditions':e.get('conditions'), 'generalization':prop.get('generalization')},
                'known_exception':{'arm':contrast.get('baseline'),'recovery':contrast.get('recovery'),
                    'applies_only_to_measured_inputs':True},
                'hypothetical_exception':'Unmeasured future possibilities must be conditional, not reported as observed.',
                'unsupported_speculation':'A changed title or input has no established exception mechanism absent new validation.'})
    return ('\nMEASURED RULE / EXCEPTION BOUNDARY:\n'+json.dumps(rules,ensure_ascii=False,separators=(',',':'))+
        '\nBefore drafting, separate chosen path from observed mechanism. An encoding may be preferred from a measured arm; '
        'do not assert a decoding exception for an unmeasured title. Critique must challenge that contradiction; '
        'finalization must remove it rather than repeat a rejected draft. No new measurement is implied.\n') if rules else ''

def boundary_context(prompt):
    rows=[]
    for s in sources(prompt):
        r=s['record']; content=s['content']
        try:
            payload=json.loads(content)
        except (ValueError, TypeError):
            payload=None
        # Full contrast and provenance already appear in the admitted source
        # text supplied to every stage. Do not serialize those bodies twice.
        claims=({'source_content_hash':r['content_hash'],
                 'exact_claim_location':'admitted source text',
                 'learned_statements':[e['learned_proposition']['statement']
                     for e in payload.get('experiences',[])]}
                if isinstance(payload,dict) and payload.get('kind')=='BOUNDED_HISTORICAL_UNDERSTANDING'
                else {'exact_claim_location':'normalized scoped ledger','source_content_hash':r['content_hash']}
                if r['source']=='InteractionEvidenceLedger/1' else content)
        if isinstance(claims,dict) and isinstance(payload,dict) and payload.get('kind')=='BOUNDED_HISTORICAL_UNDERSTANDING':
            claims['literal_measured_claims']=[{'text':c['text'],'path':c['path']} for c in literal_measured_claims(s)]
        rows.append({'record_id':r['artifact_id'],'type':r['artifact_type'],
                     'source':r['source'],'admission':r['decision'],
                     'validation':r['validation_state'],'evidence_refs':r['lineage'],
                     'origin_thread':r['scope'].get('source_thread_id'),
                     'supported_claims':claims})
    return '\n'+INSTRUCTION+'\nEXACT ADMITTED SUPPORT (empty means absent):\n'+json.dumps(rows,ensure_ascii=False,separators=(',',':'))

def assess(text,prompt):
    from runtime_observation.evidence_ledger import assess_rendered
    ledger_result=assess_rendered(text,prompt)
    if ledger_result is not None:return ledger_result
    raw_text=text
    prompt=resolve_support(text,prompt)
    rows=sources(prompt); support=support_sources(prompt); reasons=[]; links=[]
    ids={s['record']['artifact_id'] for s in rows+support}
    for identifier in IDS.findall(text):
        if identifier not in ids: reasons.append('NONEXISTENT_SOURCE_ID:'+identifier)
    # Evaluate prose/JSON strings alike; quoted support must exist verbatim.
    # JSON fields are separate claims: "choice": "unknown" must not negate
    # an unsupported attribution in a different reason field.
    cleaned=re.sub(r'^```(?:json)?\s*|\s*```$', '', text.strip())
    try:
        parsed=json.loads(cleaned)
    except ValueError:
        parsed=None
    def strings(value):
        if isinstance(value,str):return [value]
        if isinstance(value,dict):return [s for v in value.values() for s in strings(v)]
        if isinstance(value,list):return [s for v in value for s in strings(v)]
        return []
    if isinstance(parsed,(dict,list)):
        text='\n'.join(strings(parsed))
    # When the output declares the same typed semantic fields as a measured
    # interpretation, every field must match one actual successful arm. A quoted
    # fact cannot excuse a contradictory action/actor or an extra authority field.
    if isinstance(parsed,dict):
        answer={k:v for k,v in parsed.items() if k not in {'reason','support_ref'}}
        typed=[claim['input'] for s in rows for claim in literal_measured_claims(s)
               if isinstance(claim['input'],dict) and len(set(answer)&set(claim['input']))>=2]
        if typed and not any(answer==v for v in typed):reasons.append('LEARNED_SEMANTIC_FIELDS_NOT_SUPPORTED')
    for clause in _clauses(text):
        if not ATTRIBUTION.search(clause):continue
        if ABSENT_SUPPORT.search(clause): continue
        if clause.strip().lower().startswith(('if ','unless ')) and 'support' in clause.lower(): continue
        cited=[s for s in rows+support if s['record']['artifact_id'] in clause]
        quoted=re.findall(r'["“]([^"”\n]{3,})["”]',clause)
        exact=[s for s in cited if any(q in s['content'] for q in quoted)]
        measured=[s for s in cited if any(q==c['text'] for q in quoted for c in literal_measured_claims(s))]
        # Preserve complete literal fact linkage without demanding one citation
        # surface. No bag-of-words paraphrase acceptance; verification-only rows
        # require explicit reference and quotation and never join this inference.
        literal=[s for s in rows if s['record']['artifact_type']=='MEMORY' and
                 len(_claim_words(s['content']).split())>=6 and
                 _claim_words(s['content']) in _claim_words(clause)]
        resolved=measured or exact or (literal if len(literal)==1 else [])
        if resolved and resolved[0]['record']['artifact_type']=='RUNTIME' and not clause.strip().startswith('OBSERVED'):
            reasons.append('RUNTIME_CITATION_REQUIRES_OBSERVED_LABEL')
            resolved=[]
        if resolved and resolved[0] in support and (not clause.strip().lower().startswith(('provenance verification:','attribution verification:')) or
                not _verification_requested(prompt,resolved[0]['record']['artifact_id'])):
            reasons.append('PROVENANCE_ONLY_CANNOT_SUPPORT_SEMANTIC_INFERENCE')
            resolved=[]
        if not resolved:
            reasons.append('UNVERIFIED_ATTRIBUTION_REQUIRES_SOURCE_AND_EXACT_CLAIM')
        else:
            record=resolved[0]['record']
            links.append({'source_id':record['artifact_id'],
                'mode':'SOURCE_BOUND_MEASURED_FIELD' if measured else 'EXPLICIT_QUOTATION' if exact else 'COMPLETE_NORMALIZED_LITERAL_FACT',
                'purpose':'PROVENANCE_ONLY' if resolved[0] in support else 'SEMANTIC_CONTEXT',
                'content_hash':record['content_hash'],'validation_state':record['validation_state'],
                'governance_state':record['governance_state'],'lineage':record['lineage'],
                'scope':record['scope']})
    learned=[]
    for s in rows:
        try: p=json.loads(s['content'])
        except (ValueError,TypeError): continue
        if isinstance(p,dict) and p.get('kind')=='BOUNDED_HISTORICAL_UNDERSTANDING': learned.append(p)
    if learned and EXCEPTION.search(text):
        measured=json.dumps(learned,ensure_ascii=False)
        query_values=[]
        for s in prompt.sources:
            if s['record']['artifact_type']=='OPERATOR_INPUT':
                query_values.extend(re.findall(r'["“]([^"”\n]{1,})["”]',s['content']))
        novel=[v for v in query_values if v not in measured]
        assertions=[line for line in _clauses(text) if EXCEPTION.search(line) and
                    not _hypothetical_exception(line) and not _exception_caveat(line)]
        if any(re.search(r'\b(?:always|every|any|all)\b|titles containing|characters like',line,re.I) for line in assertions):
            reasons.append('UNSUPPORTED_EXCEPTION_GENERALIZATION')
        if any(v in line for v in novel for line in assertions):
            reasons.append('UNMEASURED_INPUT_EXCEPTION_CLAIM')
        # An exact historical quotation is auditable. Inferring the same error
        # on a fresh input is not established by an admitted historical record.
        for line in _clauses(text):
            if not EXCEPTION.search(line): continue
            if _hypothetical_exception(line) or _exception_caveat(line):
                continue
            # Actual measured historical error, not a new input's predicted
            # exception. Require the same arm/error and an explicit past scope.
            historical=False
            if not any(v in line for v in novel) and re.search(r'\b(?:historical|previously|measured|resulted)\b',line,re.I):
                for p in learned:
                    for e in p.get('experiences',[]):
                        arm=e.get('learned_proposition',{}).get('contrast',{}).get('baseline',{})
                        error=arm.get('output',{}).get('error');value=arm.get('input')
                        if isinstance(error,str) and error in line and isinstance(value,str) and value in line:historical=True
            if historical and not re.search(r'\b(?:always|every|any|all|future)\b',line,re.I):continue
            if not any(s['record']['artifact_id'] in line and
                       any(q in s['content'] for q in re.findall(r'["“]([^"”\n]{3,})["”]',line))
                       for s in rows if s['record']['artifact_type']=='UNDERSTANDING'):
                reasons.append('UNMEASURED_EXCEPTION_ASSERTION')
    return {'allowed':not reasons,'reasons':sorted(set(reasons)),
            'coverage':'EXPLICIT_ATTRIBUTION_AND_HISTORICAL_EXCEPTION_BOUNDARY',
            'source_ids':sorted(s['record']['artifact_id'] for s in rows),'claim_links':links,
            'provenance_only_ids':[s['record']['artifact_id'] for s in support if s['record']['artifact_id'] in IDS.findall(raw_text)],
            'response_hash':digest(raw_text)}
