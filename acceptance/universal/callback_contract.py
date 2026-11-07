"""Reject omitted documented callback effects; never rewrite inputs or expectations."""
import json,base64,time
import subprocess
from pathlib import Path
from ..engine import NODE,ROOT
from ..integrations.runner import sha,encode

UNAVAILABLE='文档回调语法核对未完成；本条不执行'


class SyntaxUnavailable(ValueError):pass


def _analyze_once(quote):
    validator=Path(__file__).with_suffix('.cjs');parser=ROOT/'web/node_modules/@babel/parser'
    request=json.dumps(dict(quote=quote)).encode();started=time.monotonic()
    receipt=dict(version=1,input_sha256=sha(request),validator_sha256=sha(validator.read_bytes()),argv=[str(NODE),str(validator),str(parser)],state='error',exit_code=None)
    try:
        package=parser/'package.json';meta=json.loads(package.read_bytes());entry=parser/meta.get('main','lib/index.js')
        receipt['dependency']=dict(name=meta['name'],version=meta['version'],package_sha256=sha(package.read_bytes()),entry_sha256=sha(entry.read_bytes()))
    except (OSError,ValueError,KeyError) as exc:receipt['dependency_error']=type(exc).__name__
    stdout=b'';stderr=b''
    try:
        result=subprocess.run(receipt['argv'],input=request,capture_output=True,timeout=15);stdout=result.stdout;stderr=result.stderr;receipt['exit_code']=result.returncode
        if result.returncode==0:
            parsed=json.loads(stdout)
            if isinstance(parsed,dict) and type(parsed.get('parsed')) is int and isinstance(parsed.get('required'),list) and isinstance(parsed.get('implicitReturns'),list):receipt['state']='completed'
    except (OSError,subprocess.TimeoutExpired,ValueError) as exc:
        stdout=getattr(exc,'stdout',None) or stdout;stderr=getattr(exc,'stderr',None) or stderr;receipt['exception']=type(exc).__name__
    receipt.update(stdout=base64.b64encode(stdout).decode(),stderr=base64.b64encode(stderr).decode(),duration_ms=round((time.monotonic()-started)*1000))
    return receipt


def analyze(quote):
    attempts=[]
    for attempt in range(3):
        receipt=_analyze_once(quote);attempts.append(receipt)
        if receipt['state']=='completed':break
        if attempt<2:time.sleep(.2)
    if len(attempts)>1:return {**receipt,'attempts':attempts}
    return receipt


def parsed_receipt(quote,receipt,validator_sha=None):
    if receipt.get('version')!=1 or receipt.get('input_sha256')!=sha(json.dumps(dict(quote=quote)).encode()) or receipt.get('validator_sha256')!=(validator_sha or sha(Path(__file__).with_suffix('.cjs').read_bytes())):raise ValueError('语法复核回执未绑定原始引用或冻结校验器')
    if receipt.get('state') not in {'error','completed'}:raise ValueError('语法复核回执状态无效')
    attempts=receipt.get('attempts')
    if attempts is not None:
        if not 1<=len(attempts)<=3 or attempts[-1]!={k:v for k,v in receipt.items() if k!='attempts'}:raise ValueError('语法复核重试回执不一致')
        for item in attempts:
            if item.get('input_sha256')!=receipt['input_sha256'] or item.get('validator_sha256')!=receipt['validator_sha256']:raise ValueError('语法重试改变了输入或校验器')
            base64.b64decode(item['stdout'],validate=True);base64.b64decode(item['stderr'],validate=True)
    base64.b64decode(receipt['stderr'],validate=True)
    stdout=base64.b64decode(receipt['stdout'],validate=True)
    if receipt.get('state')=='error':raise SyntaxUnavailable(UNAVAILABLE)
    if receipt.get('exit_code')!=0 or receipt.get('exception'):raise ValueError('语法复核回执终态不一致')
    parsed=json.loads(stdout)
    if not isinstance(parsed,dict) or type(parsed.get('parsed')) is not int or not isinstance(parsed.get('required'),list) or not isinstance(parsed.get('implicitReturns'),list):raise ValueError('语法复核回执内容不完整')
    return parsed


def verify(quote,flow,*,check_returns=False,receipt=None,on_receipt=None,validator_sha=None):
    actual=[];callbacks=[]
    def walk(v):
        if isinstance(v,list):
            for item in v:walk(item)
        elif isinstance(v,dict):
            if '$callback' in v:
                callbacks.append(v['$callback']);actual.extend(v['$callback'].get('calls',[]))
            for item in v.values():walk(item)
    walk(flow.model_dump())
    if receipt is None:receipt=analyze(quote)
    if on_receipt:on_receipt(receipt)
    parsed=parsed_receipt(quote,receipt,validator_sha);required=parsed['required']
    remaining=list(actual)
    for action in required:
        match=next((i for i,c in enumerate(remaining) if c['member']==action['member'] and ('args' not in action or c.get('args',[])==action['args'])),None)
        if match is None:raise ValueError('原文回调动作未完整表达：'+action['member']+'；不能把公开方法调用替换为返回值或省略设置')
        remaining.pop(match)
    if check_returns:
        for actions in parsed['implicitReturns']:
            matches=[cb for cb in callbacks if all(any(c['member']==a['member'] and ('args' not in a or c.get('args',[])==a['args']) for c in cb.get('calls',[])) for a in actions)]
            if not any(cb.get('return_undefined') is True for cb in matches):raise ValueError('原文回调没有返回值；JavaScript必须使用return_undefined:true，不能添加null返回值')
