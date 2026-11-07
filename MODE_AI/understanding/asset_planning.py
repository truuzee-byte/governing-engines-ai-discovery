"""Search existing custody before an explicit reuse/modify/create plan.

Creative v1.2 §§8–10. A plan does not license an asset, establish quality,
execute construction/import, or accept a production outcome.
"""
from copy import deepcopy
from system_layer.contracts import authorize,digest


def search(creative,owner,preparation,query):
    creative._check_preparation(owner,preparation)
    found=creative.documents.search(owner,query,preparation['request']['project_id'],limit=100)
    candidates=[m for m in found['matches'] if m['kind'] in {'PRODUCTION_ASSET','GENERATED_CANDIDATE','CONCEPT_ART'}]
    value={'contract':'CreativeAssetSearch/1','preparation_hash':preparation['preparation_hash'],
        'search':found,'candidates':candidates,'selection':None,'suitability':'NOT_EVALUATED',
        'absence_proven':False,'execution_authority':False}
    value['search_hash']=digest(value)
    return value


def plan(creative,owner,preparation,request,approval):
    creative._check_preparation(owner,preparation)
    required={'preparation_hash','model_reference','query','search_hash','choice','asset_reference','rationale'}
    if type(request) is not dict or set(request)!=required:raise ValueError('Complete asset plan selection required')
    authorize(owner,'CREATIVE_ASSET_PLAN',request,approval)
    if request['preparation_hash']!=preparation['preparation_hash']:raise ValueError('Asset preparation changed')
    if request['choice'] not in {'REUSE','MODIFY','CREATE'} or type(request['rationale']) is not str or not request['rationale'].strip():
        raise ValueError('Explicit asset decision and rationale required')
    models=[m for m in preparation['shared_models'] if m['definition_reference']==request['model_reference'] and m['kind']=='ASSET']
    if len(models)!=1:raise ValueError('Select one prepared shared asset model')
    current=search(creative,owner,preparation,request['query'])
    if current['search_hash']!=request['search_hash']:raise ValueError('Asset search changed; selection must be reviewed')
    selected=None
    if request['choice']=='CREATE':
        if request['asset_reference'] is not None:raise ValueError('CREATE cannot silently modify an existing asset')
    else:
        matches=[m for m in current['candidates'] if m['reference']==request['asset_reference']]
        if len(matches)!=1:raise ValueError('Reuse/modify source must be an exact discovered candidate')
        selected=creative.documents.retrieve(owner,**request['asset_reference'])
    definition=models[0]['definition']
    if definition['reuse_modify_create']!=request['choice']:
        raise ValueError('Asset decision contradicts the prepared definition')
    return {'contract':'CreativeAssetPlan/1','request':deepcopy(request),'search':current,
        'asset_definition':deepcopy(models[0]),'selected_source':selected,
        'required_stages':['ASSET_SPECIFICATION','CONSTRUCTION_OR_REUSE','TECHNICAL_VALIDATION','CREATIVE_VALIDATION',
            'OPTIMIZATION','IMPORT','INTEGRATION','OBSERVED_OUTPUT','ACCEPTANCE'],
        'unresolved_definition_fields':list(models[0]['unresolved']),
        'search_incomplete':current['search']['search_completeness']!='COMPLETE_FOR_SELECTED_NAMESPACE' or current['search']['results_limited'],
        'state':'PLAN_ONLY','licensing':'NOT_VALIDATED','completion':'UNPROVEN','execution_authority':False}
