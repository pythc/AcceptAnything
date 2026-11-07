"""Read-only evidence ledger, including native skips and individual business results."""
import argparse,json,sys
from pathlib import Path
from collections import Counter
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
from acceptance.integrations.store import IntegrationStore
from acceptance.universal.service import completion
p=argparse.ArgumentParser();p.add_argument('--batch',required=True);p.add_argument('--output',required=True);a=p.parse_args();s=IntegrationStore();rows=[]
for file in sorted((ROOT/'docs/design/d039').glob('*-'+a.batch+'-run.json')):
 rid=json.loads(file.read_text())['id'];r=s.snapshot(rid)
 if r['status']!='completed' or not r['integrity']:raise ValueError('not completed or evidence invalid: '+rid)
 native=[];business=[];tasks=[]
 for t in r['tasks']:
  report=t.get('report') or {};tests=report.get('tests',[])
  tasks.append(dict(id=t['id'],tool=t['tool'],target=t['target'],state=t['state'],error=t.get('error'),counts=dict(Counter(x['status'] for x in tests))))
  if t['tool']=='universal-native':native.append(dict(task=t['id'],target=t['target'],counts=dict(Counter(x['status'] for x in tests)),unexecuted=[x for x in tests if x['status'] in {'error','skipped'}]))
  if t['tool']=='universal-business' and (s.path(rid)/'outputs'/t['id']/'cases.json').is_file():business+=json.loads((s.path(rid)/'outputs'/t['id']/'cases.json').read_bytes())
 rows.append(dict(repository=file.name.removesuffix('-'+a.batch+'-run.json'),id=rid,decision=r['decision'],integrity=r['integrity'],engine=r['universal_plan']['implementation_digest'],source=r['context'],native=native,business=business,tasks=tasks,coverage=completion(r),requirements=r['universal_generation']['requirements'],model_batches=r['universal_generation']['batches'],findings=r['finding_review']['summary'],retrieval=r['universal_plan'].get('document_retrieval')))
with Path(a.output).open('x') as f:json.dump(rows,f,ensure_ascii=False,indent=2)
for row in rows:print(row['repository'],row['id'],row['decision'],'business',dict(Counter(x['status'] for x in row['business'])),'gaps',len(row['coverage']['gaps']))
