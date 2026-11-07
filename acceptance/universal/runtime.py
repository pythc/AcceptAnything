"""One disposable volume/container per component; oracle and reports stay outside."""
import base64,json,os,re,shlex,subprocess,time,traceback
from pathlib import Path
from xml.etree.ElementTree import Element,SubElement,tostring
from jsonpointer import resolve_pointer,JsonPointerException
from ..integrations.runner import invoke,encode,sha
from ..integrations.formats import require,parse
from ..integrations.registry import ROOT
from ..automatic_cli import equal

HARNESS=Path(__file__).parent
OFFLINE_ENV={'HF_HUB_OFFLINE':'1','TRANSFORMERS_OFFLINE':'1'}


def resource_policy():
    jobs=os.environ.get('ACCEPTANCE_COMPILER_JOBS','1')
    require(re.fullmatch(r'[1-9][0-9]*',jobs) is not None,'编译并发需为正整数')
    return dict(version=1,temporary_directory='/work/tmp',compiler_jobs=int(jobs))


def resource_snapshot(run,u,output):
    name,_=names(run,u)
    probes={
        'memory':['cat','/sys/fs/cgroup/memory.events','/sys/fs/cgroup/memory.current','/sys/fs/cgroup/memory.peak','/sys/fs/cgroup/memory.max'],
        'disk':['df','-Pk','/work','/tmp'],
        'configuration':['printenv','TMPDIR','CARGO_BUILD_JOBS'],
    }
    rows={}
    for key,args in probes.items():
        try:
            result=docker('exec',name,*args,check=False)
            rows[key]=dict(argv=args,exit_code=result.returncode,stdout=result.stdout,stderr=result.stderr)
        except (OSError,subprocess.TimeoutExpired) as exc:
            rows[key]=dict(argv=args,error=type(exc).__name__)
    (output/'resources.json').write_bytes(encode(rows))


def docker(*args,check=True):
    result=subprocess.run(['docker',*args],capture_output=True,text=True,timeout=30)
    if check:require(result.returncode==0,'容器操作失败：'+result.stderr[-1200:])
    return result


def result_file(output,rows):
    suite=Element('testsuite',name='通用验收',tests=str(len(rows)),failures=str(sum(x['status']=='failed' for x in rows)),errors=str(sum(x['status']=='error' for x in rows)))
    for row in rows:
        case=SubElement(suite,'testcase',name=row['name'],classname='universal',time=str(row.get('duration_ms',0)/1000))
        # One complete body, rather than a truncated JSON message plus body.
        # JUnit readers join those two fields, which made structured diagnostics
        # unparsable and silently lost case/environment classifications.
        if row['status']!='passed':SubElement(case,{'error':'error','skipped':'skipped'}.get(row['status'],'failure')).text=row.get('detail','')
    raw=tostring(suite,encoding='utf-8');(output/'report.xml').write_bytes(raw)
    return parse('junit',raw)


def unit(run,tid):return next(u for u in run['universal_plan']['discovery']['units'] if u['id']==tid)


def names(run,u):
    if u['id'] in run.get('_case_resources',{}):return tuple(run['_case_resources'][u['id']])
    stem='acceptance-universal-'+run['id'][4:]+'-'+u['id']
    index=run.get('universal_environment_choices',{}).get(u['id'],0)
    require(type(index) is int and index>=0,'运行环境选择编号无效')
    if index:stem+='-runtime-'+str(index)
    return stem,stem+'-work'


def command(run,u,argv,output,cancelled,timeout=None,workdir=True,offline=True):
    name,_=names(run,u)
    args=['docker','exec']
    if offline:
        for key,value in OFFLINE_ENV.items():args+=['--env',key+'='+value]
    if workdir:args+=['-w','/work/repo/'+u['path']]
    args+=[name,*argv]
    cmd,streams=invoke(args,timeout if timeout is not None else run.get('_task_timeout',300),output,cancelled,container=name)
    require(cmd['interruption'] is None,'执行中断：'+str(cmd['interruption']))
    return cmd,dict(stdout=streams,stderr=(output/'stderr.log').read_bytes())


def env_path(u):return '/work/venv/bin/python' if u['runtime']=='python' else 'node'


def prepare(run,u,output,cancelled):
    if u['runtime']=='python' and run.get('universal_plan',{}).get('execution_contract',{}).get('version',0)>=15:
        from .environment import prepare_candidates
        result=prepare_candidates(run,u,output,cancelled,_prepare_candidate)
    else:result=_prepare_candidate(run,u,output,cancelled)
    if run.get('universal_plan',{}).get('execution_contract',{}).get('version',0)>=20:
        from .case_environment import snapshot
        snapshot(run,u,output/'prepared-baseline',cancelled)
    return result


