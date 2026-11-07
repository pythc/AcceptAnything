"""Declarative stateful protocols. Assertions remain on the host, outside target code."""
import re
import json
import base64
from pathlib import PurePosixPath
from typing import Any, Literal
from pydantic import Field, model_validator
from ..planning.models import Strict, ID


def public(name):
    if not isinstance(name,str) or not re.fullmatch(r'[A-Za-z][A-Za-z0-9_]*',name) or name in {'constructor','prototype','__proto__'}:
        raise ValueError('只允许公开属性或方法名')
    return name


class Step(Strict):
    id: ID
    op: Literal['call','observe_call','get','item','collect','identity','inspect_path','enter','exit','write_file','cli']
    module: str | None = None
    export: str | None = None
    target: str | None = None
    member: str | None = None
    args: list[Any] = Field(default_factory=list)
    kwargs: dict[str,Any] = Field(default_factory=dict)
    instantiate: bool = False
    await_result: bool = False
    value: Any = None
    path: str | None = None
    encoding: Literal['utf-8','latin-1','ascii','base64'] = 'utf-8'
    entry: str | None = None
    argv: list[Any] = Field(default_factory=list,description='命令参数：字符串或对象 {"$path":"data.db"}/{"$ref":"前序步骤"}；不能使用字符串 $path/data.db',json_schema_extra={'items':{'oneOf':[{'type':'string'},*[
        {'type':'object','properties':{key:{'type':'string'}},'required':[key],'additionalProperties':False} for key in ('$path','$ref')]]}})
    stdin: str = ''

    @model_validator(mode='after')
    def valid(self):
        if self.member:public(self.member)
        if self.export:public(self.export)
        if self.op in {'call','observe_call'}:
            if bool(self.module and self.export)==bool(self.target):raise ValueError('调用须指定公开模块导出或前序对象')
        elif self.op=='write_file':
            p=PurePosixPath(self.path or '')
            if not self.path or p.is_absolute() or '..' in p.parts or '\\' in self.path or '\0' in self.path:raise ValueError('夹具只能写入用例临时目录')
            if not isinstance(self.value,str):raise ValueError('文件夹具必须为文本')
            try:
                if self.encoding=='base64':
                    raw=base64.b64decode(self.value,validate=True)
                    if base64.b64encode(raw).decode()!=self.value:raise ValueError('base64不是规范编码')
                else:self.value.encode(self.encoding)
            except (UnicodeError,ValueError):raise ValueError('文件夹具不满足声明的编码') from None
        elif self.op!='cli' and not self.target:raise ValueError('步骤需要前序对象')
        if self.op=='get' and not self.member:raise ValueError('读取需要公开属性')
        if self.op=='identity' and (not isinstance(self.value,dict) or set(self.value)!={'$ref'}):raise ValueError('对象同一性只能比较两个已创建对象的引用')
        if self.op!='write_file' and self.encoding!='utf-8':raise ValueError('编码设置仅适用于write_file')
        return self


class Check(Strict):
    step: ID
    pointer: str = Field(default='',description='RFC 6901 字段路径，嵌套用 / 分隔，例如 /headers/content-type；不是 /headers.content-type。空串检查整个 JSON 值。')
    expected: Any
    comparison: Literal['equals','one_of','contains','text','json_stream','json_schema'] = 'equals'


    @model_validator(mode='after')
    def alternatives(self):
        if self.comparison=='one_of' and (not isinstance(self.expected,list) or not self.expected):raise ValueError('one_of需要非空候选值数组')
        if self.comparison=='json_schema':validate_schema(self.expected)
        return self


