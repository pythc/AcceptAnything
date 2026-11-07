"""Disposable target, independent trusted oracle, native test reports."""
import json
import os
from pathlib import Path
import re
import subprocess
import time
import ipaddress
from urllib.request import build_opener, ProxyHandler, HTTPRedirectHandler
from .compiler import compiler_digest, dependencies, planned_operations
from ..integrations.runner import sha, encode, invoke
from ..integrations.formats import require, parse
from ..integrations.registry import ROOT


def docker(*args,check=True):
    r=subprocess.run(['docker',*args],capture_output=True,text=True,timeout=20)
    if check: require(r.returncode==0,'容器操作失败：'+r.stderr[:1000])
    return r


def create_network(name, run_id):
    ids=docker('network','ls','-q').stdout.split()
    existing=json.loads(docker('network','inspect',*ids).stdout) if ids else []
    used=[ipaddress.ip_network(c['Subnet']) for n in existing for c in (n.get('IPAM',{}).get('Config') or []) if c.get('Subnet')]
    for subnet in ipaddress.ip_network('10.231.252.0/24').subnets(new_prefix=28):
        if any(subnet.version==other.version and subnet.overlaps(other) for other in used): continue
        result=docker('network','create','--internal','--subnet',str(subnet),'--label','acceptance.integration=true','--label','acceptance.run='+run_id,name,check=False)
        if result.returncode==0:return
        if 'overlap' not in result.stderr.lower(): raise ValueError('隔离网络创建失败：'+result.stderr[:1000])
    raise ValueError('本地验收的临时隔离网段已占用')


def verify_plan_files(store, run):
    plan=run['test_plan'];directory=store.path(run['id'])/'generated'
    require(sha(encode(plan))==run['design_digest'],'执行方案摘要不符')
    _,raw=store.artifact_bytes(run['id'],run['design_ref'])
    require(json.loads(raw)==plan,'执行方案与冻结证据不一致')
    _,raw=store.artifact_bytes(run['id'],run['generated_manifest_ref'])
    require(json.loads(raw)==run['generated_manifest'],'生成文件摘要清单不一致')
    for name,digest in run['generated_manifest'].items():
        p=directory/name
        require(p.is_file() and not p.is_symlink() and sha(p.read_bytes())==digest,'生成代码发生变化：'+name)
    for row in plan['manifest']:
        p=store.path(run['id'])/'source'/row['path']
        require(p.is_file() and not p.is_symlink() and sha(p.read_bytes())==row['sha256'] and p.stat().st_mode & 0o777==row['mode'],'冻结目标发生变化：'+row['path'])


def verify_archived(store,run):
    plan=run['test_plan']
    require(sha(encode(plan))==run['design_digest'],'方案摘要不符')
    require(json.loads(store.artifact_bytes_for_record(run,run['design_ref'])[1])==plan,'归档方案不符')
    manifest=json.loads(store.artifact_bytes_for_record(run,run['generated_manifest_ref'])[1])
    require(manifest==run['generated_manifest'],'归档生成清单不符')
    artifacts={a['name']:a for a in run['artifacts']}
    for name,content in plan.get('recipe_files',{}).items():
        require('recipe/'+name in artifacts and artifacts['recipe/'+name]['sha256']==sha(content.encode()),'配方原件缺失或不一致')
    for name,digest in manifest.items():
        if name=='plan.json': continue
        key=('generated/' if name in plan['generated'] else 'driver/')+name
        require(key in artifacts and artifacts[key]['sha256']==digest,'生成文件证据缺失或不一致')
    for check in plan['checks']:
        if 'engine' not in check: continue
        task=next(t for t in run['tasks'] if t['id']==check['id'])
        if task['state']!='completed': continue
        if check['engine']=='openapi':
            verify_operation_results(plan,check,task['report'])
            continue
        names=[t['name'] for t in task['report']['tests']]
        require(len(names)==len(check['case_ids']) and set(names)=={'test_'+c for c in check['case_ids']},'归档实际用例与计划不一致')
        for cid in check['case_ids']:
            name=task['id']+'/'+cid+'-trace.json'
            require(name in artifacts,'归档步骤证据缺失')
            trace=json.loads(store.artifact_bytes_for_record(run,artifacts[name]['id'])[1])
            case=next(c for c in plan['cases'] if c['id']==cid)
            result=next(t for t in task['report']['tests'] if t['name']=='test_'+cid)
            require(trace['case_id']==cid and trace['requirement']==case['requirement'] and trace['source']==case['source'],'归档步骤来源不符')
            require((trace['status']=='passed')==(result['status']=='passed'),'归档步骤结果不符')


