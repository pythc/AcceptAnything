import json
from pathlib import Path
from types import SimpleNamespace
import pytest
from fastapi.testclient import TestClient
from acceptance import automatic
from acceptance.automatic_cli import equal,run
from acceptance.integrations.store import IntegrationStore
from acceptance.planning.models import CliSpecification,Specification


def repository(tmp_path,files):
    root=tmp_path/'repo';root.mkdir()
    for name,content in files.items():
        p=root/name;p.parent.mkdir(parents=True,exist_ok=True);p.write_text(content)
    return root


def test_manifest_recognition_does_not_execute_repository(tmp_path):
    root=repository(tmp_path,{'go.mod':'module example.org/demo\ngo 1.24\n','go.sum':'','cmd/demo/main.go':'package main\nfunc main() {}','README.md':'Independent usage: demo prints hello'})
    store=IntegrationStore(tmp_path/'store');p=automatic.inspect(store,str(root));d=p['detection']
    assert d['adapter']=='go-cli' and d['entrypoints']==['cmd/demo'] and not p['ready']
    assert d['document_candidates'][0]['path']=='README.md'
    assert not list(root.glob('**/*.xml'))


@pytest.mark.parametrize('filename,stack',[('Cargo.toml','Rust'),('pom.xml','Java / Maven'),('app.csproj','.NET'),('composer.json','PHP')])
def test_unsupported_runtime_is_explicit(tmp_path,filename,stack):
    root=repository(tmp_path,{filename:'{}','README.md':'Usage is independently specified here'})
    p=automatic.inspect(IntegrationStore(tmp_path/'store'),str(root))
    assert p['detection']['stacks'][0]['name']==stack and not p['ready']
    assert any('适配器' in x for x in p['blockers'])


def test_missing_basis_never_calls_model(tmp_path,monkeypatch):
    root=repository(tmp_path,{'go.mod':'module example.org/demo','go.sum':'','main.go':'package main\nfunc main(){}'})
    store=IntegrationStore(tmp_path/'store');p=automatic.inspect(store,str(root));calls=[]
    monkeypatch.setattr('acceptance.planning.provider.draft',lambda *a:calls.append(a))
    with pytest.raises(ValueError,match='缺少独立需求'):automatic.design(store,p['id'],[])
    with pytest.raises(ValueError,match='依据必须'):automatic.design(store,p['id'],['main.go'])
    assert not calls


def test_source_change_blocks_design(tmp_path):
    root=repository(tmp_path,{'go.mod':'module example.org/demo','go.sum':'','main.go':'package main','README.md':'usage: demo prints hello'})
    store=IntegrationStore(tmp_path/'store');p=automatic.inspect(store,str(root));(root/'main.go').write_text('package main\n// changed')
    with pytest.raises(ValueError,match='仓库发生变化'):automatic.design(store,p['id'],['README.md'])


def test_monorepo_does_not_guess_entrypoint(tmp_path):
    root=repository(tmp_path,{'go.mod':'module demo','cmd/a/main.go':'package main','cmd/b/main.go':'package main','README.md':'hello'})
    p=automatic.inspect(IntegrationStore(tmp_path/'store'),str(root));assert p['detection']['adapter'] is None


def test_json_stream_preserves_integer_precision():
    assert equal('4722366482869645213696\n','4722366482869645213696','json_stream')
    assert not equal('4722366482869645213697','4722366482869645213696','json_stream')
    assert equal('{"a":1,"b":2}\n3','{"b":2,"a":1}\n3','json_stream')
    assert not equal('[1,2]','[2,1]','json_stream')


def test_model_wrong_oracle_is_not_rewritten():
    spec={'requirements':[{'id':'REQ','quote':'独立的预期原文','scenarios':[dict(id='C1',title='独立用例',argv=['.foo'],stdin='{}',stdout='123',stderr_contains='',comparison='json_stream',exit_code=0)]}]}
    suite,rows,failures=run(spec,lambda *a,**kw:SimpleNamespace(stdout='456',stderr='',returncode=0))
    assert failures==1 and rows[0]['expected']['stdout']=='123' and rows[0]['stdout']=='456'


