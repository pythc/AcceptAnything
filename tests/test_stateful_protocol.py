import asyncio
import base64
import json
import subprocess
import uuid
from pathlib import Path
import pytest
from acceptance.universal.scenarios import Scenario, evaluate
from acceptance.universal import scenario, runtime, discovery, generation
from acceptance.planning.models import Document
from acceptance.engine import NODE


def flow(module="database.py"):
    return Scenario.model_validate(dict(steps=[
        dict(id='db',op='call',module=module,export='Database',args=[{'$path':'records.sqlite'}]),
        dict(id='insert',op='call',target='db',member='insert',args=[7,'中文记录']),
        dict(id='close',op='call',target='db',member='close'),
        dict(id='reopen',op='call',module=module,export='Database',args=[{'$path':'records.sqlite'}]),
        dict(id='read',op='call',target='reopen',member='rows'),
    ],cleanup=[dict(id='release',op='call',target='reopen',member='close')],checks=[dict(step='read',expected=[[7,'中文记录']])])).model_dump()


def database(root):
    name='database_'+uuid.uuid4().hex+'.py'
    (root/name).write_text('''import sqlite3
class Database:
 def __init__(self,path):
  self.connection=sqlite3.connect(path)
  self.connection.execute("create table if not exists records(id integer primary key, name text)")
 def insert(self,id,name):
  self.connection.execute("insert into records values (?,?)",(id,name));self.connection.commit()
 def rows(self):return self.connection.execute("select * from records order by id").fetchall()
 def close(self):self.connection.close()
''')
    return name


def test_real_sqlite_persistence_and_oracles_outside_driver(tmp_path):
    f=flow(database(tmp_path));request={k:f[k] for k in ('steps','cleanup')}
    receipt=asyncio.run(scenario.execute(request,tmp_path))
    assert evaluate(f,receipt,runtime.compare,runtime.pointer)[0]=='passed'
    assert receipt['temporary_directory_removed']
    assert not list(tmp_path.glob('*.sqlite'))
    bad=json.loads(json.dumps(f));bad['checks'][0]['expected']=[[7,'错误结果']]
    assert evaluate(bad,receipt,runtime.compare,runtime.pointer)[0]=='failed'


def test_failed_setup_blocks_dependent_steps_but_cleanup_runs(tmp_path):
    f=flow(database(tmp_path));f['steps'].insert(2,dict(id='duplicate',op='call',target='db',member='insert',args=[7,'重复']))
    f['cleanup']=[dict(id='release',op='call',target='db',member='close')]
    receipt=asyncio.run(scenario.execute(f,tmp_path))
    assert receipt['status']=='error' and receipt['steps'][2]['status']=='error'
    assert receipt['steps'][-1]['status']=='blocked' and receipt['cleanup'][0]['status']=='completed'
    assert evaluate(f,receipt,runtime.compare,runtime.pointer)[0]=='error'


@pytest.mark.parametrize('step',[
    dict(id='x',op='write_file',path='../escape',value='secret'),
    dict(id='x',op='call',target='missing',member='read'),
    dict(id='x',op='call',module='a.py',export='__import__'),
    dict(id='x',op='call',module='a.py',export='hello',args=[{'$callback':{'params':[],'return':{'$ref':'future'}}}]),
])
def test_rejects_invalid_state_paths_and_forward_references(step):
    with pytest.raises(ValueError):Scenario.model_validate(dict(steps=[step],checks=[dict(step='x',expected=None)]))


def test_static_classes_and_commonjs_factory_are_found_without_import(tmp_path):
    (tmp_path/'pyproject.toml').write_text('[project]\nname="neutral"\nversion="1"')
    (tmp_path/'object.py').write_text('raise Exception("DO NOT IMPORT")\nclass Store:\n def put(self,value): pass')
    (tmp_path/'package.json').write_text('{"name":"neutral","main":"index.js"}')
    (tmp_path/'index.js').write_text('function factory() {throw Error("DO NOT LOAD")}\nmodule.exports = factory')
    d=discovery.discover(tmp_path,['pyproject.toml','object.py','package.json','index.js'])
    assert any(f['name']=='Store' and f['kind']=='class' for i in d['interfaces'] for f in i['functions'])
    assert any(i['path']=='index.js' and any(f['name']=='default' for f in i['functions']) for i in d['interfaces'])


