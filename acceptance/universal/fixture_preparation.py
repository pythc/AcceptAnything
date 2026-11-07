"""PEP 517 fixture declarations, wheel preparation, and offline validation mounts."""
import base64,json,time,tomllib
from pathlib import PurePosixPath
from packaging.requirements import Requirement
from ..integrations.runner import encode,sha,invoke
from ..integrations.formats import require


class FixtureUnavailable(ValueError):
    def __init__(self,message,category='environment'):super().__init__(message);self.gap_category=category


def augment(plan):
    """Freeze a visible registry-preparation stage, including replay plans."""
    if plan.get('fixture_preparation_version'):return
    profile=plan['profile'];designs=[t['id'] for t in profile['tasks'] if t['tool']=='universal-design']
    added=False
    for u in plan['discovery']['units']:
        business=next((n for n in plan.get('dag',[]) if n['id']==u['id']+'-business'),None)
        if u['runtime']!='python' or business is None:continue
        tid=u['id']+'-fixture'
        added=True
        profile['tasks'].append(dict(id=tid,tool='universal-fixture',target=u['id'],timeout=3600,network='registry'))
        plan['dag'].append(dict(id=tid,stage='fixture',needs=[u['id']+'-prepare',*designs]));business['needs'].append(tid)
        plan['checks'].append(dict(id=tid,title='用例环境依赖 · '+u.get('path',u['id']),expected='从标准夹具声明缓存构建依赖，保护现有版本，业务执行保持离线'))
        profile['rules'].append(dict(id=tid+'-failed',kind='metric',tasks=[tid],metric='tests.failed',operator='le',threshold=0))
    if not added:plan['fixture_preparation_version']=1;return
    order={'universal-design':1,'universal-fixture':2,'universal-business':3,'universal-cleanup':4};profile['tasks'].sort(key=lambda t:order.get(t['tool'],0))
    stages=list(plan.get('stages',[]));position=next((i for i,s in enumerate(stages) if s['id']=='business'),len(stages))
    if added:stages.insert(position,dict(id='fixture',title='用例环境准备'))
    plan['stages']=stages
    from ..integrations.models import Profile
    plan['profile']=Profile.model_validate(profile).model_dump();plan['fixture_preparation_version']=1


def manifests(case):
    steps=(case.get('flow') or {}).get('steps',[]) if case['kind']=='scenario' else (case.get('journey') or {}).get('setup',[])
    result=[]
    for step in steps:
        if step['op']!='write_file' or PurePosixPath(step['path']).name!='pyproject.toml':continue
        raw=base64.b64decode(step['value'],validate=True) if step.get('encoding')=='base64' else step['value'].encode(step.get('encoding','utf-8'))
        data=tomllib.loads(raw.decode('utf-8'));build=data.get('build-system');project=data.get('project',{})
        requires=build.get('requires') if build is not None else ['setuptools>=40.8.0','wheel']
        runtime=project.get('dependencies',[])
        require(isinstance(requires,list) and all(isinstance(x,str) for x in requires) and isinstance(runtime,list) and all(isinstance(x,str) for x in runtime),'构建夹具 manifest 依赖声明无效')
        if 'dependencies' in project.get('dynamic',[]):raise FixtureUnavailable('夹具使用动态依赖，需要额外构建契约，未猜测下载','platform')
        for value in [*requires,*runtime]:
            if Requirement(value).url:raise FixtureUnavailable('夹具直接 URL 依赖尚无取证契约，未自动下载','platform')
        result.append(dict(path=step['path'],source_sha256=sha(raw),name=project.get('name'),build=requires,runtime=runtime,backend=(build or {}).get('build-backend','setuptools.build_meta:__legacy__'),policy='declared PEP 517 requires' if build is not None else 'pip standard legacy backend fallback'))
    return result


