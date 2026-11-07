"""HTTP probe; this filename must not shadow Python's standard http package."""
import base64,json,sys,time,urllib.request,urllib.error
r=json.loads(base64.b64decode(sys.argv[1]));start=time.monotonic()
class NoRedirect(urllib.request.HTTPRedirectHandler):
 def redirect_request(self,*args,**kwargs):return None
opener=urllib.request.build_opener(urllib.request.ProxyHandler({}),NoRedirect())
req=urllib.request.Request('http://127.0.0.1:19300'+r['path'],data=json.dumps(r['body']).encode() if r.get('body') is not None else None,method=r['method'],headers={'Content-Type':'application/json'})
try:response=opener.open(req,timeout=10)
except urllib.error.HTTPError as exc:response=exc
text=response.read().decode();value=text
try:value=json.loads(text)
except ValueError:pass
print('\nACCEPTANCE_VALUE:'+json.dumps(dict(status=response.code,value=value,duration_ms=(time.monotonic()-start)*1000)))
