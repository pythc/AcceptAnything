"""Declared-package binding and frozen-oracle recompilation invariants."""
import ast
import asyncio
import copy
import importlib
import importlib.util
import json
import os
from pathlib import Path
import sys
import shutil
import subprocess
import types
import uuid

import pytest

from acceptance.engine import ROOT
DRIVERS=Path(os.environ.get('ACCEPTANCE_REPLAY_DRIVER_DIR',ROOT/'acceptance/universal'))


def load(name,monkeypatch):
    if name=='service' and 'ACCEPTANCE_REPLAY_DRIVER_DIR' in os.environ:
        load('fixture_preparation',monkeypatch)
        from acceptance.integrations import registry
        if 'universal-fixture' not in registry.TOOLS:monkeypatch.setitem(registry.TOOLS,'universal-fixture',registry.tool('python','junit',[],report='report.xml',exits=(0,1),network=True))
    if name=='generation':load('callback_contract',monkeypatch)
    package=importlib.import_module('acceptance.universal');label='acceptance.universal.'+name
    spec=importlib.util.spec_from_file_location(label,DRIVERS/(name+'.py'));module=importlib.util.module_from_spec(spec)
    monkeypatch.setitem(sys.modules,label,module);monkeypatch.setattr(package,name,module,raising=False);spec.loader.exec_module(module);return module


@pytest.fixture
def modules(monkeypatch):
    load('callback_contract',monkeypatch)
    bindings=load('bindings',monkeypatch);scenarios=load('scenarios',monkeypatch);generation=load('generation',monkeypatch);service=load('service',monkeypatch);replay=load('replay',monkeypatch)
    return bindings,scenarios,generation,service,replay


def test_syntax_receipt_preserves_ast_obligations_without_live_subprocess(monkeypatch):
    callback=load('callback_contract',monkeypatch)
    from acceptance.universal.scenarios import Scenario
    quote='api.consume(receiver => { receiver.configure(201) })'
    raw=dict(steps=[dict(id='invoke',op='call',module='api.cjs',export='consume',args=[{'$callback':dict(params=['receiver'],calls=[dict(id='configured',target='receiver',member='configure',args=[201])],return_undefined=True)}])],checks=[dict(step='invoke',expected='ok')])
    flow=Scenario.model_validate(raw);evidence=[];callback.verify(quote,flow,check_returns=True,on_receipt=evidence.append);assert len(evidence)==1 and evidence[0]['state']=='completed'
    monkeypatch.setattr(callback,'analyze',lambda *_:pytest.fail('archive reads must not invoke mutable tools'))
    callback.verify(quote,flow,check_returns=True,receipt=evidence[0])
    with pytest.raises(ValueError,match='未绑定'):callback.verify(quote+' ',flow,receipt=evidence[0])
    altered=copy.deepcopy(evidence[0]);altered['validator_sha256']='0'*64
    with pytest.raises(ValueError,match='未绑定'):callback.verify(quote,flow,receipt=altered)
    raw['steps'][0]['args'][0]['$callback']['calls']=[]
    with pytest.raises(ValueError,match='原文回调动作'):callback.verify(quote,Scenario.model_validate(raw),receipt=evidence[0])