def _prepare_candidate(run,u,output,cancelled,*,image_key=None):
    name,volume=names(run,u);runtime=u['runtime'];key={'python':'universal-python','node':'universal-node','go':'auto-go','rust':'universal-python'}[runtime]
    resources=resource_policy()
    if runtime=='python':
        from .environment import python_image
        key=image_key or python_image(u,run['images'])
    image=run['images'][key]['id']
    # source is supplied by the caller for non-default stores as well.
    source=Path(run['_source_path'])
    docker('volume','create','--label','acceptance.integration=true','--label','acceptance.run='+run['id'],volume)
    argv=['run','-d','--name',name,'--label','acceptance.integration=true','--label','acceptance.run='+run['id'],'--network','bridge',
        '--cap-drop','ALL','--security-opt','no-new-privileges','--read-only','--cpus','2','--pids-limit','256',
        '--tmpfs','/tmp:rw,exec,nosuid','--env','HOME=/work','--env','TMPDIR='+resources['temporary_directory'],'--env','CARGO_BUILD_JOBS='+str(resources['compiler_jobs']),'--env','PYTHONDONTWRITEBYTECODE=1','--env','GOTOOLCHAIN=local','--env','CGO_ENABLED=0','--env','CARGO_HOME=/work/cargo','--env','RUSTUP_HOME=/work/rustup',
        '--mount',f'type=bind,src={source},dst=/source,readonly','--mount',f'type=volume,src={volume},dst=/work','--mount',f'type=bind,src={run["_harness_path"]},dst=/harness,readonly',
        '--entrypoint','/bin/sh',image,'-c','while :; do sleep 3600; done']
    docker(*argv)
    try:
        cmd,streams=command(run,u,['/bin/sh','-c','mkdir -p /work/repo /work/tmp; cp -R /source/. /work/repo/'],output,cancelled,workdir=False,offline=False)
        require(cmd['exit_code']==0,'创建隔离工作副本失败')
        if runtime in {'rust','python'}:
            out=output/'toolchain';out.mkdir()
            cmd,_=command(run,u,['/bin/sh','-c','cp -R /usr/local/rustup /work/rustup'],out,cancelled,timeout=300,offline=False)
            require(cmd['exit_code']==0,'初始化可写工具链缓存失败')
        cmds=[]
        if runtime=='python':
            cmds=[['python','-m','venv','/work/venv']]
            prefix=Path(run['_source_path'])/u['path']
            if (prefix/'requirements.txt').is_file():cmds.append(['/work/venv/bin/python','-m','pip','install','--report','/work/requirements-install.json','-r','requirements.txt'])
            if any((prefix/n).is_file() for n in ('pyproject.toml','setup.py')):
                local=[unit(run,uid) for uid in u.get('local_dependencies',[])]
                # Supply local candidates; pip resolves their runtime extras
                # from this component's metadata. Do not install their tests.
                specs=['/work/repo/'+v['path'] for v in local]
                specs+=['.['+u['test_extra']+']' if u.get('test_extra') else '.']
                editable=[value for spec in specs for value in ('--editable',spec)]
                cmds.append(['/work/venv/bin/python','-m','pip','install','--report','/work/package-install.json',*editable,*u.get('test_dependencies',[])])
        elif runtime=='node':
            locked=any((Path(run['_source_path'])/u['path']/n).exists() for n in ('package-lock.json','npm-shrinkwrap.json'))
            cmds=[]
            for parent in u.get('ancestor_dependencies',[]):
                locked_parent=any((source/parent['path']/n).is_file() for n in ('package-lock.json','npm-shrinkwrap.json'))
                cmds.append(['npm','--prefix','/work/repo/'+parent['path'],'ci' if locked_parent else 'install','--no-audit','--no-fund'])
            cmds.append(['npm','ci' if locked else 'install','--no-audit','--no-fund'])
        elif runtime=='go':cmds=[['go','mod','download']]
        else:cmds=[['cargo','fetch','--locked'] if (source/u['path']/'Cargo.lock').exists() else ['cargo','fetch']]
        records=[]
        for i,args in enumerate(cmds):
            out=output/('install-'+str(i));out.mkdir()
            cmd,streams=command(run,u,args,out,cancelled,timeout=run.get('_task_timeout',900),offline=False);records.append(cmd)
            require(cmd['exit_code']==0,'依赖安装失败；查看该组件安装日志')
        optional_preparation=None
        if runtime=='python':
            from .environment import execute
            optional_preparation=execute(run,u,output,cancelled)
        resource_preparation=None
        if runtime=='python':
            out=output/'tokenizer-resources';out.mkdir()
            resource_command,_=command(run,u,['/work/venv/bin/python','-P','/harness/python_tokenizer_resources.py'],out,cancelled,timeout=run.get('_task_timeout',900),offline=False)
            # Registered resources are independent. A partial warmup remains
            # evidence, while native/business checks decide actual coverage.
            resource_preparation=dict(provider='tiktoken',command=resource_command,report='tokenizer-resources/stdout.log')
        collection=None
        if runtime=='python' and u['test_files']:
            out=output/'test-runner';out.mkdir()
            probe,_=command(run,u,['/work/venv/bin/python','-c','import pytest'],out,cancelled,offline=False)
            if probe['exit_code']:
                text=run['images']['python']['versions']['pytest']['text'];version=re.search(r'pytest ([0-9.]+)',text).group(1)
                out=output/'test-runner-install';out.mkdir();cmd,_=command(run,u,['/work/venv/bin/python','-m','pip','install','--report','/work/test-runner-install.json','pytest=='+version],out,cancelled,timeout=900,offline=False)
                require(cmd['exit_code']==0,'原生测试执行器安装失败')
            if run.get('universal_plan',{}).get('execution_contract',{}).get('version',0)<20:
                out=output/'collection-warmup';out.mkdir()
                collection,_=command(run,u,['/work/venv/bin/python','-m','pytest','--collect-only','--continue-on-collection-errors','-q','--junitxml=/work/collection-warmup.xml'],out,cancelled,timeout=run.get('_task_timeout',900),offline=False)
                docker('cp',name+':/work/collection-warmup.xml',str(out/'collection.xml'),check=False)
        version=['/work/venv/bin/python','-m','pip','freeze','--all'] if runtime=='python' else ['npm','ls','--all','--json'] if runtime=='node' else ['go','list','-m','-json','all'] if runtime=='go' else ['cargo','metadata','--offline','--format-version','1']
        resolved=output/'resolved';resolved.mkdir();lockcmd,_=command(run,u,version,resolved,cancelled,offline=False)
        # The resolved dependency graph is evidence even when a project's graph is invalid.
        (output/'environment.json').write_bytes(encode(dict(unit=u['id'],image=image,source_digest=run['context']['snapshot_digest'],container=name,volume=volume,installer_commands=records,optional_preparation=optional_preparation,resource_preparation=resource_preparation,collection_probe=collection,resolution=lockcmd,source_readonly=True,workspace='disposable copy',network='network enabled for installation and collection resource warmup; disconnected before validation',validation_environment=OFFLINE_ENV,resource_policy=resources)))
    finally:
        resource_snapshot(run,u,output)
        docker('network','disconnect','bridge',name,check=False)
        state=json.loads(docker('inspect',name).stdout)[0]
        require(not state['NetworkSettings']['Networks'],'安装网络未断开，禁止执行后续验证')
    rows=[dict(name='隔离环境与依赖准备',status='passed')]
    for action in (optional_preparation or {}).get('actions',[]):
        if action['status']=='error':rows.append(dict(name='可选准备 · '+str(action.get('spec') or action.get('action',{}).get('output')),status='error',detail=action['reason']))
    return result_file(output,rows),records[-1] if records else cmd