class Scenario(Strict):
    version: Literal[1] = 1
    steps: list[Step] = Field(min_length=1)
    cleanup: list[Step] = Field(default_factory=list)
    checks: list[Check] = Field(min_length=1)

    @model_validator(mode='after')
    def dependencies(self):
        known=set()
        def refs(value,available):
            if isinstance(value,list):
                for x in value:refs(x,available)
            elif isinstance(value,dict):
                if '$ref' in value:
                    if set(value)-{'$ref','pointer'} or value['$ref'] not in available:raise ValueError('引用必须指向已有步骤或回调参数')
                    if 'pointer' in value and (not isinstance(value['pointer'],str) or not value['pointer'].startswith('/')):raise ValueError('引用字段必须使用非空JSON Pointer')
                elif '$path' in value:
                    if not isinstance(value['$path'],str):raise ValueError('临时路径必须为字符串')
                    p=PurePosixPath(value['$path'])
                    if set(value)!={'$path'} or p.is_absolute() or '..' in p.parts or '\\' in str(p) or '\0' in str(p):raise ValueError('临时路径无效')
                elif '$callback' in value:
                    cb=value['$callback']
                    if set(value)!={'$callback'} or not isinstance(cb,dict) or set(cb)-{'params','return','return_undefined','async','calls'}:raise ValueError('回调只能声明参数、公开方法调用、返回值与async')
                    if ('return' in cb)==('return_undefined' in cb) or 'return_undefined' in cb and cb['return_undefined'] is not True:raise ValueError('回调须选择return或return_undefined:true，不能同时指定')
                    params=cb.get('params',[])
                    if not isinstance(params,list) or not all(isinstance(p,str) for p in params) or len(set(params))!=len(params):raise ValueError('回调参数无效')
                    for name in params:public(name)
                    if 'async' in cb and type(cb['async']) is not bool:raise ValueError('async必须是布尔值')
                    local=available|set(params)
                    if not isinstance(cb.get('calls',[]),list):raise ValueError('回调调用必须为列表')
                    for call in cb.get('calls',[]):
                        if not isinstance(call,dict) or set(call)-{'id','target','member','args','kwargs','await_result'}:raise ValueError('回调仅支持前序对象的公开方法调用')
                        name=call.get('id');public(name)
                        if name in local or call.get('target') not in local:raise ValueError('回调调用引用未创建或重复的对象')
                        public(call.get('member'))
                        if not isinstance(call.get('args',[]),list) or not isinstance(call.get('kwargs',{}),dict):raise ValueError('回调实参格式错误')
                        if type(call.get('await_result',False)) is not bool or call.get('await_result') and not cb.get('async'):raise ValueError('等待回调调用必须声明异步回调')
                        refs(call.get('args',[]),local);refs(call.get('kwargs',{}),local);local=local|{name}
                    refs(cb.get('return'),local)
                else:
                    for x in value.values():refs(x,available)
        for step in [*self.steps,*self.cleanup]:
            if step.id in known:raise ValueError('步骤编号重复')
            if step.target and step.target not in known:raise ValueError('步骤引用未创建的对象')
            refs(step.args,known);refs(step.kwargs,known);refs(step.value,known);refs(step.argv,known)
            known.add(step.id)
        observed={s.id for s in self.steps}
        if any(c.step not in observed for c in self.checks):raise ValueError('断言必须绑定业务步骤')
        return self


def validate_bindings(flow,target,unit,projection_context=None):
    from .bindings import accessible
    permitted=accessible(target,unit,projection_context)
    allowed={(i['path'],f['name']) for i in target['interfaces'] if i['unit'] in permitted for f in i['functions']}
    component=next(u for u in target['units'] if u['id']==unit)
    entries=list(component.get('cli_commands',{})) or component.get('entries',[])
    version=target.get('execution_contract',{}).get('version',0)
    if version<15 and any(c.comparison=='json_schema' for c in flow.checks):raise ValueError('本次冻结协议不支持JSON Schema比较')
    if version>=12:validate_cli_checks(flow.model_dump(),structured_exit=version>=19)
    def callbacks(value):
        if isinstance(value,list):
            for v in value:callbacks(v)
        elif isinstance(value,dict):
            if '$ref' in value and 'pointer' in value and version<15:raise ValueError('本次冻结协议不支持引用字段读取')
            if '$callback' in value:
                cb=value['$callback']
                if cb.get('calls') and version<7:raise ValueError('本次冻结协议不支持回调方法调用')
                if cb.get('return_undefined') and (version<8 or component['runtime']!='node'):raise ValueError('无返回值标记仅适用于版本8以上的JavaScript回调')
                if component['runtime']=='node' and any(c.get('kwargs') for c in cb.get('calls',[])):raise ValueError('JavaScript回调不支持关键字实参')
            for v in value.values():callbacks(v)
    for step in [*flow.steps,*flow.cleanup]:
        if step.op in {'observe_call','identity','inspect_path'} and version<15:raise ValueError('本次冻结协议不支持该观察动作')
        if version>=15 and component['runtime']=='node' and step.op in {'enter','exit'}:raise ValueError('JavaScript流程没有Python上下文协议，不能使用enter/exit')
        if version<15 and step.encoding!='utf-8':raise ValueError('本次冻结协议不支持其他文件编码')
        if step.op=='observe_call' and step in flow.cleanup:raise ValueError('清理步骤必须显式暴露异常，不能包装成观察结果')
        for value in (step.args,step.kwargs,step.value,step.argv):callbacks(value)
        if version>=7 and step.op=='cli':
            for arg in step.argv:
                if isinstance(arg,str):
                    if arg.startswith(('$path/','$ref/','${')):raise ValueError('命令路径引用必须使用结构化 $path/$ref 对象，不能写成占位字符串')
                elif not isinstance(arg,dict) or len(arg)!=1 or not set(arg)<={'$path','$ref'}:raise ValueError('命令参数只能是字符串或结构化路径/引用')
        if step.module and (step.module,step.export) not in allowed:raise ValueError('流程调用不在公开语法索引中')
        if step.op=='cli' and not (step.entry in entries if step.entry else len(entries)==1):raise ValueError('流程命令需要唯一或明确选定的已声明入口')


