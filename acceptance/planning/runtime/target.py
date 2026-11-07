"""Target-side bridge; assertions and reports live outside this container."""
import importlib.util
import json
import os
from pathlib import Path
import sys
from http.server import HTTPServer, BaseHTTPRequestHandler
sys.path.insert(0, '/source')
cache={}

class Handler(BaseHTTPRequestHandler):
    def reply(self,status,data):
        raw=json.dumps(data,allow_nan=False).encode()
        self.send_response(status);self.send_header('Content-Type','application/json');self.end_headers();self.wfile.write(raw)
    def do_GET(self):
        self.reply(200 if self.path=='/health' else 404, {'status':'ok'})
    def do_POST(self):
        try:
            if self.path!='/call': return self.reply(404,{})
            size=int(self.headers.get('Content-Length','0'))
            if not 0<size<=1048576: raise ValueError('request too large')
            body=json.loads(self.rfile.read(size));p=(Path('/source')/body['module']).resolve()
            if not p.is_relative_to('/source') or not isinstance(body['args'],list): raise ValueError('invalid call')
            if str(p) not in cache:
                spec=importlib.util.spec_from_file_location('target_module_'+str(len(cache)),p)
                module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module);cache[str(p)]=module
            value=getattr(cache[str(p)],body['function'])(*body['args'])
            self.reply(200,{'value':value})
        except Exception as exc: self.reply(500,{'error':str(exc)[:1000]})
    def log_message(self,*args): pass

HTTPServer(('0.0.0.0',int(os.environ.get('PORT','19300'))),Handler).serve_forever()
