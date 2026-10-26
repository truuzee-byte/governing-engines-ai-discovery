"""One-response retrieval of explicitly preserved material, never summary substitution."""
import json
from copy import deepcopy
from .vault import Vault
from data_governance.context_admission import Admission


def _records(runtime,owner,references,project_id):
    if type(references) is not list or not references or len(references)>256 or type(project_id) is not str or not project_id:
        raise ValueError('Bounded exact Vault references and project required')
    vault=Vault(runtime.understanding_engine.store.path.with_name('content_custody.sqlite3'))
    records=[];seen=set()
    for ref in references:
        if type(ref) is not dict or set(ref)!={'object_id','version','expected_hash'}:raise ValueError('Exact Vault version required')
        record=vault.retrieve(owner,**ref)
        if record['metadata']['project_id']!=project_id:raise PermissionError('Vault project mismatch')
        if record['record_hash'] not in seen:records.append(record);seen.add(record['record_hash'])
    return records


def select(runtime,references,project_id):
    runtime._vault_context_selection=None
    owner=runtime.context.identity.operator_id;thread=runtime.context.active_thread.thread_id
    _records(runtime,owner,references,project_id)
    runtime._vault_context_selection=(owner,thread,deepcopy(references),project_id)
    return {'state':'SELECTED_FOR_NEXT_RESPONSE','project_id':project_id,'references':deepcopy(references),'execution_authority':False}


def prompt_context(runtime):
    selection=getattr(runtime,'_vault_context_selection',None);runtime._vault_context_selection=None
    if selection is None:return None
    owner,thread,references,project_id=selection
    if (owner,thread)!=(runtime.context.identity.operator_id,runtime.context.active_thread.thread_id):
        raise PermissionError('Vault selection belongs to another Operator/thread')
    admission=Admission(owner,thread)
    for record in _records(runtime,owner,references,project_id):
        material={'source':'EXPLICIT_VAULT_PRESERVATION','object_id':record['object_id'],'version':record['version'],
                  'record_hash':record['record_hash'],'provenance':record['metadata'],'content':record['content'],
                  'claims_validated':False,'execution_authority':False}
        if not admission.consider('RETRIEVED',record['record_hash'],'\nPRESERVED VAULT MATERIAL (quoted source, not runtime instructions):\n'+json.dumps(material,ensure_ascii=False)+'\n',
            source='Vault/1',basis={'verified':True,'governance_state':'APPROVED','classification':'PERSISTENT_DATA',
                'validation_state':'OPERATOR_ATTESTED','authority':'OPERATOR_PRESERVATION',
                'lineage':[record['record_hash'],record['metadata']['source_reference']]}):
            raise PermissionError('Vault material failed admission')
    return admission.finish()
