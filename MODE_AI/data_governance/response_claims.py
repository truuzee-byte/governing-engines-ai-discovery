"""Speech-act candidates and separate consequential publication relevance.

The grammar recognizes assertion, modal, imperative and metalinguistic structures.
It is not an open-domain semantic oracle. Unknown syntax alone is not an authority
decision. The response gate retains uncertainty where a consequential decision
depends on it; conversational publication never grants execution authority.
"""
from dataclasses import dataclass,asdict
import re
from learning.contracts import digest

STATES={'NON_MATERIAL','MATERIAL_CLAIM','MATERIAL_RECOMMENDATION','MATERIAL_AUTHORIZATION_IMPLICATION',
        'MATERIAL_EXECUTION_INSTRUCTION','MATERIAL_STATE_ASSERTION','UNKNOWN_MATERIALITY'}

def consequential(text):
    """Authority relevance is separate from grammatical assertion detection.

    This is a publication boundary, never an execution authorization. Unrecognized
    prose may continue as conversation; claims about protected operations or
    validated outcomes still require governed evidence. Mixed clauses are checked
    individually so a conversational prefix cannot hide a consequential claim.
    """
    if not isinstance(text, str):
        return False
    for clause in re.split(r'(?<=[.!?;])\s+|\n+', text):
        clause = clause.strip().replace('\u2019', "'")
        clause = re.sub(r'^(?:[-*]\s+|\d+\.\s+)', '', clause)
        # Remove only explicit negative protected predicates from relevance
        # scanning; the original proposition is retained by extract(). Other
        # affirmative predicates in the sentence still require RP.
        clause = re.sub(r'\bno (?:build(?: attempt)?|execution|deployment|permission|authorization)\s+(?:is|has been)\s+(?:authorized|supported|executed|granted)(?:\s+or\s+(?:authorized|supported|executed|granted))*\b', '', clause, flags=re.I)
        clause = re.sub(r'\bno (?:build )?(?:authorization|permission)(?: or (?:authorization|permission))? is granted\b', '', clause, flags=re.I)
        clause = re.sub(r'\bhow\s+(?:(?!(?:and|but|then|or)\b)\w+\s+)+is verified\b', '', clause, flags=re.I)
        # Evaluate coordinated claims separately: a negative first predicate
        # cannot hide an affirmative grant after a comma/conjunction.
        parts=re.split(r',?\s+\b(?:but|and then)\b\s+|,\s+and\s+',clause,flags=re.I)
        if len(parts)>1:
            if any(consequential(part) for part in parts):return True
            continue
        if _nonassertive(clause):
            continue
        # Requests for explanation and explicit refusals are not grants or
        # completion assertions. A later positive clause is evaluated separately.
        compound_action = re.search(r'\b(?:then|and (?:execute|deploy|delete|grant|release))\b', clause, re.I)
        if not compound_action and re.match(r'^(?:explain|describe|discuss|what|how|why|show the evidence|cancel)\b', clause, re.I):
            continue
        if not compound_action and re.match(r'^(?:you|the user|the operator)\s+(?:are (?:asking|requesting)|asked|requested)\b', clause, re.I):
            continue
        if not compound_action and re.match(r"^(?:I |we |you )?(?:cannot|can't|won't|will not|do not|must not)\b", clause, re.I):
            continue
        # Explicitly negated completion/permission is not an affirmative result.
        # Do not apply this to a mixed positive predicate.
        if not re.search(r'\b(?:but|then|and|until)\b',clause,re.I):
            if re.search(r'\b(?:no (?:build|execution|deployment|permission|authorization)(?: attempt)? (?:is|has been)|(?:build|execution|deployment) is not)\b',clause,re.I):
                continue
        # Describing an as-yet-unspecified check is a proof obligation, not
        # evidence that it passed. A separate success assertion still gates.
        if not compound_action and re.fullmatch(r'(?:The )?completion checks\b[^.!?]*\bwill demonstrate\s+(?:that\s+)?the build is successful(?: and meets requirements)?[.]?',clause,re.I):
            continue
        # Asking whether the Operator wants persistence is neither a save nor
        # a claim of saving. The writer still requires its own bound consent.
        if not compound_action and re.match(r'^(?:would|do) you (?:like|want)\b',clause,re.I) and clause.endswith('?'):
            continue
        verbs=r'(?:deploy|delete|erase|overwrite|execute|ship|release|transfer|authorize|approve|sign|finalize|rotate|grant|disable|publish|send|merge|revoke|purchase|remove the restriction|access the archive|commit|deactivate|distribute)'
        # Mentioning a protected action is not performing, recommending or
        # authorizing it. Require an imperative or an actor/predicate binding.
        action = re.search(r'(?:^(?:please\s+)?|\b(?:I|we|you|they)\s+|\b(?:can|may|must|should|could|will|then|and)\s+)'+verbs+r'\b',clause,re.I)
        authority = re.search(r'\b(?:is|are|was|were|remains|has established|have established|have|has|supports|requires)\s+(?:now\s+)?(?:fully\s+)?(?:permission|approval|administrator|privileges|authorized|validated|verified|compliant|compliance|operational|safe|confidential|accurate|disposable|no further review)\b|\bproves\s+(?:the|this|that)\b', clause, re.I)
        outcome = re.search(r'\b(?:passed|passes|ready for customers|capability remains available|rely on this result)\b|\b(?:is|are|remains)\s+effective\b|^(?:update|change)\s+(?:the\s+)?production\b', clause, re.I)
        completion = re.search(r'\b(?:build|artifact|deployment|test|validation|execution)\s+(?:(?:is|was|has|has been|is now)\s+)?(?:complete|completed|successful|succeeded|ready)\b', clause, re.I)
        if completion and re.search(r'\bto consider (?:a |the )?$', clause[:completion.start()], re.I):
            completion = None
        if completion and re.search(r'\bwill demonstrate\s+(?:that\s+)?(?:the\s+)?$', clause[:completion.start()], re.I):
            completion = None
        # A completed write is material. Participles inside a question or a
        # source attribution ("your statement stored in memory") are not a new
        # write. Source availability is checked separately at publication.
        storage = re.search(r'\b(?:I|we)\s+(?:have\s+)?(?:saved|stored|remembered)\b.*\b(?:persistent|vault|permanently)\b|\b(?:was|were|has been|have been)\s+(?:saved|stored)\b.*\b(?:persistent|vault|permanently)\b', clause, re.I)
        clearance = re.search(r"\b(?:clear|cleared) to\s+"+verbs+r'\b|\bnothing (?:else )?blocks?\s+'+verbs+r'\b|^push\b.*\bproduction\b',clause,re.I)
        # Terse status labels and passive decisions remain consequential even
        # without the full assertion grammar. Unknown syntax is not permission.
        status = re.search(r'^(?:[\w -]+:\s*)?(?:authorized|validated|verified|approved|operational|passed|confirmed)[.!]?$|(?<!no )\b(?:permission|approval|access|authorization)\s+(?:is\s+)?granted\b|\b(?:was|were|has been|have been)\s+(?:authorized|approved|validated|verified|deployed|executed|published)\b',clause,re.I)
        # A source being present/admitted does not establish its governing
        # authority. Assertions promoting a source require the same evidence
        # boundary as assertions promoting execution permission.
        source_authority = re.search(r'\b(?:is|are|remains|remain|becomes|become)\s+(?:the\s+)?(?:(?:only|sole|governing)\s+)?authoritative\b|\b(?:document|note|record|source)\s+(?:itself\s+)?(?:grants|confers)\s+(?:permission|authority|capability)\b',clause,re.I)
        if action or authority or outcome or completion or storage or clearance or status or source_authority:
            return True
    return False

