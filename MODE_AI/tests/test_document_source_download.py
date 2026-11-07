import base64
import hashlib
import http.client
import json
from types import SimpleNamespace as NS
from urllib.parse import urlparse,parse_qs,urlencode
from frontend.server import RuntimeViewServer
from specs.document_service import DocumentService
from system_layer.contracts import digest


def test_authenticated_exact_source_download_and_hash_mismatch_denial(tmp_path):
    raw=b'original source\x00\xff\x80';checksum=hashlib.sha256(raw).hexdigest()
    content=json.dumps(dict(schema_version='DocumentBinary/1',format='PDF',encoding='BASE64',data=base64.b64encode(raw).decode(),sha256=checksum))
    docs=DocumentService(tmp_path/'content_custody.sqlite3')
    request=dict(object_id='source',content=content,kind='DRAFT',visual_authority='NOT_APPLICABLE',knowledge_class='EXTERNAL',
        source_reference='operator:file',authority='operator',project_id='p',thread_id='t',expected_previous=None,validation_references=[])
    record=docs.intake('op',request,dict(operator_id='op',action='DOCUMENT_INTAKE',decision='APPROVE',hash=digest(request)))
    runtime=NS(context=NS(identity=NS(operator_id='op')),understanding_engine=NS(store=NS(path=tmp_path/'meaning.db')))
    view=RuntimeViewServer(runtime);url=urlparse(view.url);token=parse_qs(url.fragment)['access'][0]
    def get(hash_value,authorized=True):
        client=http.client.HTTPConnection(url.hostname,url.port,timeout=3)
        try:
            client.request('GET','/document-source?'+urlencode(dict(object_id='source',version=1,hash=hash_value)),
                headers={'Authorization':'Bearer '+token} if authorized else {})
            response=client.getresponse();return response.status,dict(response.getheaders()),response.read()
        finally:client.close()
    try:
        assert get(record['record_hash'],False)[0]==403
        status,headers,download=get(record['record_hash'])
        assert status==200 and download==raw
        assert headers['X-Content-SHA256']==checksum and headers['X-Source-Record-Hash']==record['record_hash']
        assert headers['Content-Disposition'].startswith('attachment;')
        assert get('0'*64)[0]==503
        assert docs.retrieve('op','source',1,record['record_hash'])==record
    finally:view.close()
