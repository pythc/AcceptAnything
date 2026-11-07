"""Summarize stored real runs without changing records or test outcomes."""
import argparse,json,sys
from collections import Counter
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
from acceptance.integrations.store import IntegrationStore
p=argparse.ArgumentParser();p.add_argument('--batch',required=True);p.add_argument('--verify',action='store_true');p.add_argument('--output');a=p.parse_args()
s=IntegrationStore();rows=[]
for file in sorted((ROOT/'docs/design/d039').glob('*-'+a.batch+'-run.json')):
 rid=json.loads(file.read_text())['id'];r=s.snapshot(rid) if a.verify else s.read(rid)
 tasks=[]
 for t in r['tasks']:
  report=t.get('report') or {}
  tasks.append(dict(id=t['id'],tool=t['tool'],state=t['state'],duration_ms=t.get('duration_ms'),metrics=report.get('metrics',{}),error=t.get('error'),
     tests=[{k:v for k,v in x.items() if k in ('name','status','detail')} for x in report.get('tests',[]) if t['tool']=='universal-business' or x.get('status') in ('failed','error')]))
 g=r.get('universal_generation',{})
 rows.append(dict(repository=file.name.removesuffix('-'+a.batch+'-run.json'),id=rid,status=r['status'],decision=r['decision'],integrity=r.get('integrity') if a.verify else 'not-reverified',
   snapshot_digest=(r.get('context') or {}).get('snapshot_digest'),implementation_digest=r.get('universal_plan',{}).get('implementation_digest'),
   model_batches=[{k:v for k,v in b.items() if k in ('index','status','error','connection','format_retries')} for b in g.get('batches',[])],
   requirements=len(g.get('requirements',[])),cases=sum(len(x['cases']) for x in g.get('requirements',[])),issues=g.get('issues',[]),tasks=tasks))
if a.output:
 with Path(a.output).open('x') as f:json.dump(rows,f,ensure_ascii=False,indent=2)
for r in rows:
 print(r['repository'],r['id'],r['status'],r['decision'],'cases',r['cases'],'issues',len(r['issues']))
 for t in r['tasks']:
  if t['state']!='queued':print(' ',t['id'],t['state'],{k:v for k,v in t['metrics'].items() if k.startswith('tests.') and k not in ('tests.duration_ms','tests.success_rate')},t['error'] or '')
