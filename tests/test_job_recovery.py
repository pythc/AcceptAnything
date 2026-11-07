"""Fault injection uses private neutral records, never a target repository."""
import json
import multiprocessing
from pathlib import Path
import sqlite3
import subprocess
import time

import pytest

from acceptance.jobs import Jobs
from acceptance.integrations.store import IntegrationStore


def setup(root):
    jobs=Jobs(root/'jobs');store=IntegrationStore(root/'integrations')
    run=store.new('恢复反例', 'local')
    job=jobs.enqueue('integration',run['id'])
    return jobs,store,run,job


def mark_running(jobs,store,run,job):
    run['status']='running';store.save(run)
    with jobs.db() as db:db.execute("UPDATE jobs SET state='running',lease_owner='lost-worker',attempt_id='old-attempt' WHERE id=?",(job['id'],))


def no_execute(monkeypatch):
    monkeypatch.setattr(IntegrationStore,'execute',lambda *a:pytest.fail('started attempt was replayed'))


@pytest.mark.parametrize('point',['before_queue_write','after_queue_write'])
def test_interrupted_outbox_dispatch_reaches_executor_once(tmp_path,monkeypatch,point):
    jobs=Jobs(tmp_path/'jobs');store=IntegrationStore(tmp_path/'integrations');run=store.new('outbox','local')
    send=jobs.send
    def fail(jid):
        if point=='after_queue_write':send(jid)
        raise OSError('injected queue response loss')
    monkeypatch.setattr(jobs,'send',fail)
    with pytest.raises(OSError):jobs.enqueue('integration',run['id'])
    fresh=Jobs(tmp_path/'jobs');fresh.recover();job=fresh.for_run(run['id']);seen=[]
    def execute(self,rid):
        seen.append(rid);r=self.read(rid);r['status']='completed';self.save(r)
    monkeypatch.setattr(IntegrationStore,'execute',execute)
    fresh.execute(job['id']);fresh.execute(job['id'])
    assert seen==[run['id']] and fresh.read(job['id'])['state']=='completed'


def test_claim_before_run_start_does_not_replay(tmp_path,monkeypatch):
    jobs,store,run,job=setup(tmp_path);no_execute(monkeypatch)
    with jobs.db() as db:db.execute("UPDATE jobs SET state='running' WHERE id=?",(job['id'],))
    jobs.recover();jobs.execute(job['id'])
    assert jobs.read(job['id'])['state']=='interrupted'
    assert store.read(run['id'])['status']=='error'


def test_run_started_before_claim_is_not_replayed(tmp_path,monkeypatch):
    jobs,store,run,job=setup(tmp_path);no_execute(monkeypatch)
    run['status']='running';store.save(run)
    jobs.recover();jobs.execute(job['id'])
    assert jobs.read(job['id'])['state']=='interrupted'


def test_terminal_record_before_job_receipt_is_reconciled(tmp_path,monkeypatch):
    jobs,store,run,job=setup(tmp_path);no_execute(monkeypatch)
    with jobs.db() as db:db.execute("UPDATE jobs SET state='running' WHERE id=?",(job['id'],))
    run['status']='completed';store.save(run)
    raw=(store.path(run['id'])/'run.json').read_bytes()
    jobs.recover();jobs.recover()
    assert jobs.read(job['id'])['state']=='completed'
    assert (store.path(run['id'])/'run.json').read_bytes()==raw
    assert len([e for e in jobs.events(job['id'])['items'] if e['event']=='recovered_completed'])==1


def test_cancel_ledger_before_record_write_is_reconciled(tmp_path,monkeypatch):
    jobs,store,run,job=setup(tmp_path);no_execute(monkeypatch)
    with jobs.db() as db:db.execute("UPDATE jobs SET state='cancelled',cancel_requested=1 WHERE id=?",(job['id'],))
    jobs.recover();jobs.execute(job['id'])
    assert store.read(run['id'])['status']=='cancelled'


@pytest.mark.parametrize('damage',['envelope','payload','missing_record'])
def test_damaged_started_record_does_not_block_other_jobs(tmp_path,monkeypatch,damage):
    jobs,store,run,job=setup(tmp_path);mark_running(jobs,store,run,job);no_execute(monkeypatch)
    path=store.path(run['id'])/'run.json'
    if damage=='envelope':path.write_text('{broken')
    elif damage=='payload':
        run['finding_review']={'version':'test','summary':{}};store.save(run)
        for p in (path.parent/'payloads').glob('*.json'):p.write_text('changed')
    else:path.unlink()
    before=path.read_bytes() if path.exists() else None
    other=store.new('healthy queued record','local');second=jobs.enqueue('integration',other['id'])
    jobs.recover()
    assert jobs.read(job['id'])['state']=='interrupted'
    assert jobs.read(second['id'])['state']=='queued'
    assert (path.read_bytes() if path.exists() else None)==before


