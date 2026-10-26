"""Pre-inference accountability, not truth/equivalence certification.

Only exact identity of a complete scoped PRIMARY_RECORD representation supports
an automatic representative. No similarity, size, publication or model judgment
can establish equivalence here. All other materiality remains unknown/retained.
"""
from copy import deepcopy
import json,re
from .transformation_provenance import digest

LIMIT=90000


def _identity(entry,source):
    ref=source.get('reference',{})
    if (source.get('source_type')!='PRIMARY_RECORD' or not source.get('temporal_scope')
            or not isinstance(ref,dict) or not all(ref.get(k) for k in ('path','sha256','locator'))
            or not re.fullmatch('[0-9a-f]{64}',str(ref['sha256']))
            or entry.get('derived') is not False or entry.get('directly_recorded') is not True):
        return None
    # Exact full metadata/value identity, not matching words or source labels.
    payload={k:v for k,v in entry.items() if k not in {'entry_id','source_id'}}
    return digest({'entry':payload,'source':source})


def evaluate(ledger):
    """Return an immutable-copy projection and accountability before byte gating.

    Input is the existing internal normalized ledger, not model exclusion claims.
    PRIMARY_RECORD is a custody descriptor, never independent truth validation.
    Different evidence/authority/time/uncertainty is never silently merged.
    """
    universe=deepcopy(ledger)
    entries=universe['entries'];ids=[e['entry_id'] for e in entries]
    if len(ids)!=len(set(ids)):raise ValueError('Duplicate evidence IDs')
    decisions=[];seen={};kept=[]
    for entry in entries:
        eid=entry['entry_id'];source=universe['sources'].get(entry['source_id'],{})
        key=_identity(entry,source);representative=seen.get(key) if key is not None else None
        # Do not remove IDs named by another entry/objective/dependency. The
        # caller does not rewrite evidence references to make selection succeed.
        external={k:v for k,v in universe.items() if k!='entries'}
        external['entries']=[e for e in entries if e['entry_id']!=eid]
        if representative and eid in json.dumps(external):representative=None
        represented=representative is not None
        if not represented:
            kept.append(entry)
            if key is not None:seen.setdefault(key,eid)
        decisions.append({'evidence_item_id':eid,'decision':'EXCLUDE_REPRESENTED' if represented else 'INCLUDE',
            'materiality_state':'REPRESENTED BY RETAINED EVIDENCE' if represented else 'UNKNOWN MATERIALITY',
            'basis':'EXACT_SCOPED_PRIMARY_RECORD_IDENTITY' if represented else 'NO_ADMISSIBLE_EXCLUSION_PROOF',
            'representative':representative,'source_locator':deepcopy(source),
            'entry_hash':digest(entry),'objective_specific_rationale':
                'Same complete source-bound representation remains under representative; no independent evidence discarded'
                if represented else 'Unique contribution, objective dependency or equivalence not resolved; retain',
            'preservation':{k:'EXACT_SAME_REPRESENTATION' if represented else 'RETAINED_NOT_ADJUDICATED'
                for k in ('provenance','contradictions','failures','temporal_scope','authority_qualification','uncertainty')},
            'uncertainty_remaining':'Underlying truth remains unverified; no generic semantic comparison performed'})
    selected=deepcopy(universe);selected['entries']=kept
    excluded=[d['evidence_item_id'] for d in decisions if d['decision']=='EXCLUDE_REPRESENTED']
    if excluded:
        selected.pop('ledger_id',None);selected['ledger_id']='ledger-'+digest(selected)[:16]
    size=len(json.dumps(selected).encode())
    receipt={'contract':'PreInferenceMateriality/1','objective_id':universe.get('objective',{}).get('query_hash'),
        'owner':universe.get('operator_id'),'thread':universe.get('thread_id'),
        'universe_ledger_id':universe.get('ledger_id'),'universe_hash':digest(universe),'universe_count':len(entries),
        'universe_scope':'SUPPLIED_NORMALIZED_LEDGER_ONLY_NOT_ALL_DIAGNOSTIC_HISTORY',
        'retained_ids':[e['entry_id'] for e in kept],'excluded_ids':excluded,'decisions':decisions,
        'accountability':'ALL_SUPPLIED_IDS_ACCOUNTED; NOT_A_MATERIAL_SUFFICIENCY_CERTIFICATE',
        'sufficiency_state':'MATERIALITY_UNRESOLVED_RETAINED; SOURCE_UNIVERSE_LIMITS_UNCHANGED',
        'package_bytes':size,'limit_bytes':LIMIT,'size_gate':'BLOCK' if size>LIMIT else 'WITHIN_BOUND_ONLY',
        'evidence_validation_authority':False,'execution_authority':False}
    return {'universe':universe,'ledger':selected,'receipt':receipt}