def test_node_async_callback_reference_and_cleanup(tmp_path):
    (tmp_path/'index.cjs').write_text('''module.exports=function(){let handler;return {route(fn){handler=fn},async request(x){return await handler(x)},close(){return "closed"}}}''')
    f=Scenario.model_validate(dict(steps=[dict(id='app',op='call',module='index.cjs',export='default'),
        dict(id='route',op='call',target='app',member='route',args=[{'$callback':{'params':['request'],'return':{'$ref':'request'},'async':True}}]),
        dict(id='response',op='call',target='app',member='request',args=[{'message':'中文输入'}])],
        cleanup=[dict(id='closed',op='call',target='app',member='close')],checks=[dict(step='response',pointer='/message',expected='中文输入')])).model_dump()
    driver=Path('acceptance/universal/scenario.cjs').resolve()
    js='const {execute}=require(process.argv[1]);execute(JSON.parse(process.argv[2]),process.argv[3]).then(r=>console.log(JSON.stringify(r)))'
    p=subprocess.run([str(NODE),'-e',js,str(driver),json.dumps(f),str(tmp_path)],capture_output=True,text=True,check=True)
    receipt=json.loads(p.stdout)
    assert evaluate(f,receipt,runtime.compare,runtime.pointer)[0]=='passed'
    assert receipt['cleanup'][0]['value']=='closed' and receipt['temporary_directory_removed']


def test_business_driver_does_not_receive_checks_or_expected(tmp_path,monkeypatch):
    from acceptance.universal.models import Case
    f=flow();c=Case(id='C',title='数据库持久化',unit='u',kind='scenario',flow=f,expected=None).model_dump()
    r={'universal_generation':{'requirements':[dict(id='R',source='D',quote='写入后重开仍可读回',cases=[c])]}}
    receipt=dict(status='completed',steps=[dict(id=s['id'],status='completed',observable=True,value=[[7,'中文记录']]) for s in f['steps']],cleanup=[dict(id='release',status='completed')],temporary_directory_removed=True)
    def command(run,u,argv,*args,**kwargs):
        request=json.loads(base64.b64decode(argv[-1]));assert set(request)=={'steps','cleanup'}
        assert 'checks' not in request and 'expected' not in request
        return dict(exit_code=0),dict(stdout=('ACCEPTANCE_VALUE:'+json.dumps(receipt)).encode())
    monkeypatch.setattr(runtime,'command',command)
    report,_=runtime.business(r,dict(id='u',runtime='python'),tmp_path,lambda:False)
    assert report['tests'][0]['status']=='passed'


def test_startup_recovery_does_not_audit_completed_artifacts(tmp_path,monkeypatch):
    from acceptance.integrations.store import IntegrationStore
    from acceptance.integrations.runner import encode,sha
    s=IntegrationStore(tmp_path);rid='int-'+'a'*16;p=s.root/'runs'/rid;p.mkdir()
    r=dict(id=rid,status='completed');(p/'run.json').write_bytes(encode(dict(record=r,sha256=sha(encode(r)))))
    monkeypatch.setattr(s,'list',lambda:pytest.fail('startup must not list all evidence'))
    monkeypatch.setattr(s,'snapshot',lambda *a:pytest.fail('must not audit terminal artifacts'))
    s.recover()


