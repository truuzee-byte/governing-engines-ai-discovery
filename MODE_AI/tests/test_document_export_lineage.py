import hashlib
from types import SimpleNamespace as NS
import json
from integration.content_custody import execute
from specs.document_service import DocumentService
from system_layer.contracts import digest
from runtime_observation.observation_collector import RuntimeObservationCollector
from runtime_observation.observation_store import RuntimeObservationStore


def test_export_bytes_source_and_observation_survive_round_trip(tmp_path):
    docs=DocumentService(tmp_path/'content_custody.sqlite3')
    request=dict(object_id='source',content='Exact <script>not executed</script> café\n',kind='DRAFT',
        visual_authority='NOT_APPLICABLE',source_reference='operator:1',authority='operator',project_id='p',
        thread_id='t',expected_previous=None,validation_references=[],knowledge_class='EXTERNAL')
    source=docs.intake('op',request,dict(operator_id='op',action='DOCUMENT_INTAKE',decision='APPROVE',hash=digest(request)))
    collector=RuntimeObservationCollector(store=RuntimeObservationStore(tmp_path/'observations'))
    events=[]
    def observe(name,payload,**kwargs):
        events.append(payload)
        return collector.collect(operator_id='op',thread_id='t',metadata={'observed_outcome':payload,
            'output_artifacts':payload['output_artifacts'],'required_evidence_fields':['observed_outcome']})
    runtime=NS(context=NS(identity=NS(operator_id='op')),understanding_engine=NS(store=NS(path=tmp_path/'meaning.db')),
        _observe_runtime_event=observe)
    result=execute(runtime,'/documents export '+json.dumps(dict(object_id='source',version=1,expected_hash=source['record_hash'],format='HTML')))
    raw=result['content'].encode('utf-8')
    assert result['sha256']==hashlib.sha256(raw).hexdigest() and result['byte_length']==len(raw)
    assert '&lt;script&gt;' in result['content'] and not result['rendered_output_observed']
    assert request['content'] not in str(events)
    reference=result['observation_reference'];record=collector.store.load_record('op',reference['observation_id'])
    assert digest(record.to_dict())==reference['expected_hash']
    assert record.output_artifacts[0]['sha256']==result['sha256']
    assert record.output_artifacts[0]['source_reference']['expected_hash']==source['record_hash']
    assert record.output_artifacts[0]['knowledge_class']=='EXTERNAL'
    assert record.output_artifacts[0]['source_transformation']=='SOURCE_TEXT'
    assert record.output_artifacts[0]['extraction'] is None
    assert digest({k:v for k,v in result.items() if k not in {'observation_reference','observation_state'}})==reference['result_payload_hash']