def test_syntax_timeout_is_frozen_as_platform_gap_and_not_later_promoted(monkeypatch):
    callback=load('callback_contract',monkeypatch);generation=load('generation',monkeypatch);callback=importlib.import_module('acceptance.universal.callback_contract')
    from acceptance.planning.models import Document
    quote='''约定回调设置201并返回ok。\n```javascript\napi.consume(receiver => { receiver.configure(201) })\n```'''
    doc=Document(id='D',title='契约.md',origin='README.md',content=quote)
    target=dict(units=[dict(id='u',runtime='node',path='.',capabilities=['scenario'])],interfaces=[dict(unit='u',path='api.cjs',functions=[dict(name='consume')])],execution_contract={'version':20})
    output=dict(requirements=[dict(id='R',title='回调契约',source='D',quote=quote,cases=[dict(id='C',title='配置并观察结果',unit='u',kind='scenario',expected=None,flow=dict(steps=[dict(id='invoke',op='call',module='api.cjs',export='consume',args=[{'$callback':dict(params=['receiver'],calls=[dict(id='configured',target='receiver',member='configure',args=[201])],return_undefined=True)}])],checks=[dict(step='invoke',expected='ok')]))])])
    original_run=callback.subprocess.run
    def unavailable(*a,**k):raise subprocess.TimeoutExpired(a[0],15,output=b'partial syntax output',stderr=b'actual stderr')
    monkeypatch.setattr(callback.subprocess,'run',unavailable);evidence=[];rows,issues,anchors=generation.validate(output,[doc],target,collect_syntax=evidence)
    assert not rows[0]['cases'] and issues[0]['category']=='platform'
    import base64
    assert base64.b64decode(evidence[0]['receipt']['stdout'])==b'partial syntax output'
    assert base64.b64decode(evidence[0]['receipt']['stderr'])==b'actual stderr'
    monkeypatch.setattr(callback.subprocess,'run',original_run)
    frozen=generation.validate(output,[doc],target,syntax_evidence=evidence)
    assert frozen==(rows,issues,anchors)
    healthy=generation.validate(output,[doc],target);assert len(healthy[0][0]['cases'])==1 and not healthy[1]
    # Old records have only the exact conservative refusal. Reproduce that
    # refusal; never invent a successful parser run or silently admit a case.
    old_issues=[{k:v for k,v in x.items() if x['kind']!='case' or k not in {'category','classification_source'}} for x in issues]
    rejection=generation.legacy_tool_rejections(dict(issues=old_issues))
    old=generation.validate(output,[doc],target,tool_rejections=rejection)
    assert old[0]==rows and old[1]==old_issues
    wrong=copy.deepcopy(evidence);wrong.append(copy.deepcopy(evidence[0]))
    with pytest.raises(ValueError,match='身份重复'):generation.validate(output,[doc],target,syntax_evidence=wrong)
    replay=load('replay',monkeypatch)
    from acceptance.integrations.runner import sha,encode
    record=dict(id='draft-original',model_output=output,documents=[doc.model_dump()],target=target,requirements=healthy[0],issues=healthy[1],citations=healthy[2])
    original=dict(record=record,sha256=sha(encode(record)));source=dict(run='int-1111111111111111',batch=0,snapshot_digest='same')
    derived=replay.recompile(original,None,source,model_output=output)
    plan=dict(frozen_design_run=source['run'],snapshot_digest='same',projection_context=None,frozen_syntax_validator_sha=derived['syntax_evidence'][0]['receipt']['validator_sha256'])
    monkeypatch.setattr(callback,'analyze',lambda *_:pytest.fail('frozen compilation verification must use its AST receipts'))
    replay.verify_original(original,derived,plan,output,syntax_validator_sha=plan['frozen_syntax_validator_sha'])
    tampered=copy.deepcopy(derived);tampered['requirements'][0]['cases'][0]['flow']['checks'][0]['expected']='forged'
    with pytest.raises(ValueError,match='输入或预期'):replay.verify_original(original,tampered,plan,output,syntax_validator_sha=plan['frozen_syntax_validator_sha'])


def test_pinned_parent_rechecks_all_bytes_without_relaunching_validators(modules,tmp_path):
    _,_,_,_,replay=modules;_,target,docs,output,original,context=sample(modules)
    from acceptance.integrations.runner import sha,encode
    from acceptance.integrations.discovery import manifest
    root=tmp_path/'state';source=root/'runs/int-parent/source';source.mkdir(parents=True);(source/'api.py').write_text('def public():return 4\n')
    files=manifest(str(source),['api.py']);digest=sha(encode(files));rid='int-parent';parentdir=source.parent;envelope=parentdir/'run.json';envelope.write_bytes(b'immutable parent envelope')
    blobs={'draft':encode(original),'input':b'original model input','response':encode({'choices':[{'message':{'content':json.dumps(output,ensure_ascii=False)}}]}),'receipt':b'original receipt'}
    artifacts=[]
    for name,raw in blobs.items():(parentdir/name).write_bytes(raw);artifacts.append(dict(id=name,sha256=sha(raw)))
    parent=dict(status='completed',context=dict(snapshot_digest=digest,files=files),artifacts=artifacts,universal_generation={'batches':[dict(index=0,state='completed',**{name+'_ref':name for name in blobs})]})
    class Store:
        def __init__(self):self.root=root
        def path(self,value):return parentdir
        def read(self,value):return copy.deepcopy(parent)
        def snapshot(self,value):pytest.fail('pinned reads must not rerun mutable external validators')
        def verified_artifact_path(self,record,aid):
            item=next(x for x in artifacts if x['id']==aid);p=parentdir/aid
            if sha(p.read_bytes())!=item['sha256']:raise ValueError('原件摘要不符')
            return item,p
        def artifact_bytes_for_record(self,record,aid):item,p=self.verified_artifact_path(record,aid);return item,p.read_bytes()
    store=Store();plan=dict(frozen_design_run=rid,frozen_parent_record_sha256=sha(envelope.read_bytes()),snapshot_digest=digest,projection_context=context)
    derived,copied=replay.load_draft(store,{'universal_plan':plan},0)
    assert copied['input']==blobs['input'] and derived['model_output']==output
    envelope.write_bytes(b'changed')
    with pytest.raises(ValueError,match='记录字节'):replay.load_draft(store,{'universal_plan':plan},0)
    envelope.write_bytes(b'immutable parent envelope');(source/'api.py').write_text('def public():return 9\n')
    with pytest.raises(ValueError,match='源码字节'):replay.load_draft(store,{'universal_plan':plan},0)
    (source/'api.py').write_text('def public():return 4\n');(parentdir/'receipt').write_bytes(b'changed')
    with pytest.raises(ValueError,match='原件摘要'):replay.load_draft(store,{'universal_plan':plan},0)


