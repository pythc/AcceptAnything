"""Bridge an isolated public-app session to a fresh real browser, then clean up."""
import base64,json,re,time
from pathlib import Path
from .runtime import docker,names,encode,sha,module_request,cli_command,value
from ..integrations.formats import require
from ..integrations.runner import invoke
from ..integrations.registry import ROOT
from ..engine import NODE


def execute(run,u,case,output,cancelled):
    parent,volume=names(run,u);key=sha(case['id'].encode())[:16];name=parent+'-case-'+key;relay=name+'-relay';network=parent+'-net'
    directory='/work/browser-sessions/'+key;journey=case['journey'];result=dict(status='error',session={});last={}
    request=dict(steps=journey['setup'],cleanup=journey['cleanup'],app=journey['app'],adapter=journey['adapter'],receipt_directory=directory,observe_process_results=True,observe_result_fields=True,observe_callback_errors=True)
    if run.get('_fixture_cache'):request['refresh_installed_packages']=True
    request=json.loads(json.dumps(request))
    for step in [*request['steps'],*request['cleanup']]:
        if step['op']=='cli':step['command']=cli_command(u,step.get('entry'))
        if step.get('module') and u['runtime']=='node':
            bound=module_request(u,dict(module=step['module'],function=step['export'],args=[],kwargs={}))
            if bound['runtime_entry']:step['runtime_entry']=bound['runtime_entry']
    encoded=base64.b64encode(encode(request)).decode();start=time.monotonic()
    try:
        from .fixture_preparation import options as fixture_options
        state=json.loads(docker('inspect',parent).stdout)[0];image=state['Image']
        if network not in state['NetworkSettings']['Networks']:
            from ..planning.execution import create_network
            create_network(network,run['id']);docker('network','connect','--alias','target',network,parent)
        argv=['/work/venv/bin/python','-P','/harness/managed_session.py'] if u['runtime']=='python' else ['node','--import','/opt/acceptance-loader/node_modules/tsx/dist/loader.mjs','/harness/managed_session.cjs']
        docker('run','-d','--name',name,'--label','acceptance.integration=true','--label','acceptance.run='+run['id'],'--network','container:'+parent,'--cap-drop','ALL','--security-opt','no-new-privileges','--read-only','--pids-limit','256','--cpus','2','--tmpfs','/tmp:rw,exec,nosuid','--env','HOME=/work','--env','TMPDIR=/work/tmp','--env','PYTHONDONTWRITEBYTECODE=1',*fixture_options(run),'--mount',f'type=volume,src={volume},dst=/work','--mount',f'type=bind,src={run["_harness_path"]},dst=/harness,readonly','-w','/work/repo/'+u['path'],'--entrypoint',argv[0],image,*argv[1:],encoded)
        ready=None;deadline=time.monotonic()+60
        while time.monotonic()<deadline:
            require(not cancelled(),'浏览器准备已取消')
            cp=docker('cp',name+':'+directory+'/ready.json',str(output/'session-ready.json'),check=False)
            if cp.returncode==0:ready=json.loads((output/'session-ready.json').read_bytes());break
            current=json.loads(docker('inspect',name).stdout)[0]
            require(current['State']['Running'],'应用准备进程已退出；查看session.log和session-final.json')
            time.sleep(.2)
        require(ready is not None,'应用准备没有在预算内就绪')
        port=ready['port'];require(type(port) is int and 1<=port<=65535,'应用没有返回有效TCP端口')
        # The relay has no source/work/oracle mounts. Only its loopback port is
        # published; the target namespace has an internal Docker network.
        docker('run','-d','--name',relay,'--label','acceptance.integration=true','--label','acceptance.run='+run['id'],'--network','bridge','--cap-drop','ALL','--security-opt','no-new-privileges','--read-only','--pids-limit','64','-p','127.0.0.1::'+str(port),'--env','PORT='+str(port),'--mount',f'type=bind,src={Path(run["_harness_path"])/"relay.cjs"},dst=/relay.cjs,readonly',run['images']['node-base']['id'],'node','/relay.cjs')
        docker('network','connect',network,relay)
        binding=docker('port',relay,str(port)+'/tcp').stdout.strip();require(re.fullmatch(r'127\.0\.0\.1:\d+',binding),'浏览器转发地址越界')
        modern=run.get('universal_plan',{}).get('execution_contract',{}).get('version',0)>=19
        browser=dict(base='http://'+binding,steps=journey['steps'],output=str(output),ajv=str(ROOT/'validation/node_modules/ajv/dist/2020'),assert_requests=modern,self_contained_har=modern)
        (output/'browser-request.json').write_bytes(encode(browser))
        budget=45+sum(s['timeout_ms']/1000+10 for s in journey['steps'])
        last,streams=invoke([str(NODE),str(Path(run['_harness_path'])/'journey.cjs'),str(ROOT/'validation/node_modules/@playwright/test'),str(output/'browser-request.json')],budget,output,cancelled)
        require(last['interruption'] is None and last['exit_code']==0,'浏览器驱动异常，保留日志')
        result=value(dict(stdout=streams));result['session']=ready
    except Exception as exc:result.update(status='error',error=str(exc))
    finally:
        docker('stop','--time','10',name,check=False)
        log=docker('logs',name,check=False);(output/'session.log').write_text(log.stdout+log.stderr)
        cp=docker('cp',name+':'+directory+'/final.json',str(output/'session-final.json'),check=False)
        if cp.returncode==0:
            final=json.loads((output/'session-final.json').read_bytes());result['session_cleanup']=final
            if final.get('status')!='completed' or final.get('temporary_directory_removed') is not True:result.update(status='error',cleanup_error='应用准备或清理异常')
        else:result.update(status='error',cleanup_error='缺少应用终态回执，不能宣告业务通过')
        docker('rm','-f',relay,name,check=False)
        result['resources_removed']=all(docker('inspect',n,check=False).returncode!=0 for n in (relay,name))
        if not result['resources_removed']:result['status']='error'
        result['duration_ms']=round((time.monotonic()-start)*1000)
        (output/'journey-result.json').write_bytes(encode(result))
    return result,last