def validate_schema(schema):
    """Use the installed standard validator, with no remote or regex execution."""
    from jsonschema import Draft202012Validator,FormatChecker
    from jsonschema.exceptions import SchemaError
    from referencing import Registry
    if not isinstance(schema,dict) or not set(schema)&{'type','const','enum'}:raise ValueError('JSON Schema必须显式声明type、const或enum，不能用空schema放行')
    def inspect(value):
        if isinstance(value,dict):
            for key,item in value.items():
                if key in {'$id','pattern','patternProperties'}:raise ValueError('本地Schema不支持动态基址或正则规则')
                if key in {'$ref','$dynamicRef'} and (not isinstance(item,str) or not item.startswith('#')):raise ValueError('Schema引用必须为本地片段，不能访问外部资源')
                if key=='format' and (not isinstance(item,str) or item not in FormatChecker.checkers):raise ValueError('不支持的Schema格式')
                if key in {'properties','$defs','definitions','dependentSchemas'} and isinstance(item,dict):
                    for child in item.values():inspect(child)
                elif key in {'allOf','anyOf','oneOf','prefixItems'} and isinstance(item,list):
                    for child in item:inspect(child)
                elif key in {'items','additionalProperties','unevaluatedProperties','unevaluatedItems','contains','not','propertyNames','if','then','else'}:inspect(item)
    inspect(schema)
    try:Draft202012Validator.check_schema(schema)
    except SchemaError:raise ValueError('JSON Schema定义无效') from None
    return Draft202012Validator(schema,registry=Registry(),format_checker=FormatChecker())


def schema_matches(actual,schema):
    try:return validate_schema(schema).is_valid(actual)
    except RecursionError:raise ValueError('Schema递归不可求值') from None
    except Exception as exc:
        if isinstance(exc,ValueError):raise
        raise ValueError('本地Schema无法求值：'+type(exc).__name__) from None


def validate_status_basis(flow,quote):
    """Do not turn a vague HTTP behavior into an invented exact status code."""
    steps={s.id:s for s in flow.steps}
    for check in flow.checks:
        step=steps[check.step]
        last=check.pointer.rsplit('/',1)[-1] if check.pointer else step.member if step.op=='get' else None
        if last not in {'status_code','statusCode'}:continue
        values=check.expected if check.comparison=='one_of' else [check.expected]
        if check.comparison=='json_schema':
            values=[]
            def codes(schema):
                if not isinstance(schema,dict):return
                for key in ('const','minimum','maximum','exclusiveMinimum','exclusiveMaximum'):
                    if key in schema:values.append(schema[key])
                values.extend(schema.get('enum',[]))
                for key in ('allOf','anyOf','oneOf'):
                    for child in schema.get(key,[]):codes(child)
            codes(check.expected)
        for value in values:
            if type(value) is int and 100<=value<=599 and not re.search(r'(?<![0-9])'+str(value)+r'(?![0-9])',quote):
                raise ValueError('具体HTTP状态码 '+str(value)+' 缺少引用原文数值依据；不能将重定向等文字猜成固定状态码')


