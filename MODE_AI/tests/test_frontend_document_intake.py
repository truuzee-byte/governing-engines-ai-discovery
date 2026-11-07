import os
import subprocess
import base64
import io
import hashlib
import pytest
from pathlib import Path
from types import SimpleNamespace as NS
from frontend.server import RuntimeViewServer
from memory.thread_memory import ThreadMemory
from integration.content_custody import command
from integration.strict_json import load_payload
from specs.document_extraction import extract
from system_layer.contracts import authorize


@pytest.mark.parametrize('kind',['txt','wav','png'])
def test_selected_document_bytes_reach_custody_only_after_runtime_dispatch(tmp_path,kind):
    raw=b''
    if kind=='wav':
        import wave
        stream=io.BytesIO()
        with wave.open(stream,'wb') as writer:
            writer.setnchannels(1);writer.setsampwidth(2);writer.setframerate(8000);writer.writeframes(b'\0\0'*3)
        raw=stream.getvalue()
    elif kind=='png':
        from PIL import Image
        stream=io.BytesIO()
        with Image.new('RGB',(2,2),(255,0,0)) as image:image.save(stream,format='PNG')
        raw=stream.getvalue()
    thread=ThreadMemory.create('op')
    runtime=NS(context=NS(identity=NS(operator_id='op'),active_thread=thread,runtime_state='IDLE'),
        understanding_engine=NS(store=NS(path=tmp_path/'meaning.db')))
    view=RuntimeViewServer(runtime,operator_input=True)
    dependencies=Path(os.environ.get('MODE_NODE_RUNTIME', 'optional-node-runtime'))
    try:
        result=subprocess.run([str(dependencies/'bin/node.exe'),str(Path(__file__).with_name('frontend_document_intake_smoke.cjs'))],
            env=dict(os.environ,NODE_PATH=str(dependencies/'node_modules'),MODE_VIEW_TEST_URL=view.url,
                MODE_SOURCE_KIND=kind,MODE_SOURCE_BYTES=base64.b64encode(raw).decode()),
            capture_output=True,text=True,timeout=40)
        assert result.returncode==0,'Local document fixture failed; private URL omitted'
        assert not (tmp_path/'content_custody.sqlite3').exists()
        text=view.next_input();data=load_payload(text[len('/documents intake '):])
        authorize('op','DOCUMENT_INTAKE',data['request'],data['approval'])
        assert data['request']['knowledge_class']=='EXTERNAL' and data['request']['kind']=='DRAFT'
        record=command(runtime,text)
        if kind=='txt':assert extract(record['content'])['segments'][0]['text']=='Exact source café\n'*5000
        else:
            from specs.document_service import DocumentService
            docs=DocumentService(tmp_path/'content_custody.sqlite3')
            ref=dict(object_id=record['object_id'],version=record['version'],expected_hash=record['record_hash'])
            assert docs.source_bytes('op',**ref)==(raw,hashlib.sha256(raw).hexdigest())
            with pytest.raises(ValueError,match='no admitted text'):docs.text_source('op',**ref)
            if kind=='png':
                from runtime_observation.frame_inspection import inspect_frames
                assert record['metadata']['visual_authority']=='REFERENCE'
                assert inspect_frames([record['content']])['frames'][0]['rgb_mean']==[255,0,0]
            else:
                from runtime_observation.audio_inspection import inspect_pcm
                assert inspect_pcm(raw,hashlib.sha256(raw).hexdigest())['metrics']['sample_frames']==3
        assert record['metadata']['thread_id']==thread.thread_id and view._input_bytes==0
    finally:view.close()