def sample(modules):
    bindings,_,generation,_,_=modules
    units=[dict(id='parent',runtime='python',path='lib',manifest='lib/pyproject.toml',capabilities=['module','scenario'],interfaces=1,local_dependencies=[]),dict(id='child',runtime='python',path='app',manifest='app/pyproject.toml',capabilities=['module','scenario'],interfaces=1,local_dependencies=['parent']),dict(id='other',runtime='python',path='other',manifest='other/pyproject.toml',capabilities=['module'],interfaces=1,local_dependencies=[])]
    interfaces=[dict(unit='parent',path='lib/src/public_api/__init__.py',functions=[dict(name='twice')],auxiliary=False),dict(unit='child',path='app/api.py',functions=[dict(name='create')],auxiliary=False),dict(unit='other',path='other/other_api.py',functions=[dict(name='unrelated')],auxiliary=False)]
    target=dict(units=units,interfaces=interfaces,execution_contract={'version':16})
    document=dict(id='D1',title='独立契约',content='对子组件传入整数2，公开twice函数返回整数4。',origin='README.md')
    output=dict(requirements=[dict(id='R1',title='验证公开依赖结果',source='D1',quote=document['content'],cases=[dict(id='C1',title='输入2读回4',unit='child',kind='module',module='public_api',function='twice',args=[2],expected=4)])])
    from acceptance.planning.models import Document
    docs=[Document.model_validate(document)];rows,issues,anchors=generation.validate(output,docs,target)
    from acceptance.integrations.runner import sha,encode
    original=dict(record=dict(id='draft-original',kind='universal-v1',repository='/frozen/original',documents=[document],target=target,model_output=output,requirements=rows,issues=issues,citations=anchors,connection=dict(client_request_id='original-request',actual_model='deepseek-flash',duration_ms=12345),scope='独立契约范围'))
    original['sha256']=sha(encode(original['record']))
    return units,target,docs,output,original,bindings.context(units)


def test_direct_local_public_api_binding_is_source_resolved_and_not_a_global_allowlist(modules):
    bindings,scenarios,generation,_,_=modules;units,target,docs,output,original,context=sample(modules)
    rows,issues,_=generation.validate(output,docs,target);assert not rows[0]['cases'] and issues
    rows,issues,_=generation.validate(output,docs,target,projection_context=context)
    assert not issues and rows[0]['cases'][0]['module']=='lib/src/public_api/__init__.py'
    assert rows[0]['cases'][0]['args']==[2] and rows[0]['cases'][0]['expected']==4
    invalid=copy.deepcopy(output);invalid['requirements'][0]['cases'][0].update(module='other_api',function='unrelated')
    rejected,diagnostics,_=generation.validate(invalid,docs,target,projection_context=context)
    assert not rejected[0]['cases']
    assert len(diagnostics)==1 and diagnostics[0]['kind']=='case'
    units[0]['local_dependencies']=['other'];context=bindings.context(units)
    assert bindings.accessible(target,'child',context)=={'parent','child'}
    flow=scenarios.Scenario(steps=[dict(id='result',op='call',module='lib/src/public_api/__init__.py',export='twice',args=[2])],checks=[dict(step='result',expected=4)])
    with pytest.raises(ValueError):scenarios.validate_bindings(flow,target,'child')
    scenarios.validate_bindings(flow,target,'child',projection_context=context)


