"""Deterministic, conservative prose admission inside Understanding.

This is a bounded clause grammar, not a general language competence claim.
Unsupported clauses survive as coverage gaps. Source order is not causal proof.
Each stage is an inspectable snapshot; no provider or execution dependency.
"""
from copy import deepcopy
import re
from system_layer.contracts import digest
from .story_contracts import StorySource, StoryClaim, StoryInterpretation

VERBS = (r'does not know|no longer trusts|is also known as|is called|is inside|is outside|'
         r'is near|is behind|is ahead of|is above|is below|is adjacent to|is facing|'
         r'is separated from|is grouped with|is to the left of|is to the right of|'
         r'is injured|is silent|is restrained|is sad|is angry|is afraid|is dead|is alive|'
         r'is ruler|is commander|is present|is absent|knows|believes|thinks|wants|intends|'
         r'enters|exits|leaves|approaches|holds|carries|drops|takes|receives|gives|'
         r'learns|discovers|sees|observes|hears|notices|says|speaks|reveals|hides|trusts|'
         r'distrusts|commands|obeys|refuses|attacks|retreats|dies|explodes|opens|closes|waits|'
         r'must understand|must not yet understand|may infer|reacts|recoils|flinches|becomes|is')
CLAUSE = re.compile(r'^(?P<subject>.+?)\s+(?P<verb>' + VERBS + r')(?:\s+(?P<object>.*))?$', re.I)
PRONOUNS = {'he', 'she', 'they', 'him', 'her', 'them', 'it', 'someone', 'someone else'}
TRANSITIONS = {'enters','exits','leaves','approaches','drops','takes','receives','gives','learns',
               'discovers','reveals','hides','no longer trusts','distrusts','commands','obeys',
               'refuses','attacks','retreats','dies','explodes','opens','closes','reacts','recoils','flinches',
               'sees','observes','hears','notices','becomes'}
SPATIAL = {'inside','outside','near','behind','ahead of','above','below','adjacent to','facing',
           'separated from','grouped with','to the left of','to the right of'}


def norm(value): return re.sub(r'\s+', ' ', value.strip(' .!?:')).casefold()