def options(run):
    group=run.get('_fixture_cache')
    if not group:return []
    return ['--mount',f'type=volume,src={group["volume"]},dst=/fixture-cache,readonly','--env','PIP_NO_INDEX=1','--env','PIP_FIND_LINKS=/fixture-cache/wheels','--env','PIP_CONSTRAINT=/fixture-cache/constraints.txt']


def prepare(run,u,output,cancelled):
    from .runtime import docker,names,result_file
    from .case_environment import labels
    cases=[c for q in run['universal_generation']['requirements'] for c in q['cases'] if c['unit']==u['id']]
    plan=dict(version=1,unit=u['id'],cases={},groups={});run.setdefault('universal_fixture_preparation',{})[u['id']]=plan;rows=[]
    bases=run.get('universal_bases',{}).get(u['id'],[])
    for case in cases:
        try:
            specs=manifests(case)
            if not specs:continue
            require(bases,'夹具依赖准备缺少原生测试之前的环境基线')
            base=bases[-1];key=sha(encode(dict(base=base['volume'],image=base['image'],manifests=specs)))
            plan['cases'][case['id']]=dict(key=key,manifests=specs)
            if key in plan['groups']:continue
            parent,_=names(run,u);name=parent+'-case-fixture-'+key;volume=name+'-cache';folder=output/key;folder.mkdir();cache=folder/'cache';cache.mkdir();started=time.monotonic()
            record=dict(key=key,unit=u['id'],base=base['volume'],image=base['image'],volume=volume,state='error',manifests=specs);plan['groups'][key]=record
            try:
                require(docker('volume','inspect',volume,check=False).returncode!=0,'夹具 wheel 缓存已存在，拒绝继承未知内容')
                docker('volume','create',*labels(run),volume)
                payload=encode(dict(manifests=specs));record['input_sha256']=sha(payload)
                argv=['docker','run','--name',name,*labels(run),'--network','bridge','--cap-drop','ALL','--security-opt','no-new-privileges','--read-only','--pids-limit','256','--cpus','2','--tmpfs','/tmp:rw,exec,nosuid','--env','HOME=/tmp','--mount',f'type=volume,src={base["volume"]},dst=/work,readonly','--mount',f'type=volume,src={volume},dst=/fixture-cache','--mount',f'type=bind,src={run["_harness_path"]},dst=/harness,readonly','--entrypoint','/work/venv/bin/python',base['image'],'-P','/harness/fixture_driver.py',base64.b64encode(payload).decode()]
                command,_=invoke(argv,3600,folder,cancelled,container=name);record['command']=command
                docker('cp',name+':/fixture-cache/.',str(cache),check=False)
                receipt=json.loads((cache/'receipt.json').read_bytes());record['receipt']=receipt
                require(receipt['input_sha256']==record['input_sha256'],'夹具准备回执输入摘要不符')
                require(command['interruption'] is None and command['exit_code']==0 and receipt['state']=='ready',receipt.get('error','夹具构建依赖准备未完成'))
                record['state']='ready'
            except Exception as exc:record['error']=type(exc).__name__+': '+str(exc);record['gap_category']=record.get('receipt',{}).get('gap_category','environment')
            finally:
                inspect=docker('inspect',name,check=False);(folder/'container.json').write_text(inspect.stdout);docker('rm','-f',name,check=False)
                record['container_removed']=docker('inspect',name,check=False).returncode!=0;record['duration_ms']=round((time.monotonic()-started)*1000)
            rows.append(dict(name='夹具依赖 '+str(len(rows)+1)+' · '+', '.join(str(m.get('name') or m['path']) for m in specs),status='passed' if record['state']=='ready' and record['container_removed'] else 'error',duration_ms=record['duration_ms'],detail=json.dumps(record,ensure_ascii=False)))
        except Exception as exc:
            category=getattr(exc,'gap_category','case');plan['cases'][case['id']]=dict(state='error',error=type(exc).__name__+': '+str(exc),gap_category=category);rows.append(dict(name='构建夹具声明 · '+case['id'],status='error',detail=json.dumps(dict(error=str(exc),gap_category=category),ensure_ascii=False)))
    (output/'fixture-plan.json').write_bytes(encode(plan))
    return result_file(output,rows or [dict(name='用例未声明本地 Python 构建夹具',status='passed')]),dict(argv=['pip download','declared fixture build dependencies; validation remains offline'],exit_code=0)


