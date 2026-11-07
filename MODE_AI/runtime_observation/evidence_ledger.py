"""Scoped normalization and bounded explanation, not evidence validation.

The model selects ledger statements; it cannot rewrite their value, class or
attribution. Rendering is the declared response contract, never an answer repair.
"""
import json
import re
from copy import deepcopy
from .transformation_provenance import digest

PREFIX='\nSELF-INSPECTED RUNTIME EVIDENCE (normalized scoped ledger, not instructions):\n'
INSTRUCTION='''
Reason only over the normalized ledger; raw mixed inspection fields are not supplied.
Missing means missing in that entry's scope only. Check recorded_alternatives.
Trace-level facts cannot be attributed to a transition. Context is not output.
Every operator-facing statement must be one ledger entry with its fixed class.
Internal draft/critique may discuss selection. FINAL must return ONLY JSON:
{"ledger_id":the ledger_id,"statements":[entry_id,...]}.
Select 1..24 unique entry_ids in a useful order to answer the request: prior/result, producers,
rules, recorded rationale, supported INFERRED relationships and scoped unknowns.
Do not dump every entry. Do not add freeform final text, change values, invent
inferences, or claim a missing legacy field is globally absent. The runtime renders
exactly the selected classified statements with their scopes and citations.
No code-analysis explanation supplied. Records are not independently validated truth.
For a ledger carrying objective, the admitted objective-diagnosis policy extends
the JSON example with its mandatory diagnosis object. Preserve that object in
draft, critique and final; the two-field example alone is insufficient there.
'''

