"""Reviewed GMAH runtime. Target code is read-only, dependencies pinned, no external network.

The web development server permits business diagnostics even if the production
TypeScript build fails. Build failure remains a separate mandatory rejection.
"""
from contextlib import contextmanager
import json
from pathlib import Path
import time
import uuid
from urllib.request import build_opener,ProxyHandler
from .execution import docker,create_network,execute_at
from ..integrations.runner import encode,invoke
from ..integrations.formats import require,parse
from ..integrations.registry import locks,ROOT

KEYS=('gmah-api','gmah-web','gmah-redis','gmah-postgres','node-base')
COMMON=['--cap-drop','ALL','--security-opt','no-new-privileges','--read-only','--memory','1024m','--cpus','2','--pids-limit','256','--tmpfs','/tmp:rw,exec,nosuid,size=536870912','-e','HOME=/tmp','-e','PYTHONDONTWRITEBYTECODE=1']


def wait_http(base,cancelled,timeout=45):
    opener=build_opener(ProxyHandler({}));end=time.monotonic()+timeout
    while time.monotonic()<end:
        require(not cancelled(),'准备环境时取消')
        try:
            with opener.open(base+'/healthz',timeout=1) as r:
                if r.status==200 and json.load(r).get('status')=='ok':return
        except (OSError,ValueError):pass
        time.sleep(.2)
    raise ValueError('GMAH 服务未就绪；查看已归档的容器日志')


@contextmanager
def environment(source,output,run_id,images,cancelled,port=19300):
    name='acceptance-gmah-'+uuid.uuid4().hex[:12];network=name+'-net'
    names=[];volumes=[];created=False
    require(all(images.get(k,'').startswith('sha256:') for k in KEYS),'GMAH 配方需要固定依赖镜像')
    def start(suffix,image,args,alias=None,options=None):
        n=name+'-'+suffix;names.append(n)
        docker('run','-d','--name',n,'--label','acceptance.integration=true','--label','acceptance.run='+run_id,
               '--network',network,'--network-alias',alias or suffix,*COMMON,*(options or []),image,*args)
        return n
    try:
        create_network(network,run_id);created=True
        for suffix in ('redis','postgres'):
            v=name+'-'+suffix+'-data';volumes.append(v)
            docker('volume','create','--label','acceptance.integration=true','--label','acceptance.run='+run_id,v)
        redis=start('redis',images['gmah-redis'],['redis-server','--appendonly','yes','--dir','/data'],options=['--user','redis','--mount','type=volume,src='+volumes[0]+',dst=/data'])
        postgres=start('postgres',images['gmah-postgres'],[],options=['--user','postgres','--tmpfs','/var/run/postgresql:rw,uid=70,gid=70',
            '-e','POSTGRES_PASSWORD=acceptance-synthetic','-e','POSTGRES_DB=gmah','--mount','type=volume,src='+volumes[1]+',dst=/var/lib/postgresql/data'])
        for _ in range(100):
            require(not cancelled(),'准备环境时取消')
            if docker('exec',postgres,'pg_isready','-U','postgres',check=False).returncode==0:break
            time.sleep(.2)
        else:raise ValueError('PostgreSQL 未就绪')
        api=start('api',images['gmah-api'],['python','-m','uvicorn','agent_workflow.api.app:create_app','--factory','--host','0.0.0.0','--port','8080'],options=[
            '--workdir','/tmp','--mount',f'type=bind,src={source},dst=/source,readonly','-e','PYTHONPATH=/source/src',
            '-e','REDIS_URL=redis://redis:6379/0','-e','POSTGRES_DSN=postgresql://postgres:acceptance-synthetic@postgres:5432/gmah',
            '-e','TOOLS_CONFIG_PATH=/source/configs/tools.example.json','-e','RAG_CONFIG_PATH=/source/configs/rag.example.yaml','-e','MCP_CONFIG_PATH=/source/configs/mcp-servers.example.yaml',
            '-e','AUTH_ENABLED=false','-e','MODEL_BASE_URL=http://unavailable.invalid','-e','MODEL_API_KEY='])
        frontend=start('web',images['gmah-web'],['sh','-c',f'cp -R /source/web /tmp/web && cp -R /deps/node_modules /tmp/web/node_modules && cd /tmp/web && node /deps/node_modules/vite/bin/vite.js --host 0.0.0.0 --port {port} --strictPort'],alias='target',options=[
            '--mount',f'type=bind,src={source},dst=/source,readonly','-e','VITE_API_PROXY_TARGET=http://api:8080'])
        relay=name+'-relay';names.append(relay)
        docker('run','-d','--name',relay,'--label','acceptance.integration=true','--label','acceptance.run='+run_id,'--network','bridge','-p',f'127.0.0.1::{port}',*COMMON,
               '-e',f'PORT={port}','--mount',f'type=bind,src={ROOT / "acceptance/planning/runtime/relay.cjs"},dst=/relay.cjs,readonly',images['node-base'],'node','/relay.cjs')
        docker('network','connect',network,relay)
        binding=docker('port',relay,str(port)+'/tcp').stdout.strip()
        import re
        require(re.fullmatch(r'127\.0\.0\.1:\d+',binding),'服务不得暴露到非本机地址')
        base='http://'+binding
        wait_http(base,cancelled)
        state=dict(base=base,network=network,name=name,api=api,redis=redis,postgres=postgres,frontend=frontend,
                   images=images,web_mode='Vite development server; production build is a separate mandatory gate',external_network=False,
                   grading_adapter='repository LocalGradingSystemAdapter (mock boundary)',persistent_stores=['Redis','PostgreSQL'])
        (output/'environment.json').write_bytes(encode(state))
        yield state
    finally:
        cleanup=[]
        for n in reversed(names):
            log=docker('logs','--tail','100',n,check=False)
            (output/(n.split(name+'-')[-1]+'.log')).write_text((log.stdout+log.stderr)[-30000:])
            r=docker('rm','-f',n,check=False);cleanup.append(dict(resource=n,removed=r.returncode==0))
        if created:
            r=docker('network','rm',network,check=False);cleanup.append(dict(resource=network,removed=r.returncode==0))
        for v in volumes:
            r=docker('volume','rm',v,check=False);cleanup.append(dict(resource=v,removed=r.returncode==0))
        (output/'cleanup.json').write_bytes(encode(cleanup))
        require(all(r['removed'] for r in cleanup),'GMAH 环境清理未完成')


