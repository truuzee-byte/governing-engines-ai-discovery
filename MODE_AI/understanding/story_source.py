"""Selected authoritative prose intake through existing Document custody."""
from .story_contracts import StorySource
from .story_interpretation import StoryInterpreter
from .story_cinematic_handoff import admit


def load_story(docs, owner, request):
    selection=request['story_selection']
    if type(selection) is not dict or set(selection)!={'story_scope','scene_scope','sources','operator_constraints'}:
        raise ValueError('Exact story selection required')
    if (type(selection['sources']) is not list or not 1<=len(selection['sources'])<=16 or
        type(selection['operator_constraints']) is not list or
        any(type(x) is not str or not x.strip() for x in selection['operator_constraints'])):
        raise ValueError('Bounded source selection and explicit constraints required')
    sources=[]; seen=set()
    for item in selection['sources']:
        if type(item) is not dict or set(item)!={'reference','start','end'}: raise ValueError('Exact source range required')
        ref=item['reference']
        if type(ref) is not dict or set(ref)!={'object_id','version','expected_hash'}: raise ValueError('Pinned story reference required')
        record=docs.retrieve(owner,**ref)
        if record['metadata']['project_id']!=request['project_id']: raise PermissionError('Story project mismatch')
        if docs.store.history('DOCUMENT',owner,ref['object_id'])[-1]['record_hash']!=ref['expected_hash']:
            raise PermissionError('Stale story source')
        if record['record_hash'] in seen: raise ValueError('Duplicate story source')
        seen.add(record['record_hash'])
        sources.append(StorySource(record['record_hash'],record['object_id'],record['version'],record['record_hash'],
            record['content_hash'],record['metadata']['authority'],request['project_id'],selection['story_scope'],
            selection['scene_scope'],record['metadata']['kind'],record['content'],item['start'],item['end'],selection['operator_constraints']))
    if selection['sources'][0]['reference']!=request['reference']:raise ValueError('Primary source binding mismatch')
    interpretation=StoryInterpreter(sources).run()
    parsed,lineage=admit(interpretation)
    return interpretation,parsed,lineage
