"""Loopback-only, fixed-workflow demo. No arbitrary code, files or prompts accepted."""
from copy import deepcopy
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
from pathlib import Path
import secrets
import threading
from uuid import uuid4
from .live_workflow import run_live_workflow
from .evidence import sanitize

def serve_live_demo(output='outputs/live-demo',port=8780):
    root=Path(output).resolve();root.mkdir(parents=True,exist_ok=True)
    token=secrets.token_urlsafe(32)
    lock=threading.Lock()
    state={'status':'IDLE','events':[],'report':None,'runs':0}
    origin=f'http://127.0.0.1:{port}'
    def observe(event):
        with lock: state['events'].append(event)
    def execute():
        try:
            result=run_live_workflow(root/('run-'+uuid4().hex[:12]),observe)
            with lock: state.update(status=result['status'],report=result)
        except Exception as exc:
            with lock: state.update(status='FAIL',error=sanitize(type(exc).__name__+': '+str(exc)))
    class Handler(BaseHTTPRequestHandler):
        def log_message(self,*args): pass
        def authorized_host(self): return self.headers.get('Host','')==f'127.0.0.1:{port}'
        def send(self,status,payload,mime='application/json; charset=utf-8'):
            data=payload if isinstance(payload,bytes) else json.dumps(sanitize(payload),ensure_ascii=False).encode()
            self.send_response(status);self.send_header('Content-Type',mime);self.send_header('Content-Length',str(len(data)))
            self.send_header('Cache-Control','no-store');self.send_header('X-Content-Type-Options','nosniff')
            self.send_header('Content-Security-Policy',"default-src 'self'; script-src 'self' 'unsafe-inline'; style-src 'self' 'unsafe-inline'; img-src 'self' data:; connect-src 'self'; frame-ancestors 'none'; base-uri 'none'")
            self.end_headers();self.wfile.write(data)
        def do_GET(self):
            if not self.authorized_host(): return self.send(403,{'error':'Invalid host'})
            if self.path=='/': return self.send(200,(Path(__file__).parent/'web/live.html').read_bytes(),'text/html; charset=utf-8')
            if self.path=='/session': return self.send(200,{'session':token})
            if self.path=='/state':
                with lock: snapshot=deepcopy(state)
                return self.send(200,snapshot)
            return self.send(404,{'error':'Not found'})
        def do_POST(self):
            if not self.authorized_host() or self.headers.get('Origin')!=origin or not secrets.compare_digest(self.headers.get('X-PatchCourt-Session',''),token):
                return self.send(403,{'error':'Local session required'})
            if self.path!='/run': return self.send(404,{'error':'Not found'})
            if self.headers.get('Content-Type')!='application/json' or self.headers.get('Content-Length')!='2' or self.rfile.read(2)!=b'{}':
                return self.send(400,{'error':'Only the fixed empty workflow request is allowed'})
            with lock:
                if state['status']=='RUNNING': return self.send(409,{'error':'Run already active'})
                if state['runs']>=3: return self.send(429,{'error':'Three-run server budget exhausted; restart deliberately for more'})
                state.update(status='RUNNING',events=[],report=None,runs=state['runs']+1)
            threading.Thread(target=execute,daemon=True).start()
            return self.send(202,{'status':'RUNNING'})
    server=ThreadingHTTPServer(('127.0.0.1',port),Handler)
    print(f'PatchCourt live development demo: {origin} (glm-5.3-flash only)',flush=True)
    try: server.serve_forever()
    except KeyboardInterrupt: pass
    finally: server.server_close()
