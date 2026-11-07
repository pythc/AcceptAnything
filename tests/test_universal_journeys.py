import asyncio,json,os,subprocess,threading
from http.server import BaseHTTPRequestHandler,ThreadingHTTPServer
from pathlib import Path
import pytest
from types import SimpleNamespace
from acceptance.engine import NODE,ROOT
from acceptance.universal import orchestration
from acceptance.universal.journeys import Journey,BrowserStep
from acceptance.universal.models import Case
from acceptance.universal.scenario import execute


def test_browser_contract_rejects_ignored_oracles_bad_types_and_opaque_expected():
    for raw in [dict(action='expect_count',selector='p',expected='1'),dict(action='expect_visible',selector='p',expected='yes'),dict(action='expect_text',selector='p',expected='${actual}'),dict(action='expect_validity',selector='input',expected={}),dict(action='goto',path='//elsewhere')]:
        with pytest.raises(ValueError):BrowserStep(id='s',**raw)
    with pytest.raises(ValueError,match='request只采集回执'):BrowserStep.model_validate(dict(id='s',action='request',expected=200),context={'protocol_version':18})
    assert BrowserStep(id='s',action='request',expected=200).expected==200
    with pytest.raises(ValueError):Case(id='c',title='步骤',unit='u',kind='journey',expected=None)
    with pytest.raises(ValueError):Journey(setup=[dict(id='app',op='call',module='a.py',export='create')],app='missing',adapter='wsgi',steps=[dict(id='check',action='expect_text',selector='p',expected='ok')])


def test_source_bound_graph_works_for_neutral_names_and_excludes_tests(tmp_path):
    (tmp_path/'src').mkdir();(tmp_path/'tests').mkdir()
    (tmp_path/'src/queue_app.py').write_text('BROKER="redis://localhost"\ndef create(): pass')
    (tmp_path/'launcher.py').write_text('from src.queue_app import create\napplication=create()')
    (tmp_path/'tests/sample.py').write_text('URL="redis://localhost:7777"')
    (tmp_path/'README.md').write_text('$ celery -A launcher worker --loglevel INFO\n$ celery -A launcher worker; curl bad\n')
    (tmp_path/'page.html').write_text('<form id="request"><input name="amount" required><button>提交</button></form><span id="result">实现输出不可作预期</span><section data-testid="status"></section><div role="alert" aria-label="状态"></div><p>未标识文本不可作预期</p>')
    u=dict(id='u',runtime='python',path='.',interfaces=1,capabilities=['scenario'])
    orchestration.discover(tmp_path,[str(p.relative_to(tmp_path)) for p in tmp_path.rglob('*') if p.is_file()],[u],lambda p,r:u)
    nodes=u['service_graph']['nodes'];assert len(nodes)==2
    assert nodes[0]['id']=='redis-6379' and nodes[0]['supported']
    assert nodes[1]['needs']==['redis-6379'] and nodes[1]['sources'][0]['command'].startswith('celery -A launcher ')
    assert u['ui_bindings'][0]['elements'][1]['attributes']['name']=='amount'
    elements=u['ui_bindings'][0]['elements']
    assert elements[3:]==[dict(tag='span',attributes={'id':'result'}),dict(tag='section',attributes={'data-testid':'status'}),dict(tag='div',attributes={'role':'alert','aria-label':'状态'})]
    assert '实现输出不可作预期' not in json.dumps(u['ui_bindings'])


def test_managed_session_lifetime_precedes_declared_cleanup(tmp_path):
    (tmp_path/'api.py').write_text('def create():return {"alive":True}\ndef close(app):app["alive"]=False\n')
    state_seen={}
    async def ready(state,work,steps):
        assert work.is_dir() and state['app']['alive'];state_seen.update(state);await asyncio.sleep(.01)
    req=dict(steps=[dict(id='app',op='call',module='api.py',export='create')],cleanup=[dict(id='close',op='call',module='api.py',export='close',args=[{'$ref':'app'}])])
    result=asyncio.run(execute(req,tmp_path,ready))
    assert result['status']=='completed' and result['temporary_directory_removed']
    assert state_seen['app']['alive'] is False


def test_journey_requires_a_page_outcome_after_last_action():
    raw=dict(setup=[dict(id='app',op='call',module='app.py',export='create')],app='app',adapter='wsgi',steps=[dict(id='open',action='goto',path='/'),dict(id='visible',action='expect_visible',selector='form',expected=True),dict(id='submit',action='click',selector='button'),dict(id='poll',action='poll',path='/job',expected='ok')])
    with pytest.raises(ValueError,match='页面结果'):Journey.model_validate(raw)
    assert Journey.model_validate(raw,context={'protocol_version':18})