def test_recompile_keeps_original_oracle_and_rejects_tampered_expected_values(modules):
    _,_,_,_,replay=modules;units,target,docs,output,original,context=sample(modules)
    before=copy.deepcopy(original);source=dict(run='int-1111111111111111',batch=0,snapshot_digest='frozen')
    derived=replay.recompile(original,context,source,model_output=output)
    assert original==before and derived['model_output']==output
    assert derived['requirements'][0]['cases'][0]['expected']==4
    plan=dict(frozen_design_run=source['run'],snapshot_digest='frozen',projection_context=context)
    replay.verify_original(original,derived,plan,output)
    bad=copy.deepcopy(derived);bad['requirements'][0]['cases'][0]['expected']=3
    with pytest.raises(ValueError,match='输入或预期'):replay.verify_original(original,bad,plan,output)
    bad=copy.deepcopy(derived);bad['model_output']['requirements'][0]['cases'][0]['args']=[100]
    with pytest.raises(ValueError):replay.verify_original(original,bad,plan,output)
    bad=copy.deepcopy(derived);bad['recompiled_from']['snapshot_digest']='other'
    with pytest.raises(ValueError):replay.verify_original(original,bad,plan,output)


def test_replay_preparation_rejects_source_drift_partial_design_and_empty_design(modules,tmp_path,monkeypatch):
    bindings,_,_,service,replay=modules;units,target,docs,output,original,context=sample(modules)
    from acceptance.integrations.discovery import manifest
    from acceptance.integrations.runner import encode,sha
    repository=tmp_path/'repo';repository.mkdir();(repository/'api.py').write_text('def public(): return 4')
    files=manifest(str(repository),['api.py']);root=tmp_path/'state';root.mkdir();(root/'automatic-plans').mkdir()
    p=dict(id='auto-original',repository=str(repository),manifest=files,snapshot_digest=sha(encode(files)),toolchain_digest=sha(encode({})),profile=dict(id='profile-original',name='原始验收',tasks=[dict(id='design-1',tool='universal-design')]),checks=[dict(id='design-1',title='原检查')],batches=[[docs[0].model_dump()]],discovery=dict(units=units,interface_count=3),scope='原始范围',documents=['README.md'],exclusions=[],gaps=[],blockers=[])
    parent=dict(status='completed',integrity=True,universal_plan=p,universal_generation={'batches':[dict(index=0,state='completed')]})
    class Store:
        def __init__(self):self.root=root
        def snapshot(self,rid):return copy.deepcopy(parent)
    monkeypatch.setattr(service,'implementation',lambda:'new-compiler');monkeypatch.setattr(service,'runtime_identity',lambda:{})
    monkeypatch.setattr(replay,'locks',lambda:{})
    unchanged=copy.deepcopy(parent);prepared=replay.prepare(Store(),'int-1111111111111111')
    assert parent==unchanged and prepared['frozen_design_run']=='int-1111111111111111'
    assert prepared['universal']['design_mode']=='frozen-response-replay'
    parent['universal_generation']['batches'][0]['state']='error'
    with pytest.raises(ValueError,match='未完整结束'):replay.prepare(Store(),'int-1111111111111111')
    parent['universal_generation']['batches']=[]
    with pytest.raises(ValueError):replay.prepare(Store(),'int-1111111111111111')
    parent['universal_generation']['batches']=[dict(index=0,state='completed')]
    parent['universal_generation']['batches'][0]['index']=1
    with pytest.raises(ValueError):replay.prepare(Store(),'int-1111111111111111')
    parent['universal_generation']['batches'][0]['index']=0
    (repository/'api.py').write_text('def public(): return 3')
    with pytest.raises(ValueError):replay.prepare(Store(),'int-1111111111111111')


