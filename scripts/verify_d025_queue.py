"""Kill only an owned calibration consumer; verify pending work and cleanup."""
from pathlib import Path
import json,os,subprocess,sys,time,uuid
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from acceptance.engine import ROOT
from acceptance.integrations.store import IntegrationStore
from acceptance.jobs import Jobs

root=ROOT/'var/d025-queue'/uuid.uuid4().hex[:8];repo=root/'repo';repo.mkdir(parents=True)
source=repo/'sample.test.mjs'
source.write_text("import test from 'node:test'; test('durable',async()=>await new Promise(r=>setTimeout(r,30000)));\n")
store=IntegrationStore(root/'integrations');jobs=Jobs(root/'jobs')
store.register(dict(id='queue-control',name='Queue interruption control',repository=str(repo),version='1',environment='isolated',scope='one node test',files=['sample.test.mjs'],tasks=[dict(id='test',tool='node-test',target='sample.test.mjs',timeout=60)],rules=[dict(id='fail',kind='metric',tasks=['test'],metric='tests.failed',threshold=0),dict(id='count',kind='metric',tasks=['test'],metric='tests.total',operator='eq',threshold=1)]))
first=store.create('queue-control');one=jobs.enqueue('integration',first['id'])
source.write_text("import test from 'node:test'; test('durable',()=>{});\n")
second=store.create('queue-control');two=jobs.enqueue('integration',second['id'])
log=(root/'consumer.log').open('w')
def launch():return subprocess.Popen([str(ROOT/'.venv/bin/python'),'-m','acceptance.jobs','--root',str(root)],cwd=ROOT,stdout=log,stderr=log,start_new_session=True)
def wait(predicate,seconds):
    deadline=time.monotonic()+seconds
    while time.monotonic()<deadline:
        if predicate():return
        time.sleep(.2)
    raise TimeoutError('control did not reach required state')
p=launch()
try:
    wait(lambda:jobs.read(one['id'])['state']=='running' and bool(subprocess.check_output(['docker','ps','-q','--filter','label=acceptance.run='+first['id']],text=True).strip()),25)
    p.kill();p.wait(timeout=10)
    assert jobs.read(two['id'])['state']=='queued'
    p=launch()
    wait(lambda:jobs.read(two['id'])['state'] not in {'queued','running'},40)
    a=store.snapshot(first['id']);b=store.snapshot(second['id'])
    assert jobs.read(one['id'])['state']=='interrupted' and a['decision']=='inconclusive'
    assert b['status']=='completed' and b['decision']=='allow' and b['integrity']
    remaining=subprocess.check_output(['docker','ps','-aq','--filter','label=acceptance.run='+first['id']],text=True).strip()
    assert not remaining
    result=dict(interrupted=dict(run=first['id'],job=jobs.read(one['id'])['state'],decision=a['decision']),pending=dict(run=second['id'],job=jobs.read(two['id'])['state'],decision=b['decision']),orphan_containers=False,model_requests_replayed=0,root=str(root))
    (ROOT/'docs/design/d025/queue-crash.json').write_text(json.dumps(result,ensure_ascii=False,indent=2));print(json.dumps(result,ensure_ascii=False))
finally:
    if p.poll() is None:p.terminate();p.wait(timeout=15)
    log.close()