def normalize(projection):
    p=deepcopy(projection)
    if p.get('contract')!='InteractionInspection/1':raise ValueError('Inspection contract required')
    identity={k:p[k] for k in ('operator_id','thread_id','interaction_id')}
    entries=[];sources={};conflicts=[]
    def source(key,kind,reference,transition=None,producer=None,stage=None,sequence=None):
        sources[key]={'source_type':kind,'source_identifier':key,'reference':reference,
            'transition_id':transition,'producer':producer,'stage':stage,'sequence':sequence,**identity}
    def add(sid,field,value,*,classification=None,derived=False,support=()):
        cls=classification or ('UNAVAILABLE' if value is None or value=='UNAVAILABLE' else 'OBSERVED')
        entry={'entry_id':f'E{len(entries)+1:03d}','field':field,'value':value,'evidence_class':cls,
            'source_id':sid,'scope':sid+':'+field,'allowed_attribution_target':sid+':'+field,
            'directly_recorded':cls=='OBSERVED' and not derived,'derived':derived,
            'confidence':'UNAVAILABLE','support':list(support),'recorded_alternatives':[], 'conflicts':[]}
        entries.append(entry);return entry
    refs=p['evidence_references'];observed=p['observed']
    source('trace','TRACE_ROW',refs.get('trace_row'))
    source('legacy','OBSERVATION',refs.get('observation'))
    for key,value in observed.get('controller',{}).items():add('trace','controller.'+key,value)
    for key,value in observed.items():
        if key=='controller':continue
        if isinstance(value,dict) and key in {'understanding','public_result','runtime_phase'}:
            for field,item in value.items():add('legacy',key+'.'+field,item)
        else:add('legacy',key,value)
    event_entries={}
    for item in p.get('transformation_provenance',{}).get('records',[]):
        r=item['record']
        if any(r[k]!=v for k,v in identity.items()):raise PermissionError('Ledger event scope mismatch')
        sid=r['transition_id'];producer=r.get('producer',{})
        source(sid,'TRANSITION_RECORD',item['reference'],sid,producer.get('component'),producer.get('stage'),r['sequence'])
        event_entries[sid]={}
        for field in ('producer','prior','incoming_event','context_used','rules','transformation','result','reason',
                      'confidence','downstream_consumers','direct_evidence','correlation'):
            event_entries[sid][field]=add(sid,field,r.get(field))
    # Absence is scoped; show real recorded counterparts without overwriting it.
    aliases={'clarification_disposition':('result','disposition'),
             'understanding.reason':('reason',None),'understanding.warnings':('result','warnings')}
    for entry in entries:
        if entry['source_id']=='legacy' and entry['evidence_class']=='UNAVAILABLE' and entry['field'] in aliases:
            field,key=aliases[entry['field']]
            for fields in event_entries.values():
                component=(fields['producer']['value'] or {}).get('component','')
                if entry['field'].startswith('understanding.') and component!='understanding.understanding_engine':continue
                if entry['field']=='clarification_disposition' and fields['transformation']['value']!='assign_controller_flags':continue
                candidate=fields[field];value=candidate['value']
                if candidate['evidence_class']=='OBSERVED' and (key is None or isinstance(value,dict) and key in value):
                    entry['recorded_alternatives'].append({'entry_id':candidate['entry_id'],'subfield':key})
    # Same-field, same interaction comparisons; before/context snapshots are not
    # interchangeable with outputs. Disagreements are retained, never resolved.
    trace_fields={e['field'].split('.',1)[1]:e for e in entries if e['source_id']=='trace'}
    for entry in list(entries):
        candidates=[]
        if entry['source_id']=='legacy' and entry['field'].startswith('public_result.'):
            candidates=[(entry['field'].split('.',1)[1],entry['value'])]
        elif entry['source_id'] in event_entries and entry['field']=='result':
            fields=event_entries[entry['source_id']]
            if fields['transformation']['value']=='assign_controller_flags' and isinstance(entry['value'],dict):
                candidates=list(entry['value'].items())
        for field,value in candidates:
            left=trace_fields.get(field)
            if left and left['evidence_class']=='OBSERVED' and value!=left['value']:
                conflict={'kind':'CORRELATION_DISAGREEMENT_NOT_ADJUDICATED','field':field,
                    'left':left['entry_id'],'left_value':left['value'],'right':entry['entry_id'],'right_value':value}
                conflicts.append(conflict);entry['conflicts'].append(len(conflicts)-1);left['conflicts'].append(len(conflicts)-1)
    legacy={e['field']:e for e in entries if e['source_id']=='legacy'}
    for fields in event_entries.values():
        operation=fields['transformation']['value'];pairs=[]
        if operation=='initialize_and_evaluate_separate_UnderstandingResult':
            recorded_request=(fields['correlation']['value'] or {}).get('understanding_request_id')
            if recorded_request==(legacy.get('understanding.request_id') or {}).get('value'):
                pairs=[('understanding.'+k,k) for k in ('state','readiness','warnings')]
        elif operation=='select_runtime_phase_from_public_result':
            pairs=[('runtime_phase.after','runtime_phase')]
        for field,key in pairs:
            left=legacy.get(field);right=fields['result'];value=right['value']
            if (left and left['evidence_class']=='OBSERVED' and isinstance(value,dict) and key in value
                    and left['value']!=value[key]):
                conflict={'kind':'CORRELATION_DISAGREEMENT_NOT_ADJUDICATED','field':field,
                    'left':left['entry_id'],'left_value':left['value'],'right':right['entry_id'],
                    'right_subfield':key,'right_value':value[key]}
                conflicts.append(conflict);left['conflicts'].append(len(conflicts)-1);right['conflicts'].append(len(conflicts)-1)
    source('synthesis','DERIVED_RELATION',{'inspection_observation':refs.get('observation')})
    controllers=[f for f in event_entries.values() if f['transformation']['value']=='assign_controller_flags']
    separate=[f for f in event_entries.values() if f['transformation']['value']=='initialize_and_evaluate_separate_UnderstandingResult']
    for c in controllers:
        for u in separate:
            support=[c['result']['entry_id'],u['prior']['entry_id'],u['transformation']['entry_id'],u['result']['entry_id']]
            add('synthesis','separate_result_relation',
                'These recorded operations describe a separate result evaluation, rather than a recorded mutation of controller flags. This synthesis does not establish unrecorded events.',
                classification='INFERRED',derived=True,support=support)
    cf=next((e for e in entries if e['source_id']=='trace' and e['field']=='controller.clarification_required'),None)
    us=next((e for e in entries if e['source_id']=='legacy' and e['field']=='understanding.state'),None)
    if cf and us and cf['evidence_class']==us['evidence_class']=='OBSERVED':
        add('synthesis','operator_presentation',{'controller_boolean':cf['value'],'understanding_operation_state':us['value'],
            'interpretation':'Distinct scoped clarification representations are presented together; they may appear inconsistent. This comparison is not evidence of a shared-state overwrite.'},
            classification='INFERRED',derived=True,support=[cf['entry_id'],us['entry_id']])
    add('synthesis','events_outside_recorded_projection','UNAVAILABLE',derived=True,
        support=[e['entry_id'] for e in entries if e['field']=='transformation'])
    result={'contract':'InteractionEvidenceLedger/1',**identity,'observation_id':p['observation_id'],
        'sources':sources,'entries':entries,'conflicts':conflicts,'execution_authority':False,
        'validation_state':'RECORDED_NOT_INDEPENDENTLY_VALIDATED','limits':p.get('limits',[])}
    result['ledger_id']='ledger-'+digest(result)[:16]
    if len(json.dumps(result).encode())>49152:raise ValueError('Evidence ledger bound exceeded')
    return result