def test_frozen_design_source_is_mutually_exclusive_with_new_repository_selection(monkeypatch):
    path=ROOT/'acceptance/api.py'
    tree=ast.parse(path.read_text());node=next(n for n in tree.body if isinstance(n,ast.ClassDef) and n.name=='FullPlan')
    module=types.ModuleType('d040_plan_schema');monkeypatch.setitem(sys.modules,module.__name__,module)
    exec('from pydantic import BaseModel,ConfigDict,Field,model_validator\nfrom typing import Literal',module.__dict__)
    exec(compile(ast.Module(body=[node],type_ignores=[]),str(path),'exec'),module.__dict__)
    model=module.FullPlan;rid='int-1111111111111111'
    assert model(frozen_design_run=rid).frozen_design_run==rid
    for extra in [dict(repository='/new'),dict(remote_url='https://github.com/org/repo'),dict(configuration='/new/config'),dict(ref='main')]:
        with pytest.raises(ValueError):model(frozen_design_run=rid,**extra)
    assert model(repository='/path').repository=='/path'


def test_design_replay_copies_original_bytes_without_calling_the_model(modules,tmp_path,monkeypatch):
    _,_,_,service,replay=modules;units,target,docs,output,original,context=sample(modules)
    from acceptance.integrations.runner import encode,sha
    derived=replay.recompile(original,context,dict(run='int-1111111111111111',batch=0,snapshot_digest='same'),model_output=output)
    copied=dict(draft=encode(dict(record=derived,sha256=sha(encode(derived)))),original_draft=encode(original),input=b'original input bytes',response=b'original response bytes',receipt=b'original receipt bytes',format_retries=[])
    parent_before=copy.deepcopy(original)
    monkeypatch.setattr(replay,'load_draft',lambda store,run,index:(derived,copied))
    monkeypatch.setattr(service.provider,'draft',lambda *args,**kwargs:pytest.fail('frozen replay must not call the model'))
    monkeypatch.setattr(service,'implementation',lambda:'new-compiler');monkeypatch.setattr(service,'locks',lambda:{})
    class Store:
        def __init__(self):self.root=tmp_path;self.saved={};self.count=0
        def path(self,rid):return tmp_path/rid
        def artifact(self,run,name,raw):
            self.count+=1;aid='artifact-'+str(self.count);self.saved[name]=raw;return aid
        def save(self,run):pass
    store=Store();rid='int-2222222222222222';task=dict(id='design-1',tool='universal-design',target='0')
    p=dict(implementation_digest='new-compiler',toolchain_digest=sha(encode({})),dag=[dict(id='design-1',needs=[])],batches=[[docs[0].model_dump()]],discovery=dict(interfaces=target['interfaces'],types=[]),model_units=units,execution_contract={'version':16},projection_context=context,frozen_design_run='int-1111111111111111',scope='独立验证')
    run=dict(id=rid,universal_plan=p,tasks=[task],universal_generation=dict(requirements=[],issues=[],batches=[]))
    report,_=service.execute(store,run,task,tmp_path/'output',lambda:False)
    assert report['tests'][0]['status']=='passed'
    batch=run['universal_generation']['batches'][0]
    assert batch['generation_mode']=='frozen-response-replay' and batch['connection']['duration_ms']==12345
    for role in ['input','response','receipt']:assert store.saved['model/batch-1-'+role+'.json']==copied[role]
    assert original==parent_before and run['universal_generation']['requirements'][0]['cases'][0]['expected']==4