def test_timeout_is_failed_execution_not_pass():
    import subprocess
    spec={'requirements':[{'id':'REQ','quote':'独立预期','scenarios':[dict(id='C1',title='独立用例',argv=[],stdin='',stdout='1',stderr_contains='',comparison='json_stream',exit_code=0)]}]}
    def timeout(*a,**kw):raise subprocess.TimeoutExpired('app',15)
    _,rows,failures=run(spec,timeout);assert failures==1 and 'TimeoutExpired' in rows[0]['errors'][0]


def test_cli_cannot_enter_legacy_compiler():
    with pytest.raises(ValueError,match='CLI 需要'):Specification.model_validate(dict(title='命令行',scope='业务验收',environment=dict(mode='cli',runtime='go',entrypoint='cmd/demo'),requirements=[dict(id='R',title='标准',source='DOC',quote='独立依据原文',disposition='unresolved',reason='缺少依据')]))


def test_direct_profile_cannot_bypass_plan(tmp_path):
    root=repository(tmp_path,{'go.mod':'module demo'});store=IntegrationStore(tmp_path/'store')
    store.register(dict(id='demo',name='demo',repository=str(root),version='1',environment='container',scope='test',files=['go.mod'],tasks=[dict(id='business',tool='auto-go-business')],rules=[dict(id='gate',kind='metric',tasks=['business'],metric='tests.failed')]))
    with pytest.raises(ValueError,match='已确认方案'):store.create('demo')


def test_incomplete_task_prevents_scoped_completion():
    record=dict(tasks=[dict(id='native',tool='auto-go-native',state='error')],automatic_plan=dict(planner=dict(connection=dict(verified=True)),blockers=[],scope='CLI'))
    assert not automatic.completion(record)['complete']


def connected_plan(tmp_path,monkeypatch,unresolved=False):
    import httpx
    from acceptance.planning import provider
    from acceptance.integrations import discovery
    root=repository(tmp_path,{'go.mod':'module example.org/demo\ngo 1.24\n','go.sum':'','main.go':'package main\n// BODY_MUST_NOT_BE_ORACLE','README.md':'每个输入原样输出，错误输入提示格式错误。'})
    store=IntegrationStore(tmp_path/'store')
    config=tmp_path/'connection.json';config.write_text(json.dumps(dict(base_url='http://127.0.0.1:9999/v1',model='gpt-6-thinking',provider='chat2api',reasoning_effort='high')))
    monkeypatch.setenv('ACCEPTANCE_PLANNER_CONFIG_FILE',str(config))
    for key in ('BASE_URL','MODEL','KEY_FILE','PROVIDER','REASONING_EFFORT','TIMEOUT_SECONDS'):monkeypatch.delenv('ACCEPTANCE_PLANNER_'+key,raising=False)
    images={key:{'id':'sha256:'+'1'*64} for key in ('auto-go','python','syft','trivy','gitleaks')}
    monkeypatch.setattr(automatic,'locks',lambda:images);monkeypatch.setattr(discovery,'locks',lambda:images);monkeypatch.setattr('acceptance.integrations.store.locks',lambda:images)
    spec=dict(title='命令行业务验收',scope='独立文档范围',environment=dict(mode='cli',runtime='go',entrypoint='.',port=19300,ready_path='/health',recipe=None),requirements=[dict(id='REQ',title='输入输出',source='DOC1',quote='每个输入原样输出，错误输入提示格式错误。',disposition='unresolved' if unresolved else 'required',reason='文档没有足够预期' if unresolved else '',scenarios=[] if unresolved else [dict(id='C'+str(n),title='输入验证'+str(n),dimension='normal',rationale='文档明确输入应原样输出',argv=[],stdin=str(n),comparison='json_stream',stdout=str(n),stderr_contains='',exit_code=0) for n in range(4)])])
    Client=httpx.Client
    def response(request):
        assert 'BODY_MUST_NOT_BE_ORACLE' not in request.content.decode()
        assert json.loads(request.content)['reasoning_effort']=='high'
        return httpx.Response(200,json=dict(model='gpt-6-thinking',thinking_effort='extended',choices=[dict(finish_reason='stop',message=dict(content=json.dumps(spec,ensure_ascii=False)))]))
    monkeypatch.setattr(provider.httpx,'Client',lambda **kwargs:Client(transport=httpx.MockTransport(response),**kwargs))
    intake=automatic.inspect(store,str(root));p=automatic.design(store,intake['id'],['README.md'])
    return store,p,intake