def build(run,u,output,cancelled):
    runtime=u['runtime'];commands=[]
    if runtime=='rust':
        commands=[['cargo','build','--offline','--workspace'],*([['cp','target/debug/'+entry,'/work/app-'+str(i)] for i,entry in enumerate(u.get('entries',[]))])]
    elif runtime=='go':
        require(u.get('entries'),'没有明确CLI入口')
        commands=[['go','build','-o','/work/app-'+str(i),'./'+entry] for i,entry in enumerate(u['entries'])]
    elif runtime=='python':commands=[['/work/venv/bin/python','-m','compileall','-q','.']]
    else:
        scripts=u['settings'].get('scripts',{})
        if scripts.get('build'):commands=[['npm','run','build']]
        else:
            paths=u.get('syntax_files',[])
            require(paths,'未发现可构建入口或已声明build命令')
            commands=[['node','--check','/work/repo/'+p] for p in paths]
    rows=[];last={}
    for i,argv in enumerate(commands):
        target=output/('step-'+str(i));target.mkdir();last,_=command(run,u,argv,target,cancelled)
        failure=(target/'stderr.log').read_text(errors='replace')
        environment_error=any(x in failure for x in ['OUT_OF_MEMORY','heap out of memory','Cannot find module','command not found'])
        rows.append(dict(name='构建检查'+str(i+1),status='passed' if last['exit_code']==0 else 'error' if environment_error else 'failed',detail='构建命令退出码 '+str(last['exit_code'])))
    report=result_file(output,rows)
    if run.get('universal_plan',{}).get('execution_contract',{}).get('version',0)>=20 and all(row['status']=='passed' for row in rows):
        from .case_environment import snapshot
        snapshot(run,u,output/'build-baseline',cancelled)
    return report,last


