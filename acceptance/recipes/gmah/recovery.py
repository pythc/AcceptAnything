"""Trusted fault driver: restart actual services, verify actual durable business state."""
import json,os,subprocess,time,uuid
from pathlib import Path
import httpx


def test_session_approval_idempotency_and_audit_survive_restart():
    env=json.loads(Path(os.environ['GMAH_ENVIRONMENT']).read_text());base=env['base']
    evidence=[]
    def request(method,path,body=None,status=200):
        r=httpx.request(method,base+path,json=body,timeout=10,trust_env=False)
        evidence.append(dict(method=method,path=path,status=r.status_code,body=r.json()))
        assert r.status_code==status
        return r.json()
    def sql(query):
        return subprocess.check_output(['docker','exec',env['postgres'],'psql','-U','postgres','-d','gmah','-Atc',query],text=True).strip()
    try:
        uid='恢复验收-'+uuid.uuid4().hex
        s=request('POST','/sessions',{'user_id':uid},201);tid=s['thread_id']
        draft=dict(thread_id=tid,message='恢复前保存草稿',tool_call=dict(tool_name='save_feedback_draft',arguments=dict(submission_id='submission-1',draft_revision=uid,feedback_markdown='恢复验收反馈')))
        first=request('POST','/sessions/run',draft);assert first['tool_result']['status']=='accepted' and not first['idempotent_replay']
        p=request('POST','/sessions/run',dict(thread_id=tid,message='请求发布',tool_call=dict(tool_name='publish_grade',arguments=dict(submission_id='submission-1',rubric_version='v1',score=80,feedback_markdown='恢复验收反馈'))))
        assert p['approval_required'] and p['tool_result'] is None
        aid=p['pending_approval']['approval_id'];before=request('GET','/sessions/'+tid)
        before_audit=sql('SELECT payload::text FROM audit_events ORDER BY id');assert before_audit
        # Stop application before stores. Restart same containers with durable volumes.
        subprocess.run(['docker','stop','-t','3',env['api']],check=True,capture_output=True)
        subprocess.run(['docker','restart',env['redis'],env['postgres']],check=True,capture_output=True)
        for _ in range(100):
            pg=subprocess.run(['docker','exec',env['postgres'],'pg_isready','-U','postgres'],capture_output=True)
            redis=subprocess.run(['docker','exec',env['redis'],'redis-cli','ping'],capture_output=True)
            if pg.returncode==0 and redis.stdout.strip()==b'PONG':break
            time.sleep(.2)
        else:raise AssertionError('持久化服务重启后未就绪')
        subprocess.run(['docker','start',env['api']],check=True,capture_output=True)
        for _ in range(100):
            try:
                if httpx.get(base+'/healthz',timeout=1,trust_env=False).status_code==200:break
            except httpx.HTTPError:pass
            time.sleep(.2)
        else:raise AssertionError('服务重启后未恢复健康')
        after=request('GET','/sessions/'+tid)
        for key in ('thread_id','user_id','messages','tool_results','pending_approvals','approval_status'):assert after[key]==before[key],key
        assert sql('SELECT payload::text FROM audit_events ORDER BY id')==before_audit
        replay=request('POST','/sessions/run',draft);assert replay['idempotent_replay'] and replay['tool_result']['status']=='accepted'
        approved=request('POST','/approvals/'+aid+'/decide',dict(approved_by='恢复验收员',approved=True,reason='恢复后复核'))
        assert approved['tool_result']['status']=='accepted' and approved['state']['approval_status']=='approved'
        assert sql('SELECT count(*) FROM audit_events')!=str(len(before_audit.splitlines()))
    finally:Path(os.environ['GMAH_ENVIRONMENT']).with_name('recovery-steps.json').write_text(json.dumps(evidence,ensure_ascii=False,indent=2))
