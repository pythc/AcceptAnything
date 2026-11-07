"""Provider-attested budgets and disk-spooled responses; no platform size ceiling."""
import json
import shutil
import tempfile
import time
from datetime import datetime,timezone

import httpx

from ..integrations.formats import require
from ..integrations.runner import encode,sha
from ..integrations.storage import file_digest
from . import calls


def selected_capabilities(raw,model,effort):
    data=json.loads(raw)
    require(isinstance(data,dict) and isinstance(data.get('data'),list),'模型能力响应格式无效')
    rows=[r for r in data['data'] if isinstance(r,dict) and r.get('id')==model]
    require(len(rows)==1,'官方模型能力没有唯一匹配请求型号')
    row=rows[0]
    require(all(type(row.get(key)) is int and row[key]>0 for key in ('context_window','max_output_tokens')),'官方接口未声明有效的上下文或输出能力，不能猜测默认上限')
    require(row['max_output_tokens']<=row['context_window'],'官方输出能力超过上下文范围')
    declared_effort=row.get('effort');levels=declared_effort.get('supported_levels') if isinstance(declared_effort,dict) else None
    require(isinstance(levels,list) and effort in levels,'官方能力不支持请求的推理强度')
    modalities=row.get('output_modalities')
    require(isinstance(modalities,list) and 'text' in modalities,'官方能力未声明文本输出')
    return {key:row[key] for key in ('context_window','max_output_tokens')}


def calculate(raw,model,effort,messages,source):
    limits=selected_capabilities(raw,model,effort)
    # UTF-8 bytes bound the content token count conservatively. Framing reserve
    # is explicit, not presented as an exact provider tokenizer measurement.
    upper=len(encode(messages))+4096
    maximum=min(limits['max_output_tokens'],limits['context_window']-upper)
    require(maximum>0,'本批输入已占满模型上下文；需进一步分批，不能截断仓库总范围')
    return dict(version=1,source=source,raw_response=raw,response_sha256=sha(raw.encode()),model=model,reasoning_effort=effort,**limits,
                input_byte_upper_bound=upper,framing_reserve=4096,selected_output_tokens=maximum,
                method='official maximum constrained by conservative UTF-8 input bound; not an exact tokenizer count')


def discover(config,headers,messages):
    source=config.base_url.rstrip('/')+'/models'
    try:
        with httpx.Client(timeout=30,follow_redirects=False,trust_env=False) as client:
            response=client.get(source,headers=headers)
            require(response.status_code==200,'官方模型能力接口返回 HTTP '+str(response.status_code))
            raw=response.text
    except httpx.HTTPError as exc:raise ValueError('模型能力查询失败：'+type(exc).__name__) from None
    result=calculate(raw,config.model,config.reasoning_effort,messages,source)
    result['observed_at']=datetime.now(timezone.utc).isoformat()
    return result


def verify(wrapper,receipt):
    budget=wrapper.get('generation_budget');parameters=wrapper.get('request_parameters')
    require(isinstance(budget,dict) and isinstance(parameters,dict),'模型生成预算原件缺失')
    require(wrapper.get('provider')=='deepseek','模型预算不属于DeepSeek接入')
    require(budget['source'] in {'https://api.deepseek.com/models','https://api.deepseek.com/v1/models'},'模型能力不是官方接口来源')
    messages=[dict(role='system',content=wrapper['system']),dict(role='user',content=json.dumps(wrapper['prompt'],ensure_ascii=False))]
    expected=calculate(budget['raw_response'],wrapper['model'],wrapper['reasoning_effort'],messages,budget['source'])
    require({k:v for k,v in budget.items() if k!='observed_at'}==expected,'模型能力或生成预算与原件不一致')
    require(receipt.get('generation_budget')==budget,'模型回执预算与实际输入不一致')
    require(parameters==dict(model=wrapper['model'],response_format={'type':'json_object'},stream=False,reasoning_effort=wrapper['reasoning_effort'],thinking={'type':'enabled'},max_tokens=expected['selected_output_tokens']),'模型请求参数与能力预算不一致')


def receive(store,config,headers,payload,receipt,started,*,unbounded=False):
    """The spool threshold moves bytes to disk; it never truncates a response."""
    server_id=None
    with tempfile.SpooledTemporaryFile(max_size=1024*1024) as spool:
        def preserve_partial():
            directory=store.root/'model-responses';directory.mkdir(exist_ok=True)
            path=directory/(receipt['client_request_id']+'.partial')
            size=spool.tell();spool.seek(0)
            try:
                with path.open('xb') as output:
                    import os
                    os.chmod(path,0o600);shutil.copyfileobj(spool,output)
                receipt.update(partial_response_file=path.name,partial_response_bytes=size,partial_response_sha256=file_digest(path))
            except OSError as exc:receipt['partial_capture_error']=type(exc).__name__
        try:
            with httpx.Client(timeout=httpx.Timeout(config.timeout_seconds,connect=10),follow_redirects=False,trust_env=False) as client:
                with client.stream('POST',config.base_url.rstrip('/')+'/chat/completions',headers=headers,json=payload) as response:
                    server_id=response.headers.get('X-Request-Id')
                    receipt.update(server_request_id=server_id,http_status=response.status_code,state='response_headers');calls.write(store,receipt)
                    require(response.status_code==200,'模型接口返回 HTTP '+str(response.status_code)+'；请求 '+receipt['client_request_id'])
                    size=0
                    for part in response.iter_bytes():
                        require(time.monotonic()-started<=config.timeout_seconds,'模型请求超过总时限')
                        size+=len(part)
                        if not unbounded:require(size<=1048576,'模型响应超过1MiB')
                        spool.write(part)
        except httpx.HTTPError as exc:
            preserve_partial()
            receipt.update(state='failed' if isinstance(exc,(httpx.ConnectError,httpx.ConnectTimeout)) else 'upstream_unknown',error=type(exc).__name__,duration_ms=round((time.monotonic()-started)*1000));calls.write(store,receipt)
            raise ValueError('模型连接失败：'+type(exc).__name__+'；请求 '+receipt['client_request_id']+'。未自动重试。') from None
        except (ValueError,OSError):
            preserve_partial()
            code=receipt.get('http_status');receipt.update(state='upstream_unknown' if code==200 or code==408 or isinstance(code,int) and code>=500 else 'failed',duration_ms=round((time.monotonic()-started)*1000));calls.write(store,receipt);raise
        receipt.update(state='received',duration_ms=round((time.monotonic()-started)*1000),response_bytes=size);calls.write(store,receipt)
        directory=store.root/'model-responses';directory.mkdir(exist_ok=True)
        path=directory/(receipt['client_request_id']+'.json');spool.seek(0)
        with path.open('xb') as output:
            import os
            os.chmod(path,0o600);shutil.copyfileobj(spool,output)
        receipt.update(response_file=path.name,response_sha256=file_digest(path));calls.write(store,receipt)
    with path.open() as stream:raw=json.load(stream)
    return raw,server_id