def test_node_thenable_factory_is_not_started_before_configuration(tmp_path):
    (tmp_path/'index.cjs').write_text('''module.exports=function(){let started=false;return {then(ok){started=true;ok()},set(){if(started)throw Error("started early");return 8},close(){}}}''')
    request=dict(steps=[dict(id='app',op='call',module='index.cjs',export='default'),dict(id='configure',op='call',target='app',member='set')],cleanup=[dict(id='close',op='call',target='app',member='close')])
    js='require(process.argv[1]).execute(JSON.parse(process.argv[2]),process.argv[3]).then(r=>console.log(JSON.stringify(r)))'
    p=subprocess.run([str(NODE),'-e',js,str(Path('acceptance/universal/scenario.cjs').resolve()),json.dumps(request),str(tmp_path)],capture_output=True,text=True,check=True,timeout=10)
    receipt=json.loads(p.stdout)
    assert receipt['status']=='completed' and receipt['steps'][1]['value']==8


def test_missing_cleanup_or_opaque_handle_cannot_pass():
    f=flow();receipt=dict(status='completed',steps=[dict(id=s['id'],status='completed',observable=True,value=[[7,'中文记录']]) for s in f['steps']],cleanup=[],temporary_directory_removed=True)
    assert evaluate(f,receipt,runtime.compare,runtime.pointer)[0]=='error'
    receipt['cleanup']=[dict(id='release',status='completed')];receipt['steps'][-1]['observable']=False
    assert evaluate(f,receipt,runtime.compare,runtime.pointer)[0]=='error'


def test_scenario_alias_is_resolved_only_for_new_frozen_protocol(tmp_path):
    docs=[Document(id='D',title='独立契约',content='写入中文记录后应读回中文记录。')]
    f=flow();f['steps'][0]['module']='database';f['steps'][3]['module']='database'
    row=dict(id='R',source='D',quote=docs[0].content,title='写入后查询',cases=[dict(id='C',title='持久化查询',unit='u',kind='scenario',flow=f,expected=None)])
    t=dict(units=[dict(id='u',path='.',runtime='python',capabilities=['scenario'])],interfaces=[dict(unit='u',path='database.py',functions=[dict(name='Database')])],execution_contract=dict(version=4))
    accepted,issues,_=generation.validate(dict(requirements=[row]),docs,t)
    assert not issues and accepted[0]['cases'][0]['flow']['steps'][0]['module']=='database.py'
    t['execution_contract']['version']=3
    old,issues,_=generation.validate(dict(requirements=[row]),docs,t)
    assert issues and old[0]['disposition']=='unresolved'


def test_cli_steps_share_file_state_with_api_and_enforce_declared_entry(tmp_path):
    import sys
    f=flow(database(tmp_path))
    # Neutral readback executable, bound by host; models never choose binaries.
    script=tmp_path/'readback.py';script.write_text('import sqlite3,sys,json\nprint(json.dumps(sqlite3.connect(sys.argv[1]).execute("select * from records").fetchall()))')
    f['steps'] += [dict(id='cli',op='cli',entry='records',argv=[{'$path':'records.sqlite'}])]
    f['checks'] += [dict(step='cli',pointer='/stdout',expected='[[7,"中文记录"]]',comparison='json_stream')]
    f=Scenario.model_validate(f).model_dump();request=json.loads(json.dumps(f));request['steps'][-1]['command']=[sys.executable,str(script)]
    receipt=asyncio.run(scenario.execute(request,tmp_path))
    assert evaluate(f,receipt,runtime.compare,runtime.pointer)[0]=='passed'
    from acceptance.universal.scenarios import validate_bindings
    target=dict(units=[dict(id='u',entries=[])],interfaces=[dict(unit='u',path=f['steps'][0]['module'],functions=[dict(name='Database')])])
    with pytest.raises(ValueError,match='命令'):validate_bindings(Scenario.model_validate(f),target,'u')
    receipt['steps'][-1]['value']['exit_code']=2
    assert evaluate(f,receipt,runtime.compare,runtime.pointer)[0]=='error'


