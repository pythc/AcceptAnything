"""Immutable prepared baselines and a disposable filesystem/network per case."""
import json,time
from contextlib import contextmanager
from ..integrations.runner import encode,sha
from ..integrations.formats import require


def labels(run):return ['--label','acceptance.integration=true','--label','acceptance.run='+run['id']]


def copy_volume(run,image,source,destination,output,cancelled):
    from .runtime import docker
    from ..integrations.runner import invoke
    inspected=json.loads(docker('volume','inspect',source).stdout)[0]
    require((inspected.get('Labels') or {}).get('acceptance.run')==run['id'],'环境快照不属于当前执行，禁止隐式创建或复用其他运行数据')
    require(docker('volume','inspect',destination,check=False).returncode!=0,'用例工作卷已经存在，拒绝继承残留数据')
    docker('volume','create',*labels(run),destination)
    name=destination+'-copy'
    argv=['docker','run','--rm','--name',name,*labels(run),'--network','none','--cap-drop','ALL','--security-opt','no-new-privileges','--mount',f'type=volume,src={source},dst=/baseline,readonly','--mount',f'type=volume,src={destination},dst=/work','--entrypoint','/bin/sh',image,'-c','cp -R /baseline/. /work/']
    cmd,_=invoke(argv,3600,output,cancelled,container=name)
    require(cmd['interruption'] is None and cmd['exit_code']==0,'复制隔离工作快照失败；保留复制日志')
    return cmd


def snapshot(run,u,output,cancelled):
    from .runtime import docker,names
    output.mkdir(parents=True,exist_ok=True)
    container,volume=names(run,u);image=json.loads(docker('inspect',container).stdout)[0]['Image']
    versions=run.setdefault('universal_bases',{}).setdefault(u['id'],[]);name=volume+'-base-'+str(len(versions));start=time.monotonic()
    command=copy_volume(run,image,volume,name,output,cancelled)
    record=dict(version=1,unit=u['id'],volume=name,image=image,source_digest=run['context']['snapshot_digest'],command=command,duration_ms=round((time.monotonic()-start)*1000),scope='prepared source/dependencies before native tests and business cases; immutable mount for copying')
    versions.append(record);(output/'baseline.json').write_bytes(encode(record));return record


