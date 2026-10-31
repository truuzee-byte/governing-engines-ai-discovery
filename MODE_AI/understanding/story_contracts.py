"""Source-grounded story contracts; authored truth is not external RP truth.

Offsets are half-open Unicode code-point ranges in the exact selected text.
PROPOSED claims have no authority and never enter canonical cinematic Facts.
"""
from dataclasses import dataclass, field
from system_layer.contracts import digest
from .cinematic_models import Contract

EPISTEMIC = {'ESTABLISHED', 'INFERRED', 'UNKNOWN', 'CONFLICTED', 'PROPOSED'}
RESOLUTION = {'RESOLVED', 'PROBABLE', 'AMBIGUOUS', 'UNRESOLVED', 'CONFLICTED'}
CAUSAL = {'CAUSES', 'ENABLES', 'TRIGGERS', 'CONTRIBUTES_TO', 'FOLLOWS', 'CORRELATED_WITH', 'UNKNOWN_CAUSE'}


@dataclass
class StorySource(Contract):
    source_id: str
    document_id: str
    version: int
    record_hash: str
    content_hash: str
    authority: str
    project: str
    story_scope: str
    scene_scope: str
    source_type: str
    text: str
    start: int
    end: int
    operator_constraints: list[str] = field(default_factory=list)

    def __post_init__(self):
        super().__post_init__()
        if not all(x.strip() for x in (self.source_id, self.document_id, self.authority, self.project, self.story_scope)):
            raise ValueError('Missing source custody')
        if self.version < 1 or self.source_type not in {'CANON', 'AUTHORITATIVE', 'SPECIFICATION'}:
            raise ValueError('Authoritative versioned source required')
        if not 0 <= self.start < self.end <= len(self.text) or self.end-self.start > 100_000:
            raise ValueError('Invalid bounded source range')
        if digest(self.text) != self.content_hash:
            raise ValueError('Source text hash mismatch')
        for value in (self.record_hash, self.content_hash):
            if len(value) != 64 or any(c not in '0123456789abcdefABCDEF' for c in value):
                raise ValueError('Invalid source hash')


@dataclass
class StoryClaim(Contract):
    claim_id: str
    category: str
    subject: str
    predicate: str
    value: object
    epistemic_state: str
    source_references: list[str]
    rule: str
    rp_state: str = 'PENDING_VALIDATION'

    def __post_init__(self):
        super().__post_init__()
        if self.rp_state != 'PENDING_VALIDATION':
            raise ValueError('Story interpretation cannot issue an RP verdict')
        if self.epistemic_state not in EPISTEMIC or not self.source_references or not self.rule:
            raise ValueError('Unclassified or ungrounded story claim')
        if self.epistemic_state == 'UNKNOWN' and self.value is not None:
            raise ValueError('Unknown cannot assert a value')