def test_archived_replay_is_self_contained_and_preserves_original_model_bytes(tmp_path,monkeypatch):
    """Use the real store, provider boundary and archive verifier, no inference.

    Non-design tasks deliberately stay errors in this calibration. It proves
    source/oracle/evidence binding, and does not claim a business run passed.
    """
    import httpx
    import shutil
    from acceptance.universal import service as installed_service
    original_identity=installed_service.runtime_identity
    bindings=load('bindings',monkeypatch);load('scenarios',monkeypatch);load('generation',monkeypatch)
    service=load('service',monkeypatch);replay=load('replay',monkeypatch)
    monkeypatch.setattr(service,'runtime_identity',original_identity)
    from acceptance.integrations.store import IntegrationStore,now
    from acceptance.integrations.runner import encode,sha
    from acceptance.automatic import load as load_plan
    from acceptance.planning import provider
    for key in ('BASE_URL','MODEL','KEY_FILE','PROVIDER','REASONING_EFFORT','TIMEOUT_SECONDS','CONFIG_FILE'):
        monkeypatch.delenv('ACCEPTANCE_PLANNER_'+key,raising=False)
    config=tmp_path/'connection.json';config.write_text(json.dumps(dict(base_url='http://127.0.0.1:9999/v1',model='gpt-6-thinking',provider='chat2api',reasoning_effort='high')))
    monkeypatch.setenv('ACCEPTANCE_PLANNER_CONFIG_FILE',str(config))
    repository=tmp_path/'repo';repository.mkdir()
    files={'pyproject.toml':'[project]\nname="public-library"\nversion="1"',
           'src/public_api/__init__.py':'def twice(value):return value*2',
           'app/pyproject.toml':'[project]\nname="child-app"\nversion="1"',
           'app/child.py':'from public_api import twice\ndef create(value):return twice(value)',
           'README.md':'对子组件传入整数2，公开twice函数返回整数4。'}
    for name,raw in files.items():
        path=repository/name;path.parent.mkdir(parents=True,exist_ok=True);path.write_text(raw)
    store=IntegrationStore(tmp_path/'store');public=service.prepare(store,str(repository));plan=load_plan(store,public['id'])
    # An original v16 model input predates the dependency projection context.
    plan.pop('projection_context');plan['execution_contract']['version']=16
    plan['execution_contract'].pop('public_dependencies',None)
    digest=sha(encode(plan));(store.root/'automatic-plans'/(plan['id']+'.json')).write_bytes(encode(dict(record=plan,sha256=digest)))
    child=next(u for u in plan['discovery']['units'] if u['path']=='app')
    assert child['local_dependencies'] and len(plan['batches'])==1
    doc=plan['batches'][0][0]
    output=dict(requirements=[dict(id='R1',title='公开依赖结果',source=doc['id'],quote=doc['content'],cases=[dict(id='C1',title='输入2返回4',kind='module',unit=child['id'],module='public_api',function='twice',args=[2],expected=4)])])
    requests=[]
    def response(request):
        requests.append(request)
        return httpx.Response(200,json=dict(model='gpt-6-thinking',thinking_effort='extended',choices=[dict(finish_reason='stop',message=dict(content=json.dumps(output,ensure_ascii=False)))]))
    client=httpx.Client;monkeypatch.setattr(provider.httpx,'Client',lambda **kwargs:client(transport=httpx.MockTransport(response),**kwargs))
    parent=service.create(store,plan['id'],digest)
    def finish_design(run):
        for task in run['tasks']:
            if task['tool']!='universal-design':
                task.update(state='error',error='校准任务未执行，不代表业务失败');continue
            out=store.path(run['id'])/'outputs'/task['id']
            task.update(state='running',started_at=now())
            report,command=service.execute(store,run,task,out,lambda:False)
            task.update(state='completed',finished_at=now(),duration_ms=1,report=report,command=command)
            for path in out.iterdir():
                aid=store.artifact(run,task['id']+'/'+path.name,path.read_bytes());task['artifacts'].append(aid)
                if path.name=='report.xml':task['report_ref']=aid
        store.finish(run)
        snapshot=store.snapshot(run['id']);assert snapshot['integrity'],snapshot['errors']
        assert snapshot['decision']=='inconclusive' and snapshot['status']=='completed'
        return snapshot
    parent=finish_design(parent)
    assert len(requests)==1 and not parent['universal_generation']['requirements'][0]['cases']
    frozen={role:store.artifact_bytes_for_record(parent,parent['universal_generation']['batches'][0][role+'_ref'])[1] for role in ['input','response','receipt']}
    monkeypatch.setattr(provider,'draft',lambda *a,**kw:pytest.fail('archive replay cannot request a new oracle'))
    public=replay.prepare(store,parent['id']);derived=service.create(store,public['id'],public['digest']);derived=finish_design(derived)
    assert len(requests)==1 and derived['universal_generation']['requirements'][0]['cases'][0]['expected']==4
    batch=derived['universal_generation']['batches'][0]
    for role,raw in frozen.items():assert store.artifact_bytes_for_record(derived,batch[role+'_ref'])[1]==raw
    shutil.rmtree(store.path(parent['id']))
    assert store.snapshot(derived['id'])['integrity']  # Original bytes embedded in child archive.