def test_model_plan_frozen_evidence_and_tamper_detection(tmp_path,monkeypatch):
    store,p,_=connected_plan(tmp_path,monkeypatch);assert p['ready'] and p['planner']['connection']['verified']
    r=automatic.create(store,p['id'],p['digest']);assert store.verify(r)
    r['automatic_plan']['specification']['requirements'][0]['scenarios'][0]['stdout']='changed oracle'
    with pytest.raises(ValueError,match='冻结自动方案'):store.verify(r)


def test_unknown_business_expectation_stays_blocked(tmp_path,monkeypatch):
    store,p,_=connected_plan(tmp_path,monkeypatch,unresolved=True)
    assert not p['ready'] and any('文档没有足够预期' in b for b in p['blockers'])
    with pytest.raises(ValueError,match='未就绪'):automatic.create(store,p['id'],p['digest'])


def test_source_drift_after_model_generation_is_not_accepted(tmp_path,monkeypatch):
    store,p,_=connected_plan(tmp_path,monkeypatch);(Path(p['repository'])/'main.go').write_text('package main\n// changed')
    with pytest.raises(ValueError,match='仓库发生变化'):automatic.create(store,p['id'],p['digest'])


def test_booleans_and_numbers_are_not_equivalent_json():
    assert not equal('true','1','json_stream')
    assert not equal('{"x":true}','{"x":1}','json_stream')
    assert not equal(' hello','hello','text')


def test_many_candidates_publish_input_budget_and_prefer_primary_basis(tmp_path):
    files={'go.mod':'module demo','go.sum':'','main.go':'package main','README.md':'中😀'*7000,'docs/README.md':'文档导航'}
    files.update({f'packages/p{i}/README.md':'组件说明' for i in range(21)})
    root=repository(tmp_path,files);p=automatic.inspect(IntegrationStore(tmp_path/'store'),str(root))
    candidates=p['detection']['document_candidates']
    assert len(candidates)==23 and candidates[0]['path']=='README.md' and candidates[1]['path']=='docs/README.md'
    assert candidates[0]['characters']==14000 and candidates[0]['excerpt_characters']==12000
    assert p['detection']['basis_limits']['max_documents']==4
    assert p['detection']['basis_limits']['max_total_characters']==24000


def test_23_document_api_request_is_rejected_before_model_call(tmp_path,monkeypatch):
    from acceptance.api import create_app
    from acceptance.engine import Store
    calls=[];monkeypatch.setattr(automatic,'design',lambda *a:calls.append(a))
    client=TestClient(create_app(Store(tmp_path/'store')))
    response=client.post('/api/acceptance/automatic/design',json=dict(intake_id='intake-'+'a'*16,documents=[f'component/{i}/README.md' for i in range(23)]))
    assert response.status_code==422
    assert response.json()['detail'][0]['ctx']['actual_length']==23 and not calls


def test_oversized_basis_is_rejected_before_any_model_request(tmp_path,monkeypatch):
    files={'go.mod':'module demo','go.sum':'','main.go':'package main','README.md':'中'*12000,'docs/PRD.md':'文'*12000}
    root=repository(tmp_path,files);store=IntegrationStore(tmp_path/'store');p=automatic.inspect(store,str(root));calls=[]
    monkeypatch.setattr('acceptance.planning.provider.draft',lambda *a:calls.append(a))
    with pytest.raises(ValueError,match='24,000'):automatic.design(store,p['id'],['README.md','docs/PRD.md'],'额外需求')
    assert not calls