def validate_cli_checks(flow,structured_exit=False):
    """Validate the fixed CLI receipt shape, without inventing a business oracle."""
    cli={s['id'] for s in flow['steps'] if s['op']=='cli'}
    for c in flow['checks']:
        if c['step'] not in cli:continue
        path=c.get('pointer','');mode=c.get('comparison','equals');expected=c['expected']
        if path in {'/stdout','/stderr'}:
            if mode!='json_stream' and not isinstance(expected,str):raise ValueError('CLI文本字段需要字符串预期或json_stream比较')
        elif path=='/exit_code':
            if structured_exit and mode=='json_schema':
                validator=validate_schema(expected)
                if expected.get('type')!='integer':raise ValueError('CLI退出码Schema必须声明integer类型')
                accepted=[validator.is_valid(code) for code in range(256)]
                if not any(accepted) or all(accepted):raise ValueError('CLI退出码Schema必须区分0至255中的实际结果，不能全部放行或全部拒绝')
                continue
            if mode!='equals' or type(expected) is not int or not 0<=expected<=255:raise ValueError('CLI退出码必须使用equals和0至255整数预期')
        elif path=='':
            if mode=='json_stream' and isinstance(expected,str):
                try:expected=json.loads(expected)
                except ValueError:raise ValueError('CLI完整回执预期不是JSON对象') from None
            if mode not in {'equals','json_stream'} or not isinstance(expected,dict) or set(expected)!={'stdout','stderr','exit_code'}:
                raise ValueError('CLI步骤返回完整回执；比较输出必须显式选择/stdout或/stderr，退出码选择/exit_code，不能将回执直接与输出文本比较')
            if not isinstance(expected['stdout'],str) or not isinstance(expected['stderr'],str) or type(expected['exit_code']) is not int or not 0<=expected['exit_code']<=255:
                raise ValueError('CLI完整回执的字段类型无效')
        else:raise ValueError('CLI回执只有/stdout、/stderr和/exit_code；JSON输出先选择/stdout并用json_stream比较')


def validate_observation_checks(flow):
    """Capturing an exception cannot silently replace checking the outcome."""
    steps={s.id:s for s in flow.steps};checked=set()
    for check in flow.checks:
        current=steps[check.step];fields=[p.replace('~1','/').replace('~0','~') for p in check.pointer[1:].split('/')] if check.pointer else []
        while current.op in {'get','item'} and current.target in steps:
            key=current.member if current.op=='get' else current.value
            if not isinstance(key,str):break
            fields.insert(0,key);current=steps[current.target]
        if current.op!='observe_call':continue
        whole=isinstance(check.expected,dict) and 'raised' in check.expected and check.comparison=='equals'
        if (fields and fields[0] in {'raised','exception','return_observable','value'}) or (not fields and whole):checked.add(current.id)
    missing=[s.id for s in flow.steps if s.op=='observe_call' and s.id not in checked]
    if missing:raise ValueError('观察调用必须独立断言其实际异常或返回结果，不能仅检查旁路状态：'+', '.join(missing))


def evaluate(flow,receipt,compare,pointer,validate_cli_contract=False,structured_cli_exit=False):
    """A driver error/cleanup failure is never a confirmed business failure."""
    if validate_cli_contract:
        try:validate_cli_checks(flow,structured_exit=structured_cli_exit)
        except ValueError as exc:return 'error',[dict(status='error',reason=str(exc))]
    rows=receipt.get('steps',[])
    expected_ids=[s['id'] for s in flow['steps']]
    cleanup=receipt.get('cleanup',[])
    declared=[s for s in cleanup if not s.get('automatic_context_exit')]
    if ([s.get('id') for s in rows]!=expected_ids or receipt.get('status')!='completed'
        or [s.get('id') for s in declared]!=[s['id'] for s in flow.get('cleanup',[])]
        or any(s.get('status')!='completed' for s in cleanup)
        or receipt.get('temporary_directory_removed') is not True):
        return 'error',[]
    actual={s['id']:s for s in rows};checks=[]
    for step,row in zip(flow.get('cleanup',[]),declared):
        if step['op']=='cli' and row.get('value',{}).get('exit_code')!=0:return 'error',[]
    for s in flow['steps']:
        if s['op']=='cli' and actual[s['id']].get('value',{}).get('exit_code')!=0:
            if not any(c['step']==s['id'] and c.get('pointer')=='/exit_code' for c in flow['checks']):return 'error',[]
    for c in flow['checks']:
        row=actual[c['step']]
        if row.get('status')!='completed':return 'error',checks
        try:
            if row.get('observable'):value=pointer(row['value'],c.get('pointer',''))
            else:
                fields=[o for o in row.get('observations',[]) if o.get('pointer')==c.get('pointer')]
                if not c.get('pointer') or len(fields)!=1 or not fields[0].get('observable'):raise ValueError('对象字段未成功读取')
                value=fields[0]['value']
            passed=compare(value,c['expected'],c.get('comparison','equals'))
            checks.append(dict(**c,actual=value,status='passed' if passed else 'failed'))
        except (ValueError,TypeError,KeyError):
            checks.append(dict(**c,status='error',reason='返回值不满足声明的观察路径或比较协议'))
    return ('error' if any(c['status']=='error' for c in checks) else 'failed' if any(c['status']=='failed' for c in checks) else 'passed'),checks