@pytest.mark.parametrize('phase',['container_listing','container_removal','network_removal','volume_removal'])
def test_cleanup_failure_is_pending_then_recovered(tmp_path,monkeypatch,phase):
    jobs,store,run,job=setup(tmp_path);mark_running(jobs,store,run,job)
    calls=[]
    def listing(argv,**kwargs):
        calls.append(argv[1:3])
        if phase=='container_listing' and argv[1]=='ps':raise OSError(phase+' unavailable')
        target={'container_removal':'ps','network_removal':'network','volume_removal':'volume'}.get(phase)
        return 'owned-resource\n' if argv[1]==target else ''
    def removal(argv,**kwargs):
        assert argv[-1]=='owned-resource'
        raise OSError(phase+' unavailable')
    with monkeypatch.context() as patch:
        patch.setattr('acceptance.integrations.store.subprocess.check_output',listing)
        patch.setattr('acceptance.integrations.store.subprocess.run',removal)
        jobs.recover();jobs.recover()
    pending=jobs.read(job['id'])
    assert pending['state']=='running' and phase in pending['recovery_error']
    assert store.read(run['id'])['status']=='running'
    assert len([x for x in jobs.events(job['id'])['items'] if x['event']=='recovery_deferred'])==1
    jobs.recover()
    assert jobs.read(job['id'])['state']=='interrupted'
    assert jobs.read(job['id'])['recovery_error'] is None


def waiting_worker(root,jid,point,ready):
    jobs=Jobs(Path(root)/'jobs')
    def execute(self,rid):
        r=self.read(rid);r['status']='running'
        r['pipeline']=[dict(name=point,state='running',started_at='unknown')]
        self.save(r)
        if point=='report_written':self.artifact(r,'partial-report.json',b'{"partial":true}')
        elif point=='receipt_written':(self.path(rid)/'unknown-model-receipt.json').write_text('{"state":"unknown","request_id":"fault-injection"}')
        ready.set()
        while True:time.sleep(.1)
    IntegrationStore.execute=execute
    jobs.execute(jid)


@pytest.mark.parametrize('point',['model_wait','container_start','report_written','receipt_written','archive_wait'])
def test_real_worker_death_preserves_attempt_and_unknown_receipt(tmp_path,monkeypatch,point):
    jobs,store,run,job=setup(tmp_path)
    ctx=multiprocessing.get_context('spawn');ready=ctx.Event()
    worker=ctx.Process(target=waiting_worker,args=(str(tmp_path),job['id'],point,ready));worker.start()
    try:
        assert ready.wait(15)
        first=jobs.read(job['id']);assert first['attempt_id'] and first['heartbeat_at']
        # A held OS lock is authoritative even when the clock looks stale.
        with jobs.db() as db:db.execute("UPDATE jobs SET heartbeat_at='1970-01-01' WHERE id=?",(job['id'],))
        assert 'integration' in jobs.recover()['deferred']
        assert jobs.read(job['id'])['state']=='running'
        if point=='model_wait':
            deadline=time.monotonic()+5
            while jobs.read(job['id'])['heartbeat_at']=='1970-01-01' and time.monotonic()<deadline:time.sleep(.05)
            assert jobs.read(job['id'])['heartbeat_at']!='1970-01-01'
    finally:worker.terminate();worker.join(10)
    evidence={p.name:p.read_bytes() for p in store.path(run['id']).glob('*receipt.json')}
    no_execute(monkeypatch);jobs.recover();jobs.execute(job['id'])
    result=jobs.read(job['id'])
    assert result['state']=='interrupted' and result['attempt_id']==first['attempt_id']
    assert store.read(run['id'])['interruption']['cleanup']=='completed'
    assert evidence=={p.name:p.read_bytes() for p in store.path(run['id']).glob('*receipt.json')}


def test_heartbeat_cannot_update_another_owner_or_finished_job(tmp_path):
    jobs,store,run,job=setup(tmp_path);mark_running(jobs,store,run,job)
    assert not jobs.heartbeat(job['id'])
    with jobs.db() as db:db.execute("UPDATE jobs SET lease_owner=? WHERE id=?",(jobs.owner,job['id']))
    assert jobs.heartbeat(job['id'])
    with jobs.db() as db:db.execute("UPDATE jobs SET state='completed' WHERE id=?",(job['id'],))
    assert not jobs.heartbeat(job['id'])