@dataclass
class StoryInterpretation(Contract):
    interpretation_id: str
    story_scope: str
    sources: list[StorySource]
    spans: dict[str, dict[str, object]]
    claims: list[StoryClaim]
    references: list[dict[str, object]]
    events: list[dict[str, object]]
    relationships: list[dict[str, object]]
    scenes: list[dict[str, object]]
    stages: list[dict[str, object]]
    unresolved: list[str]
    conflicts: list[dict[str, object]]
    creative_proposals: list[StoryClaim] = field(default_factory=list)
    schema_version: str = 'StoryInterpretation/1'

    def __post_init__(self):
        super().__post_init__()
        if self.schema_version != 'StoryInterpretation/1': raise ValueError('Unknown story schema')
        if not self.sources or len(self.sources) > 16: raise ValueError('Bounded sources required')
        if len({s.project for s in self.sources}) != 1 or any(s.story_scope != self.story_scope for s in self.sources):
            raise ValueError('Mixed story scope')
        source_map = {s.source_id: s for s in self.sources}
        if len(source_map) != len(self.sources): raise ValueError('Duplicate source')
        for ref, span in self.spans.items():
            s = source_map.get(span.get('source_id'))
            a, b = span.get('start'), span.get('end')
            if s is None or type(a) is not int or type(b) is not int or not s.start <= a < b <= s.end:
                raise ValueError('Unbound span')
            if span.get('text') != s.text[a:b]: raise ValueError('Altered source span')
        ids = [c.claim_id for c in self.claims + self.creative_proposals]
        if len(ids) != len(set(ids)): raise ValueError('Duplicate claim identity')
        for c in self.claims + self.creative_proposals:
            if set(c.source_references) - self.spans.keys(): raise ValueError('Unbound claim')
        if any(c.epistemic_state == 'PROPOSED' for c in self.claims): raise ValueError('Proposal in canon')
        if any(c.epistemic_state != 'PROPOSED' for c in self.creative_proposals): raise ValueError('Unclassified proposal')
        for r in self.references:
            if r.get('state') not in RESOLUTION: raise ValueError('Unknown resolution state')
        for r in self.relationships:
            if r.get('domain') == 'CAUSAL' and r.get('type') not in CAUSAL: raise ValueError('Unknown causal state')

    def canonical_view(self):
        """Field index over source-linked records, not a second truth store.

        Empty lists mean no supported claim; they never supply default content.
        The typed cinematic adapter remains the owner of Scene/Beat/Audience.
        """
        category_fields={
            'WORLD_FACTS':{'WORLD_FACT','PHYSICAL'}, 'CHARACTER_IDENTITIES':{'IDENTITY'},
            'CHARACTER_OBJECTIVES':{'OBJECTIVE'}, 'CHARACTER_KNOWLEDGE':{'KNOWLEDGE'},
            'CHARACTER_BELIEFS':{'BELIEF'}, 'CHARACTER_RELATIONSHIPS':{'RELATIONSHIP'},
            'CHARACTER_EMOTIONAL_STATE':{'EMOTION'}, 'ENVIRONMENT_STATE':{'ENVIRONMENT'},
            'OBJECTS_PROPS':{'POSSESSION'}, 'ACTIONS':{'ACTION','AUTHORITY'}, 'REACTIONS':{'REACTION'},
            'SCENE_PURPOSE':{'PURPOSE'}}
        value={name:[c.to_dict() for c in self.claims if c.category in categories] for name,categories in category_fields.items()}
        value.update(STORY_SCOPE=self.story_scope,ENTITIES=self.references,
            CHARACTERS=sorted({c.subject for c in self.claims if c.category in {'KNOWLEDGE','BELIEF','EMOTION','OBJECTIVE','AUTHORITY'} and c.epistemic_state!='UNKNOWN'}),
            LOCATIONS=[c.to_dict() for c in self.claims if c.category=='SPATIAL' or c.predicate in {'enters','exits','leaves','approaches'}],
            EVENTS=self.events,CAUSAL_LINKS=[r for r in self.relationships if r['domain']=='CAUSAL'],
            TEMPORAL_ORDER=[r for r in self.relationships if r['domain']=='TEMPORAL'],
            SPATIAL_RELATIONSHIPS=[r for r in self.relationships if r['domain']=='SPATIAL'],
            SCENE_BOUNDARIES=self.scenes,
            BEATS=next(s['state'] for s in self.stages if s['stage']=='BEAT_DERIVATION'),
            STATE_TRANSITIONS=next(s['state']['transitions'] for s in self.stages if s['stage']=='STATE_CONSTRUCTION'),
            ENTRY_STATE=[{'event_id':e['event_id'],'state':e['pre_state_map']} for e in self.events],
            EXIT_STATE=[{'event_id':e['event_id'],'state':e['post_state_map']} for e in self.events],
            CONTINUITY_REQUIREMENTS=[{'event_id':e['event_id'],'preserve':e['pre_state_map'],'changes':e['state_key']} for e in self.events],
            AUDIENCE_KNOWLEDGE=[c.to_dict() for c in self.claims if c.category=='AUDIENCE' and c.predicate in {'knows','learns','discovers'}],
            AUDIENCE_IGNORANCE=[c.to_dict() for c in self.claims if c.category=='AUDIENCE' and c.predicate=='does not know'],
            AUDIENCE_REQUIRED_UNDERSTANDING=[c.to_dict() for c in self.claims if c.category=='AUDIENCE' and c.predicate=='must understand'],
            UNRESOLVED_DETAILS={'coverage':self.unresolved,'unknown_claims':[c.to_dict() for c in self.claims if c.epistemic_state=='UNKNOWN']},
            CONFLICTS=self.conflicts)
        return {'CANONICAL_INTERPRETATION':value,'CREATIVE_PROPOSALS':[c.to_dict() for c in self.creative_proposals]}