@dataclass(frozen=True)
class ResponseClaim:
    claim_id: str
    proposition: str
    claim_type: str
    subject: str
    transition: str
    authority_implication: str
    evidence_requirement: dict
    scope: dict
    temporal_state: str
    source_runtime_basis: str
    rp_required: bool
    governance_requirement: str
    validation_state: str
    def to_dict(self):return asdict(self)

def _nonassertive(text):
    # Only complete utterances of these speech acts are intrinsically non-assertive.
    social=re.fullmatch(r"(?:hello|hi|good morning|good afternoon|good evening|thanks|thank you|you're welcome|goodbye|bye|please clarify your request|could you clarify your request|how can i help)[.!?]*",text.strip(),re.I)
    metalinguistic=re.fullmatch(r'\s*(?:What does|How do you define|What is meant by)\s+"[^"\n]+"\s*(?:mean)?\s*\?\s*',text,re.I)
    discussion=re.fullmatch(r'(?:Let us discuss|I can explain|I am discussing) "[^"\n]+" (?:as a term|as an example|without recommending action)\.',text,re.I)
    conversation_management=re.fullmatch(r'(?:that is all(?: for now)?|let us stop here|end this conversation)[.!?]*',text.strip(),re.I)
    return bool(social or metalinguistic or discussion or conversation_management)