def test_system_exit_still_runs_cleanup(tmp_path):
    (tmp_path/'abrupt.py').write_text('def stop(): raise SystemExit(2)\ndef close(): return "released"')
    receipt=asyncio.run(scenario.execute(dict(steps=[dict(id='stop',op='call',module='abrupt.py',export='stop')],cleanup=[dict(id='release',op='call',module='abrupt.py',export='close')]),tmp_path))
    assert receipt['status']=='error' and receipt['cleanup'][0]['value']=='released' and receipt['temporary_directory_removed']


def test_typescript_type_contracts_do_not_become_callable_exports(tmp_path):
    (tmp_path/'package.json').write_text('{"name":"neutral"}')
    (tmp_path/'index.d.ts').write_text('export interface Client { send(value: string): Promise<string>; close(): void; }')
    d=discovery.discover(tmp_path,['package.json','index.d.ts'])
    assert not d['interfaces']
    assert [m['name'] for m in d['types'][0]['types'][0]['members']]==['send','close']
    assert d['types'][0]['types'][0]['members'][0]['parameters'][0]['name']=='value'


def test_node_cli_uses_same_temporary_directory(tmp_path):
    script=tmp_path/'read.cjs';script.write_text('console.log(require("node:fs").readFileSync(process.argv[2],"utf8"))')
    request=dict(steps=[dict(id='file',op='write_file',path='input.txt',value='中文内容'),dict(id='read',op='cli',command=[str(NODE),str(script)],argv=[{'$path':'input.txt'}])],cleanup=[])
    js='require(process.argv[1]).execute(JSON.parse(process.argv[2]),process.argv[3]).then(r=>console.log(JSON.stringify(r)))'
    p=subprocess.run([str(NODE),'-e',js,str(Path('acceptance/universal/scenario.cjs').resolve()),json.dumps(request),str(tmp_path)],capture_output=True,text=True,check=True,timeout=10)
    r=json.loads(p.stdout);assert r['steps'][1]['value']['stdout'].strip()=='中文内容' and r['temporary_directory_removed']


def test_cli_cleanup_nonzero_cannot_pass():
    f=dict(steps=[dict(id='read',op='get')],checks=[dict(step='read',expected=1)],cleanup=[dict(id='release',op='cli')])
    receipt=dict(status='completed',steps=[dict(id='read',status='completed',observable=True,value=1)],cleanup=[dict(id='release',status='completed',value={'exit_code':1})],temporary_directory_removed=True)
    assert evaluate(f,receipt,runtime.compare,runtime.pointer)[0]=='error'


def test_node_lazy_result_await_preserves_factory_and_resolves_response(tmp_path):
    (tmp_path/'index.cjs').write_text('''module.exports=function(){let started=false,handler;return {then(ok){started=true;ok()},route(fn){if(started)throw Error("factory awaited before setup");handler=fn},request(){return {then(ok){Promise.resolve(handler()).then(body=>ok({json(){return body}}))}}},close(){}}}''')
    f=dict(steps=[dict(id='app',op='call',module='index.cjs',export='default'),dict(id='route',op='call',target='app',member='route',args=[{'$callback':{'return':{'message':'真实响应'},'async':True}}]),dict(id='response',op='call',target='app',member='request'),dict(id='json',op='call',target='response',member='json')],cleanup=[dict(id='close',op='call',target='app',member='close')],checks=[dict(step='json',expected={'message':'真实响应'})])
    js='require(process.argv[1]).execute(JSON.parse(process.argv[2]),process.argv[3]).then(r=>console.log(JSON.stringify(r)))'
    p=subprocess.run([str(NODE),'-e',js,str(Path('acceptance/universal/scenario.cjs').resolve()),json.dumps(f),str(tmp_path)],capture_output=True,text=True,check=True,timeout=10)
    r=json.loads(p.stdout)
    assert evaluate(f,r,runtime.compare,runtime.pointer)[0]=='passed'
    assert r['steps'][-1]['awaited_target']=='response'
    assert r['steps'][0]['observable'] is False