def selected(run,u,case):
    plan=run.get('universal_fixture_preparation',{}).get(u['id'],{});ref=plan.get('cases',{}).get(case['id'])
    if not ref:return None
    if ref.get('state')=='error':raise FixtureUnavailable(ref.get('error','夹具声明无效'),ref.get('gap_category','case'))
    group=plan.get('groups',{}).get(ref['key'])
    if group is None or group['state']!='ready':raise FixtureUnavailable('此用例的构建夹具依赖未准备，其他用例继续',group.get('gap_category','environment') if group else 'environment')
    from .runtime import docker
    owner=json.loads(docker('volume','inspect',group['volume']).stdout)[0]
    require((owner.get('Labels') or {}).get('acceptance.run')==run['id'],'夹具依赖缓存不属于当前运行')
    return group


def verify_archived(store,run):
    if not run['universal_plan'].get('fixture_preparation_version'):return
    from ..integrations.storage import file_digest
    artifacts={a['name']:a for a in run['artifacts']}
    cases={c['id']:c for q in run['universal_generation']['requirements'] for c in q['cases']}
    for task in run['tasks']:
        if task['tool']!='universal-fixture' or task['state']!='completed':continue
        prefix=task['id']+'/';plan=run.get('universal_fixture_preparation',{}).get(task['target']);ref=artifacts.get(prefix+'fixture-plan.json')
        require(plan is not None and ref is not None and json.loads(store.artifact_bytes_for_record(run,ref['id'])[1])==plan,'构建夹具准备原件不一致')
        expected={}
        for cid,case in cases.items():
            if case['unit']!=task['target']:continue
            try:specs=manifests(case)
            except (ValueError,TypeError,AttributeError):
                require(plan['cases'].get(cid,{}).get('state')=='error','无效夹具声明被当成就绪');continue
            if specs:expected[cid]=specs
        require(set(expected)<=set(plan['cases']) and set(plan['cases'])<=set(cases),'夹具准备包含未声明的用例')
        bases={b['volume']:b for b in run.get('universal_bases',{}).get(task['target'],[])}
        for cid,specs in expected.items():
            entry=plan['cases'][cid]
            if entry.get('state')=='error':continue
            group=plan['groups'].get(entry['key']);require(group is not None and group['manifests']==specs and entry['manifests']==specs,'夹具缓存改变了冻结声明')
        for key,group in plan['groups'].items():
            base=bases.get(group['base']);require(base is not None and group['image']==base['image'] and key==sha(encode(dict(base=base['volume'],image=base['image'],manifests=group['manifests']))),'夹具缓存未绑定冻结基线')
            if group['state']!='ready':continue
            receipt=group['receipt'];ref=artifacts.get(prefix+key+'/cache/receipt.json')
            require(ref is not None and json.loads(store.artifact_bytes_for_record(run,ref['id'])[1])==receipt,'夹具依赖回执被改变')
            require(receipt['state']=='ready' and receipt['input_sha256']==sha(encode(dict(manifests=group['manifests']))) and group['container_removed'],'夹具准备输入或终态不符')
            require(group['command']['exit_code']==0 and group['command']['interruption'] is None,'构建夹具准备没有真实成功退出')
            for wheel in receipt['wheels']:
                require(PurePosixPath(wheel['name']).name==wheel['name'],'夹具 wheel 路径无效')
                item=artifacts.get(prefix+key+'/cache/wheels/'+wheel['name']);require(item is not None,'夹具 wheel 原件缺失')
                _,path=store.verified_artifact_path(run,item['id']);require(path.stat().st_size==wheel['size'] and file_digest(path)==wheel['sha256'],'夹具 wheel 与准备输入不一致')