def is_conversation_request(text):
    """Operator requests for discussion/drafting are not assertions made by Mode.

    Only whole requests qualify. Output still receives the full claim gate.
    This grants no tool, filesystem, persistence or execution permission.
    """
    if type(text) is not str:return False
    clauses=[v.strip() for v in re.split(r'(?<=[.!?;])\s+|\n+',text.strip()) if v.strip()]
    if not clauses:return False
    for clause in clauses:
        if _nonassertive(clause):continue
        if re.search(r'\b(?:and then|then execute|and execute|and deploy|and delete)\b',clause,re.I):return False
        discussion=re.fullmatch(r'(?:explain|describe|summarize|discuss|define|compare|elaborate)\b[^\n]+',clause,re.I)
        drafting=re.fullmatch(r'(?:help me (?:plan|draft|organize|think through)\b[^\n]+|(?:create|write|draft) (?:a |an )?(?:short |brief )?(?:checklist|outline|summary|plan|list)\b[^\n]*)',clause,re.I)
        inspection=re.fullmatch(r'(?:show|list) (?:the )?(?:evidence|receipts|requirements|missing information|available sources)\b[^\n]*',clause,re.I)
        source_question=re.fullmatch(r'(?:use|read)\s+[^\n]+\s+(?:to tell me|and tell me)\s+(?:whether|what|why|how)\b[^\n]+',clause,re.I)
        question=re.fullmatch(r'(?:what|which|why|how|does|did|is|are|can)\b[^\n]*\?',clause,re.I)
        preference=re.fullmatch(r'(?:actually,?\s+)?I (?:prefer|like|dislike)\b[^\n]+',clause,re.I)
        session_restriction=re.fullmatch(r'(?:keep|use) (?:this|that|it) (?:in|within|for) (?:this|the current) (?:conversation|session|thread) only[.!]?',clause,re.I)
        if not (discussion or drafting or inspection or source_question or preference or session_restriction or question):return False
    return True


def extract(text,scope):
    if not isinstance(text,str) or not text.strip():return {'state':'UNKNOWN_MATERIALITY','claims':[],'coverage':'INCOMPLETE'}
    if _nonassertive(text):return {'state':'NON_MATERIAL','claims':[],'coverage':'COMPLETE'}
    # Preserve each complete clause. Unsupported conjunctions/quotations are
    # retained as unknown instead of discarding potentially consequential text.
    clauses=[v.strip() for v in re.split(r'(?<=[.!?;])\s+|\n+',text.strip()) if v.strip()]
    claims=[]
    for clause in clauses:
        # Composition must preserve speech acts: several non-assertive clauses
        # do not acquire a consequential claim merely by sharing one response.
        # Mixed/unknown clauses still pass the unchanged fail-closed checks.
        if _nonassertive(clause):
            continue
        normalized=clause.replace('\u2019',"'")
        normalized=re.sub(r"\byou're\b",'you are',normalized,flags=re.I)
        normalized=re.sub(r"\bit's\b",'it is',normalized,flags=re.I)
        kind='UNKNOWN_MATERIALITY';subject='UNRESOLVED';transition='UNRESOLVED'
        modal=re.fullmatch(r'(.+?)\s+(can|may|must|should|ought to|could|will)\s+(.+?)[.!]?',normalized,re.I)
        assertion=re.fullmatch(r'(.+?)\s+(is|are|was|were|has|have|passed|passes|supports|requires|blocks|remains)\s+(.+?)[.!]?',normalized,re.I)
        imperative=re.fullmatch(r'(?:Please\s+)?([A-Za-z]+)\s+(.+?)[.!]?',normalized,re.I)
        if not any(c in normalized for c in ('"','?',':')):
            if modal:
                subject,operator,transition=modal.groups()
                kind='MATERIAL_AUTHORIZATION_IMPLICATION' if operator.lower() in {'can','may'} else 'MATERIAL_RECOMMENDATION'
            elif assertion:
                subject,predicate,value=assertion.groups();transition=predicate+' '+value
                kind='MATERIAL_CLAIM' if predicate.lower() in {'supports','requires','blocks'} else 'MATERIAL_STATE_ASSERTION'
                if re.match(r'(?:approval|permission|authorized|clear\b)',value,re.I):kind='MATERIAL_AUTHORIZATION_IMPLICATION'
            elif imperative and imperative[1].lower() not in {'i','you','it','we','they','the','a','an','this','that'}:
                subject='response recipient';transition=imperative[1]+' '+imperative[2]
                kind='MATERIAL_EXECUTION_INSTRUCTION'
        proposition=clause
        # No authority/evidence is inferred from the sentence's own assertion.
        requirement={'authority':'Exact proposition and transition scope authorization',
                     'evidence':'External governed validation of the proposition',
                     'resolution':'UNRESOLVED_UNTIL_GOVERNED_EVIDENCE'}
        identity='response-claim:'+digest([proposition,kind,scope])
        claims.append(ResponseClaim(identity,proposition,kind,subject,transition,
            'Claimed readiness/permission for '+transition if kind=='MATERIAL_AUTHORIZATION_IMPLICATION' else 'Does not itself grant permission',requirement,dict(scope),'CURRENT_RESPONSE_ONLY',
            'Generated response:'+digest(text),True,'EXPLICIT_SCOPED_APPROVAL','PENDING_VALIDATION').to_dict())
    unknown=any(c['claim_type']=='UNKNOWN_MATERIALITY' for c in claims)
    if not claims:return {'state':'NON_MATERIAL','claims':[],'coverage':'COMPLETE'}
    return {'state':'UNKNOWN_MATERIALITY' if unknown else claims[0]['claim_type'],'claims':claims,
            'coverage':'INCOMPLETE' if unknown else 'COMPLETE'}
