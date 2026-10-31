import http.client
import json
from types import SimpleNamespace as NS
from urllib.parse import urlparse,urlencode
from frontend.server import RuntimeViewServer
from runtime_observation.observation_collector import RuntimeObservationCollector
from runtime_observation.observation_store import RuntimeObservationStore
from system_layer.contracts import digest


def test_pinned_observation_view_preserves_history_without_revalidation(tmp_path):
    collector=RuntimeObservationCollector(store=RuntimeObservationStore(tmp_path/'observations'))
    record=collector.collect(operator_id='op',thread_id='t',metadata={'runtime_component':'integration.build_runtime',
        'observed_outcome':{'request_id':'r','state':'UNPROVEN'},'produced_receipts':['receipt:existing']})
    runtime=NS(context=NS(identity=NS(operator_id='op')),runtime_observation_collector=collector)
    view=RuntimeViewServer(runtime);url=urlparse(view.url);token=url.fragment.split('=',1)[1]
    def read(checksum,authorized=True):
        client=http.client.HTTPConnection(url.hostname,url.port,timeout=3)
        try:
            client.request('GET','/observation?'+urlencode({'id':record.observation_id,'hash':checksum}),
                headers={'Authorization':'Bearer '+token} if authorized else {})
            response=client.getresponse();return response.status,response.read()
        finally:client.close()
    try:
        checksum=digest(record.to_dict());assert read(checksum,False)[0]==403
        status,body=read(checksum);value=json.loads(body)
        assert status==200 and value['observation']==record.to_dict()
        assert value['current_validity']=='NOT_REVALIDATED'
        assert read('0'*64)[0]==503
        runtime.context.identity.operator_id='other';assert read(checksum)[0]==403
    finally:view.close()