def native(run,u,output,cancelled):
    runtime=u['runtime']
    if runtime=='python' and run.get('universal_plan',{}).get('execution_contract',{}).get('version',0)>=20:
        # Collection can execute import-time fixture code. Run it only after
        # immutable business baselines exist, inside the native workspace.
        name,_=names(run,u);warm=output/'collection-warmup';warm.mkdir()
        docker('network','connect','bridge',name)
        try:
            cmd,_=command(run,u,['/work/venv/bin/python','-m','pytest','--collect-only','--continue-on-collection-errors','-q','--junitxml=/work/collection-warmup.xml'],warm,cancelled,timeout=run.get('_task_timeout',900),offline=False)
            docker('cp',name+':/work/collection-warmup.xml',str(warm/'collection.xml'),check=False)
        finally:
            docker('network','disconnect','bridge',name,check=False)
            require('bridge' not in json.loads(docker('inspect',name).stdout)[0]['NetworkSettings']['Networks'],'原生测试资源预热网络没有断开')
    if runtime=='rust':
        cmd,streams=command(run,u,['cargo','test','--offline','--workspace'],output,cancelled,timeout=3600)
        text=streams['stdout'].decode(errors='replace')
        status='passed' if cmd['exit_code']==0 and 'test result:' in text else 'failed' if 'test result: FAILED' in text else 'error'
        return result_file(output,[dict(name='项目声明的 Cargo workspace 测试命令（非内部用例数）',status=status)]),cmd
    args=(['/work/venv/bin/python','-m','pytest','--continue-on-collection-errors','-q','--junitxml=/work/native.xml'] if runtime=='python' else ['npm','test'] if runtime=='node' else ['/go/bin/gotestsum','--junitfile','/work/native.xml','--jsonfile','/work/native.jsonl','--format','standard-quiet','--','-count=1','./...'])
    cmd,_=command(run,u,args,output,cancelled,timeout=3600)
    name,_=names(run,u)
    if runtime!='node':
        cp=docker('cp',name+':/work/native.xml',str(output/'report.xml'),check=False)
        require(cp.returncode==0,'原生测试没有产生JUnit；保留执行日志，不补造通过结果')
        raw=(output/'report.xml').read_bytes();report=parse('junit',raw)
        require(report['tests'],'原生测试未执行任何用例')
        require(cmd['exit_code'] in {0,1,2,5},'原生测试执行器异常')
        return report,cmd
    # Keep command results distinct from inner reporter totals. An exit 0
    # must not hide native skips; unknown formats keep their original logs.
    from .native_observations import node_spec
    observation=node_spec((output/'stdout.log').read_text(errors='replace'))
    (output/'measurement.json').write_bytes(encode(dict(unit='declared test command',inner_reporter=observation,argv=args)))
    rows=[dict(name='项目声明的 npm test 命令（非内部用例数）',status='passed' if cmd['exit_code']==0 else 'error',detail='测试命令退出码 '+str(cmd['exit_code']))]
    if observation:
        rows+=observation['unexecuted']
        if observation['totals']['fail'] or observation['totals']['cancelled']:
            rows.append(dict(name='原生内部执行器未全部成功',status='error',detail=json.dumps(observation['totals'])))
        if not observation['unexecuted_names_complete']:
            rows.append(dict(name='原生跳过项明细不完整',status='error',detail='Node 汇总与已解析明细数量不一致；查看 measurement.json 与原始日志'))
    return result_file(output,rows),cmd



def value(streams):
    raw=streams['stdout']
    if isinstance(raw,bytes):raw=raw.decode(errors='replace')
    lines=[line[len('ACCEPTANCE_VALUE:'):] for line in raw.splitlines() if line.startswith('ACCEPTANCE_VALUE:')]
    require(len(lines)==1,'运行入口未返回唯一可解析结果')
    return json.loads(lines[0])


