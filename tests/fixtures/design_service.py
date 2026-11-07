"""Isolated acceptance calibration target; no real users or external services."""
from http.server import BaseHTTPRequestHandler,HTTPServer
import json
import os

items={}
class Handler(BaseHTTPRequestHandler):
    def send_error(self,code,message=None,explain=None):
        if code==501:return self.reply(405,{'error':'method not allowed'})
        return super().send_error(code,message,explain)
    def reply(self,status,value):
        self.send_response(status);self.send_header('Content-Type','application/json')
        if status==405:self.send_header('Allow','GET')
        self.end_headers();self.wfile.write(json.dumps(value).encode())
    def do_GET(self):
        if self.path=='/health':return self.reply(200,{'status':'ok'})
        if self.path=='/private':return self.reply(401,{'error':'login required'})
        if self.path.startswith('/items/'):
            value=items.get(self.path.split('/')[-1]);return self.reply(200 if value else 404,value or {'error':'not found'})
        if self.path=='/':
            raw='''<!doctype html><html lang="zh"><meta charset="utf-8"><title>校准页面</title><label>名称<input id="name"></label><button onclick="document.querySelector('#result').textContent='已保存：'+document.querySelector('#name').value">保存</button><p id="result">尚未保存</p></html>'''
            self.send_response(200);self.send_header('Content-Type','text/html;charset=utf-8');self.end_headers();self.wfile.write(raw.encode());return
        self.reply(404,{'error':'not found'})
    def do_POST(self):
        if self.path!='/items':return self.reply(405 if self.path=='/health' else 404,{})
        body=json.loads(self.rfile.read(int(self.headers.get('Content-Length','0'))))
        if not isinstance(body.get('name'),str) or not body['name']:return self.reply(400,{'error':'name required'})
        key=str(len(items)+1);items[key]={'id':key,'name':body['name']};self.reply(201,items[key])
    def log_message(self,*args):pass

HTTPServer(('0.0.0.0',int(os.environ.get('PORT','19300'))),Handler).serve_forever()