@contextmanager
def allocate(run,u,case,output,cancelled):
    from .runtime import docker,names,legacy_service
    from .orchestration import start as start_graph,cleanup as clean_graph
    from ..planning.execution import create_network
    bases=run.get('universal_bases',{}).get(u['id'],[])
    require(bases,'没有测试前的环境快照；拒绝继承原生测试或前条用例的数据')
    base=bases[-1];key=sha(case['id'].encode())[:16];parent,_=names(run,u);name=parent+'-case-'+key;volume=name+'-work';network=name+'-net';start=time.monotonic()
    view={**run,'_case_resources':{u['id']:[name,volume]},'universal_graphs':{},'universal_services':{}}
    evidence=dict(version=1,case_id=case['id'],base=base['volume'],image=base['image'],container=name,volume=volume,network=network,scope='private filesystem, broker/worker services and network for one frozen case',status='preparing')
    target=output/'environment';target.mkdir(parents=True,exist_ok=True)
    try:
        copied=target/'copy';copied.mkdir();evidence['copy_command']=copy_volume(run,base['image'],base['volume'],volume,copied,cancelled)
        from .fixture_preparation import selected,options
        fixture=selected(run,u,case)
        if fixture:view['_fixture_cache']=fixture
        create_network(network,run['id'])
        docker('run','-d','--name',name,*labels(run),'--network',network,'--network-alias','target','--cap-drop','ALL','--security-opt','no-new-privileges','--read-only','--pids-limit','256','--cpus','2','--tmpfs','/tmp:rw,exec,nosuid','--env','HOME=/work','--env','TMPDIR=/work/tmp','--env','PYTHONDONTWRITEBYTECODE=1',*options(view),'--mount',f'type=volume,src={volume},dst=/work','--mount',f'type=bind,src={run["_harness_path"]},dst=/harness,readonly','--entrypoint','/bin/sh',base['image'],'-c','while :; do sleep 3600; done')
        if fixture:
            mounts=json.loads(docker('inspect',name).stdout)[0]['Mounts'];mount=next(m for m in mounts if m['Destination']=='/fixture-cache')
            require(mount['Name']==fixture['volume'] and mount['RW'] is False,'构建夹具缓存必须以只读方式挂载')
            evidence['fixture_preparation']=dict(key=fixture['key'],volume=fixture['volume'],mount_readonly=True)
        graph=target/'services';graph.mkdir();evidence['services']=start_graph(view,u,graph,cancelled)
        ready={n['id'] for n in evidence['services'] if n['status']=='ready'}
        require(set(case.get('requires',[]))<=ready,'该用例的独立服务未就绪：'+', '.join(sorted(set(case.get('requires',[]))-ready)))
        if case['kind'] in {'http','browser'}:
            web=target/'web';web.mkdir();legacy_service(view,u,web,cancelled)
        evidence['status']='ready';yield view,evidence
    except BaseException as exc:
        evidence.update(status='error',error=type(exc).__name__+': '+str(exc));raise
    finally:
        clean=target/'cleanup';clean.mkdir(exist_ok=True)
        try:evidence['service_cleanup']=clean_graph(view,u,clean)
        except Exception as exc:evidence['service_cleanup_error']=str(exc)
        log=docker('logs',name,check=False);(clean/'workspace.log').write_text(log.stdout+log.stderr)
        docker('rm','-f',name+'-relay',name,check=False);docker('network','rm',network,check=False);docker('volume','rm',volume,check=False)
        remaining={kind+':'+item:docker(kind,'inspect',item,check=False).returncode==0 for kind,item in [('container',name),('container',name+'-relay'),('network',network),('volume',volume)]}
        evidence['remaining']=remaining;evidence['removed']=not any(remaining.values()) and not evidence.get('service_cleanup_error') and all(x['removed'] for x in evidence.get('service_cleanup',[]));evidence['duration_ms']=round((time.monotonic()-start)*1000)
        (target/'environment.json').write_bytes(encode(evidence))


def business(run,u,output,cancelled):
    from .runtime import legacy_business,result_file
    cases=[(r,c) for r in run.get('universal_generation',{}).get('requirements',[]) for c in r['cases'] if c['unit']==u['id']]
    require(cases,'该组件没有经过依据校验的业务用例；其他任务继续，缺口保留')
    rows=[];traces=[];last={}
    for requirement,case in cases:
        if cancelled():raise ValueError('已取消')
        target=output/case['id'];target.mkdir();begin=time.monotonic();environment=None
        trace=dict(case=case,requirement=requirement['id'],source=requirement['source'],quote=requirement['quote'])
        try:
            with allocate(run,u,case,target,cancelled) as (view,environment):
                view['universal_generation']={'requirements':[{**requirement,'cases':[case]}]}
                view['_case_trace_output']=str(target/'case-trace.json');view['_case_report_output']=str(target)
                _,last=legacy_business(view,u,output,cancelled)
                trace=json.loads((target/'case-trace.json').read_bytes())[0]
            trace['environment']=environment
            if not environment['removed']:trace.update(status='error',error='用例环境未完整清理')
        except Exception as exc:trace.update(status='error',error=type(exc).__name__+': '+str(exc),environment=environment,**({'gap_category':getattr(exc,'gap_category','environment')} if environment is None else {}))
        trace['duration_ms']=round((time.monotonic()-begin)*1000);traces.append(trace)
        rows.append(dict(name=case['id']+' · '+case['title'],status=trace['status'],duration_ms=trace['duration_ms'],detail=json.dumps({k:trace[k] for k in ('error','actual','checks','environment','gap_category') if k in trace},ensure_ascii=False)))
        from ..integrations.storage import write_json
        write_json(output/'cases.json',traces)
    return result_file(output,rows),last