class StoryInterpreter:
    """One run owns no external state; all intermediate evidence is returned."""
    def __init__(self, sources):
        self.sources = [StorySource.from_dict(s.to_dict()) for s in sources]
        if not 1 <= len(sources) <= 16 or sum(s.end-s.start for s in sources) > 100_000:
            raise ValueError('Story selection bound exceeded')
        if len({(s.project,s.story_scope) for s in sources}) != 1: raise ValueError('Mixed scope')
        self.spans = {}; self.units = []; self.entities = {}; self.references = []
        self.claims = []; self.events = []; self.relationships = []; self.scenes = []
        self.stages = []; self.unresolved = []; self.conflicts = []; self.proposals = []

    def snapshot(self, stage, value):
        self.stages.append({'stage':stage, 'state':deepcopy(value), 'hash':digest(value)})

    def claim(self, category, subject, predicate, value, ref, state='ESTABLISHED', rule='explicit-clause'):
        content = dict(category=category,subject=subject,predicate=predicate,value=value,
                       epistemic_state=state,source_references=[ref],rule=rule)
        claim = StoryClaim(claim_id='claim:'+digest(content), **content)
        if claim.claim_id not in {c.claim_id for c in self.claims+self.proposals}:
            (self.proposals if state == 'PROPOSED' else self.claims).append(claim)
        return claim

    def segment(self):
        self.snapshot('SOURCE', [s.to_dict() for s in self.sources])
        for source in self.sources:
            # Preserve offsets. Blank lines are not scene boundaries. A bounded
            # sentence/semicolon split never interprets text inside quotation marks.
            selection = source.text[source.start:source.end]
            for match in re.finditer(r'[^.!?;\n]+(?:[.!?;]|(?=\n|$))', selection):
                raw = match.group(); text = raw.strip()
                if not text: continue
                start = source.start + match.start() + len(raw)-len(raw.lstrip())
                end = start + len(text)
                ref = 'span:'+digest([source.source_id,source.record_hash,start,end])
                self.spans[ref] = {'source_id':source.source_id,'start':start,'end':end,'text':text}
                self.units.append({'ref':ref,'text':text.rstrip('.!;?'),'source_id':source.source_id})
        if not self.units or len(self.units)>512: raise ValueError('Empty or excessive story segmentation')
        self.snapshot('SOURCE_SEGMENTATION', self.spans)

    def entity(self, label, ref):
        key = norm(label)
        if key in PRONOUNS:
            # Recency alone does not resolve a pronoun or establish its gender.
            possibles = sorted(self.entities)
            state = 'AMBIGUOUS' if len(possibles)>1 else 'PROBABLE' if possibles else 'UNRESOLVED'
            eid = 'reference:'+digest([ref,key])
            self.references.append(dict(reference=label,entity_id=eid,candidates=possibles,state=state,source_reference=ref))
            self.unresolved.append('IDENTITY_'+state+':'+eid)
            self.entities[eid] = {'label':label,'identity':None,'refs':[ref],'state':state}
            return eid
        for eid, value in self.entities.items():
            if key in value.get('aliases',[]):
                if ref not in value['refs']: value['refs'].append(ref)
                self.references.append(dict(reference=label,entity_id=eid,candidates=[eid],state='RESOLVED',source_reference=ref))
                return eid
        eid = 'entity:'+digest([self.sources[0].story_scope,key])
        role = key.startswith(('the ','a ','an '))
        self.entities[eid] = {'label':label,'identity':None if role else label,'aliases':[key],
                              'refs':[ref],'state':'UNRESOLVED' if role else 'RESOLVED'}
        self.references.append(dict(reference=label,entity_id=eid,candidates=[eid],
                                    state='UNRESOLVED' if role else 'RESOLVED',source_reference=ref))
        if role: self.unresolved.append('ROLE_IDENTITY_UNKNOWN:'+eid)
        return eid

    def resolve(self):
        expanded=[]
        connectors={'because':('CAUSAL','CAUSES',True),'so':('CAUSAL','CAUSES',False),
                    'therefore':('CAUSAL','CAUSES',False),'while':('TEMPORAL','OVERLAP',False),
                    'before':('TEMPORAL','BEFORE',False),'after':('TEMPORAL','AFTER',False),
                    'which enables':('CAUSAL','ENABLES',False),'which triggers':('CAUSAL','TRIGGERS',False),
                    'which contributes to':('CAUSAL','CONTRIBUTES_TO',False),
                    'which is correlated with':('CAUSAL','CORRELATED_WITH',False)}
        for unit in self.units:
            split=re.split(r',?\s+(because|so|therefore|while|before|after|which enables|which triggers|which contributes to|which is correlated with)\s+',unit['text'],maxsplit=1,flags=re.I)
            if len(split)==3 and CLAUSE.fullmatch(split[0]) and CLAUSE.fullmatch(split[2]):
                parent=self.spans[unit['ref']]; left=None
                for index,part in enumerate((split[0],split[2])):
                    start=parent['start']+unit['text'].index(part)
                    ref='span:'+digest([unit['source_id'],start,start+len(part)])
                    self.spans[ref]={'source_id':unit['source_id'],'start':start,'end':start+len(part),'text':part}
                    child=dict(unit,ref=ref,text=part)
                    if index:child['connector']={'left_ref':left,'kind':connectors[split[1].lower()]}
                    else:left=ref
                    expanded.append(child)
            else:expanded.append(unit)
        self.units=expanded
        for unit in self.units:
            text = unit['text']; ref=unit['ref']
            # Presentation annotations are kept separately; they never create world facts.
            presentation = re.match(r'^(Off[- ]screen|On[- ]screen|Meanwhile|Then|Afterward|Later|Simultaneously),?\s+', text, re.I)
            unit['presentation'] = presentation.group(1).upper().replace(' ','-') if presentation else ''
            core = text[presentation.end():] if presentation else text
            unit['core']=core
            if re.match(r'^(?:Scene\s+\d+\s*:|INT\.|EXT\.)',text,re.I): unit['heading']=True; continue
            if re.fullmatch(r'(?:The )?(weather|time of day|architecture|cause|scene purpose) is (.+)',core,re.I):continue
            if re.fullmatch(r'.+? (causes|enables|triggers|contributes to|is correlated with) .+',core,re.I):continue
            if re.match(r'^(?:Proposal|Possibility):',core,re.I):
                self.claim('PROPOSAL','story','creative_possibility',core.split(':',1)[1].strip(),ref,'PROPOSED','proposal-marker')
                unit['proposal']=True; continue
            match=CLAUSE.fullmatch(core)
            if not match: continue
            # Never reinterpret conditional/quoted/coordinated subjects as names.
            if (re.search(r'\b(if|unless|perhaps|maybe|when|although|and|or|because)\b',match['subject'],re.I)
                    or len(match['subject'].split())>6 or any(c in match['subject'] for c in '\"“:,') or
                    re.search(r'\b(not|never|might|could|would|may)\b',match['subject'],re.I)):
                continue
            unit.update(verb=match['verb'].lower(),object=(match['object'] or '').strip(),subject_label=match['subject'])
            if norm(match['subject']) in {'the audience','audience','the viewer','viewers'}:
                unit['subject']='AUDIENCE'; continue
            unit['subject']=self.entity(match['subject'],ref)
            if unit['verb']=='gives':
                transfer=re.fullmatch(r'(.+?) to ([A-Z][A-Za-z]*(?:[-\'][A-Za-z]+)*)',unit['object'])
                if transfer:
                    recipient=self.entity(transfer[2],ref)
                    if (recipient!=unit['subject'] and self.entities[recipient]['state']=='RESOLVED'):
                        unit.update(transfer_prop=transfer[1],transfer_recipient=recipient)
            if unit['verb'] in {'is called','is also known as'} and unit['object']:
                entity=self.entities[unit['subject']]; alias=norm(unit['object'])
                competitors=[e for e,v in self.entities.items() if e!=unit['subject'] and alias in v.get('aliases',[])]
                if competitors:
                    self.unresolved.append('ALIAS_CONFLICT:'+ref); entity['state']='CONFLICTED'
                else:
                    entity.setdefault('aliases',[]).append(alias)
                    if entity['identity'] is None and not alias.startswith(('the ','a ','an ')):
                        entity['identity']=unit['object'];entity['identity_refs']=[ref];entity['state']='RESOLVED'
        self.snapshot('ENTITY_REFERENCE_RESOLUTION', {'entities':self.entities,'references':self.references})

    def extract_facts(self):
        for unit in self.units:
            ref=unit['ref']; verb=unit.get('verb'); subject=unit.get('subject'); obj=unit.get('object','')
            if unit.get('proposal') or unit.get('heading'): continue
            if not verb or (verb=='is' and norm(unit.get('subject_label','')) in {'the weather','weather','time of day','the time of day','architecture','the architecture','cause','the cause','scene purpose','the scene purpose'}):
                relation=re.fullmatch(r'(.+?) (causes|enables|triggers|contributes to|is correlated with) (.+)',unit['core'],re.I)
                if relation:
                    self.relationships.append(dict(domain='CAUSAL',type={'causes':'CAUSES','enables':'ENABLES','triggers':'TRIGGERS',
                        'contributes to':'CONTRIBUTES_TO','is correlated with':'CORRELATED_WITH'}[relation[2].lower()],
                        source=relation[1],target=relation[3],source_references=[ref],epistemic_state='ESTABLISHED',
                        endpoint_state='EXPLICIT_NOMINAL_RELATION_NOT_OBSERVED_EVENT'))
                    unit['covered']=True;continue
                special = re.fullmatch(r'(?:The )?(weather|time of day|architecture|cause|scene purpose) is (.+)',unit['core'],re.I)
                if special:
                    self.claim('ENVIRONMENT' if special[1].lower()!='scene purpose' else 'PURPOSE','story',special[1].lower(),special[2],ref)
                    unit['covered']=True
                else: self.unresolved.append('UNPARSED_MATERIAL:'+ref)
                continue
            if not obj and verb not in {'enters','exits','leaves','retreats','dies','explodes','waits','reacts','recoils','flinches'} and not verb.startswith('is '):
                self.unresolved.append('MISSING_CLAUSE_OBJECT:'+ref); continue
            if '"' in unit['core'] or '“' in unit['core']:
                self.unresolved.append('QUOTED_SCOPE_UNRESOLVED:'+ref); continue
            if re.search(r'\b(?:if|unless|might|perhaps|because|therefore|while|before|after|and then)\b', obj, re.I):
                self.unresolved.append('COMPLEX_CLAUSE_SCOPE_UNRESOLVED:'+ref); continue
            category='ACTION'; predicate=verb; value=obj or True
            if subject=='AUDIENCE': category='AUDIENCE'
            elif verb in {'knows','does not know','learns','discovers'}: category='KNOWLEDGE'
            elif verb in {'believes','thinks'}: category='BELIEF'
            elif verb in {'wants','intends'}: category='OBJECTIVE'
            elif verb in {'trusts','distrusts','no longer trusts'}: category='RELATIONSHIP'
            elif verb in {'holds','carries','takes','receives','drops','gives'}: category='POSSESSION'
            elif verb in {'is called','is also known as'}: category='IDENTITY'
            elif verb in {'is sad','is angry','is afraid'}: category='EMOTION'; value=verb[3:]
            elif verb=='becomes' and obj in {'sad','angry','afraid','calm'}: category='EMOTION';predicate='emotional state'
            elif verb in {'reacts','recoils','flinches'}:category='REACTION'
            elif verb in {'sees','observes','hears','notices'}:category='PERCEPTION'
            elif verb in {'is ruler','is commander','commands','obeys'}: category='AUTHORITY'
            elif verb.startswith('is ') and verb[3:] in SPATIAL: category='SPATIAL'; predicate=verb[3:]
            elif verb in {'is injured','is restrained','is dead','is alive','is silent','is present','is absent'}:
                category='PHYSICAL'; predicate=verb[3:]; value=True
            elif verb=='is':category='WORLD_FACT';predicate='state'
            if verb=='is' and re.fullmatch(r".+['’]s (?:sister|brother|parent|child|ally|enemy|commander)",obj,re.I):
                category='RELATIONSHIP';predicate=obj.rsplit(' ',1)[1];value=obj.rsplit(' ',1)[0][:-2]
            if verb=='gives':
                if unit.get('transfer_recipient'):
                    value=unit['transfer_prop']
                    recipient=self.claim('POSSESSION',unit['transfer_recipient'],'receives',value,ref,
                                         rule='explicit-transfer-recipient')
                    unit['recipient_claim_id']=recipient.claim_id
                else:self.unresolved.append('TRANSFER_RECIPIENT_STATE_REQUIRES_RESOLUTION:'+ref)
            # An unresolved reference can support the occurrence, but not a
            # particular character attribution. It remains a separate entity.
            c=self.claim(category,subject,predicate,value,ref)
            unit['claim_id']=c.claim_id; unit['covered']=True
        self.snapshot('FACT_EXTRACTION',[c.to_dict() for c in self.claims])

    def extract_events(self):
        claims={c.claim_id:c for c in self.claims}
        for unit in self.units:
            c=claims.get(unit.get('claim_id'))
            if not c or c.subject=='AUDIENCE': continue
            if unit['verb'] not in TRANSITIONS and c.category not in {'ACTION'}: continue
            self.events.append({'event_id':'event:'+digest([c.claim_id]),'claim_id':c.claim_id,
                'subject':c.subject,'verb':unit['verb'],'object':unit['object'],'source_reference':unit['ref'],
                'source_id':unit['source_id'],'presentation':unit['presentation'],
                'material_transition':unit['verb'] in TRANSITIONS,'epistemic_state':c.epistemic_state})
        self.snapshot('EVENT_EXTRACTION',self.events)

    def construct_state(self):
        state={}; transitions=[]; prior_source=None
        claims={c.claim_id:c for c in self.claims}
        for unit in self.units:
            if prior_source!=unit['source_id']:
                state={};prior_source=unit['source_id']
            c=claims.get(unit.get('claim_id'))
            if not c or c.subject=='AUDIENCE': continue
            category=c.category
            # Dimensions keep proposition identity; ignorance of X is not
            # ignorance of Y. Possession is tracked per prop.
            dimension = ('knowledge:'+norm(str(c.value)) if category=='KNOWLEDGE' else
                         'possession:'+norm(str(c.value)) if category=='POSSESSION' else
                         'relationship:'+norm(str(c.value)) if category=='RELATIONSHIP' else
                         'location' if c.predicate in {'enters','exits','leaves'} else
                         category.lower()+':'+c.predicate)
            key=c.subject+'/'+dimension
            before=deepcopy(state)
            pre=deepcopy(state.get(key))
            state[key]=c.to_dict()
            if unit.get('recipient_claim_id'):
                recipient=claims[unit['recipient_claim_id']]
                state[recipient.subject+'/possession:'+norm(str(recipient.value))]=recipient.to_dict()
            event=next((e for e in self.events if e['claim_id']==c.claim_id),None)
            if event:
                event.update(state_key=key,pre_state=pre,post_state=c.to_dict(),
                             pre_state_map=before,post_state_map=deepcopy(state))
                transitions.append({k:deepcopy(event[k]) for k in ('event_id','state_key','pre_state','post_state')})
        self.snapshot('STATE_CONSTRUCTION',{'state':state,'transitions':transitions})

    def relate(self):
        previous={}
        for event in self.events:
            prev=previous.get(event['source_id']); marker=event['presentation']
            if prev:
                order='SIMULTANEOUS' if marker in {'MEANWHILE','SIMULTANEOUSLY'} else 'AFTER' if marker in {'THEN','AFTERWARD','LATER'} else 'UNKNOWN_ORDER'
                self.relationships.append(dict(domain='TEMPORAL',type=order,source=prev['event_id'],target=event['event_id'],
                    source_references=[prev['source_reference'],event['source_reference']],epistemic_state='ESTABLISHED' if order!='UNKNOWN_ORDER' else 'UNKNOWN'))
                if order=='AFTER': self.relationships.append(dict(domain='CAUSAL',type='FOLLOWS',source=prev['event_id'],target=event['event_id'],source_references=[event['source_reference']],epistemic_state='ESTABLISHED'))
            if event['verb'] in {'explodes','dies'}:
                self.relationships.append(dict(domain='CAUSAL',type='UNKNOWN_CAUSE',source=None,target=event['event_id'],source_references=[event['source_reference']],epistemic_state='UNKNOWN'))
            previous[event['source_id']]=event
            duration=re.fullmatch(r'for (\d+(?:\.\d+)?|one|two|three|four|five|six|seven|eight|nine|ten) (seconds?|minutes?|hours?)',event['object'],re.I)
            if duration and event['verb']=='waits':
                self.relationships.append(dict(domain='TEMPORAL',type='HOLD',source=event['event_id'],target=event['event_id'],
                    duration=duration.group(),source_references=[event['source_reference']],epistemic_state='ESTABLISHED'))
        for c in self.claims:
            if c.category=='SPATIAL':
                targets=[eid for eid,e in self.entities.items() if norm(str(c.value)) in e.get('aliases',[]) and e['state']=='RESOLVED']
                target=targets[0] if len(targets)==1 else None
                self.relationships.append(dict(domain='SPATIAL',type=c.predicate,source=c.subject,target=c.value,
                    target_entity_id=target,endpoint_state='RESOLVED' if target else 'UNRESOLVED',
                    source_references=c.source_references,epistemic_state=c.epistemic_state))
        for unit in self.units:
            if 'connector' not in unit:continue
            link=unit['connector'];left=next((e for e in self.events if e['source_reference']==link['left_ref']),None)
            right=next((e for e in self.events if e['source_reference']==unit['ref']),None)
            if not left or not right:
                self.unresolved.append('RELATION_ENDPOINT_UNRESOLVED:'+unit['ref']);continue
            domain,kind,reverse=link['kind']
            a,b=(right,left) if reverse else (left,right)
            self.relationships.append(dict(domain=domain,type=kind,source=a['event_id'],target=b['event_id'],
                source_references=[left['source_reference'],right['source_reference']],epistemic_state='ESTABLISHED'))
            if domain=='CAUSAL':
                self.relationships=[r for r in self.relationships if not(r['type']=='UNKNOWN_CAUSE' and r['target']==b['event_id'])]
        self.snapshot('CAUSAL_TEMPORAL_SPATIAL',self.relationships)
        self.snapshot('CHARACTER_KNOWLEDGE_BELIEF',[c.to_dict() for c in self.claims if c.category in {'KNOWLEDGE','BELIEF'}])

    def boundaries(self):
        for source in self.sources:
            current=None
            for unit in (u for u in self.units if u['source_id']==source.source_id):
                if current is None or unit.get('heading'):
                    current={'scene_id':'scene:'+digest([source.source_id,unit['ref']]),'source_id':source.source_id,
                        'source_references':[],'boundary_state':'ESTABLISHED' if unit.get('heading') or source.scene_scope else 'INFERRED',
                        'boundary_reason':'EXPLICIT_HEADING' if unit.get('heading') else 'SELECTED_SCOPE' if source.scene_scope else 'CONTIGUOUS_SELECTED_UNIT',
                        'scope':source.scene_scope or source.story_scope,'events':[]}
                    self.scenes.append(current)
                current['source_references'].append(unit['ref'])
                event=next((e for e in self.events if e['source_reference']==unit['ref']),None)
                if event: current['events'].append(event['event_id']); event['scene_id']=current['scene_id']
                if unit.get('presentation') in {'LATER','MEANWHILE'} and not unit.get('heading'):
                    self.unresolved.append('SCENE_BOUNDARY_AMBIGUOUS:'+unit['ref'])
                if unit.get('verb')=='enters':
                    previous_entries=[e for e in self.events if e.get('scene_id')==current['scene_id'] and e['verb']=='enters' and e['source_reference']!=unit['ref']]
                    if previous_entries and previous_entries[-1]['object']!=unit.get('object'):
                        self.unresolved.append('LOCATION_BOUNDARY_AMBIGUOUS:'+unit['ref'])
        self.snapshot('SCENE_BOUNDARY',self.scenes)

    def beats(self):
        beats=[]
        for event in self.events:
            if not event['material_transition']: continue
            beats.append(dict(beat_id='beat:'+digest(event),event_id=event['event_id'],scene_id=event['scene_id'],
                participants=[event['subject']],pre_state=event['pre_state'],post_state=event['post_state'],
                change={event['state_key']:event['post_state']},source_reference=event['source_reference'],
                epistemic_state=event['epistemic_state'],unresolved=['TRIGGER_UNKNOWN','AUDIENCE_EFFECT_UNRESOLVED']))
        self.snapshot('BEAT_DERIVATION',beats)
        if not beats:self.unresolved.append('NO_SUPPORTED_MATERIAL_TRANSITION')

    def audience(self):
        self.snapshot('AUDIENCE_STATE',[c.to_dict() for c in self.claims if c.category=='AUDIENCE'])
        # On-screen establishes a presentation requirement, not proof of a render.
        for event in self.events:
            if event['presentation'] in {'OFF-SCREEN','OFFSCREEN'}:
                self.unresolved.append('OFFSCREEN_AUDIENCE_ACCESS_UNKNOWN:'+event['event_id'])

    def purposes(self):
        for scene in self.scenes:
            explicit=[c for c in self.claims if c.category=='PURPOSE' and c.source_references[0] in scene['source_references']]
            if explicit: scene['purpose_claim']=explicit[0].claim_id; continue
            events=[e for e in self.events if e['scene_id']==scene['scene_id'] and e['material_transition']]
            if not events: continue
            categories={c.category for c in self.claims if c.claim_id in {e['claim_id'] for e in events}}
            purpose=('establish authority' if 'AUTHORITY' in categories else 'change relationship' if 'RELATIONSHIP' in categories else
                     'reveal information' if 'KNOWLEDGE' in categories else 'transition state')
            c=self.claim('PURPOSE',scene['scene_id'],'scene purpose',purpose,events[0]['source_reference'],'INFERRED','transition-category-purpose')
            scene['purpose_claim']=c.claim_id
        self.snapshot('NARRATIVE_SCENE_PURPOSE',[c.to_dict() for c in self.claims if c.category=='PURPOSE'])

    def reconcile(self):
        # Different assertions within one source may be temporal updates. Between
        # sources no precedence is guessed: retain both and require adjudication.
        for source in self.sources:
            self.unresolved.extend('OPERATOR_CONSTRAINT_REQUIRES_ENFORCEMENT:'+c for c in source.operator_constraints)
        grouped={}
        for c in self.claims:
            if c.category not in {'ENVIRONMENT','PHYSICAL','SPATIAL','IDENTITY','KNOWLEDGE','WORLD_FACT','PURPOSE'}: continue
            if c.category=='PURPOSE' and c.epistemic_state!='ESTABLISHED':continue
            dimension = ('life' if c.predicate in {'dead','alive'} else
                         'knowledge:'+norm(str(c.value)) if c.category=='KNOWLEDGE' else c.predicate)
            key=(c.category,c.subject,dimension)
            grouped.setdefault(key,[]).append(c)
        for values in grouped.values():
            for i,a in enumerate(values):
                for b in values[i+1:]:
                    sa=self.spans[a.source_references[0]]['source_id']; sb=self.spans[b.source_references[0]]['source_id']
                    if sa==sb: continue
                    differs = (a.predicate!=b.predicate if a.category=='KNOWLEDGE' or a.predicate in {'dead','alive'} else a.value!=b.value)
                    if not differs: continue
                    a.epistemic_state=b.epistemic_state='CONFLICTED'
                    self.conflicts.append(dict(source_a=sa,claim_a=a.claim_id,source_b=sb,claim_b=b.claim_id,
                        scope=self.sources[0].story_scope,materiality='MATERIAL',required_authority_for_resolution='OPERATOR_SOURCE_ADJUDICATION'))
        for category,predicate in [('ENVIRONMENT','weather'),('ENVIRONMENT','time of day'),('ENVIRONMENT','architecture'),('CAUSAL','cause')]:
            if not any(c.predicate==predicate for c in self.claims):
                self.claim(category,'story',predicate,None,self.units[0]['ref'],'UNKNOWN','absence-in-selected-scope')
        for eid,entity in self.entities.items():
            for category,predicate in [('OBJECTIVE','motivation'),('RELATIONSHIP','unspecified relationship'),('IDENTITY','identity')]:
                if category=='IDENTITY' and entity['identity'] is not None: continue
                if not any(c.subject==eid and c.category==category for c in self.claims):
                    self.claim(category,eid,predicate,None,entity['refs'][0],'UNKNOWN','absence-in-selected-scope')
        if self.conflicts:self.unresolved.append('SOURCE_CONFLICT_REQUIRES_ADJUDICATION')
        self.snapshot('GOVERNED_STORY_INTERPRETATION',{'claims':[c.to_dict() for c in self.claims], 'conflicts':self.conflicts,'unresolved':self.unresolved})

    def run(self):
        for stage in (self.segment,self.resolve,self.extract_facts,self.extract_events,self.construct_state,
                      self.relate,self.boundaries,self.beats,self.audience,self.purposes,self.reconcile): stage()
        return StoryInterpretation('interpretation:'+digest([s.to_dict() for s in self.sources]),self.sources[0].story_scope,
            self.sources,self.spans,self.claims,self.references,self.events,self.relationships,self.scenes,
            self.stages,sorted(set(self.unresolved)),self.conflicts,self.proposals)
