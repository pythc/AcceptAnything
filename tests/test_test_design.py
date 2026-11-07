from copy import deepcopy
import json
from pathlib import Path
import pytest
from fastapi.testclient import TestClient
from acceptance.planning.models import DesignInput, Specification
from acceptance.planning import compiler, service
from acceptance.planning.execution import validate_results, verify_plan_files
from acceptance.integrations.store import IntegrationStore
from acceptance.integrations.runner import sha, encode
from acceptance.api import create_app
from acceptance.engine import Store


@pytest.fixture
def design(tmp_path):
    root=tmp_path/'repository';root.mkdir()
    (root/'math.mjs').write_text('export const inRange = n => n >= 10 && n <= 20;')
    return dict(repository=str(root),include_scanners=False,documents=[dict(id='PRD',title='独立标准',content='接受十到二十的数值，包含两端边界。')],
        specification=dict(title='区间验收',scope='仅验数值区间',requirements=[dict(id='R1',title='数值范围',source='PRD',quote='接受十到二十的数值，包含两端边界。',scenarios=[
            dict(id='S1',title='边界',dimension='boundary',engine='module',boundary=dict(variable='n',minimum=10,maximum=20),steps=[
                dict(kind='call',module='math.mjs',function='inRange',args=['${n}'],assertions=[dict(value='${expected}')])])])]))


def test_generation_has_real_source_lineage_and_new_assertions(design):
    plan=compiler.compile_plan(DesignInput.model_validate(design))
    assert [c['parameters'] for c in plan['cases']]==[{'n':9,'expected':False},{'n':10,'expected':True},{'n':15,'expected':True},{'n':20,'expected':True},{'n':21,'expected':False}]
    assert all(c['source']['quote']==design['documents'][0]['content'] for c in plan['cases'])
    assert plan['generated']['test_generated.py'].count('def test_C')==5
    assert plan['coverage'][0]['cases']==[c['id'] for c in plan['cases']]
    assert plan['coverage'][0]['dimensions']==['boundary']
    assert not list(Path(design['repository']).glob('test*'))


@pytest.mark.parametrize('fault',['quote','source','duplicate','path','function','variable','empty','vacuous','schema','range','explosion','environment'])
def test_unsupported_or_untraceable_plans_are_rejected(design,fault):
    r=design['specification']['requirements'][0];s=r['scenarios'][0];a=s['steps'][0]
    if fault=='quote':r['quote']='不是原文中的业务标准'
    if fault=='source':r['source']='unknown'
    if fault=='duplicate':design['specification']['requirements'].append(deepcopy(r))
    if fault=='path':a['module']='../escape.mjs'
    if fault=='function':a['function']='process.exit(0)'
    if fault=='variable':a['args']=['${undefined}']
    if fault=='empty':r['scenarios']=[]
    if fault=='vacuous':a['assertions']=[{'operator':'contains','value':''}]
    if fault=='schema':a['assertions']=[{'operator':'schema','value':{'$ref':'https://external.example/schema'}}]
    if fault=='range':s['boundary']['maximum']=5
    if fault=='explosion':s.pop('boundary');s['matrix']={'n':list(range(30)),'expected':list(range(30))}
    if fault=='environment':design['specification']['environment']={'mode':'service','entrypoint':'math.mjs'}
    with pytest.raises(ValueError):compiler.compile_plan(DesignInput.model_validate(design))


def test_required_unresolved_stays_blocked_exclusion_does_not_generate_cases(tmp_path,design):
    r=deepcopy(design['specification']['requirements'][0]);r.update(id='R2',scenarios=[],disposition='unresolved',reason='缺少业务期望');design['specification']['requirements'].append(r)
    excluded=deepcopy(r);excluded.update(id='R3',disposition='excluded',reason='真实邮箱本次不接入');design['specification']['requirements'].append(excluded)
    store=IntegrationStore(tmp_path/'store');p=service.prepare(store,DesignInput.model_validate(design))
    assert not p['ready'] and len(p['cases'])==5 and p['blockers'][0]['id']=='R2'
    assert any(x['reason']=='真实邮箱本次不接入' for x in p['exclusions'])
    with pytest.raises(ValueError,match='待确认'):service.create_run(store,p['id'],p['digest'])