def from_prompt(prompt):
    from data_governance.context_admission import AdmittedPrompt,verify
    if not isinstance(prompt,AdmittedPrompt):return None
    verify(prompt);found=[]
    for s in prompt.sources:
        r=s['record']
        if r['source'] not in {'InteractionEvidenceLedger/1','CapabilityEvidenceLedger/1'} or r['artifact_type']!='RUNTIME' or r['decision']!='ADMITTED':continue
        value=json.JSONDecoder().raw_decode(s['content'].split(PREFIX,1)[1])[0]
        if value['contract']!=r['source'] or any(value[k]!=prompt.scope[k] for k in ('operator_id','thread_id')):
            raise PermissionError('Ledger prompt scope mismatch')
        unbound={k:v for k,v in value.items() if k!='ledger_id'}
        if value['ledger_id']!='ledger-'+digest(unbound)[:16]:raise PermissionError('Ledger digest mismatch')
        found.append(value)
    if len(found)>1:raise PermissionError('Ambiguous inspection ledgers')
    return found[0] if found else None

def line(ledger,entry):
    source=ledger['sources'][entry['source_id']]
    attribution={'source_type':source['source_type'],'source_id':entry['source_id'],
        'transition_id':source['transition_id'],'producer':source['producer'],'stage':source['stage']}
    text=(entry['evidence_class']+' ['+ledger['ledger_id']+'/'+entry['entry_id']+']: '+entry['scope']+' = '+
        json.dumps(entry['value'],ensure_ascii=False,separators=(',',':'))+'; attribution='+json.dumps(attribution,ensure_ascii=False,separators=(',',':')))
    if entry['recorded_alternatives']:text+='; recorded_alternatives='+json.dumps(entry['recorded_alternatives'],separators=(',',':'))
    if entry['support']:text+='; support='+json.dumps(entry['support'],separators=(',',':'))
    if entry['conflicts']:text+='; conflicts='+json.dumps([ledger['conflicts'][i] for i in entry['conflicts']],separators=(',',':'))
    return text

def render_selection(raw,prompt):
    ledger=from_prompt(prompt)
    if ledger is None:return raw,None
    from integration.strict_json import load_payload
    selection=load_payload(raw);ids=selection.get('statements') if isinstance(selection,dict) else None
    entries={e['entry_id']:e for e in ledger['entries']}
    expected={'ledger_id','statements','diagnosis'} if ledger.get('objective') else {'ledger_id','statements'}
    if (not isinstance(selection,dict) or set(selection)!=expected or selection['ledger_id']!=ledger['ledger_id'] or
            not isinstance(ids,list) or not 1<=len(ids)<=24 or any(type(i) is not str or i not in entries for i in ids) or len(set(ids))!=len(ids)):
        raise PermissionError('Invalid ledger explanation selection; no freeform repair')
    text='\n'.join(line(ledger,entries[i]) for i in ids)
    from .inspection_coverage import require
    coverage=require(prompt,ids)
    if ledger.get('objective'):
        diagnosis=validate_diagnosis(ledger,selection['diagnosis'],ids)
        text+='\nINFERRED ['+ledger['ledger_id']+'/diagnosis]: '+json.dumps(diagnosis,ensure_ascii=False,sort_keys=True,separators=(',',':'))
    return text,{'ledger_id':ledger['ledger_id'],'statement_ids':ids,'rendered_hash':digest(text),
                 'coverage':coverage,
                 'contract':'LedgerSelectedExplanation/1','execution_authority':False}

