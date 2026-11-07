import asyncio,json,subprocess
from pathlib import Path
import pytest
from acceptance.universal import scenario,runtime
from acceptance.universal.scenarios import Scenario,evaluate
from acceptance.engine import NODE


def definition(module):
    return dict(steps=[dict(id='app',op='call',module=module,export='create'),
        dict(id='register',op='call',target='app',member='register',args=[{'$callback':dict(params=['receiver'],calls=[
            dict(id='configured',target='receiver',member='configure',args=[201]),
            dict(id='sent',target='configured',member='publish',args=[{'message':'真实回调'}])],return_value=None)}]),
        dict(id='response',op='call',target='app',member='request')],
        checks=[dict(step='response',pointer='/body/message',expected='真实回调'),dict(step='response',pointer='/statusCode',expected=201)])


def flow(module):
    f=definition(module);cb=f['steps'][1]['args'][0]['$callback'];cb['return']=cb.pop('return_value');return f


def run_node(tmp_path,request):
    js='require(process.argv[1]).execute(JSON.parse(process.argv[2]),process.argv[3]).then(r=>console.log(JSON.stringify(r)))'
    p=subprocess.run([str(NODE),'-e',js,str(Path('acceptance/universal/scenario.cjs').resolve()),json.dumps(request),str(tmp_path)],capture_output=True,text=True,check=True,timeout=10)
    return json.loads(p.stdout)


def test_node_callback_calls_preserve_order_and_read_actual_response(tmp_path):
    (tmp_path/'callbacks.cjs').write_text('''exports.create=()=>{let handler;return {register(fn){handler=fn},request(){const receiver={statusCode:200,body:null,configure(code){this.statusCode=code;return this},publish(body){this.body=body;return this}};handler(receiver);return {then(resolve){resolve(receiver)}}}}}''')
    f=Scenario.model_validate(flow('callbacks.cjs')).model_dump();request={k:f[k] for k in ('steps','cleanup')};request['observations']=[{k:c[k] for k in ('step','pointer')} for c in f['checks']]
    receipt=run_node(tmp_path,request)
    assert evaluate(f,receipt,runtime.compare,runtime.pointer)[0]=='passed'
    assert [x['id'] for x in receipt['callbacks'][0]['calls']]==['configured','sent']
    assert receipt['steps'][-1]['awaited_result'] is True
    f['checks'][0]['expected']='错误'
    assert evaluate(f,receipt,runtime.compare,runtime.pointer)[0]=='failed'


def test_python_callback_calls_read_actual_response(tmp_path):
    (tmp_path/'callbacks.py').write_text('''class Receiver:
 def __init__(self):self.statusCode=200;self.body=None
 def configure(self,code):self.statusCode=code;return self
 def publish(self,body):self.body=body;return self
class App:
 def register(self,fn):self.handler=fn
 def request(self):
  receiver=Receiver();self.handler(receiver);return receiver
def create():return App()
''')
    f=Scenario.model_validate(flow('callbacks.py')).model_dump();request={k:f[k] for k in ('steps','cleanup')};request['observations']=[{k:c[k] for k in ('step','pointer')} for c in f['checks']]
    receipt=asyncio.run(scenario.execute(request,tmp_path))
    assert evaluate(f,receipt,runtime.compare,runtime.pointer)[0]=='passed'
    assert [x['id'] for x in receipt['callbacks'][0]['calls']]==['configured','sent']


@pytest.mark.parametrize('mutation',['private','forward','duplicate','await_sync','arbitrary'])
def test_callback_actions_are_scoped_and_public(mutation):
    f=flow('callbacks.py');cb=f['steps'][1]['args'][0]['$callback'];action=cb['calls'][0]
    if mutation=='private':action['member']='__class__'
    if mutation=='forward':action['target']='sent'
    if mutation=='duplicate':action['id']='receiver'
    if mutation=='await_sync':action['await_result']=True
    if mutation=='arbitrary':action['module']='os'
    with pytest.raises(ValueError):Scenario.model_validate(f)


def test_callback_error_swallowed_by_target_remains_execution_error(tmp_path):
    (tmp_path/'caught.cjs').write_text('exports.create=()=>{let handler;return {register(fn){handler=fn},request(){try{handler({})}catch{}return {body:{message:"真实回调"},statusCode:201}}}}')
    f=Scenario.model_validate(flow('caught.cjs')).model_dump();receipt=run_node(tmp_path,f)
    assert receipt['callbacks'][0]['status']=='error'
    assert evaluate(f,receipt,runtime.compare,runtime.pointer)[0]=='error'


