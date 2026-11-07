from concurrent.futures import ThreadPoolExecutor
import pytest
from acceptance.jobs import Jobs
from acceptance.integrations.store import IntegrationStore


def queued(tmp_path):
    jobs=Jobs(tmp_path/'jobs')
    store=IntegrationStore(tmp_path/'integrations')
    r=store.new('durable-test','local')
    store.save(r)
    return jobs,store,r


def test_outbox_survives_new_instance_and_duplicate_messages(tmp_path,monkeypatch):
    jobs,store,r=queued(tmp_path)
    job=jobs.enqueue('integration',r['id'])
    assert job['task_id'] and jobs.huey.pending_count()==1
    other=Jobs(tmp_path/'jobs'); calls=[]
    def execute(self,rid):
        calls.append(rid);record=self.read(rid);record['status']='completed';self.save(record)
    monkeypatch.setattr(IntegrationStore,'execute',execute)
    other.execute(job['id']);other.execute(job['id'])
    assert calls==[r['id']] and other.read(job['id'])['state']=='completed'


def test_concurrent_enqueue_is_idempotent(tmp_path):
    jobs,store,r=queued(tmp_path)
    with ThreadPoolExecutor(max_workers=4) as pool:
        results=list(pool.map(lambda _:jobs.enqueue('integration',r['id']),range(8)))
    assert len({x['id'] for x in results})==1 and jobs.huey.pending_count()==1


def test_cancel_before_start_never_invokes_executor(tmp_path,monkeypatch):
    jobs,store,r=queued(tmp_path);job=jobs.enqueue('integration',r['id'])
    jobs.cancel(job['id'])
    monkeypatch.setattr(IntegrationStore,'execute',lambda *a:pytest.fail('cancelled job executed'))
    jobs.execute(job['id'])
    assert store.read(r['id'])['status']=='cancelled'
    assert store.read(r['id'])['decision']=='inconclusive'


def test_executor_exception_closes_both_records(tmp_path,monkeypatch):
    jobs,store,r=queued(tmp_path);job=jobs.enqueue('integration',r['id'])
    def fail(*args):raise ValueError('broken executor')
    monkeypatch.setattr(IntegrationStore,'execute',fail)
    jobs.execute(job['id'])
    assert jobs.read(job['id'])['state']=='error'
    assert store.read(r['id'])['status']=='error' and store.read(r['id'])['decision']=='inconclusive'


def test_recovery_includes_jobs_beyond_ui_limit_and_does_not_retry_started(tmp_path,monkeypatch):
    from acceptance.engine import Store
    jobs,store,r=queued(tmp_path);job=jobs.enqueue('integration',r['id'])
    with jobs.db() as db:
        db.execute("UPDATE jobs SET state='running' WHERE id=?",(job['id'],))
        for i in range(205):db.execute("INSERT INTO jobs(id,run_id,kind,state,created_at) VALUES(?,?,?,?,?)",(str(i),str(i),'integration','completed','z'))
    seen=[]
    monkeypatch.setattr(Store,'recover',lambda self,exclude,**kw:seen.append(exclude))
    monkeypatch.setattr(IntegrationStore,'recover',lambda self,exclude,**kw:seen.append(exclude))
    monkeypatch.setattr(IntegrationStore,'snapshot',lambda self,rid:{'status':'error','integrity':False})
    before=jobs.huey.pending_count();jobs.recover()
    assert jobs.read(job['id'])['state']=='interrupted'
    assert jobs.huey.pending_count()==before and seen==[set(),set()]


def test_busy_lease_does_not_claim_or_execute(tmp_path):
    jobs,store,r=queued(tmp_path);job=jobs.enqueue('integration',r['id'])
    with store.lease():jobs.execute(job['id'])
    assert jobs.read(job['id'])['state']=='queued'
    assert store.read(r['id'])['status']=='queued'


def test_startup_snapshot_does_not_kill_new_run_before_enqueue(tmp_path,monkeypatch):
    jobs,store,r=queued(tmp_path)
    # Recovery captured an empty job list before this new run was enqueued.
    monkeypatch.setattr(store,'list',lambda:[store.read(r['id'])])
    with store.lease():store.recover(exclude=set())
    assert store.read(r['id'])['status']=='queued'
    job=jobs.enqueue('integration',r['id'])
    assert job['state']=='queued'