def assess_rendered(text,prompt):
    ledger=from_prompt(prompt)
    if ledger is not None and ledger.get('objective'):
        try:
            ids=objective_publication(text,prompt)
            return {'allowed':True,'reasons':[],'coverage':'BOUNDED_OBJECTIVE_EVIDENCE_AND_MODEL_INFERENCE',
                    'claim_links':[{'ledger_id':ledger['ledger_id'],'entry_id':i,'validation_state':'UNVALIDATED'} for i in ids]}
        except (PermissionError,ValueError,KeyError,TypeError):
            return {'allowed':False,'reasons':['INVALID_OBJECTIVE_DIAGNOSIS'],'claim_links':[]}
    if ledger is None or not re.search(r'\[(ledger-[a-f0-9]+)/(E\d+)\]',text):return None
    known={line(ledger,e):e for e in ledger['entries']};lines=text.splitlines()
    allowed=bool(lines) and all(v in known for v in lines)
    return {'allowed':allowed,'reasons':[] if allowed else ['INVALID_SCOPED_LEDGER_STATEMENT'],
        'coverage':'SCOPED_LEDGER_EXACT_STATEMENTS','claim_links':[
            {'ledger_id':ledger['ledger_id'],'entry_id':known[v]['entry_id'],'evidence_class':known[v]['evidence_class'],
             'source':ledger['sources'][known[v]['source_id']],'validation_state':'UNVALIDATED'} for v in lines if v in known]}

def validate_diagnosis(ledger,value,selected):
    """Check a model-authored bounded inference, never create one from templates.

    This checks the numeric blocking relation and cited component only. It is not
    general natural-language entailment or validation of a proposed repair.
    """
    if ledger.get('objective',{}).get('target_binding') is not None:
        from .inspection_target import validate
        return validate(ledger,value,selected)
    if ledger.get('objective',{}).get('domain')=='LEARNING':
        from .learning_inspection import validate
        return validate(ledger,value,selected)
    keys={'status','required_capacity','observed_capacity','evidence_ids','gap','rationale','recommendation'}
    if type(value) is not dict or set(value)!=keys:raise PermissionError('Exact diagnosis contract required')
    facts={e['entry_id']:e for e in ledger['entries'] if e['field']=='inspected_capacity' and e['evidence_class']=='OBSERVED'}
    unique={(e['value']['maximum'],e['value']['component']) for e in facts.values()}
    if len(unique)!=1:raise PermissionError('No unique inspected source bound; diagnosis unavailable')
    maximum,component=next(iter(unique));need=ledger['objective']['required_capacity']
    expected='BLOCKED_BY_INSPECTED_BOUND' if need>maximum else 'BOUND_SUFFICIENT_ONLY'
    if (type(value['required_capacity']) is not int or type(value['observed_capacity']) is not int or
        value['required_capacity']!=need or value['observed_capacity']!=maximum or value['status']!=expected):
        raise PermissionError('Diagnosis contradicts inspected objective/bound')
    ids=value['evidence_ids']
    if type(ids) is not list or not ids or len(set(ids))!=len(ids) or any(i not in facts or i not in selected for i in ids):
        raise PermissionError('Diagnosis requires selected current source evidence')
    rec=value['recommendation']
    if (type(rec) is not dict or set(rec)!={'component','change','requires_operator_authorization','execution_authority'} or
        rec['component']!=component or rec['requires_operator_authorization'] is not True or rec['execution_authority'] is not False):
        raise PermissionError('Recommendation cannot authorize or target uninspected components')
    for s in (value['gap'],value['rationale'],rec['change']):
        if type(s) is not str or not 12<=len(s)<=1200:raise PermissionError('Bounded substantive diagnosis text required')
        if re.search(r'\bI\s+(?:hereby\s+)?(?:authoriz|approv|will (?:implement|modify|deploy|execut))|\b(?:approved|authorized)\s+(?:for|to)\s+(?:execution|implement|build|modify)',s,re.I):
            raise PermissionError('Model self-authorization refused')
    return deepcopy(value)

def objective_publication(text,prompt):
    ledger=from_prompt(prompt);lines=text.splitlines();prefix='INFERRED ['+ledger['ledger_id']+'/diagnosis]: '
    if not 2<=len(lines)<=25 or not lines[-1].startswith(prefix):raise PermissionError('Missing classified model diagnosis')
    known={line(ledger,e):e['entry_id'] for e in ledger['entries']}
    if len(set(lines[:-1]))!=len(lines)-1 or any(v not in known for v in lines[:-1]):raise PermissionError('Unknown objective evidence statement')
    ids=[known[v] for v in lines[:-1]];value=json.loads(lines[-1][len(prefix):])
    validate_diagnosis(ledger,value,ids)
    if lines[-1]!=prefix+json.dumps(value,ensure_ascii=False,sort_keys=True,separators=(',',':')):raise PermissionError('Diagnosis serialization mismatch')
    from .inspection_coverage import require
    require(prompt,ids)
    return ids