def test_python_properties_are_distinguished_from_methods(tmp_path):
    (tmp_path/'record.py').write_text('class Record:\n @property\n def count(self) -> int: return 2\n def query(self, *, order="id"): return []\n')
    row=discovery.python_exports(tmp_path,'record.py')[0]
    count=next(m for m in row['methods'] if m['name']=='count')
    query=next(m for m in row['methods'] if m['name']=='query')
    assert count['kind']=='property' and query['kind']=='method'
    assert query['keyword_only']==[{'name':'order','optional':True}]


@pytest.mark.parametrize('kind,state,expected_calls',[('json_syntax','rejected',2),('json_syntax','upstream_unknown',1),('semantic','rejected',1)])
def test_only_known_completed_json_syntax_failure_is_retried(tmp_path,monkeypatch,kind,state,expected_calls):
    from acceptance.universal import service
    from acceptance.integrations.store import IntegrationStore
    s=IntegrationStore(tmp_path/'store');(s.root/'model-calls').mkdir();attempts=[];captured=[]
    def draft(store,data):
        n=len(attempts)+1;attempts.append(n)
        if n==2:return {'id':'new-draft'}
        receipt=dict(client_request_id='r1',state=state,rejection_kind=kind)
        (s.root/'model-calls'/'r1.json').write_text(json.dumps(receipt))
        raise ValueError('first response rejected')
    monkeypatch.setattr(service.provider,'draft',draft)
    if expected_calls==2:
        assert service.design_draft(s,None,lambda:False,captured.append)['id']=='new-draft'
        assert len(captured)==1
    else:
        with pytest.raises(ValueError):service.design_draft(s,None,lambda:False,captured.append)
        assert not captured
    assert len(attempts)==expected_calls


def test_json_format_retry_is_bounded_and_does_not_change_input(tmp_path,monkeypatch):
    from acceptance.universal import service
    from acceptance.integrations.store import IntegrationStore
    s=IntegrationStore(tmp_path/'store');(s.root/'model-calls').mkdir();attempts=[];data=object();captured=[]
    def draft(store,actual):
        assert actual is data
        n=len(attempts)+1;attempts.append(n)
        (s.root/'model-calls'/f'r{n}.json').write_text(json.dumps(dict(client_request_id=f'r{n}',state='rejected',rejection_kind='json_syntax')))
        raise ValueError('malformed output')
    monkeypatch.setattr(service.provider,'draft',draft)
    with pytest.raises(ValueError):service.design_draft(s,data,lambda:False,captured.append)
    assert attempts==[1,2] and len(captured)==1


def projected_flow():
    return Scenario.model_validate(dict(steps=[dict(id='reply',op='call',module='reply.py',export='reply')],checks=[dict(step='reply',pointer='/body/message',expected='实际响应')])).model_dump()


def test_python_projects_public_data_without_turning_handle_into_oracle(tmp_path):
    (tmp_path/'reply.py').write_text('class Response:\n def __init__(self):self.body={"message":"实际响应"};self.circular=self\n def close(self):pass\ndef reply():return Response()\n')
    f=projected_flow();request={k:f[k] for k in ('steps','cleanup')};request['observations']=[dict(step='reply',pointer='/body/message')]
    receipt=asyncio.run(scenario.execute(request,tmp_path))
    assert receipt['steps'][0]['observable'] is False
    assert evaluate(f,receipt,runtime.compare,runtime.pointer)[0]=='passed'
    f['checks'][0]['expected']='错误预期'
    assert evaluate(f,receipt,runtime.compare,runtime.pointer)[0]=='failed'
    f['checks'][0].update(pointer='',expected={})
    assert evaluate(f,receipt,runtime.compare,runtime.pointer)[0]=='error'


