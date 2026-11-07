"""Huey-backed durable dispatch. Running attempts are never automatically retried."""
from contextlib import contextmanager
from datetime import datetime, timezone
import fcntl
from pathlib import Path
import sqlite3
import threading
import time
import uuid

from huey import SqliteHuey
from .integrations.formats import require


def now():
    return datetime.now(timezone.utc).isoformat()


class Jobs:
    def __init__(self, root):
        self.root = Path(root).resolve()
        self.root.mkdir(parents=True, exist_ok=True)
        self.database = self.root / 'jobs.sqlite3'
        self.owner = 'worker-' + uuid.uuid4().hex
        self._redispatched = {}
        self.huey = SqliteHuey('acceptance', filename=str(self.root/'queue.sqlite3'), results=False)
        with self.db() as db:
            db.executescript('''
                CREATE TABLE IF NOT EXISTS jobs (
                    id TEXT PRIMARY KEY, run_id TEXT UNIQUE NOT NULL,
                    kind TEXT NOT NULL, state TEXT NOT NULL, created_at TEXT NOT NULL,
                    started_at TEXT, finished_at TEXT, error TEXT, task_id TEXT,
                    cancel_requested INTEGER NOT NULL DEFAULT 0
                );
                CREATE TABLE IF NOT EXISTS job_events (
                    id INTEGER PRIMARY KEY, job_id TEXT NOT NULL,
                    at TEXT NOT NULL, event TEXT NOT NULL, detail TEXT NOT NULL
                );
            ''')
            columns = {r['name'] for r in db.execute('PRAGMA table_info(jobs)')}
            for name in ('attempt_id','lease_owner','heartbeat_at','recovery_error'):
                if name not in columns: db.execute(f'ALTER TABLE jobs ADD COLUMN {name} TEXT')
            db.execute('CREATE INDEX IF NOT EXISTS jobs_state ON jobs(state,created_at)')
            db.execute('CREATE INDEX IF NOT EXISTS events_job ON job_events(job_id,id)')

        def execute(job_id):
            self.execute(job_id)
        # `python -m` uses __main__, while HTTP imports acceptance.jobs.
        # Huey includes the function module in its durable task identity.
        execute.__module__ = 'acceptance.jobs'
        self.task = self.huey.task(name='acceptance.execute', retries=0)(execute)

    @contextmanager
    def db(self):
        db = sqlite3.connect(self.database, timeout=30)
        db.row_factory = sqlite3.Row
        db.execute('PRAGMA journal_mode=WAL')
        try:
            with db:
                yield db
        finally:
            db.close()

    def event(self, db, jid, event, detail=''):
        db.execute('INSERT INTO job_events(job_id,at,event,detail) VALUES(?,?,?,?)', (jid,now(),event,detail))

    def send(self, jid):
        if self.read(jid)['state'] != 'queued': return
        task = self.task.s(jid)
        self.huey.enqueue(task)
        with self.db() as db:
            db.execute('UPDATE jobs SET task_id=? WHERE id=?',(task.id,jid))
            self.event(db,jid,'dispatched',task.id)

    def enqueue(self, kind, run_id):
        require(kind in {'native','integration'}, '不支持的执行类型')
        # Validate identity and existence before persisting a dispatch request.
        store = self.store(kind)
        require(store.read(run_id)['status']=='queued', '只能提交尚未执行的记录')
        jid = 'job-'+uuid.uuid4().hex
        with self.db() as db:
            db.execute('BEGIN IMMEDIATE')
            existing=db.execute('SELECT * FROM jobs WHERE run_id=?',(run_id,)).fetchone()
            if existing:return dict(existing)
            db.execute('INSERT INTO jobs(id,run_id,kind,state,created_at) VALUES(?,?,?,?,?)', (jid,run_id,kind,'queued',now()))
            self.event(db,jid,'queued')
        # Metadata is an outbox: startup can redispatch an interrupted enqueue.
        self.send(jid)
        return self.read(jid)

    def store(self, kind):
        if kind=='integration':
            from .integrations.store import IntegrationStore
            return IntegrationStore(self.root.parent/'integrations')
        from .engine import Store
        return Store(self.root.parent)

    def read(self, jid):
        with self.db() as db:
            row=db.execute('SELECT * FROM jobs WHERE id=?',(jid,)).fetchone()
            if row is None:raise FileNotFoundError('任务不存在')
            return dict(row)

    def list(self, active=False):
        with self.db() as db:
            query="SELECT * FROM jobs WHERE state IN ('queued','running') ORDER BY created_at" if active else 'SELECT * FROM jobs ORDER BY created_at DESC,id DESC'
            return [dict(x) for x in db.execute(query)]

    def events(self, jid, after=0, limit=100):
        self.read(jid)
        require(after >= 0 and 1 <= limit <= 500, '事件分页参数无效')
        with self.db() as db:
            rows=[dict(x) for x in db.execute('SELECT * FROM job_events WHERE job_id=? AND id>? ORDER BY id LIMIT ?', (jid,after,limit+1))]
        more=len(rows)>limit;rows=rows[:limit]
        return {'items':rows,'has_more':more,'next_cursor':rows[-1]['id'] if more else None}

    def heartbeat(self, jid):
        with self.db() as db:
            return db.execute("UPDATE jobs SET heartbeat_at=? WHERE id=? AND state='running' AND lease_owner=?",(now(),jid,self.owner)).rowcount == 1

    @contextmanager
    def heartbeats(self, jid):
        stopped=threading.Event()
        def beat():
            while not stopped.wait(2):
                try:
                    if not self.heartbeat(jid): return
                except sqlite3.Error:
                    # The next heartbeat retries; a clock alone never authorizes
                    # stealing the process-wide execution lease.
                    continue
        thread=threading.Thread(target=beat,name='acceptance-heartbeat',daemon=True)
        thread.start()
        try: yield
        finally:
            stopped.set();thread.join(timeout=12)

    def cancelled_jobs(self):
        with self.db() as db:
            return [dict(x) for x in db.execute("SELECT * FROM jobs WHERE state='cancelled'")]

    def for_run(self, rid):
        with self.db() as db:
            row=db.execute('SELECT * FROM jobs WHERE run_id=?',(rid,)).fetchone()
            return dict(row) if row else None

    def cancel(self, jid):
        with self.db() as db:
            db.execute('BEGIN IMMEDIATE')
            row=db.execute('SELECT * FROM jobs WHERE id=?',(jid,)).fetchone()
            if row is None:raise FileNotFoundError('任务不存在')
            require(row['state'] in {'queued','running'}, '任务已经结束')
            # Native recipes lack cooperative mid-check cancellation. Never
            # acknowledge a running cancellation that cannot actually stop it.
            require(row['kind']=='integration' or row['state']=='queued','此配方执行中暂不支持取消；可取消尚未开始的任务')
            if row['state']=='queued':
                db.execute("UPDATE jobs SET state='cancelled',finished_at=?,cancel_requested=1 WHERE id=?",(now(),jid))
            else:
                self.store(row['kind']).cancel(row['run_id'])
                db.execute('UPDATE jobs SET cancel_requested=1 WHERE id=?',(jid,))
            self.event(db,jid,'cancel_requested')
        if row['state']=='queued':self.close_attempt(dict(row),'已在执行前取消',cancelled=True)
        return self.read(jid)

    def close_attempt(self, job, reason, cancelled=False):
        store=self.store(job['kind']);run=store.read(job['run_id'])
        if run['status'] not in {'queued','running'}:return
        run.update(status='cancelled' if cancelled else 'error',decision='inconclusive',finished_at=now())
        key='errors' if job['kind']=='integration' else 'reasons'
        run[key]=list(run.get(key,[]))+[reason]
        for check in run.get('tasks',[])+run.get('check_runs',[]):
            state='state' if 'state' in check else 'status'
            if check.get(state) in {'queued','running'}:check.update({state:'cancelled' if cancelled else 'error','error':reason,'finished_at':now()})
        for phase in run.get('pipeline',[]):
            state='state' if 'state' in phase else 'status'
            if phase.get(state)=='running':phase.update({state:'error','finished_at':now(),'detail':reason})
        store.save(run)

    def execute(self, jid):
        job=self.read(jid)
        if job['state']!='queued':return
        store=self.store(job['kind'])
        # Leases are acquired before claim. A busy legacy execution postpones
        # an unstarted message; it never retries an already-started attempt.
        try:lease=store.lease();lease.__enter__()
        except (ValueError,RuntimeError):
            self.task.schedule((jid,),delay=2)
            return
        try:
            with self.db() as db:
                changed=db.execute("UPDATE jobs SET state='running',started_at=?,heartbeat_at=?,lease_owner=?,attempt_id=?,recovery_error=NULL WHERE id=? AND state='queued'",(now(),now(),self.owner,'attempt-'+uuid.uuid4().hex,jid)).rowcount
                if not changed:return
                self.event(db,jid,'running')
            try:
                current=store.read(job['run_id'])
                if current['status']=='queued':
                    with self.heartbeats(jid): store.execute(job['run_id'])
                elif current['status']=='running':
                    # A run has already started even if its dispatch row was
                    # left queued. Never turn that ambiguity into a retry.
                    raise ValueError('执行记录已开始，需恢复原尝试，不能重新执行')
                result=store.read(job['run_id'])
                state='cancelled' if result['status']=='cancelled' else 'completed' if result['status']=='completed' else 'error'
                error='；'.join(result.get('errors',result.get('reasons',[])))[:1000] if state=='error' else None
            except Exception as exc:
                state,error='error',str(exc)[:1000]
                try:self.close_attempt(job,error)
                except (OSError,ValueError,KeyError,TypeError) as damaged:
                    # Do not leave a forever-running ledger row merely because
                    # its original evidence can no longer be decoded.
                    error += '; 原记录保留：'+str(damaged)[:400]
            with self.db() as db:
                changed=db.execute("UPDATE jobs SET state=?,finished_at=?,heartbeat_at=?,error=? WHERE id=? AND state='running' AND lease_owner=?",(state,now(),now(),error,jid,self.owner)).rowcount
                if changed:self.event(db,jid,state,error or '')
        finally:lease.__exit__(None,None,None)

    def recover(self, *, scan_orphans=True):
        """Reconcile under real execution leases, never by heartbeat expiry alone."""
        summary={'recovered':[],'deferred':[],'redispatched':[]}
        with (self.root/'recovery.lock').open('a') as lock:
            try:fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
            except BlockingIOError:return summary
            for job in self.cancelled_jobs():
                try:self.close_attempt(job,'已在执行前取消',cancelled=True)
                except (OSError,ValueError,KeyError):pass  # A damaged record remains available for audit.
            active=self.list(active=True)
            if not active and not scan_orphans: return summary
            queued=set()
            for job in active:
                if job['state']!='queued':continue
                try:
                    if self.store(job['kind']).read(job['run_id'])['status']=='queued':queued.add(job['run_id'])
                except (OSError,ValueError,KeyError,TypeError):pass
            for kind in ('native','integration'):
                store=self.store(kind)
                lease=store.lease()
                try:lease.__enter__()
                except (ValueError,RuntimeError):
                    summary['deferred'].append(kind)
                    continue
                try:
                    # Orphan cleanup must finish before marking interruption
                    # complete. A Docker outage keeps recovery pending.
                    try:cleanup_errors=store.recover(exclude=queued, candidates=[j['run_id'] for j in active if j['kind']==kind and j['state']=='running'],scan_orphans=scan_orphans) or {}
                    except Exception as exc:
                        summary['deferred'].append(kind)
                        for job in active:
                            if job['kind']==kind and job['state']=='running':self.recovery_error(job,str(exc))
                        continue
                    for job in active:
                        if job['kind']!=kind:continue
                        if job['run_id'] in cleanup_errors:
                            self.recovery_error(job,cleanup_errors[job['run_id']])
                            summary['deferred'].append(job['id'])
                            continue
                        current=self.read(job['id'])
                        if current['state']=='running':
                            try:
                                result=store.snapshot(job['run_id'])
                                state='cancelled' if result['status']=='cancelled' else 'completed' if result['status']=='completed' and result.get('integrity') else 'interrupted'
                                message='' if state in {'completed','cancelled'} else '执行进程中断；原尝试保留，不自动重放'
                                if state=='interrupted':self.close_attempt(job,message)
                            except (OSError,ValueError,KeyError,TypeError) as exc:
                                state,message='interrupted','记录无法核对；原件保留：'+str(exc)[:500]
                            with self.db() as db:
                                changed=db.execute("UPDATE jobs SET state=?,finished_at=?,error=?,recovery_error=NULL WHERE id=? AND state='running'",(state,now(),message,job['id'])).rowcount
                                if changed:self.event(db,job['id'],'recovered_'+state,message)
                            summary['recovered'].append(job['id'])
                        elif current['state']=='queued' and time.monotonic()-self._redispatched.get(job['id'],float('-inf')) >= 30:
                            try:
                                prior=store.read(job['run_id'])
                            except (OSError,ValueError,KeyError,TypeError) as exc:
                                with self.db() as db:
                                    db.execute("UPDATE jobs SET state='interrupted',finished_at=?,error=? WHERE id=? AND state='queued'",(now(),str(exc)[:500],job['id']))
                                    self.event(db,job['id'],'recovered_interrupted','排队记录无法核对；未执行')
                                continue
                            if prior['status']!='queued':
                                with self.db() as db:
                                    db.execute("UPDATE jobs SET state='interrupted',finished_at=?,error=? WHERE id=? AND state='queued'",(now(),'执行记录已开始；不重放原尝试',job['id']))
                                    self.event(db,job['id'],'recovered_interrupted','执行记录已开始；不重放原尝试')
                                summary['recovered'].append(job['id'])
                                continue
                            try:self.send(job['id'])
                            except Exception as exc:
                                self.recovery_error(job,str(exc));continue
                            self._redispatched[job['id']]=time.monotonic()
                            summary['redispatched'].append(job['id'])
                finally:lease.__exit__(None,None,None)
        return summary

    def recovery_error(self, job, detail):
        detail=detail[:1000]
        with self.db() as db:
            previous=db.execute('SELECT recovery_error FROM jobs WHERE id=?',(job['id'],)).fetchone()
            db.execute('UPDATE jobs SET recovery_error=? WHERE id=?',(detail,job['id']))
            if previous and previous[0]!=detail:self.event(db,job['id'],'recovery_deferred',detail)


def main():
    import argparse
    parser=argparse.ArgumentParser()
    parser.add_argument('--root',required=True)
    args=parser.parse_args()
    jobs=Jobs(Path(args.root)/'jobs')
    with (jobs.root/'consumer.lock').open('a') as lock:
        try:fcntl.flock(lock.fileno(),fcntl.LOCK_EX|fcntl.LOCK_NB)
        except BlockingIOError:raise SystemExit('已有任务消费者')
        jobs.recover()
        stopped=threading.Event()
        def reconcile():
            cycles=0
            while not stopped.wait(5):
                cycles += 1
                try:jobs.recover(scan_orphans=cycles % 12 == 0)
                except Exception:
                    import logging
                    logging.exception('任务恢复检查失败；下次继续，未重放运行中的任务')
        recovery=threading.Thread(target=reconcile,name='acceptance-recovery',daemon=True)
        recovery.start()
        try:jobs.huey.create_consumer(workers=1,periodic=False,shutdown_timeout=5).run()
        finally:stopped.set();recovery.join(timeout=15)


if __name__=='__main__':main()