def pointer(v,path):
    try:return resolve_pointer(v,path)
    except JsonPointerException:raise ValueError('返回值的JSON Pointer无法解析') from None


def compare(actual,expected,mode):
    if mode=='json_schema':
        from .scenarios import schema_matches
        return schema_matches(actual,expected)
    if mode=='one_of':
        require(isinstance(expected,list) and bool(expected),'one_of需要非空候选值列表')
        return any(compare(actual,candidate,'equals') for candidate in expected)
    if mode=='contains':return expected in actual
    if mode=='json_stream':
        # Serialization preserves the frozen JSON value; it does not rewrite
        # expectations. Keep stream text intact and use the typed comparator.
        return equal(actual if isinstance(actual,str) else json.dumps(actual,allow_nan=False),
                     expected if isinstance(expected,str) else json.dumps(expected,allow_nan=False),mode)
    if mode=='text':return equal(actual,expected,mode)
    return equal(json.dumps(actual,allow_nan=False),json.dumps(expected,allow_nan=False),'json_stream')


def service(run,u,output,cancelled,on_progress=None):
    if run.get('universal_plan',{}).get('execution_contract',{}).get('version',0)<18:return legacy_service(run,u,output,cancelled)
    from .orchestration import start
    records=start(run,u,output,cancelled,on_progress=on_progress)
    rows=[dict(name=n['id']+' 服务就绪',status='passed' if n['status']=='ready' else 'error',detail=n.get('error','真实服务探针已响应'),duration_ms=n['duration_ms']) for n in records]
    cmd={}
    if 'http' in u['capabilities']:
        target=output/'web';target.mkdir()
        try:
            report,cmd=legacy_service(run,u,target,cancelled);rows+=report['tests']
        except Exception as exc:rows.append(dict(name='Web 服务就绪',status='error',detail=str(exc)))
    return result_file(output,rows),cmd


def legacy_service(run,u,output,cancelled):
    from ..planning.execution import create_network
    name,_=names(run,u);network=name+'-net';relay=name+'-relay'
    current=json.loads(docker('inspect',name).stdout)[0]['NetworkSettings']['Networks']
    if network not in current:
        create_network(network,run['id']);docker('network','connect','--alias','target',network,name)
    spec=u['services'][0]
    if spec['framework']=='npm-start':argv=['npm','run','start']
    elif spec['framework']=='FastAPI':argv=['/work/venv/bin/python','-m','uvicorn',spec['module']+':'+spec['attribute'],*(['--factory'] if spec.get('factory') else []),'--host','0.0.0.0','--port','19300']
    else:argv=['/work/venv/bin/python','-m','flask','--app',spec['module']+':'+spec['attribute'],'run','--host','0.0.0.0','--port','19300']
    docker('exec','-d','-w','/work/repo/'+u['path'],'-e','PORT=19300',*[part for key,value in OFFLINE_ENV.items() for part in ('--env',key+'='+value)],name,'/bin/sh','-c','exec "$@" >/work/service.log 2>&1','acceptance',*argv)
    # A fixed relay is the only host-exposed endpoint. No source/oracle mounts.
    modern=run.get('universal_plan',{}).get('execution_contract',{}).get('version',0)>=20
    bridge=Path(run['_harness_path'])/'relay.cjs' if modern else Path(__file__).parents[1]/'planning/runtime/relay.cjs'
    docker('run','-d','--name',relay,'--label','acceptance.integration=true','--label','acceptance.run='+run['id'],'--network','bridge',
        '--cap-drop','ALL','--security-opt','no-new-privileges','--read-only','--memory','128m','--pids-limit','64','--tmpfs','/tmp:rw,nosuid,size=16777216',
        '-p','127.0.0.1::19300','--env','PORT=19300','--mount',f'type=bind,src={bridge},dst=/relay.cjs,readonly',run['images']['node-base']['id'],'node','/relay.cjs')
    # Docker Desktop publishes from a bridge network; internal target connectivity
    # is retained while the relay's external bridge carries only the host port.
    docker('network','connect',network,relay)
    binding=docker('port',relay,'19300/tcp').stdout.strip();require(re.fullmatch(r'127\.0\.0\.1:\d+',binding),'服务转发地址不符合本机限制')
    encoded=base64.b64encode(encode(dict(method='GET',path='/',body=None))).decode();ready=False
    for i in range(30):
        if cancelled():raise ValueError('服务准备已取消')
        target=output/('ready-'+str(i));target.mkdir()
        if modern:
            probe=['/work/venv/bin/python','-c','import socket; s=socket.create_connection(("127.0.0.1",19300),1.5); s.close()'] if u['runtime']=='python' else ['node','-e','const s=require("node:net").connect(19300,"127.0.0.1",()=>{s.end();process.exit(0)});s.on("error",()=>process.exit(1));setTimeout(()=>process.exit(1),1500)']
        else:probe=[env_path(u),*(['-P','/harness/http_driver.py'] if u['runtime']=='python' else ['/harness/http.cjs']),encoded]
        cmd,streams=command(run,u,probe,target,cancelled,timeout=15)
        if cmd['exit_code']==0:ready=True;break
        time.sleep(.2)
    log=docker('exec',name,'cat','/work/service.log',check=False);(output/'service.log').write_text(log.stdout+log.stderr)
    require(ready,'服务没有在声明端口就绪；只影响此服务依赖的验证')
    run.setdefault('universal_services',{})[u['id']]=dict(base='http://'+binding,container=name,network=network,relay=relay)
    (output/'service.json').write_bytes(encode(run['universal_services'][u['id']]))
    return result_file(output,[dict(name='声明服务可访问（不代表业务通过）',status='passed')]),cmd


