"""Trusted pytest driver. No target imports, eval, shell, or redirects."""
import json
import os
from pathlib import Path
import re
import time
from urllib.request import Request, build_opener, ProxyHandler, HTTPRedirectHandler
from urllib.error import HTTPError
from jsonschema import Draft202012Validator

PLAN=json.loads(Path(os.environ['ACCEPTANCE_PLAN']).read_text())
BASE=os.environ['ACCEPTANCE_BASE']
OUT=Path(os.environ['ACCEPTANCE_OUTPUT'])
TOKEN=re.compile(r'\$\{([A-Za-z][A-Za-z0-9_-]*)\}')

class NoRedirect(HTTPRedirectHandler):
    def redirect_request(self,*args,**kwargs): return None

def pointer(data,path):
    for part in path.split('/')[1:] if path else []:
        part=part.replace('~1','/').replace('~0','~')
        data=data[int(part)] if isinstance(data,list) else data[part]
    return data

def replace(value,variables):
    if isinstance(value,list): return [replace(v,variables) for v in value]
    if isinstance(value,dict): return {k:replace(v,variables) for k,v in value.items()}
    if not isinstance(value,str): return value
    m=TOKEN.fullmatch(value)
    if m: return variables[m[1]]
    return TOKEN.sub(lambda m:str(variables[m[1]]),value)

def redact(value):
    if isinstance(value,list): return [redact(x) for x in value]
    if isinstance(value,dict): return {k:('[redacted]' if re.search(r'password|token|secret|authorization|cookie',k,re.I) else redact(v)) for k,v in value.items()}
    return value

def request(method,path,body=None,headers=None):
    if not path.startswith('/') or path.startswith('//') or any(c in path for c in ('\\','\r','\n','#')): raise ValueError('request escaped target')
    headers={**(headers or {})}
    raw=None if body is None else json.dumps(body,allow_nan=False).encode()
    if raw is not None: headers.setdefault('Content-Type','application/json')
    req=Request(BASE+path,data=raw,headers=headers,method=method)
    try: response=build_opener(ProxyHandler({}),NoRedirect()).open(req,timeout=5)
    except HTTPError as error: response=error
    with response:
        content=response.read(1048577)
        if len(content)>1048576: raise RuntimeError('response exceeds 1 MiB')
        text=content.decode('utf-8',errors='replace')
        try: data=json.loads(text,parse_constant=lambda _:(_ for _ in ()).throw(ValueError('nonfinite response')))
        except ValueError: data=text
        return response.status,data

def same(a,b):
    if isinstance(a,bool)!=isinstance(b,bool): return False
    if isinstance(a,dict) and isinstance(b,dict): return a.keys()==b.keys() and all(same(a[k],b[k]) for k in a)
    if isinstance(a,list) and isinstance(b,list): return len(a)==len(b) and all(same(x,y) for x,y in zip(a,b))
    return a==b

def run_case(cid):
    case=next(c for c in PLAN['cases'] if c['id']==cid)
    trace={'case_id':cid,'requirement':case['requirement'],'source':case['source'],'steps':[],'status':'error'}
    variables={'run_id':os.environ['ACCEPTANCE_RUN']+'-'+cid}
    start=time.monotonic()
    try:
        for original in case['steps']:
            step=replace(original,variables);row={'input':redact(step)};trace['steps'].append(row)
            t=time.monotonic()
            if step['kind']=='call':
                status,data=request('POST','/call',{k:step[k] for k in ('module','function','args')})
                row['response']={'status':status,'body':redact(data)}
                assert status==200,f"{cid} 函数调用异常：{data}"
                data=data['value']
            else:
                status,data=request(step['method'],step['path'],step['body'],step['headers'])
                row['response']={'status':status,'body':redact(data)}
                assert status==step['status'],f"{cid} 预期 HTTP {step['status']}，实际 {status}；{str(redact(data))[:1000]}"
            row['assertions']=[]
            for assertion in step['assertions']:
                actual=pointer(data,assertion['pointer']);expected=assertion['value']
                result={'pointer':assertion['pointer'],'operator':assertion['operator'],'expected':redact(expected),'actual':redact(actual)}
                row['assertions'].append(result)
                if assertion['operator']=='schema':
                    errors=list(Draft202012Validator(expected).iter_errors(actual));ok=not errors
                elif assertion['operator']=='contains': ok=expected in actual
                else: ok=same(actual,expected)
                result['passed']=ok
                assert ok,f"{cid} {assertion['pointer'] or '/'} 预期 {expected!r}，实际 {actual!r}"
            for name,p in step.get('capture',{}).items(): variables[name]=pointer(data,p)
            row['duration_ms']=round((time.monotonic()-t)*1000)
        trace['status']='passed'
    except AssertionError as error:
        trace.update(status='failed',error=str(error)[:3000]);raise
    except Exception as error:
        trace['error']=str(error)[:3000];raise
    finally:
        trace['duration_ms']=round((time.monotonic()-start)*1000)
        (OUT/(cid+'-trace.json')).write_text(json.dumps(trace,ensure_ascii=False,allow_nan=False,indent=2))
