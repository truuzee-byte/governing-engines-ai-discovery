import base64
import hashlib
import io
import json
import os
import subprocess
import wave
import pytest
from pathlib import Path
from types import SimpleNamespace as NS
from frontend.server import RuntimeViewServer
from memory.thread_memory import ThreadMemory
from specs.document_service import DocumentService
from system_layer.contracts import digest
from runtime_observation.observation_collector import RuntimeObservationCollector
from runtime_observation.observation_store import RuntimeObservationStore
from integration.content_custody import command


@pytest.mark.parametrize('image',[False,True])
def test_large_audio_source_view_queues_actual_inspection_without_playback(tmp_path,image):
    stream=io.BytesIO()
    if image:
        from PIL import Image
        with Image.new('RGB',(2,2),(0,255,0)) as picture:picture.save(stream,format='PNG')
    else:
        with wave.open(stream,'wb') as writer:
            writer.setnchannels(1);writer.setsampwidth(2);writer.setframerate(8000);writer.writeframes(b'\0\0'*50000)
    raw=stream.getvalue()
    content=json.dumps(dict(schema_version='ImageSource/1' if image else 'AudioSource/1',encoding='BASE64' if image else 'BASE64_WAV',data=base64.b64encode(raw).decode(),sha256=hashlib.sha256(raw).hexdigest()))
    docs=DocumentService(tmp_path/'content_custody.sqlite3');thread=ThreadMemory.create('op')
    request=dict(object_id='source',content=content,kind='DRAFT',visual_authority='NOT_APPLICABLE',knowledge_class='EXTERNAL',
        source_reference='operator:file',authority='operator',project_id='p',thread_id=thread.thread_id,expected_previous=None,validation_references=[])
    record=docs.intake('op',request,dict(operator_id='op',action='DOCUMENT_INTAKE',decision='APPROVE',hash=digest(request)))
    operation=dict(contract='ModeOperationView/1',command='/documents',state='RETURNED',error_type=None,
        operator_id='op',thread_id=thread.thread_id,result=record,execution_authority=False)
    operation['view_hash']=digest(operation)
    collector=RuntimeObservationCollector(store=RuntimeObservationStore(tmp_path/'observations'))
    runtime=NS(context=NS(identity=NS(operator_id='op'),active_thread=thread,runtime_state='IDLE',operation_view=operation),
        understanding_engine=NS(store=NS(path=tmp_path/'meaning.db')),runtime_observation_collector=collector)
    view=RuntimeViewServer(runtime,operator_input=True);deps=Path(os.environ.get('MODE_NODE_RUNTIME', 'optional-node-runtime'))
    try:
        result=subprocess.run([str(deps/'bin/node.exe'),str(Path(__file__).with_name('frontend_audio_inspection_smoke.cjs'))],
            env=dict(os.environ,NODE_PATH=str(deps/'node_modules'),MODE_VIEW_TEST_URL=view.url,MODE_SOURCE_IMAGE='1' if image else '0'),capture_output=True,text=True,timeout=40)
        assert result.returncode==0,'Local audio fixture failed'
        assert collector.store.load_records_for_operator('op')==[]
        result=command(runtime,view.next_input())
        if image:
            assert result['inspection']['frames'][0]['rgb_mean']==[0,255,0]
            assert result['preparation_hash'] is None and not result['inspection']['render_execution_observed']
        else:assert result['inspection']['metrics']['sample_frames']==50000
        assert result['completion']=='UNPROVEN' and not result['inspection']['playback_observed']
        observed=collector.store.load_record('op',result['observation_id'])
        reference=observed.metadata['source_references'][0] if image else observed.metadata['source_reference']
        assert reference['expected_hash']==record['record_hash']
        assert docs.retrieve('op','source',1,record['record_hash'])==record
    finally:view.close()