def execute_generated(store,run,task,output,cancelled):
    plan=run['test_plan'];images=plan['toolchain']['images']
    with environment(store.path(run['id'])/'source',output,run['id'],images,cancelled,plan['specification']['environment']['port']) as env:
        return execute_at(run,task,output,cancelled,store.path(run['id'])/'generated',env['base'],env['network'],env['name'],COMMON)


def execute_native(task,source,output,cancelled):
    images={k:v['id'] for k,v in locks().items()};output.mkdir(parents=True,exist_ok=True)
    name='acceptance-gmah-check-'+uuid.uuid4().hex[:12]
    base=['docker','run','--name',name,'--label','acceptance.integration=true','--label','acceptance.run='+source.parent.name,'--network','none',*COMMON,
          '--mount',f'type=bind,src={source},dst=/source,readonly','--mount',f'type=bind,src={output},dst=/output']
    if task.tool=='gmah-regression':
        command=base+[images['gmah-api'],'sh','-c','cp -R /source /tmp/repository && cd /tmp/repository && PYTHONPATH=/tmp/repository/src pytest -p no:cacheprovider --junitxml=/output/report.xml tests --deselect=tests/test_agent_api.py::TestAgentAPIEndpoint::test_agent_chat_endpoint --deselect=tests/test_agent_core.py::TestAgentIntegration --deselect=tests/test_agent_e2e.py::TestAgentWithRealTools']
    elif task.tool=='gmah-build':
        command=base+[images['gmah-web'],'sh','-c','cp -R /source/web /tmp/web && cp -R /deps/node_modules /tmp/web/node_modules && cd /tmp/web && npm run build']
    else:
        with environment(source,output,source.parent.name,images,cancelled) as env:
            if task.tool=='gmah-recovery':
                command=[str(ROOT/'.venv/bin/python'),'-m','pytest','--noconftest','-p','no:cacheprovider','--rootdir='+str(ROOT/'acceptance/recipes/gmah'),
                         '--junitxml='+str(output/'report.xml'),str(ROOT/'acceptance/recipes/gmah/recovery.py')]
                return invoke(command,task.timeout,output,cancelled,extra_env={'GMAH_ENVIRONMENT':str(output/'environment.json'),'PYTEST_DISABLE_PLUGIN_AUTOLOAD':'1'})
            command=['docker','run','--name',name,'--network',env['network'],*COMMON,'--mount',f'type=bind,src={ROOT / "acceptance/recipes/gmah/load.js"},dst=/load.js,readonly',
                     '--mount',f'type=bind,src={output},dst=/output',images['gmah-k6'],'run','/load.js']
            try:return invoke(command,task.timeout,output,cancelled,name)
            finally:docker('rm','-f',name,check=False)
    try:
        result,stdout=invoke(command,task.timeout,output,cancelled,name)
        if task.tool=='gmah-build':
            # Preserve the real build exit; the report wraps this single build check only.
            import xml.etree.ElementTree as ET
            suite=ET.Element('testsuite',name='生产构建',tests='1',failures=str(int(result['exit_code']!=0)))
            case=ET.SubElement(suite,'testcase',name='production_typescript_build',time=str(result['duration_ms']/1000))
            if result['exit_code']!=0:ET.SubElement(case,'failure',message='生产构建失败；见原始 stdout/stderr').text=stdout.decode(errors='replace')[-20000:]
            ET.ElementTree(suite).write(output/'report.xml',encoding='utf-8')
        return result,stdout
    finally:docker('rm','-f',name,check=False)