def test_graph_partial_failure_preserves_other_branch_and_reverse_cleanup(tmp_path,monkeypatch):
    from acceptance.universal import runtime
    calls=[]
    def docker(*args,check=True):
        calls.append(args)
        if args[0]=='run' and args[args.index('--name')+1].endswith('broken'):raise ValueError('calibrated startup failure')
        if args[0]=='exec':return SimpleNamespace(returncode=0,stdout='PONG\n',stderr='')
        if args[0]=='inspect':return SimpleNamespace(returncode=1,stdout='',stderr='not found')
        return SimpleNamespace(returncode=0,stdout='',stderr='')
    monkeypatch.setattr(runtime,'docker',docker)
    u=dict(id='u',path='.',service_graph=dict(nodes=[dict(id='broken',kind='redis',needs=[],supported=True),dict(id='dependent',kind='celery',needs=['broken'],supported=True),dict(id='independent',kind='redis',needs=[],supported=True)]))
    r=dict(id='int-calibration',images={'universal-redis':{'id':'locked'}},universal_environment_choices={})
    rows=orchestration.start(r,u,tmp_path,lambda:False)
    assert [x['status'] for x in rows]==['error','error','ready']
    assert '依赖服务未就绪' in rows[1]['error']
    assert len([a for a in calls if a[0]=='run'])==2
    cleanup=tmp_path/'cleanup';cleanup.mkdir();result=orchestration.cleanup(r,u,cleanup)
    assert [x['id'] for x in result]==['independent','dependent','broken'] and all(x['removed'] for x in result)


def test_real_browser_form_async_poll_and_failure_evidence(tmp_path):
    html='''<form id="job"><input name="a" type="number" required><button>提交</button></form><p id="result">待提交</p><script>
    document.querySelector('form').onsubmit=async e=>{e.preventDefault();await fetch('/submit',{method:'POST',body:new FormData(e.target)});let timer=setInterval(async()=>{let r=await (await fetch('/job')).json();if(r.ready){document.querySelector('#result').textContent=String(r.value);clearInterval(timer)}},30)}
    </script>'''
    class Handler(BaseHTTPRequestHandler):
        submitted=False;polls=0
        def log_message(self,*args):pass
        def do_POST(self):
            self.rfile.read(int(self.headers.get('Content-Length',0)));Handler.submitted=True;self.send_response(200);self.end_headers();self.wfile.write(b'{}')
        def do_GET(self):
            self.send_response(200);self.send_header('Content-Type','application/json' if self.path=='/job' else 'text/html; charset=utf-8');self.end_headers()
            if self.path=='/job':
                Handler.polls+=1;self.wfile.write(json.dumps(dict(ready=Handler.submitted and Handler.polls>1,value=6)).encode())
            else:self.wfile.write(html.encode())
    server=ThreadingHTTPServer(('127.0.0.1',0),Handler);thread=threading.Thread(target=server.serve_forever,daemon=True);thread.start()
    try:
        steps=[dict(id='open',action='goto',path='/'),dict(id='required',action='expect_validity',selector='input',expected={'valueMissing':True}),dict(id='fill',action='fill',selector='input',value='6'),dict(id='submit',action='click',selector='button'),dict(id='result',action='expect_text',selector='#result',expected='6',timeout_ms=3000),dict(id='poll',action='poll',path='/job',pointer='/value/value',expected=6,timeout_ms=3000)]
        steps+=[dict(id='instant',action='request',path='/job',pointer='/value/value',expected=6)]
        for label,tail,status in [('pass',[],'passed'),('assert',[dict(id='bad',action='expect_text',selector='#result',expected='wrong',timeout_ms=100)],'failed'),('action',[dict(id='bad',action='click',selector='#missing',timeout_ms=100)],'error'),('request-assert',[dict(id='bad',action='request',path='/job',pointer='/value/value',expected=7)],'failed')]:
            folder=tmp_path/label;folder.mkdir();q=dict(base='http://127.0.0.1:'+str(server.server_port),output=str(folder),steps=steps+tail,ajv=str(ROOT/'validation/node_modules/ajv/dist/2020'),assert_requests=True,self_contained_har=True)
            file=folder/'request.json';file.write_text(json.dumps(q));p=subprocess.run([str(NODE),str(ROOT/'acceptance/universal/journey.cjs'),str(ROOT/'validation/node_modules/@playwright/test'),str(file)],capture_output=True,text=True,timeout=30)
            assert p.returncode==0,p.stdout+p.stderr
            receipt=json.loads((folder/'receipt.json').read_bytes());assert receipt['status']==status,receipt
            assert (folder/'trace.zip').stat().st_size>0 and (folder/'network.har').stat().st_size>0
            assert all('_file' not in e['response']['content'] for e in json.loads((folder/'network.har').read_bytes())['log']['entries'])
            assert (folder/('bad.png' if tail else 'result.png')).is_file()
    finally:server.shutdown();server.server_close()


