import copy,importlib,importlib.util,json,os,shutil,sys,uuid
from pathlib import Path
import pytest
from acceptance.engine import ROOT

DRIVERS=Path(os.environ.get('ACCEPTANCE_FIXTURE_DRIVER_DIR',ROOT/'acceptance/universal'))

@pytest.fixture
def modules(monkeypatch):
    package=importlib.import_module('acceptance.universal');loaded={}
    for name in ['fixture_preparation','case_environment','runtime','orchestration','browser_runtime','coverage','service']:
        label='acceptance.universal.'+name;spec=importlib.util.spec_from_file_location(label,DRIVERS/(name+'.py'));module=importlib.util.module_from_spec(spec);monkeypatch.setitem(sys.modules,label,module);monkeypatch.setattr(package,name,module,raising=False);spec.loader.exec_module(module);loaded[name]=module
    return loaded

def manifest(name='neutral-extension'):
    return '[build-system]\nrequires=["setuptools>=40.8.0", "wheel"]\nbuild-backend="setuptools.build_meta"\n[project]\nname="'+name+'"\nversion="0.0.1"\n[project.entry-points."acceptance.neutral"]\ndemo="neutral_extension:value"\n'

def case_spec(name='neutral-extension',cid='install'):
    from acceptance.universal.models import Case
    return Case(id=cid,title='安装独立本地插件并观察实际结果',unit='u-neutral',kind='scenario',expected=None,flow=dict(steps=[dict(id='manifest',op='write_file',path='extension/pyproject.toml',value=manifest(name)),dict(id='module',op='write_file',path='extension/neutral_extension.py',value='def value():return 41\n'),dict(id='install',op='cli',entry='installer',argv=[{'$path':'extension'}]),dict(id='actual',op='call',module='api.py',export='extension_value')],checks=[dict(step='install',pointer='/exit_code',expected=0),dict(step='actual',expected=41)])).model_dump()

def test_standard_manifest_extraction_and_direct_reference_rejection(modules):
    module=modules['fixture_preparation'];case=case_spec();before=copy.deepcopy(case);spec=module.manifests(case)[0]
    assert spec['name']=='neutral-extension' and spec['build']==['setuptools>=40.8.0','wheel'] and case==before
    case['flow']['steps'][0]['value']='[project]\nname="plain-fixture"\nversion="0.1"\n'
    assert module.manifests(case)[0]['build']==['setuptools>=40.8.0','wheel']
    case['flow']['steps'][0]['value']='[build-system]\nrequires=["thing @ https://example.invalid/payload.whl"]\n'
    with pytest.raises(ValueError):module.manifests(case)

def test_fixture_failure_does_not_block_unrelated_business_and_categories_are_kept(modules,tmp_path,monkeypatch):
    service=modules['service'];runtime=modules['runtime'];monkeypatch.setattr(service,'implementation',lambda:'same');monkeypatch.setattr(service,'locks',lambda:{})
    from acceptance.integrations.runner import sha,encode
    called=[];monkeypatch.setattr(runtime,'business',lambda *a:(called.append(True) or runtime.result_file(a[2],[dict(name='独立用例',status='passed')]),{}))
    dependency=dict(id='u-fixture',tool='universal-fixture',state='completed',report={'tests':[dict(name='一个夹具准备失败',status='error')]})
    task=dict(id='u-business',tool='universal-business',target='u',state='running',timeout=120)
    run=dict(id='int-'+uuid.uuid4().hex[:16],tasks=[dependency,task],universal_plan=dict(implementation_digest='same',toolchain_digest=sha(encode({})),dag=[dict(id='u-business',needs=['u-fixture'])],discovery={'units':[{'id':'u'}]}))
    class Store:
        def path(self,rid):return tmp_path
    output=tmp_path/'result';output.mkdir();service.execute(Store(),run,task,output,lambda:False);assert called
    issue=dict(kind='execution',source='u-fixture',observations=[dict(detail=json.dumps(dict(gap_category='case')))])
    assert modules['coverage'].classify(dict(tasks=[dependency]),[issue])[0]['category']=='case'