def test_node_projects_public_data_with_methods_and_circular_links(tmp_path):
    (tmp_path/'reply.cjs').write_text('exports.reply=()=>{const r={body:{message:"实际响应"},close(){}};r.circular=r;return r}')
    f=projected_flow();f['steps'][0]['module']='reply.cjs'
    request={k:f[k] for k in ('steps','cleanup')};request['observations']=[dict(step='reply',pointer='/body/message')]
    js='require(process.argv[1]).execute(JSON.parse(process.argv[2]),process.argv[3]).then(r=>console.log(JSON.stringify(r)))'
    p=subprocess.run([str(NODE),'-e',js,str(Path('acceptance/universal/scenario.cjs').resolve()),json.dumps(request),str(tmp_path)],capture_output=True,text=True,check=True,timeout=10)
    receipt=json.loads(p.stdout)
    assert receipt['steps'][0]['observable'] is False
    assert evaluate(f,receipt,runtime.compare,runtime.pointer)[0]=='passed'
    f['checks'][0]['expected']='错误预期'
    assert evaluate(f,receipt,runtime.compare,runtime.pointer)[0]=='failed'


def test_projection_request_contains_paths_but_never_oracles(tmp_path,monkeypatch):
    from acceptance.universal.models import Case
    f=projected_flow();c=Case(id='C',title='对象字段读取',unit='u',kind='scenario',flow=f,expected=None).model_dump()
    r={'universal_plan':{'execution_contract':{'version':6}},'universal_generation':{'requirements':[dict(id='R',source='D',quote='返回实际响应',cases=[c])]}}
    def command(run,u,argv,*args,**kwargs):
        request=json.loads(base64.b64decode(argv[-1]))
        assert set(request)=={'steps','cleanup','observations'} and request['observations']==[dict(step='reply',pointer='/body/message')]
        assert '实际响应' not in json.dumps(request,ensure_ascii=False) and 'checks' not in request
        receipt=dict(status='completed',steps=[dict(id='reply',status='completed',observable=False,value={'handle_type':'Response'},observations=[dict(pointer='/body/message',observable=True,value='实际响应')])],cleanup=[],temporary_directory_removed=True)
        return dict(exit_code=0),dict(stdout=('ACCEPTANCE_VALUE:'+json.dumps(receipt)).encode())
    monkeypatch.setattr(runtime,'command',command)
    report,_=runtime.business(r,dict(id='u',runtime='python'),tmp_path,lambda:False)
    assert report['tests'][0]['status']=='passed'


@pytest.mark.parametrize('expression',['()=>42','undefined'])
def test_node_non_json_values_are_not_observable_null(tmp_path,expression):
    (tmp_path/'value.cjs').write_text('exports.result=()=>('+expression+')')
    f=Scenario.model_validate(dict(steps=[dict(id='r',op='call',module='value.cjs',export='result')],checks=[dict(step='r',expected=None)])).model_dump()
    js='require(process.argv[1]).execute(JSON.parse(process.argv[2]),process.argv[3]).then(r=>console.log(JSON.stringify(r)))'
    p=subprocess.run([str(NODE),'-e',js,str(Path('acceptance/universal/scenario.cjs').resolve()),json.dumps(f),str(tmp_path)],capture_output=True,text=True,check=True,timeout=10)
    receipt=json.loads(p.stdout)
    assert evaluate(f,receipt,runtime.compare,runtime.pointer)[0]=='error'


def test_missing_or_private_projection_is_error_not_product_failure(tmp_path):
    (tmp_path/'reply.py').write_text('class Response:\n def __init__(self):self.body={"message":"实际响应"}\ndef reply():return Response()\n')
    for name in ['/missing','/__class__']:
        f=projected_flow();f['checks'][0]['pointer']=name
        request={k:f[k] for k in ('steps','cleanup')};request['observations']=[dict(step='reply',pointer=name)]
        receipt=asyncio.run(scenario.execute(request,tmp_path))
        assert evaluate(f,receipt,runtime.compare,runtime.pointer)[0]=='error'