def test_click_result_observation_keeps_real_exception_and_original_failed_assertion(tmp_path,monkeypatch):
    scenario=load('scenario',monkeypatch)
    name='commands_'+uuid.uuid4().hex+'.py'
    (tmp_path/name).write_text('''import click
from click.testing import CliRunner
@click.command()
def command():
    raise RuntimeError('required state unavailable')
def invoke():return CliRunner().invoke(command)
''')
    steps=[dict(id='result',op='call',module=name,export='invoke')]
    request=dict(steps=steps,cleanup=[],observations=[dict(step='result',pointer='/output')],observe_process_results=True)
    receipt=asyncio.run(scenario.execute(request,tmp_path));row=receipt['steps'][0]
    assert receipt['status']=='completed'  # Result is returned normally; no invented exception.
    actual=row['process_result'];assert actual['exit_code']==1 and actual['exception']['type']=='RuntimeError'
    assert actual['exception']['message']=='required state unavailable' and actual['output']==''
    assert actual['stdout_bytes']==dict(encoding='base64',value='')
    from acceptance.universal.scenarios import evaluate
    from acceptance.universal.runtime import compare,pointer
    flow=dict(steps=steps,cleanup=[],checks=[dict(step='result',pointer='/output',comparison='contains',expected='Initialized')])
    assert evaluate(flow,receipt,compare,pointer)[0]=='failed'  # Evidence enriches, not suppresses failure.
    request.pop('observe_process_results');legacy=asyncio.run(scenario.execute(request,tmp_path))
    assert 'process_result' not in legacy['steps'][0]


def test_subprocess_observation_keeps_binary_streams_and_ignores_ordinary_objects(tmp_path,monkeypatch):
    scenario=load('scenario',monkeypatch)
    name='process_'+uuid.uuid4().hex+'.py'
    (tmp_path/name).write_text('''import subprocess,sys
def invoke():return subprocess.run([sys.executable,'-c','import sys;sys.stdout.buffer.write(bytes([0,255]));sys.stderr.write("diagnostic");sys.exit(7)'],capture_output=True)
''')
    receipt=asyncio.run(scenario.execute(dict(steps=[dict(id='result',op='call',module=name,export='invoke')],cleanup=[],observe_process_results=True),tmp_path))
    actual=receipt['steps'][0]['process_result']
    assert actual['exit_code']==7 and actual['stdout']==dict(encoding='base64',value='AP8=')
    assert actual['stderr']==dict(encoding='base64',value='ZGlhZ25vc3RpYw==')
    assert scenario.process_result({'exit_code':1,'exception':'not a process result'}) is None


def test_pending_builder_data_read_awaits_result_while_configuration_calls_stay_pending(tmp_path):
    node=os.environ.get('ACCEPTANCE_TEST_NODE') or shutil.which('node');assert node
    name='builder_'+uuid.uuid4().hex+'.mjs'
    (tmp_path/name).write_text('''export function create(){
let configured='original';
return {body(value){configured=value;return this;},then(resolve){resolve({body:configured});}};
}
class Data {count=0;get body(){return 'read'+(++this.count);}}
class PendingData extends Data {then(resolve){resolve({body:'settled'});}}
export function data(){return new Data();}
export function pendingData(){return new PendingData();}
''')
    steps=[dict(id='builder',op='call',module=name,export='create'),dict(id='configured',op='call',target='builder',member='body',args=['actual configured input']),dict(id='field',op='get',target='builder',member='body')]
    payload=dict(steps=steps,cleanup=[],observe_result_fields=True)
    program="require(process.argv[1]).execute(JSON.parse(process.argv[2]),process.argv[3]).then(r=>console.log(JSON.stringify(r))).catch(e=>{console.error(e);process.exit(1)})"
    def run(value):
        result=subprocess.run([node,'-e',program,str((DRIVERS/'scenario.cjs').resolve()),json.dumps(value),str(tmp_path)],capture_output=True,text=True,check=True)
        return json.loads(result.stdout)
    receipt=run(payload);assert receipt['status']=='completed'
    assert not receipt['steps'][1]['observable']  # Config call was not awaited.
    assert receipt['steps'][2]['value']=='actual configured input' and receipt['steps'][2]['awaited_target']=='builder'
    payload.pop('observe_result_fields');legacy=run(payload)
    assert legacy['steps'][2]['value']=={'handle_type':'Function'} and not legacy['steps'][2]['observable']
    for export in ['data','pendingData']:
        receipt=run(dict(steps=[dict(id='object',op='call',module=name,export=export),dict(id='field',op='get',target='object',member='body')],cleanup=[],observe_result_fields=True))
        assert receipt['steps'][1]['value']=='read1' and 'awaited_target' not in receipt['steps'][1]