def completion(record):
    """Execution completeness is separate from whether the product passed."""
    tasks=record['tasks'];plan=record.get('test_plan') or {};missing=[]
    required={'gmah-build','gmah-regression','gmah-performance','gmah-recovery'}
    if not required<={t['tool'] for t in tasks}:missing.append('构建、回归、性能或恢复任务缺失')
    engines={c['engine'] for c in plan.get('checks',[]) if 'engine' in c}
    if not {'api','browser'}<=engines:missing.append('API 与浏览器业务用例缺失')
    if not any(t['tool'] not in required|{'acceptance-generated'} for t in tasks):missing.append('仓库扫描缺失')
    from ..workflow import verified_high
    planner=plan.get('planner',{})
    if planner.get('kind')!='model' or planner.get('edited') or not all(verified_high(c) for c in planner.get('connections') or [planner.get('connection') or {}]):missing.append('原始 GPT-6 High 设计方案未验证')
    for t in tasks:
        report=t.get('report',{})
        if t['state']!='completed' or not report.get('complete') or any(x['status'] in {'skipped','error','unknown'} for x in report.get('tests',[])):
            missing.append(t['id']+' 未完整执行')
    cleanup=[a for a in record['artifacts'] if a['name'].endswith('/cleanup.json')]
    if len(cleanup)<4:missing.append('隔离环境清理证据缺失')
    if not record.get('integrity'):missing.append('证据完整性未验证')
    return dict(kind='recipe',complete=not missing,missing=missing,scope='GMAH 本地 MVP：会话、草稿幂等、人工审批、负载与重启恢复')


def present(view,record):
    """Use the same details page, but expose real business execution layers."""
    groups={
        'Lscanners':'仓库扫描','L1':'生产构建与回归','L2':'模型 API 用例','L3':'模型浏览器用例','performance':'业务负载','recovery':'重启与恢复'}
    def group(t):
        if t['tool']=='acceptance-generated':return 'L3' if t['target']=='browser' else 'L2'
        return {'gmah-build':'L1','gmah-regression':'L1','gmah-performance':'performance','gmah-recovery':'recovery'}.get(t['tool'],'Lscanners')
    mapping={t['id']:group(t) for t in record['tasks']}
    # Historical runs keep their actual task order, including diagnostic runs
    # which exercise the UI before the separate production build gate.
    order=list(dict.fromkeys(mapping.values()))
    groups={key:groups[key] for key in order}
    for rows in (view['baseline']['criteria'],view['results'],view['findings']):
        for row in rows:row['layer']=mapping.get(row.get('criterion_id',row.get('id')),'L1')
    stages=[s for s in view['pipeline'] if s['id']=='baseline']
    planner=record['test_plan'].get('planner',{});connection=planner.get('connection') or {}
    from .verification import label
    stages.append(dict(id='design',title='模型设计方案',tool=label(connection),work='核对已确认的中文方案与原始调用证据',
        detail='复用已确认模型方案；不是本次重新调用'+('；交互定位器已修订，模型输入与预期保持原样' if planner.get('binding_revisions') else ''),status='passed' if connection.get('verified') and not planner.get('edited') else 'blocked',duration_ms=sum(c.get('duration_ms',0) for c in planner.get('connections') or [connection])))
    for key,title in groups.items():
        tasks=[t for t in record['tasks'] if mapping[t['id']]==key]
        rows=[r for r in view['results'] if r['layer']==key]
        state='running' if any(t['state']=='running' for t in tasks) else 'queued' if any(t['state']=='queued' for t in tasks) else 'error' if not tasks or any(t['state'] in {'error','cancelled'} for t in tasks) else 'failed' if any(r['status']=='failed' for r in rows) else 'passed'
        starts=[t['started_at'] for t in tasks if t.get('started_at')];ends=[t['finished_at'] for t in tasks if t.get('finished_at')]
        s=dict(id=key,title=title,tool='固定执行器',work=title,detail=f'{len(tasks)} 项检查',status=state)
        if starts:s['started_at']=min(starts)
        if tasks and len(ends)==len(tasks):
            s.update(finished_at=max(ends),duration_ms=sum(t['duration_ms'] for t in tasks) if all(t.get('duration_ms') is not None for t in tasks) else None)
        stages.append(s)
    stages += [s for s in view['pipeline'] if s['id'] in {'review','gate'}]
    view.update(pipeline=stages,display_stages=stages,completion=completion(record),
        reasons=record.get('errors') or ['本地 MVP 业务流程门禁：'+record['decision']],
        limits=['开发模式浏览器验证不能代替生产构建。只覆盖冻结的本地 MVP 范围，外部批改、模型和消息渠道另列边界。'])
    return view