def test_fixture_preparation_is_visible_network_scoped_and_idempotent(modules,tmp_path,monkeypatch):
    from acceptance.integrations import registry
    monkeypatch.setitem(registry.TOOLS,'universal-fixture',registry.tool('python','junit',[],report='report.xml',exits=(0,1),network=True))
    # Use an actual schema-valid profile, keeping the invariant independent of a repository.
    from acceptance.integrations.models import Profile
    tasks=[dict(id='design-0',tool='universal-design',target='0'),dict(id='u-prepare',tool='universal-prepare',target='u',network='registry'),dict(id='u-business',tool='universal-business',target='u'),dict(id='cleanup',tool='universal-cleanup')]
    rules=[dict(id=t['id']+'-gate',kind='metric',tasks=[t['id']],metric='tests.failed',operator='le',threshold=0) for t in tasks]
    p=Profile.model_validate(dict(id='fixture-test',name='通用夹具',repository=str(tmp_path),version='1',environment='isolated',files=['README.md'],scope='独立夹具',tasks=tasks,rules=rules)).model_dump()
    plan=dict(profile=p,discovery={'units':[{'id':'u','runtime':'python','path':'.'}]},dag=[dict(id='u-business',stage='business',needs=['u-prepare','design-0'])],checks=[],stages=[dict(id='design',title='设计'),dict(id='business',title='业务')])
    modules['fixture_preparation'].augment(plan);frozen=copy.deepcopy(plan);modules['fixture_preparation'].augment(plan)
    assert plan==frozen
    assert [x['id'] for x in plan['stages']]==['design','fixture','business']
    fixture=next(x for x in plan['profile']['tasks'] if x['tool']=='universal-fixture')
    assert fixture['network']=='registry'
    assert next(x for x in plan['profile']['tasks'] if x['tool']=='universal-business')['network']=='none'
    assert next(x for x in plan['dag'] if x['id']=='u-business')['needs'][-1]=='u-fixture'

def test_real_offline_editable_fixture_install_protects_baseline_and_cleans_resources(modules,tmp_path):
    runtime=modules['runtime'];environment=modules['case_environment'];fixtures=modules['fixture_preparation']
    from acceptance.integrations.registry import locks
    from acceptance.universal.models import Case
    u=dict(id='u-neutral',runtime='python',path='.',settings={},capabilities=['scenario','module'],service_graph={'nodes':[]},cli_commands={'installer':['/work/venv/bin/python','-m','pip','install','-e']})
    run=dict(id='int-'+uuid.uuid4().hex[:16],images=locks(),context={'snapshot_digest':'neutral-fixture'},_harness_path=str(DRIVERS.resolve()),universal_plan={'execution_contract':{'version':20},'fixture_preparation_version':1,'discovery':{'units':[u]}})
    name,volume=runtime.names(run,u);image=run['images']['universal-python312']['id'];runtime.docker('volume','create',*environment.labels(run),volume)
    runtime.docker('run','-d','--name',name,*environment.labels(run),'--network','none','--mount',f'type=volume,src={volume},dst=/work','--entrypoint','/bin/sh',image,'-c','while :; do sleep 3600; done')
    api=tmp_path/'api.py';api.write_text('from importlib.metadata import entry_points\ndef extension_value():return next(iter(entry_points(group="acceptance.neutral"))).load()()\ndef extensions():return [e.name for e in entry_points(group="acceptance.neutral")]\n')
    try:
        runtime.docker('exec',name,'/bin/sh','-c','mkdir -p /work/repo /work/tmp; python -m venv /work/venv');runtime.docker('cp',str(api),name+':/work/repo/api.py')
        environment.snapshot(run,u,tmp_path/'baseline',lambda:False)
        ordinary=Case(id='unrelated',title='前条安装不会污染下一条用例',unit=u['id'],kind='module',module='api.py',function='extensions',expected=[]).model_dump()
        run['universal_generation']={'requirements':[dict(id='R',source='D',quote='独立插件安装后返回41，每条用例独立；禁止替换原环境发行包。',cases=[case_spec(),ordinary,case_spec('pip','protected')])]}
        output=tmp_path/'fixture';output.mkdir();report,_=fixtures.prepare(run,u,output,lambda:False)
        assert [t['status'] for t in report['tests']]==['passed','error'],report['tests']
        prepared=run['universal_fixture_preparation'][u['id']];good=prepared['groups'][prepared['cases']['install']['key']]
        assert good['state']=='ready' and good['receipt']['wheels'] and all((output/good['key']/'cache/wheels'/w['name']).is_file() for w in good['receipt']['wheels'])
        business=tmp_path/'business';business.mkdir();report,_=runtime.business(run,u,business,lambda:False)
        assert [t['status'] for t in report['tests']]==['passed','passed','error'],report['tests']
        traces=json.loads((business/'cases.json').read_bytes());assert traces[0]['environment']['fixture_preparation']['mount_readonly'] is True
        assert traces[1]['actual']==[] and all(x['environment']['removed'] for x in traces[:2])
        assert traces[2]['gap_category']=='case'
    finally:
        cleanup=tmp_path/'cleanup';cleanup.mkdir();report,_=runtime.cleanup(run,cleanup)
        assert all(t['status']=='passed' for t in report['tests'])