def test_real_title_assertions_locator_ambiguity_and_transport_pointer_classification(tmp_path):
    html='<title id="head-title">验收 + [A]?</title><h1>品牌</h1><header><h1>目标</h1></header><p id="message">正确</p><headtitle>普通自定义元素</headtitle>'
    class Handler(BaseHTTPRequestHandler):
        def log_message(self,*args):pass
        def do_GET(self):
            self.send_response(200);self.send_header('Content-Type','application/json' if self.path=='/api' else 'text/html; charset=utf-8');self.end_headers();self.wfile.write(b'{"ready":true}' if self.path=='/api' else (html+('<svg><title>图标标题</title></svg>' if self.path=='/svg-title' else '')).encode())
    server=ThreadingHTTPServer(('127.0.0.1',0),Handler);thread=threading.Thread(target=server.serve_forever,daemon=True);thread.start()
    tests=[
        ('title',dict(action='expect_text',selector='title',expected='验收 + [A]?'),'passed',None),
        ('contains',dict(action='expect_text',selector='head > title',comparison='contains',expected='+ [A]?'),'passed',None),
        ('alias',dict(action='expect_text',selector='#head-title',expected='验收 + [A]?'),'passed',None),
        ('svg-ambiguous',dict(action='expect_text',selector='title',expected='验收 + [A]?'),'error','case'),
        ('svg-specific',dict(action='expect_text',selector='#head-title',expected='验收 + [A]?'),'passed',None),
        ('custom',dict(action='expect_text',selector='headtitle',expected='普通自定义元素'),'passed',None),
        ('wrong-title',dict(action='expect_text',selector='title',expected='错误'),'failed',None),
        ('ambiguous',dict(action='expect_text',selector='h1',expected='目标'),'error','case'),
        ('pointer',dict(action='request',path='/api',pointer='/value/ready',expected=True),'passed',None),
        ('capture',dict(action='request',path='/api',pointer='/unused',expected=None,capture='raw'),'passed',None),
        ('bad-pointer',dict(action='poll',path='/api',pointer='/ready',expected=True),'error','case'),
        ('missing',dict(action='expect_text',selector='#missing',expected='应出现'),'failed',None),
        ('mismatch',dict(action='expect_text',selector='#message',expected='错误'),'failed',None),
    ]
    try:
        for label,step,status,category in tests:
            folder=tmp_path/label;folder.mkdir();step=dict(id='assertion',timeout_ms=150,**step)
            request=dict(base='http://127.0.0.1:'+str(server.server_port),output=str(folder),steps=[dict(id='open',action='goto',path='/svg-title' if label.startswith('svg-') else '/'),step],ajv=str(ROOT/'validation/node_modules/ajv/dist/2020'),assert_requests=True,self_contained_har=True)
            file=folder/'request.json';file.write_text(json.dumps(request));driver=os.environ.get('ACCEPTANCE_TEST_JOURNEY_DRIVER',str(ROOT/'acceptance/universal/journey.cjs'))
            p=subprocess.run([str(NODE),driver,str(ROOT/'validation/node_modules/@playwright/test'),str(file)],capture_output=True,text=True,timeout=20)
            assert p.returncode==0,p.stdout+p.stderr
            receipt=json.loads((folder/'receipt.json').read_bytes());assert receipt['status']==status,(label,receipt)
            assert receipt.get('gap_category')==category,(label,receipt)
            assert receipt['steps'][-1]['input']==step
            assert (folder/'trace.zip').is_file() and (folder/'network.har').is_file()
            if label in {'title','contains','alias'}:assert receipt['steps'][-1]['assertion_adapter']=='Playwright.PageAssertions.toHaveTitle'
    finally:server.shutdown();server.server_close()


def test_browser_case_classification_survives_business_report(tmp_path,monkeypatch):
    from acceptance.universal import browser_runtime,runtime
    if os.environ.get('ACCEPTANCE_TEST_UNIVERSAL_RUNTIME'):
        import importlib.util
        spec=importlib.util.spec_from_file_location('acceptance.universal._staged_runtime',os.environ['ACCEPTANCE_TEST_UNIVERSAL_RUNTIME']);runtime=importlib.util.module_from_spec(spec);spec.loader.exec_module(runtime)
    receipt=dict(status='error',gap_category='case',steps=[dict(id='assertion',status='error',gap_category='case',error='strict mode violation',observed='原始观察'*10000+'END')])
    monkeypatch.setattr(browser_runtime,'execute',lambda *a:(receipt,{}))
    case=dict(id='c',title='非唯一定位器',unit='u',kind='journey',requires=[])
    run=dict(universal_generation={'requirements':[dict(id='r',source='d',quote='独立预期',cases=[case])]})
    report,_=runtime.legacy_business(run,dict(id='u'),tmp_path,lambda:False)
    assert report['tests'][0]['status']=='error'
    assert json.loads(report['tests'][0]['detail'])==receipt
    assert json.loads((tmp_path/'cases.json').read_bytes())[0]['gap_category']=='case'