def test_legacy_queue_migration_preserves_rows_and_events(tmp_path):
    root=tmp_path/'jobs';root.mkdir()
    with sqlite3.connect(root/'jobs.sqlite3') as db:
        db.executescript("CREATE TABLE jobs(id TEXT PRIMARY KEY,run_id TEXT UNIQUE NOT NULL,kind TEXT NOT NULL,state TEXT NOT NULL,created_at TEXT NOT NULL,started_at TEXT,finished_at TEXT,error TEXT,task_id TEXT,cancel_requested INTEGER NOT NULL DEFAULT 0);CREATE TABLE job_events(id INTEGER PRIMARY KEY,job_id TEXT NOT NULL,at TEXT NOT NULL,event TEXT NOT NULL,detail TEXT NOT NULL);")
        db.execute("INSERT INTO jobs(id,run_id,kind,state,created_at) VALUES('old','int-old','integration','interrupted','before')")
        db.execute("INSERT INTO job_events VALUES(1,'old','before','unknown','preserved')")
    jobs=Jobs(root)
    assert jobs.read('old')['state']=='interrupted' and jobs.read('old')['attempt_id'] is None
    assert jobs.events('old')['items'][0]['detail']=='preserved'


def test_event_cursor_reaches_every_event(tmp_path):
    jobs,store,run,job=setup(tmp_path)
    with jobs.db() as db:
        for i in range(315):jobs.event(db,job['id'],'fault-point',str(i))
    ids=[];cursor=0
    while True:
        page=jobs.events(job['id'],cursor,17);ids.extend(e['id'] for e in page['items'])
        if not page['has_more']:break
        cursor=page['next_cursor']
    assert len(ids)==len(set(ids))==317


def test_lost_unclaimed_message_is_redispatched_without_restarting_worker(tmp_path):
    jobs,store,run,job=setup(tmp_path)
    jobs.recover()
    while jobs.huey.dequeue() is not None:pass  # Inject a consumer crash before the durable claim.
    jobs.recover();assert jobs.huey.pending_count()==0  # No tight-loop queue flooding.
    jobs._redispatched[job['id']]=time.monotonic()-31
    jobs.recover()
    assert jobs.huey.pending_count()==1 and jobs.read(job['id'])['state']=='queued'


def test_real_owned_resources_are_cleaned_unrelated_volume_survives(tmp_path):
    import ipaddress
    from acceptance.integrations.registry import locks
    jobs,store,run,job=setup(tmp_path);mark_running(jobs,store,run,job)
    label='acceptance.run='+run['id'];name='d043-'+run['id'];sentinel=name+'-unrelated'
    docker=lambda *a:subprocess.check_output(['docker',*a],text=True,stderr=subprocess.STDOUT,timeout=30).strip()
    container=None
    try:
        docker('volume','create',sentinel)
        docker('volume','create','--label','acceptance.integration=true','--label',label,name)
        networks=json.loads(docker('network','inspect',*docker('network','ls','-q').split()))
        used=[ipaddress.ip_network(c['Subnet']) for n in networks for c in (n.get('IPAM',{}).get('Config') or []) if c.get('Subnet')]
        subnet=next(c for c in ipaddress.ip_network('10.254.0.0/16').subnets(new_prefix=24) if not any(c.overlaps(u) for u in used if u.version==4))
        docker('network','create','--internal','--subnet',str(subnet),'--label','acceptance.integration=true','--label',label,name)
        image=locks()['node']['id']
        container=docker('run','-d','--label','acceptance.integration=true','--label',label,'--network',name,'--mount',f'type=volume,source={name},target=/private',image,'node','-e','setInterval(()=>{},1000)')
        jobs.recover()
        assert jobs.read(job['id'])['state']=='interrupted'
        assert not docker('ps','-aq','--filter','label='+label)
        assert not docker('network','ls','-q','--filter','label='+label)
        assert not docker('volume','ls','-q','--filter','label='+label)
        assert docker('volume','inspect',sentinel)
    finally:
        if container:subprocess.run(['docker','rm','-f',container],capture_output=True,timeout=20)
        subprocess.run(['docker','network','rm',name],capture_output=True,timeout=20)
        subprocess.run(['docker','volume','rm',name,sentinel],capture_output=True,timeout=20)