@pytest.mark.parametrize('fault',['source','added','mode','plan','confirmation','toolchain','compiler'])
def test_confirmed_plan_drift_blocks_start(tmp_path,design,monkeypatch,fault):
    store=IntegrationStore(tmp_path/'store');p=service.prepare(store,DesignInput.model_validate(design));digest=p['digest']
    target=Path(design['repository'])/'math.mjs'
    if fault=='source':target.write_text('changed')
    if fault=='added':(target.parent/'new.mjs').write_text('new')
    if fault=='mode':target.chmod(0o700)
    if fault=='plan':
        file=store.root/'designs'/(p['id']+'.json');r=json.loads(file.read_bytes());r['record']['scope']='changed';file.write_text(json.dumps(r))
    if fault=='confirmation':digest='a'*64
    if fault=='toolchain':monkeypatch.setattr(compiler,'dependencies',lambda:{})
    if fault=='compiler':monkeypatch.setattr(compiler,'compiler_digest',lambda:'0'*64)
    monkeypatch.setattr(store,'create',lambda *a,**kw:pytest.fail('must reject before freeze'))
    with pytest.raises(ValueError):service.create_run(store,p['id'],digest)


def test_generated_files_and_plan_are_frozen_and_cannot_bypass_confirmation(tmp_path,design):
    store=IntegrationStore(tmp_path/'store');p=service.prepare(store,DesignInput.model_validate(design));r=service.create_run(store,p['id'],p['digest'])
    assert store.snapshot(r['id'])['integrity']
    verify_plan_files(store,r)
    with pytest.raises(ValueError,match='已确认方案'):store.create(r['profile_id'])
    (store.path(r['id'])/'generated/test_generated.py').write_text('pass')
    with pytest.raises(ValueError,match='生成代码'):verify_plan_files(store,r)


@pytest.mark.parametrize('fault',['missing','duplicate','skip','exit','trace','identity','partial'])
def test_reports_must_match_planned_cases_and_steps(tmp_path,design,fault):
    plan=compiler.compile_plan(DesignInput.model_validate(design));task={'id':'generated-pytest'}
    rows=[dict(name=c['name'],status='passed') for c in plan['cases']]
    for c in plan['cases']:(tmp_path/(c['id']+'-trace.json')).write_bytes(encode(dict(case_id=c['id'],requirement=c['requirement'],status='passed',steps=c['steps'])))
    code=0
    if fault=='missing':rows.pop()
    if fault=='duplicate':rows[-1]['name']=rows[0]['name']
    if fault=='skip':rows[0]['status']='skipped'
    if fault=='exit':code=1
    if fault=='trace':(tmp_path/'C0001-trace.json').unlink()
    if fault in {'identity','partial'}:
        f=tmp_path/'C0001-trace.json';x=json.loads(f.read_bytes());x['case_id' if fault=='identity' else 'steps']='wrong' if fault=='identity' else [];f.write_bytes(encode(x))
    with pytest.raises(ValueError):validate_results(plan,task,{'tests':rows},{'exit_code':code},tmp_path)


def test_api_captures_only_previous_variables_and_rejects_external_requests(design):
    design['specification']['environment']={'mode':'service','runtime':'node','entrypoint':'math.mjs'}
    s=design['specification']['requirements'][0]['scenarios'][0]
    s.update(engine='api',steps=[{'kind':'http','method':'POST','path':'/objects','status':201,'capture':{'id':'/id'}},{'kind':'http','path':'/objects/${id}','status':200,'assertions':[{'pointer':'/id','value':'${id}'}]}]);s.pop('boundary')
    assert len(compiler.compile_plan(DesignInput.model_validate(design))['cases'])==1
    s['steps'][1]['path']='https://external.example'
    with pytest.raises(ValueError):compiler.compile_plan(DesignInput.model_validate(design))


