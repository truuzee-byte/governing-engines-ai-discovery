"""Loopback presentation and opt-in input queue; HTTP never executes commands.

The per-instance token authorizes reading this operator's displayed conversation.
It is not a Kernel credential, grant, persistent identity or RP authority.
"""
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
import hmac
import json
import secrets
import threading
import queue
from .runtime_view import snapshot, history, thread_view, observation_view, operation_export
from urllib.parse import urlsplit,parse_qs


class RuntimeViewServer:
    def __init__(self, runtime, *, operator_input=False):
        if type(operator_input) is not bool:raise ValueError('Explicit input mode required')
        self.runtime = runtime
        self.owner = runtime.context.identity.operator_id
        self._token = secrets.token_urlsafe(32)
        self.operator_input=operator_input
        self._input_token=secrets.token_urlsafe(32) if operator_input else None
        self._inputs=queue.Queue(maxsize=32)
        self._input_ids=set()
        self._input_lock=threading.Lock()
        self._input_bytes=0
        root = Path(__file__).parent
        owner = self

        class Handler(BaseHTTPRequestHandler):
            def log_message(self, *args):
                pass  # No URL, token, conversation or request logging.

            def send(self, status, body=b'', content_type='text/plain; charset=utf-8'):
                self.send_response(status)
                self.send_header('Content-Type', content_type)
                self.send_header('Content-Length', str(len(body)))
                self.send_header('Cache-Control', 'no-store')
                self.send_header('X-Content-Type-Options', 'nosniff')
                self.send_header('Content-Security-Policy', "default-src 'self'; connect-src 'self'; frame-ancestors 'none'; object-src 'none'")
                self.end_headers()
                self.wfile.write(body)

            def do_GET(self):
                expected_host = '127.0.0.1:' + str(owner.server.server_port)
                if self.headers.get('Host') != expected_host:
                    return self.send(403)
                origin = self.headers.get('Origin')
                if origin is not None and origin != 'http://' + expected_host:
                    return self.send(403)
                parsed=urlsplit(self.path)
                if self.path in {'/state','/history'} or parsed.path in {'/thread','/observation','/document-source','/operation-export'}:
                    supplied = self.headers.get('Authorization', '')
                    if not hmac.compare_digest(supplied, 'Bearer ' + owner._token):
                        return self.send(403)
                    try:
                        if owner.runtime.context.identity.operator_id != owner.owner:
                            return self.send(403)
                        if parsed.path=='/operation-export':
                            query=parse_qs(parsed.query,strict_parsing=True)
                            if set(query)!={'hash'} or len(query['hash'])!=1:return self.send(400)
                            raw,checksum=operation_export(owner.runtime,query['hash'][0],expected_owner=owner.owner)
                            self.send_response(200)
                            self.send_header('Content-Type','application/octet-stream')
                            self.send_header('Content-Disposition','attachment; filename="mode-export-'+checksum+'.bin"')
                            self.send_header('Content-Length',str(len(raw)))
                            self.send_header('X-Content-SHA256',checksum)
                            self.send_header('Cache-Control','no-store')
                            self.send_header('X-Content-Type-Options','nosniff')
                            self.end_headers();self.wfile.write(raw);return
                        elif parsed.path=='/document-source':
                            query=parse_qs(parsed.query,strict_parsing=True)
                            if set(query)!={'object_id','version','hash'} or any(len(v)!=1 for v in query.values()):return self.send(400)
                            path=owner.runtime.understanding_engine.store.path.with_name('content_custody.sqlite3')
                            if not path.is_file():return self.send(404)
                            from specs.document_service import DocumentService
                            raw,checksum=DocumentService(path).source_bytes(owner.owner,query['object_id'][0],int(query['version'][0]),query['hash'][0])
                            self.send_response(200)
                            self.send_header('Content-Type','application/octet-stream')
                            self.send_header('Content-Disposition','attachment; filename="mode-source-'+checksum+'.bin"')
                            self.send_header('Content-Length',str(len(raw)))
                            self.send_header('X-Content-SHA256',checksum)
                            self.send_header('X-Source-Record-Hash',query['hash'][0])
                            self.send_header('Cache-Control','no-store')
                            self.send_header('X-Content-Type-Options','nosniff')
                            self.end_headers();self.wfile.write(raw);return
                        elif parsed.path=='/observation':
                            query=parse_qs(parsed.query,strict_parsing=True)
                            if set(query)!={'id','hash'} or any(len(v)!=1 for v in query.values()):return self.send(400)
                            value=observation_view(owner.runtime,query['id'][0],query['hash'][0],expected_owner=owner.owner)
                        elif parsed.path=='/thread':
                            query=parse_qs(parsed.query,strict_parsing=True)
                            if set(query)!={'id'} or len(query['id'])!=1:return self.send(400)
                            value=thread_view(owner.runtime,query['id'][0],expected_owner=owner.owner)
                        else:
                            projection=snapshot if self.path=='/state' else history
                            value=projection(owner.runtime, expected_owner=owner.owner)
                        payload = json.dumps(value, ensure_ascii=False).encode('utf-8')
                    except Exception:
                        return self.send(503, b'Runtime view unavailable')
                    return self.send(200, payload, 'application/json; charset=utf-8')
                files = {'/':('index.html','text/html'), '/app.js':('app.js','text/javascript'), '/style.css':('style.css','text/css')}
                if self.path not in files:
                    return self.send(404)
                name, media = files[self.path]
                return self.send(200, (root / name).read_bytes(), media+'; charset=utf-8')

            def do_POST(self):
                if self.path!='/input' or not owner.operator_input:return self.send(405)
                expected='127.0.0.1:'+str(owner.server.server_port)
                if self.headers.get('Host')!=expected or self.headers.get('Origin')!='http://'+expected:return self.send(403)
                if not hmac.compare_digest(self.headers.get('Authorization',''),'Bearer '+owner._input_token):return self.send(403)
                if self.headers.get('Content-Type')!='application/json':return self.send(400)
                try:
                    self.connection.settimeout(5)
                    size=int(self.headers.get('Content-Length','0'))
                    if not 0<size<=12*1024*1024:return self.send(413)
                    def unique(pairs):
                        value={}
                        for key,item in pairs:
                            if key in value:raise ValueError('Duplicate input field')
                            value[key]=item
                        return value
                    data=json.loads(self.rfile.read(size),object_pairs_hook=unique)
                    if type(data) is not dict or not {'request_id','thread_id','text'}.issubset(data) or set(data)-{'request_id','thread_id','text','pending_action_id'}:return self.send(400)
                    if any(type(data[k]) is not str or not data[k].strip() for k in data):return self.send(400)
                    if len(data['request_id'])>128:return self.send(400)
                    if size>65536 and not data['text'].startswith('/documents intake '):return self.send(413)
                    if owner.runtime.context.identity.operator_id!=owner.owner or data['thread_id']!=owner.runtime.context.active_thread.thread_id:return self.send(409)
                    pending=getattr(getattr(owner.runtime,'pending_action',None),'action_id',None)
                    if 'pending_action_id' in data and data['pending_action_id']!=pending:return self.send(409)
                    data['_pending_action_id']=pending
                    data['_queued_bytes']=size
                    with owner._input_lock:
                        if data['request_id'] in owner._input_ids:return self.send(409)
                        if len(owner._input_ids)>=1024:return self.send(429)
                        if owner._input_bytes+size>24*1024*1024:return self.send(429)
                        owner._inputs.put_nowait(data)
                        owner._input_bytes+=size
                        owner._input_ids.add(data['request_id'])
                    return self.send(202,json.dumps({'queued':True,'request_id':data['request_id']}).encode(),'application/json')
                except queue.Full:return self.send(429)
                except (ValueError,UnicodeError,OSError):return self.send(400)

        self.server = ThreadingHTTPServer(('127.0.0.1', 0), Handler)
        self.thread = threading.Thread(target=self.server.serve_forever, name='ModeRuntimeView', daemon=True)
        self.thread.start()

    @property
    def url(self):
        suffix='&operator_access='+self._input_token if self.operator_input else ''
        return f'http://127.0.0.1:{self.server.server_port}/#access={self._token}'+suffix

    def next_input(self):
        """Main-runtime thread only; HTTP handlers cannot execute the queued text."""
        if not self.operator_input:raise PermissionError('Input mode not enabled')
        data=self._inputs.get()
        if data is None:return 'exit'
        with self._input_lock:self._input_bytes-=data.get('_queued_bytes',0)
        if self.runtime.context.identity.operator_id!=self.owner or data['thread_id']!=self.runtime.context.active_thread.thread_id:
            raise PermissionError('Queued Operator input scope changed')
        if data.get('_pending_action_id')!=getattr(getattr(self.runtime,'pending_action',None),'action_id',None):
            raise PermissionError('Queued consent context changed')
        return data['text']

    def close(self):
        if self.operator_input:
            while True:
                try:self._inputs.get_nowait()
                except queue.Empty:break
            self._inputs.put_nowait(None)
            with self._input_lock:self._input_bytes=0
        self.server.shutdown()
        self.server.server_close()
        self.thread.join(timeout=5)
        self._token = ''
        self._input_token=''