def verify_operation_results(plan, check, report):
    expected=planned_operations(plan,check)
    names=[t['name'] for t in report['tests']]
    require(len(names)==len(expected) and set(names)==set(expected), 'OpenAPI 实际接口操作与冻结契约不一致')


def validate_results(plan, task, report, command, output):
    check=next(c for c in plan['checks'] if c['id']==task['id'])
    if check['engine']=='openapi':
        verify_operation_results(plan,check,report)
    else:
        expected={'test_'+cid for cid in check['case_ids']}
        names=[t['name'] for t in report['tests']]
        require(len(names)==len(expected) and set(names)==expected,'实际执行用例与生成清单不一致')
        for case in (c for c in plan['cases'] if c['id'] in check['case_ids']):
            path=output/(case['id']+'-trace.json')
            require(path.is_file() and not path.is_symlink(),'用例步骤证据缺失：'+case['id'])
            trace=json.loads(path.read_bytes())
            result=next(t for t in report['tests'] if t['name']==case['name'])
            require(trace['case_id']==case['id'] and trace['requirement']==case['requirement'],'步骤证据身份不一致')
            require(trace['status']!='error','测试驱动未完整执行：'+str(trace.get('error','未知错误')))
            # pytest represents raised infrastructure exceptions as failures. Trace retains finer distinction.
            require((trace['status']=='passed')==(result['status']=='passed'),'步骤证据与原生结果不一致')
            if result['status']=='passed':
                require(len(trace['steps'])==len(case['steps']),'通过用例的步骤不完整')
    failures=any(t['status'] in {'failed','error'} for t in report['tests'])
    require(command['exit_code']==(1 if failures else 0),'测试退出码与原始报告不一致')
    require(all(t['status'] in {'passed','failed'} for t in report['tests']),'存在错误、跳过或未知的生成用例')


def execute_generated(store, run, task, output, cancelled):
    output.mkdir(parents=True,exist_ok=True)
    verify_plan_files(store,run)
    plan=run['test_plan'];spec=plan['specification'];environment=spec['environment']
    require(compiler_digest()==plan['compiler_digest'] and dependencies()==plan['toolchain'],'执行器版本漂移')
    if environment.get('recipe'):
        from .gmah import execute_generated as execute_recipe
        return execute_recipe(store,run,task,output,cancelled)
    directory=store.path(run['id'])/'generated';source=store.path(run['id'])/'source'
    name='acceptance-design-'+run['id'][4:]+'-'+task['id'];network=name+'-net';relay=name+'-relay'
    image=plan['toolchain']['images']['node-base' if environment['runtime']=='node' else 'python']
    common=['--cap-drop','ALL','--security-opt','no-new-privileges','--read-only','--memory','512m','--cpus','1',
            '--pids-limit','128','--tmpfs','/tmp:rw,nosuid,size=134217728','--env','HOME=/tmp','--env','PYTHONDONTWRITEBYTECODE=1']
    runtime='node' if environment['runtime']=='node' else 'python'
    bridge=directory/('target.cjs' if runtime=='node' else 'target.py')
    port=environment['port'];ready='/health' if environment['mode']=='module' else environment['ready_path']
    entry='/target-bridge' if environment['mode']=='module' else '/source/'+environment['entrypoint']
    target=['run','-d','--name',name,'--label','acceptance.integration=true','--label','acceptance.run='+run['id'],
        '--network',network,'--network-alias','target',*common,'--env',f'PORT={port}',
        '--workdir','/source','--mount',f'type=bind,src={source},dst=/source,readonly']
    if environment['mode']=='module': target+=['--mount',f'type=bind,src={bridge},dst=/target-bridge,readonly']
    target += [image,runtime,entry]
    created_network=False
    try:
        create_network(network,run['id'])
        created_network=True
        docker(*target)
        # Docker Desktop does not publish ports from internal networks. A fixed relay
        # exposes only the target service; it receives no source, oracle, or report mount.
        docker('run','-d','--name',relay,'--label','acceptance.integration=true','--label','acceptance.run='+run['id'],
               '--network','bridge','-p',f'127.0.0.1::{port}',*common,'--env',f'PORT={port}',
               '--mount',f'type=bind,src={directory / "relay.cjs"},dst=/relay.cjs,readonly',
               plan['toolchain']['images']['node-base'],'node','/relay.cjs')
        docker('network','connect',network,relay)
        binding=docker('port',relay,str(port)+'/tcp').stdout.strip()
        require(re.fullmatch(r'127\.0\.0\.1:\d+',binding),'目标监听地址不符合本地限制')
        base='http://'+binding
        class NoRedirect(HTTPRedirectHandler):
            def redirect_request(self,*args,**kwargs): return None
        opener=build_opener(ProxyHandler({}),NoRedirect())
        start=time.monotonic()
        while time.monotonic()-start<15:
            require(not cancelled(),'准备环境时取消')
            try:
                with opener.open(base+ready,timeout=.5) as response:
                    if response.status==200: break
            except OSError: pass
            require(docker('inspect','--format','{{.State.Running}}',name).stdout.strip()=='true','目标服务提前退出')
            time.sleep(.1)
        else: raise ValueError('目标服务未就绪；请检查入口、依赖与健康路径')
        (output/'environment.json').write_bytes(encode(dict(image=image,argv=target,target=base,network='internal',
            source_digest=plan['snapshot_digest'],design_digest=run['design_digest'],ready_ms=round((time.monotonic()-start)*1000))))
        return execute_at(run,task,output,cancelled,directory,base,network,name,common)
    finally:
        logs=docker('logs','--tail','100',name,check=False)
        (output/'target.log').write_text((logs.stdout+logs.stderr)[-30000:])
        docker('rm','-f',name,check=False)
        docker('rm','-f',relay,check=False)
        if created_network: docker('network','rm',network,check=False)