def test_public_api_enforces_schema_same_origin_and_no_model_fallback(tmp_path,design,monkeypatch):
    monkeypatch.delenv('ACCEPTANCE_PLANNER_BASE_URL',raising=False)
    client=TestClient(create_app(Store(tmp_path/'api')))
    assert client.get('/api/integrations/planning/status').json()['configured'] is False
    url='/api/integrations/planning/plan'
    assert client.post(url,json={**design,'command':'run anything'}).status_code==422
    assert client.post(url,json=design,headers={'Origin':'https://foreign.example'}).status_code==403
    p=client.post(url,json=design);assert p.status_code==200 and len(p.json()['cases'])==5
    body={k:design[k] for k in ['repository','documents']};body['scope']='测试范围'
    response=client.post('/api/integrations/planning/draft',json=body)
    assert response.status_code==409 and '未配置' in response.text


@pytest.mark.parametrize('fault',['none','quote','environment','truncated'])
def test_model_proposals_use_same_contract_and_record_provenance(tmp_path,design,monkeypatch,fault):
    import httpx
    from acceptance.planning import provider
    from acceptance.planning.models import DraftInput
    monkeypatch.setenv('ACCEPTANCE_PLANNER_BASE_URL','http://127.0.0.1:12345/v1')
    monkeypatch.setenv('ACCEPTANCE_PLANNER_MODEL','contract-test-model')
    monkeypatch.delenv('ACCEPTANCE_PLANNER_KEY_FILE',raising=False)
    spec=deepcopy(design['specification'])
    if fault=='quote':spec['requirements'][0]['quote']='模型编造的业务标准'
    if fault=='environment':spec['environment']={'mode':'module','runtime':'python'}
    def respond(request):
        body=json.loads(request.content)
        assert 'output_schema' in body['messages'][1]['content']
        assert 'return n >=' not in request.content.decode()
        return httpx.Response(200,json={'choices':[{'finish_reason':'length' if fault=='truncated' else 'stop','message':{'content':json.dumps(spec)}}]})
    Client=httpx.Client
    monkeypatch.setattr(provider.httpx,'Client',lambda **kwargs:Client(transport=httpx.MockTransport(respond),**kwargs))
    store=IntegrationStore(tmp_path/'store')
    data=DraftInput(repository=design['repository'],documents=design['documents'],scope='区间判定')
    if fault!='none':
        with pytest.raises(ValueError):provider.draft(store,data)
    else:
        d=provider.draft(store,data);design['draft_id']=d['id'];design['specification']=d['specification']
        p=service.prepare(store,DesignInput.model_validate(design))
        assert p['planner']['kind']=='model' and p['planner']['edited'] is False and len(p['cases'])==5


def test_unsupported_dimensions_require_real_executor_conditions(design):
    design['specification']['requirements'][0]['scenarios'][0]['dimension']='recovery'
    with pytest.raises(ValueError,match='恢复环境'):DesignInput.model_validate(design)


@pytest.mark.parametrize('fault',['none','missing','duplicate','skipped','empty','ref'])
def test_contract_must_execute_every_declared_operation(tmp_path,design,fault):
    contract={'openapi':'3.0.3','paths':{'/health':{'get':{'responses':{'200':{'description':'OK'}}}},'/items':{'post':{'responses':{'201':{'description':'Created'}}}}}}
    if fault=='empty':contract['paths']={'/health':{}}
    if fault=='ref':contract['paths']['/health']={'$ref':'#/components/pathItems/Health'}
    design['documents'].append(dict(id='API',title='接口契约',content=json.dumps(contract)))
    design['specification']['environment']={'mode':'service','entrypoint':'math.mjs'}
    scenario=design['specification']['requirements'][0]['scenarios'][0]
    scenario.update(engine='openapi',steps=[],contract='API');scenario.pop('boundary')
    if fault in {'empty','ref'}:
        with pytest.raises(ValueError):compiler.compile_plan(DesignInput.model_validate(design))
        return
    plan=compiler.compile_plan(DesignInput.model_validate(design));task={'id':plan['checks'][0]['id']}
    rows=[dict(name='GET /health',status='passed'),dict(name='POST /items',status='passed')]
    if fault=='missing':rows.pop()
    if fault=='duplicate':rows[-1]['name']='GET /health'
    if fault=='skipped':rows[-1]['status']='skipped'
    if fault=='none':validate_results(plan,task,{'tests':rows},{'exit_code':0},tmp_path)
    else:
        with pytest.raises(ValueError):validate_results(plan,task,{'tests':rows},{'exit_code':0},tmp_path)
