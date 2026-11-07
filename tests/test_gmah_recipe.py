import json
from pathlib import Path
import pytest
from acceptance.planning.models import Environment,ServiceSpecification
from acceptance.planning.gmah import KEYS
from acceptance.planning import service,compiler
from acceptance.planning.models import DesignInput
from acceptance.integrations.store import IntegrationStore


def test_gmah_recipe_rejects_unreviewed_runtime_and_commands():
    with pytest.raises(ValueError):Environment(mode='service',runtime='node',entrypoint='run.cjs',recipe='gmah-v1')
    with pytest.raises(ValueError):Environment(mode='service',runtime='python',entrypoint='src/agent_workflow/api/app.py',recipe='gmah-v1',command='anything')


def test_service_model_schema_does_not_offer_module_or_fake_recovery():
    schema=ServiceSpecification.model_json_schema()
    scenario=schema['$defs']['ServiceScenario']['properties']
    assert set(scenario['engine']['enum'])=={'api','browser','openapi'}
    assert 'performance' not in scenario['dimension']['enum'] and 'recovery' not in scenario['dimension']['enum']
    assert 'Call' not in schema['$defs']


def test_recipe_adds_mandatory_native_gates_and_pins_runtime(tmp_path):
    repo=tmp_path/'repo';entry=repo/'src/agent_workflow/api/app.py';entry.parent.mkdir(parents=True);entry.write_text('# no target execution')
    text='创建会话之后必须能读回。'
    data=DesignInput(repository=str(repo),include_scanners=False,documents=[dict(id='R',title='合同',content=text)],
        specification=dict(title='本地验收',scope='本地会话',environment=dict(mode='service',runtime='python',entrypoint='src/agent_workflow/api/app.py',recipe='gmah-v1'),requirements=[dict(id='R1',title='会话读回',source='R',quote=text,scenarios=[dict(id='S1',title='读取会话',dimension='normal',engine='api',steps=[dict(kind='http',path='/sessions/example',status=200)])])]))
    store=IntegrationStore(tmp_path/'store');p=service.prepare(store,data)
    native={t['tool'] for t in p['profile']['tasks'] if t['tool'].startswith('gmah-')}
    assert native=={'gmah-build','gmah-regression','gmah-performance','gmah-recovery'}
    assert all(p['toolchain']['images'][k].startswith('sha256:') for k in KEYS)
    assert next(r for r in p['profile']['rules'] if r['id']=='gmah-regression-count')['threshold']==248
    assert compiler.compiler_digest()==p['compiler_digest']


@pytest.mark.parametrize('fault',['missing-native','missing-browser','unverified-model','incomplete-report','missing-cleanup','integrity'])
def test_recipe_never_calls_partial_execution_complete(fault):
    from acceptance.planning.gmah import completion
    tools=['gmah-build','gmah-regression','gmah-performance','gmah-recovery','bandit']
    r=dict(tasks=[dict(id=t,tool=t,state='completed',report=dict(complete=True,tests=[])) for t in tools],integrity=True,
        artifacts=[dict(name=str(i)+'/cleanup.json') for i in range(4)],test_plan=dict(checks=[dict(engine='api'),dict(engine='browser')],
        planner=dict(kind='model',edited=False,connection=dict(verified=True,provider='chat2api',requested_model='gpt-6-thinking',actual_model='gpt-6-thinking',reasoning_effort='high',actual_thinking_effort='extended',finish_reason='stop'))))
    assert completion(r)['complete']
    if fault=='missing-native':r['tasks'].pop(0)
    if fault=='missing-browser':r['test_plan']['checks'].pop()
    if fault=='unverified-model':r['test_plan']['planner']['connection']['verified']=False
    if fault=='incomplete-report':r['tasks'][0]['report']['complete']=False
    if fault=='missing-cleanup':r['artifacts'].pop()
    if fault=='integrity':r['integrity']=False
    assert not completion(r)['complete'] and completion(r)['missing']