def execute_at(run,task,output,cancelled,directory,base,network,name,common):
    plan=run['test_plan'];port=plan['specification']['environment']['port']
    engine=next(c['engine'] for c in plan['checks'] if c['id']==task['id'])
    env={'ACCEPTANCE_PLAN':str(directory/'plan.json'),'ACCEPTANCE_BASE':base,'ACCEPTANCE_OUTPUT':str(output),
         'ACCEPTANCE_RUN':run['id'],'PYTEST_DISABLE_PLUGIN_AUTOLOAD':'1','PYTHONPATH':str(directory),
         'ACCEPTANCE_PLAYWRIGHT':str(ROOT/'validation/node_modules/@playwright/test')}
    if engine in {'module','api'}:
        argv=[str(ROOT/'.venv/bin/python'),'-m','pytest','--noconftest','-p','no:cacheprovider','-q',
              '--rootdir='+str(directory),'--junitxml='+str(output/'report.xml'),str(directory/'test_generated.py')]
        command,_=invoke(argv,task['timeout'],output,cancelled,extra_env=env)
    elif engine=='browser':
        from ..engine import NODE
        argv=[str(NODE),str(ROOT/'validation/node_modules/@playwright/test/cli.js'),'test','--config',str(directory/'playwright.config.cjs')]
        command,_=invoke(argv,task['timeout'],output,cancelled,extra_env=env)
    else:
        cid=next(c['case_ids'][0] for c in plan['checks'] if c['id']==task['id'])
        toolname=name+'-schema'
        argv=['docker','run','--name',toolname,'--network',network,*common,'--mount',f'type=bind,src={directory},dst=/plan,readonly',
              '--mount',f'type=bind,src={output},dst=/output',plan['toolchain']['images']['python'],
              'schemathesis','run','/plan/'+cid+'-openapi.json','--url',f'http://target:{port}',
              '--report','junit','--report-junit-path','/output/report.xml','--max-examples','10',
              '--phases','examples,coverage,fuzzing','--generation-database','none']
        try: command,_=invoke(argv,task['timeout'],output,cancelled,toolname)
        finally: docker('rm','-f',toolname,check=False)
    (output/'command.json').write_bytes(encode(command))
    require(command['interruption'] is None,'测试中断：'+str(command['interruption']))
    require(command['exit_code'] in {0,1},'测试工具执行异常：'+str(command['exit_code']))
    raw=(output/'report.xml').read_bytes();report=parse('junit',raw)
    validate_results(plan,task,report,command,output)
    return report,command