def module_request(u,case):
    request={k:case[k] for k in ('module','function','args','kwargs')}
    root=Path(u['path']);declared=u.get('settings',{}).get('source')
    roots={str(root/declared)} if isinstance(declared,str) else {str(root/p/('index'+ext)) for p in ('.','src') for ext in ('.ts','.js','.mjs','.cjs','.d.ts')}
    request['runtime_entry']=u.get('runtime_entry') if u['runtime']=='node' and case['module'] in roots else None
    return request


def cli_command(u,entry):
    entries=list(u.get('cli_commands',{})) or u.get('entries',[])
    entry=entry or (entries[0] if len(entries)==1 else None)
    require(entry in entries,'多个CLI入口未明确对应关系')
    return u.get('cli_commands',{}).get(entry) or ['/work/app-'+str(entries.index(entry))]


def business(run,u,output,cancelled):
    if run.get('universal_plan',{}).get('execution_contract',{}).get('version',0)>=20:
        from .case_environment import business as isolated_business
        return isolated_business(run,u,output,cancelled)
    return legacy_business(run,u,output,cancelled)


def fixture(run,u,output,cancelled):
    from .fixture_preparation import prepare
    return prepare(run,u,output,cancelled)


def legacy_business(run,u,output,cancelled):
    cases=[(r,c) for r in run.get('universal_generation',{}).get('requirements',[]) for c in r['cases'] if c['unit']==u['id']]
    require(cases,'该组件没有经过依据校验的业务用例；其他任务继续，缺口保留')
    rows=[];traces=[];last={}
    for requirement,case in cases:
        if cancelled():raise ValueError('已取消')
        target=output/case['id'];target.mkdir(exist_ok=True);start=time.monotonic()
        trace=dict(case=case,requirement=requirement['id'],source=requirement['source'],quote=requirement['quote']);protocol_ok=True
        try:
            if case.get('requires'):
                ready={n['id'] for n in run.get('universal_graphs',{}).get(u['id'],[]) if n['status']=='ready'}
                require(set(case['requires'])<=ready,'该用例依赖的服务未就绪：'+', '.join(sorted(set(case['requires'])-ready)))
            if case['kind']=='journey':
                from .browser_runtime import execute
                receipt,last=execute(run,u,case,target,cancelled)
                trace.update(actual=receipt,status=receipt['status'])
                if receipt.get('gap_category'):trace['gap_category']=receipt['gap_category']
                trace['duration_ms']=round((time.monotonic()-start)*1000);traces.append(trace)
                rows.append(dict(name=case['id']+' · '+case['title'],status=receipt['status'],duration_ms=trace['duration_ms'],detail=json.dumps(receipt,ensure_ascii=False)))
                continue
            if case['kind']=='scenario':
                from .scenarios import evaluate
                flow=case['flow'];request={k:flow[k] for k in ('steps','cleanup')}
                if run.get('_fixture_cache'):request['refresh_installed_packages']=True
                # Only invocation and fixture inputs enter the target. No checks/oracle.
                request=json.loads(json.dumps(request))
                if run.get('universal_plan',{}).get('projection_context'):
                    request['observe_process_results']=True
                    request['observe_result_fields']=True
                    request['observe_callback_errors']=True
                if run.get('universal_plan',{}).get('execution_contract',{}).get('version',0)>=6:
                    # Field selection is plumbing, not an oracle. Preserve legacy
                    # execution semantics for older frozen plans.
                    request['observations']=[dict(step=step,pointer=field) for step,field in
                        dict.fromkeys((c['step'],c['pointer']) for c in flow['checks'] if c.get('pointer'))]
                for step in [*request['steps'],*request['cleanup']]:
                    if step['op']=='cli':step['command']=cli_command(u,step.get('entry'))
                    if step.get('module') and u['runtime']=='node':
                        bound=module_request(u,dict(module=step['module'],function=step['export'],args=[],kwargs={}))
                        if bound['runtime_entry']:step['runtime_entry']=bound['runtime_entry']
                encoded=base64.b64encode(encode(request)).decode()
                argv=[env_path(u),*(['--import','/opt/acceptance-loader/node_modules/tsx/dist/loader.mjs'] if u['runtime']=='node' else ['-P']),'/harness/scenario.py' if u['runtime']=='python' else '/harness/scenario.cjs',encoded]
                last,streams=command(run,u,argv,target,cancelled,timeout=120)
                require(last['exit_code']==0,'状态流程运行异常，查看原始日志')
                receipt=value(streams);trace['actual']=receipt
                version=run.get('universal_plan',{}).get('execution_contract',{}).get('version',0)
                status,checks=evaluate(flow,receipt,compare,pointer,validate_cli_contract=version>=12,structured_cli_exit=version>=19)
                trace.update(actual=receipt,status=status,checks=checks)
                trace['duration_ms']=round((time.monotonic()-start)*1000);traces.append(trace)
                category='case' if status=='error' and receipt.get('status')=='completed' and any(c.get('status')=='error' for c in checks) else 'unclassified'
                if status=='error' and run.get('universal_plan',{}).get('execution_contract',{}).get('version',0)>=15:
                    errors=[s for s in [*receipt.get('steps',[]),*receipt.get('cleanup',[])] if s.get('status')=='error']
                    if errors and all(s.get('error_origin')=='protocol' for s in errors):category='case'
                if status=='error':trace['gap_category']=category
                rows.append(dict(name=case['id']+' · '+case['title'],status=status,duration_ms=trace['duration_ms'],detail=json.dumps(dict(gap_category=category,steps=receipt,checks=checks),ensure_ascii=False)))
                continue
            elif case['kind']=='module':
                encoded=base64.b64encode(encode(module_request(u,case))).decode()
                argv=[env_path(u),*(['--import','/opt/acceptance-loader/node_modules/tsx/dist/loader.mjs'] if u['runtime']=='node' else ['-P']),'/harness/target.py' if u['runtime']=='python' else '/harness/target.cjs',encoded]
                last,streams=command(run,u,argv,target,cancelled,timeout=30);require(last['exit_code']==0,'运行环境或公开入口调用异常，查看调用日志');actual=pointer(value(streams),case.get('pointer',''))
            elif case['kind']=='cli':
                executable=cli_command(u,case.get('entry'))
                payload=base64.b64encode(case['stdin'].encode()).decode()
                # No shell interpolation of model arguments: fixed wrapper and positional argv.
                argv=['/bin/sh','-c','input="$1"; shift; printf %s "$input" | base64 -d | "$@"','acceptance',payload,*executable,*case['argv']]
                last,streams=command(run,u,argv,target,cancelled,timeout=30);actual=streams['stdout'].decode(errors='replace') if isinstance(streams['stdout'],bytes) else streams['stdout']
                trace['exit_code']=last['exit_code']
                if case['comparison']=='exit_code':trace['stdout']=actual;actual=last['exit_code']
                if case['exit_code'] is not None:protocol_ok=last['exit_code']==case['exit_code']
            elif case['kind']=='http':
                require(u['id'] in run.get('universal_services',{}),'该用例依赖的服务未就绪')
                encoded=base64.b64encode(encode({k:case[k] for k in ('method','path','body')})).decode()
                last,streams=command(run,u,[env_path(u),*(['-P','/harness/http_driver.py'] if u['runtime']=='python' else ['/harness/http.cjs']),encoded],target,cancelled,timeout=30)
                require(last['exit_code']==0,'HTTP执行器异常');response=value(streams);trace['response']=response
                protocol_ok=response['status']==case['status'];actual=pointer(response['value'],case['pointer']) if protocol_ok else response['value']
            else:
                require(u['id'] in run.get('universal_services',{}),'该用例依赖的服务未就绪')
                request=dict(base=run['universal_services'][u['id']]['base'],path=case['path'],selector=case['selector'],screenshot=str(target/'page.png'),trace=str(target/'trace.zip'))
                (target/'request.json').write_bytes(encode(request))
                from ..engine import NODE
                last,out=invoke([str(NODE),str(Path(run['_harness_path'])/'browser.cjs'),str(ROOT/'validation/node_modules/@playwright/test'),str(target/'request.json')],45,target,cancelled)
                require(last['interruption'] is None and last['exit_code']==0,'浏览器执行器异常；保留日志');actual=value(dict(stdout=out))
            try:passed=protocol_ok and compare(actual,case['expected'],case['comparison'])
            except (ValueError,TypeError):passed=False;trace['assertion']='实际输出不满足已冻结的比较协议'
            trace['actual']=actual
            if case['kind']=='cli' and case['comparison']!='exit_code' and case['exit_code'] is None:
                require(last['exit_code']==0,'CLI异常退出且没有独立退出码契约；可能是环境或用例前置条件问题，不确认为产品缺陷')
            trace.update(actual=actual,status='passed' if passed else 'failed')
        except Exception as exc:
            # Unexpected driver/comparator defects must remain execution errors
            # and must not erase earlier rows or block independent cases.
            trace.update(status='error',error=str(exc)[:1000],error_type=type(exc).__name__)
            (target/'driver-error.log').write_text(traceback.format_exc())
        trace['duration_ms']=round((time.monotonic()-start)*1000);traces.append(trace)
        rows.append(dict(name=case['id']+' · '+case['title'],status=trace['status'],duration_ms=trace['duration_ms'],detail=json.dumps({k:trace[k] for k in ('actual','exit_code','response','error') if k in trace},ensure_ascii=False)))
    Path(run.get('_case_trace_output',output/'cases.json')).write_bytes(encode(traces))
    return result_file(Path(run.get('_case_report_output',output)),rows),last