def test_quoted_callback_effects_cannot_be_silently_replaced_by_return():
    from acceptance.universal.callback_contract import verify
    quote='app.register(receiver => { receiver.configure(201).publish({message: "真实回调"}) })'
    f=flow('callbacks.cjs');verify(quote,Scenario.model_validate(f))
    f['steps'][1]['args'][0]['$callback']['calls']=[]
    f['steps'][1]['args'][0]['$callback']['return']={'message':'真实回调'}
    with pytest.raises(ValueError,match='原文回调动作'):verify(quote,Scenario.model_validate(f))


def test_callback_and_path_grammar_is_versioned_and_explicit():
    from acceptance.universal.scenarios import validate_bindings
    target=dict(units=[dict(id='u',runtime='node',entries=['tool'])],interfaces=[dict(unit='u',path='callbacks.cjs',functions=[dict(name='create')])],execution_contract=dict(version=6))
    f=Scenario.model_validate(flow('callbacks.cjs'))
    with pytest.raises(ValueError,match='不支持回调'):validate_bindings(f,target,'u')
    target['execution_contract']['version']=7;validate_bindings(f,target,'u')
    cli=Scenario.model_validate(dict(steps=[dict(id='cmd',op='cli',argv=['$path/data.csv'])],checks=[dict(step='cmd',pointer='/stdout',expected='')]))
    with pytest.raises(ValueError,match='占位字符串'):validate_bindings(cli,target,'u')
    cli.steps[0].argv=[{'$path':'data.csv'}];validate_bindings(cli,target,'u')


def test_async_callback_waits_for_real_method_result(tmp_path):
    (tmp_path/'async.cjs').write_text('exports.create=()=>{let handler;return {register(fn){handler=fn},async request(){const r={async configure(code){await Promise.resolve();this.statusCode=code;return this},publish(body){this.body=body;return this}};await handler(r);return r}}}')
    f=flow('async.cjs');cb=f['steps'][1]['args'][0]['$callback'];cb['async']=True;cb['calls'][0]['await_result']=True
    f=Scenario.model_validate(f).model_dump();request={k:f[k] for k in ('steps','cleanup')};request['observations']=[{k:c[k] for k in ('step','pointer')} for c in f['checks']]
    receipt=run_node(tmp_path,request);assert evaluate(f,receipt,runtime.compare,runtime.pointer)[0]=='passed'


def test_python_async_callback_waits_for_real_method_result(tmp_path):
    (tmp_path/'async_receiver.py').write_text('''import asyncio
class Receiver:
 async def configure(self,code):
  await asyncio.sleep(0);self.statusCode=code;return self
 def publish(self,body):self.body=body;return self
class App:
 def register(self,fn):self.handler=fn
 async def request(self):
  receiver=Receiver();await self.handler(receiver);return receiver
def create():return App()
''')
    f=flow('async_receiver.py');cb=f['steps'][1]['args'][0]['$callback'];cb['async']=True;cb['calls'][0]['await_result']=True
    f=Scenario.model_validate(f).model_dump();request={k:f[k] for k in ('steps','cleanup')};request['observations']=[{k:c[k] for k in ('step','pointer')} for c in f['checks']]
    receipt=asyncio.run(scenario.execute(request,tmp_path));assert evaluate(f,receipt,runtime.compare,runtime.pointer)[0]=='passed'


@pytest.mark.parametrize('asynchronous',[False,True])
def test_undefined_callback_return_is_not_null_or_literal(tmp_path,asynchronous):
    # A receiver distinguishes absent return from an explicitly returned value,
    # as real request dispatchers do. No expected value reaches the driver.
    (tmp_path/'receiver.cjs').write_text('exports.create=()=>{let handler;return {register(fn){handler=fn},async request(){let body;const r={publish(value){body=value}};const result=await handler(r);return {body:result===undefined?body:result,duplicate:result!==undefined&&body!==undefined}}}}')
    f=flow('receiver.cjs');cb=f['steps'][1]['args'][0]['$callback']
    cb.update(calls=[dict(id='sent',target='receiver',member='publish',args=[{'message':'真实回调'}])],async_=asynchronous)
    cb['async']=cb.pop('async_');cb.pop('return');cb['return_undefined']=True
    f['checks']=[dict(step='response',pointer='/body/message',expected='真实回调'),dict(step='response',pointer='/duplicate',expected=False)]
    f=Scenario.model_validate(f).model_dump();request={k:f[k] for k in ('steps','cleanup')}
    receipt=run_node(tmp_path,request)
    assert evaluate(f,receipt,runtime.compare,runtime.pointer)[0]=='passed'
    assert receipt['callbacks'][0]['return_value']=={'observable':False,'value':{'handle_type':'undefined'}}
    cb=f['steps'][1]['args'][0]['$callback'];cb.pop('return_undefined');cb['return']=None
    receipt=run_node(tmp_path,request)
    assert receipt['steps'][-1]['value']=={'body':None,'duplicate':True}
    assert evaluate(f,receipt,runtime.compare,runtime.pointer)[0]!='passed'
    cb['calls']=[];cb['return']={'message':'真实回调'}
    receipt=run_node(tmp_path,request)
    assert evaluate(f,receipt,runtime.compare,runtime.pointer)[0]=='passed'
    f['checks'][0]['expected']='错误预期'
    assert evaluate(f,receipt,runtime.compare,runtime.pointer)[0]=='failed'


