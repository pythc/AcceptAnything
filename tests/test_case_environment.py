import json,uuid,sqlite3
from pathlib import Path
import pytest
from acceptance.universal import runtime
from acceptance.integrations.registry import locks


def candidate():
    from acceptance.universal import case_environment
    return case_environment


def test_private_default_state_and_baseline_survive_native_and_prior_case_writes(tmp_path,monkeypatch):
    module=candidate();original=runtime.names
    monkeypatch.setattr(runtime,'names',lambda r,u:tuple(r['_case_resources'][u['id']]) if u['id'] in r.get('_case_resources',{}) else original(r,u))
    run=dict(id='int-'+uuid.uuid4().hex[:16],context={'snapshot_digest':'neutral-fixture'},_harness_path=str(runtime.HARNESS),images=locks())
    u=dict(id='u-neutral',runtime='python',path='.',service_graph={'nodes':[]});name,volume=runtime.names(run,u);image=run['images']['universal-python312']['id']
    runtime.docker('volume','create',*module.labels(run),volume)
    runtime.docker('run','-d','--name',name,*module.labels(run),'--network','none','--mount',f'type=volume,src={volume},dst=/work','--entrypoint','/bin/sh',image,'-c','while :; do sleep 3600; done')
    try:
        runtime.docker('exec',name,'/bin/sh','-c','mkdir -p /work/repo /work/tmp; echo baseline > /work/repo/default-state')
        module.snapshot(run,u,tmp_path/'baseline',lambda:False)
        runtime.docker('exec',name,'/bin/sh','-c','echo native-poison > /work/repo/default-state')
        for cid in ['one','two']:
            output=tmp_path/cid;output.mkdir()
            with module.allocate(run,u,dict(id=cid,kind='module'),output,lambda:False) as (view,evidence):
                assert runtime.docker('exec',evidence['container'],'cat','/work/repo/default-state').stdout.strip()=='baseline'
                runtime.docker('exec',evidence['container'],'/bin/sh','-c','echo case-poison > /work/repo/default-state')
            assert evidence['removed'] and not any(evidence['remaining'].values())
        output=tmp_path/'failure';output.mkdir()
        with pytest.raises(ValueError,match='calibrated failure'):
            with module.allocate(run,u,dict(id='failed',kind='module'),output,lambda:False):raise ValueError('calibrated failure')
        assert json.loads((output/'environment/environment.json').read_bytes())['removed']
        assert runtime.docker('exec',name,'cat','/work/repo/default-state').stdout.strip()=='native-poison'
    finally:
        runtime.docker('rm','-f',name,check=False)
        for item in [volume,*[v['volume'] for v in run.get('universal_bases',{}).get(u['id'],[])]]:runtime.docker('volume','rm',item,check=False)