def cleanup(run,output):
    rows=[]
    if run.get('universal_plan',{}).get('execution_contract',{}).get('version',0)>=18:
        # Recover sessions left by a cancelled/interrupted driver before trying
        # to remove their shared network namespace and work volume.
        sessions=docker('ps','-a','--filter','label=acceptance.run='+run['id'],'--format','{{.Names}}',check=False).stdout.splitlines()
        for name in sessions:
            if not name.startswith('acceptance-universal-') or not ('-case-' in name or name.endswith('-copy')):continue
            log=docker('logs',name,check=False);(output/(name+'.log')).write_text(log.stdout+log.stderr)
            docker('rm','-f',name,check=False)
    for u in run['universal_plan']['discovery']['units']:
        if run.get('universal_plan',{}).get('execution_contract',{}).get('version',0)>=18:
            from .orchestration import cleanup as graph_cleanup
            target=output/u['id'];target.mkdir(exist_ok=True)
            graph=graph_cleanup(run,u,target)
            rows+=[dict(name=u['id']+' · '+n['id']+' 服务回收',status='passed' if n['removed'] else 'error') for n in graph]
        choices=run.get('universal_environment_choices',{})
        indices={choices.get(u['id'],0),*[a['index'] for a in run.get('universal_environment_attempts',{}).get(u['id'],[])]}
        remaining={}
        for index in sorted(indices):
            view={**run,'universal_environment_choices':{**choices,u['id']:index}}
            name,volume=names(view,u);docker('rm','-f',name+'-relay',name,check=False);docker('network','rm',name+'-net',check=False);docker('volume','rm',volume,check=False)
            remaining.update({kind+':'+value:docker(kind,'inspect',value,check=False).returncode==0 for kind,value in [('container',name),('container',name+'-relay'),('volume',volume),('network',name+'-net')]})
        rows.append(dict(name=u['id']+' 临时环境回收',status='passed' if not any(remaining.values()) else 'error',detail=json.dumps(remaining)))
    if not rows:rows=[dict(name='未创建组件运行环境',status='passed')]
    if run.get('universal_plan',{}).get('execution_contract',{}).get('version',0)>=20:
        for kind in ('volume','network'):
            for item in docker(kind,'ls','--filter','label=acceptance.run='+run['id'],'-q',check=False).stdout.splitlines():
                docker(kind,'rm',item,check=False)
                rows.append(dict(name='本轮 '+kind+' '+item+' 回收',status='passed' if docker(kind,'inspect',item,check=False).returncode!=0 else 'error'))
    return result_file(output,rows),dict(argv=['docker','rm / volume rm','本次标记的容器、转发器、网络和卷'],exit_code=0)