def test_documented_absent_return_cannot_be_replaced_by_null():
    from acceptance.universal.callback_contract import verify
    quote='app.register(receiver => { receiver.configure(201).publish({message: "真实回调"}) })'
    f=flow('callbacks.cjs')
    # Frozen version 7 preserves its original validation boundary.
    verify(quote,Scenario.model_validate(f),check_returns=False)
    with pytest.raises(ValueError,match='没有返回值'):verify(quote,Scenario.model_validate(f),check_returns=True)
    cb=f['steps'][1]['args'][0]['$callback'];cb.pop('return');cb['return_undefined']=True
    verify(quote,Scenario.model_validate(f),check_returns=True)


def test_undefined_callback_return_requires_node_and_new_protocol():
    from acceptance.universal.scenarios import validate_bindings
    f=flow('callbacks.cjs');cb=f['steps'][1]['args'][0]['$callback'];cb.pop('return');cb['return_undefined']=True
    target=dict(units=[dict(id='u',runtime='node')],interfaces=[dict(unit='u',path='callbacks.cjs',functions=[dict(name='create')])],execution_contract=dict(version=7))
    with pytest.raises(ValueError,match='版本8'):validate_bindings(Scenario.model_validate(f),target,'u')
    target['execution_contract']['version']=8;validate_bindings(Scenario.model_validate(f),target,'u')
    target['units'][0]['runtime']='python'
    with pytest.raises(ValueError,match='JavaScript'):validate_bindings(Scenario.model_validate(f),target,'u')
    cb['return']=None
    with pytest.raises(ValueError,match='不能同时'):Scenario.model_validate(f)


def test_document_reference_schema_lists_exact_sources_without_fuzzy_repair():
    from acceptance.universal.models import output_schema
    from acceptance.universal.generation import validate
    from acceptance.planning.models import Document
    schema=output_schema(['D1','D2'])
    assert schema['properties']['requirements']['items']['properties']['source']['enum']==['D1','D2']
    data={'requirements':[dict(id='r',title='中文标题',source='D',quote='A precise independent requirement.',disposition='unresolved',reason='缺少调用契约',cases=[])]}
    docs=[Document(id='D1',title='标准',content='A precise independent requirement.')]
    rows,issues,_=validate(data,docs,dict(units=[],interfaces=[]))
    assert rows==[] and issues[0]['reason']=='文档编号不存在'


def test_thenable_builder_method_is_not_a_response_field(tmp_path):
    (tmp_path/'lazy.cjs').write_text('exports.create=()=>{let handler;return {register(fn){handler=fn},request(){return {body(){throw Error("builder method must not be called")},then(resolve){const r={configure(code){this.statusCode=code;return this},publish(body){this.body=body;return this}};handler(r);resolve(r)}}}}}')
    f=flow('lazy.cjs');f['checks']=[dict(step='response',pointer='/body',expected={'message':'真实回调'})]
    f=Scenario.model_validate(f).model_dump();request={k:f[k] for k in ('steps','cleanup')};request['observations']=[{k:c[k] for k in ('step','pointer')} for c in f['checks']]
    receipt=run_node(tmp_path,request)
    assert evaluate(f,receipt,runtime.compare,runtime.pointer)[0]=='passed'
    assert receipt['steps'][-1]['awaited_result'] is True
    assert receipt['callbacks'][0]['status']=='completed'
    f['checks'][0]['expected']={'message':'错误预期'}
    assert evaluate(f,receipt,runtime.compare,runtime.pointer)[0]=='failed'
