"""Read-only final evidence review of the selected immutable acceptance runs."""
from collections import Counter
import json,sys,subprocess
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from acceptance.integrations.store import IntegrationStore
from acceptance.integrations.discovery import inventory,manifest
from acceptance.integrations.storage import file_digest
from acceptance.universal.service import completion

store=IntegrationStore(ROOT/'var/integrations')
folder=ROOT/'docs/design/d038'
for label in ('primary','flask','fastify'):
    rid=json.loads((folder/(label+'-final-run-id.json')).read_text())['id']
    r=store.snapshot(rid)
    if r['status'] in {'queued','running'}:
        print(label,rid,r['status']);continue
    p=r['universal_plan'];root,files,_=inventory(p['repository'])
    frozen=store.path(rid)/'source'
    unchanged=manifest(str(root),files)==p['manifest']
    frozen_ok=all(file_digest(frozen/row['path'])==row['sha256'] for row in p['manifest'])
    tasks=[]
    for task in r['tasks']:
        report=task.get('report') or {}
        tasks.append(dict(id=task['id'],tool=task['tool'],state=task['state'],error=task.get('error'),duration_ms=task.get('duration_ms'),
                          complete=report.get('complete'),counts=dict(Counter(t['status'] for t in report.get('tests',[]))),findings=len(report.get('findings',[])),
                          nonpassing_tests=[t for t in report.get('tests',[]) if t['status']!='passed'],diagnostics=report.get('diagnostics',[])))
    git=lambda *args:subprocess.run(['git','-C',str(root),*args],capture_output=True,text=True,check=True).stdout.strip()
    live=[]
    for kind,args in [('container',['ps','-aq']),('volume',['volume','ls','-q']),('network',['network','ls','-q'])]:
        command=['docker',*args,'--filter','label=acceptance.run='+rid]
        result=subprocess.run(command,capture_output=True,text=True,check=True)
        live.extend(kind+':'+name for name in result.stdout.splitlines())
    out=dict(id=rid,status=r['status'],decision=r['decision'],integrity=r['integrity'],created_at=r['created_at'],finished_at=r['finished_at'],
             implementation_digest=p['implementation_digest'],runtime_identity=p['runtime_identity'],snapshot_digest=p['snapshot_digest'],
             source=dict(commit=git('rev-parse','HEAD'),git_status=git('status','--porcelain'),file_count=len(p['manifest']),repository_unchanged=unchanged,frozen_source_unchanged=frozen_ok),
             task_states=dict(Counter(t['state'] for t in r['tasks'])),tasks=tasks,review=r.get('finding_review',{}).get('summary'),coverage=completion(r),
             models=[dict(index=b['index'],state=b['state'],connection=b.get('connection'),issues=b.get('issues'),reason=b.get('reason')) for b in r['universal_generation']['batches']],
             cleanup_remaining=live,artifacts=dict(count=len(r['artifacts']),largest=max(r['artifacts'],key=lambda a:a['size'])))
    (folder/(label+'-final-summary.json')).write_text(json.dumps(out,ensure_ascii=False,indent=2))
    print(json.dumps({k:out[k] for k in ('id','status','decision','integrity','source','task_states','review','cleanup_remaining')},ensure_ascii=False))