@pytest.mark.parametrize('language',['python','node'])
@pytest.mark.parametrize('asynchronous',[False,True])
def test_expected_callback_exception_is_observed_by_identity_without_swallowing_other_failures(tmp_path,monkeypatch,language,asynchronous):
    suffix='.py' if language=='python' else '.mjs';name='callback_'+uuid.uuid4().hex+suffix
    raw='''class Resource:
 def fail(self):raise RuntimeError('injected failure')
def invoke(fn):return fn(Resource())
async def invoke_async(fn):return await fn(Resource())
def unrelated(fn):
 try:fn(Resource())
 except RuntimeError:raise ValueError('different failure')
def swallowed(fn):
 try:fn(Resource())
 except RuntimeError:return None
''' if language=='python' else '''class Resource{fail(){throw new Error('injected failure');}}
export function invoke(fn){return fn(new Resource());}
export async function invoke_async(fn){return await fn(new Resource());}
export function unrelated(fn){try{fn(new Resource());}catch{throw new TypeError('different failure');}}
export function swallowed(fn){try{fn(new Resource());}catch{return null;}}
'''
    (tmp_path/name).write_text(raw)
    callback=dict(params=['resource'],calls=[dict(id='fault',target='resource',member='fail')],**({'return':None} if language=='python' else {'return_undefined':True}))
    if asynchronous:callback['async']=True
    step=dict(id='observed',op='observe_call',module=name,export='invoke_async' if asynchronous else 'invoke',args=[{'$callback':callback}])
    payload=dict(steps=[step],cleanup=[],observe_callback_errors=True)
    def execute(value):
        if language=='python':return asyncio.run(load('scenario',monkeypatch).execute(value,tmp_path))
        node=os.environ.get('ACCEPTANCE_TEST_NODE') or shutil.which('node');assert node
        program="require(process.argv[1]).execute(JSON.parse(process.argv[2]),process.argv[3]).then(r=>console.log(JSON.stringify(r))).catch(e=>{console.error(e);process.exit(1)})"
        result=subprocess.run([node,'-e',program,str((DRIVERS/'scenario.cjs').resolve()),json.dumps(value),str(tmp_path)],capture_output=True,text=True,check=True)
        return json.loads(result.stdout)
    receipt=execute(payload);assert receipt['status']=='completed'
    assert receipt['callbacks'][0]['status']=='observed-error' and receipt['callbacks'][0]['observed_by']=='observed'
    assert receipt['steps'][0]['value']['raised'] is True
    from acceptance.universal.scenarios import evaluate
    from acceptance.universal.runtime import compare,pointer
    flow=dict(steps=[step],cleanup=[],checks=[dict(step='observed',pointer='/raised',comparison='equals',expected=True)])
    assert evaluate(flow,receipt,compare,pointer)[0]=='passed'
    flow['checks'][0]['expected']=False;assert evaluate(flow,receipt,compare,pointer)[0]=='failed'
    payload.pop('observe_callback_errors');assert execute(payload)['status']=='error'
    if asynchronous:return
    payload['observe_callback_errors']=True
    for export in ('unrelated','swallowed'):
        payload['steps'][0]['export']=export;assert execute(payload)['status']=='error'
    payload['steps']=[];payload['cleanup']=[{**step,'export':'invoke'}]
    assert execute(payload)['status']=='error'


def test_observed_call_requires_its_own_outcome_check_and_preserves_legacy_projection(modules):
    _,scenarios,generation,_,_=modules
    units,target,docs,output,original,context=sample(modules)
    flow=scenarios.Scenario(steps=[dict(id='outcome',op='observe_call',module='lib/src/public_api/__init__.py',export='twice',args=[2]),dict(id='side',op='call',module='lib/src/public_api/__init__.py',export='twice',args=[2])],checks=[dict(step='side',expected=4)])
    invalid=copy.deepcopy(output);invalid['requirements'][0]['cases']=[dict(id='C-observed',title='观察结果需独立检查',kind='scenario',unit='parent',expected=None,flow=flow.model_dump())]
    assert generation.validate(invalid,docs,target)[0][0]['cases']
    rejected,issues,_=generation.validate(invalid,docs,target,projection_context=context)
    assert not rejected[0]['cases'] and any('旁路状态' in i['reason'] for i in issues)
    with pytest.raises(ValueError,match='旁路状态'):scenarios.validate_observation_checks(flow)
    flow.checks.append(scenarios.Check(step='outcome',pointer='/value',expected=4));scenarios.validate_observation_checks(flow)