def test_real_sqlite_default_database_isolated_through_business_executor(tmp_path):
    from acceptance.universal.models import Case
    module=candidate();run=dict(id='int-'+uuid.uuid4().hex[:16],context={'snapshot_digest':'neutral'},_harness_path=str(runtime.HARNESS),images=locks(),universal_plan={'execution_contract':{'version':20},'discovery':{'units':[]}})
    u=dict(id='u-db',runtime='python',path='.',settings={},service_graph={'nodes':[]});run['universal_plan']['discovery']['units']=[u]
    name,volume=runtime.names(run,u);image=run['images']['universal-python312']['id']
    api=tmp_path/'api.py';api.write_text('import sqlite3\nfrom pathlib import Path\ndef state():\n with sqlite3.connect(Path(__file__).with_name("state.sqlite")) as db:return db.execute("select value from sample").fetchone()[0]\ndef change(value):\n with sqlite3.connect(Path(__file__).with_name("state.sqlite")) as db:db.execute("update sample set value=?",(value,))\n return value\n')
    db=sqlite3.connect(tmp_path/'state.sqlite');db.execute('create table sample(value text)');db.execute('insert into sample values (?)',('baseline',));db.commit();db.close()
    runtime.docker('volume','create',*module.labels(run),volume);runtime.docker('run','-d','--name',name,*module.labels(run),'--network','none','--mount',f'type=volume,src={volume},dst=/work','--mount',f'type=bind,src={runtime.HARNESS},dst=/harness,readonly','--entrypoint','/bin/sh',image,'-c','while :; do sleep 3600; done')
    try:
        runtime.docker('exec',name,'/bin/sh','-c','mkdir -p /work/repo /work/tmp; python -m venv /work/venv')
        for file in [api,tmp_path/'state.sqlite']:runtime.docker('cp',str(file),name+':/work/repo/'+file.name)
        module.snapshot(run,u,tmp_path/'snapshot',lambda:False)
        runtime.docker('exec',name,'/work/venv/bin/python','-c','import sys;sys.path.insert(0,"/work/repo");import api;api.change("native-poison")')
        first=Case(id='write',title='修改默认数据库',unit=u['id'],kind='scenario',expected=None,flow=dict(steps=[dict(id='before',op='call',module='api.py',export='state'),dict(id='write',op='call',module='api.py',export='change',args=['case-poison'])],checks=[dict(step='before',expected='baseline'),dict(step='write',expected='case-poison')])).model_dump()
        second=Case(id='read',title='下一条用例仍读取初始数据',unit=u['id'],kind='module',module='api.py',function='state',expected='baseline').model_dump()
        run['universal_generation']={'requirements':[dict(id='R',source='D',quote='每条用例从独立默认数据库读取baseline。',cases=[first,second])]}
        output=tmp_path/'business';output.mkdir();report,_=runtime.business(run,u,output,lambda:False)
        assert [x['status'] for x in report['tests']]==['passed','passed']
        traces=json.loads((output/'cases.json').read_bytes());assert len(traces)==2 and traces[1]['actual']=='baseline'
        assert all(x['environment']['removed'] for x in traces)
        assert (output/'write/case-trace.json').is_file() and (output/'read/case-trace.json').is_file()
        assert traces[0]['environment']['volume']!=traces[1]['environment']['volume']
    finally:
        cleanup=tmp_path/'cleanup';cleanup.mkdir();report,_=runtime.cleanup(run,cleanup)
        assert all(x['status']=='passed' for x in report['tests'])


def test_http_case_starts_on_owned_network_and_readiness_does_not_consume_request(tmp_path):
    from acceptance.universal.models import Case
    module=candidate();u=dict(id='u-http',runtime='node',path='.',settings={},capabilities=['http'],services=[{'framework':'npm-start','port':19300}],service_graph={'nodes':[]})
    run=dict(id='int-'+uuid.uuid4().hex[:16],context={'snapshot_digest':'neutral-http'},_harness_path=str(runtime.HARNESS),images=locks(),universal_plan={'execution_contract':{'version':20},'discovery':{'units':[u]}})
    name,volume=runtime.names(run,u);image=run['images']['universal-node']['id'];runtime.docker('volume','create',*module.labels(run),volume)
    runtime.docker('run','-d','--name',name,*module.labels(run),'--network','none','--mount',f'type=volume,src={volume},dst=/work','--entrypoint','/bin/sh',image,'-c','while :; do sleep 3600; done')
    try:
        runtime.docker('exec',name,'mkdir','-p','/work/repo','/work/tmp')
        (tmp_path/'package.json').write_text(json.dumps({'scripts':{'start':'node server.cjs'}}))
        (tmp_path/'server.cjs').write_text('let count=0;require("node:http").createServer((q,r)=>{r.setHeader("content-type","application/json");r.end(JSON.stringify({count:++count}));}).listen(Number(process.env.PORT),"0.0.0.0");')
        for file in ['package.json','server.cjs']:runtime.docker('cp',str(tmp_path/file),name+':/work/repo/'+file)
        module.snapshot(run,u,tmp_path/'snapshot',lambda:False)
        c=Case(id='request',title='首次业务请求不被就绪探针消费',unit=u['id'],kind='http',expected={'count':1}).model_dump()
        run['universal_generation']={'requirements':[dict(id='R',source='D',quote='第一次业务请求返回count=1。',cases=[c])]}
        out=tmp_path/'business';out.mkdir();report,_=runtime.business(run,u,out,lambda:False)
        assert report['tests'][0]['status']=='passed',report['tests']
    finally:
        out=tmp_path/'cleanup';out.mkdir();runtime.cleanup(run,out)
