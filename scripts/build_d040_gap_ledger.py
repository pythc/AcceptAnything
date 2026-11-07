"""Read-only per-gap ledger; model opinions remain attributed, never silently closed."""
import argparse,json,sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
from acceptance.integrations.store import IntegrationStore
from acceptance.universal.service import completion
p=argparse.ArgumentParser();p.add_argument('--batch',required=True);p.add_argument('--output',required=True);a=p.parse_args();s=IntegrationStore();ledger=[]
for file in sorted((ROOT/'docs/design/d039').glob('*-'+a.batch+'-run.json')):
 rid=json.loads(file.read_bytes())['id'];run=s.snapshot(rid)
 if run['status']!='completed' or not run['integrity']:raise ValueError('Ledger requires terminal verified evidence: '+rid)
 plan=run['universal_plan'];docs={d['id']:d for batch in plan['batches'] for d in batch};tasks={t['id']:t for t in run['tasks']};by_case={c['id']:(q,c) for q in run['universal_generation']['requirements'] for c in q['cases']}
 for gap in completion(run)['gaps']:
  row=dict(number=len(ledger)+1,repository=file.name.removesuffix('-'+a.batch+'-run.json'),run=rid,decision=run['decision'],classification=gap['category_label'],classification_source=gap.get('classification_source'),reason=gap['reason'],source=gap.get('source'),case=gap.get('case'),requirement=gap.get('requirement'),evidence=[],review_status='coverage gap; not a confirmed product defect')
  source=gap.get('source');doc=docs.get(source)
  if doc:
   row['document']=dict(title=doc['title'],origin=doc['origin'])
   for index,batch in enumerate(plan['batches']):
    if any(d['id']==source for d in batch):
     generated=next((b for b in run['universal_generation']['batches'] if b['index']==index),{})
     for key in ['input_ref','response_ref','draft_ref','receipt_ref']:
      if generated.get(key):row['evidence'].append(dict(role=key,artifact=generated[key]))
  if source in tasks:
   task=tasks[source]
   if task.get('report_ref'):row['evidence'].append(dict(role='task-report',artifact=task['report_ref']))
   for artifact in run['artifacts']:
    if artifact['name'] in {source+'/cases.json',source+'/environment-selection.json'}:row['evidence'].append(dict(role=artifact['name'],artifact=artifact['id']))
  if gap.get('case') in by_case:
   requirement,case=by_case[gap['case']];row['requirement']=requirement['id'];row['quoted_basis']=requirement['quote'];row['case_title']=case['title']
  for evidence in row['evidence']:evidence['url']='http://127.0.0.1:18890/api/runs/'+rid+'/artifacts/'+evidence['artifact']
  ledger.append(row)
output=Path(a.output)
with output.open('x') as f:json.dump(ledger,f,ensure_ascii=False,indent=2)
lines=['# D040 逐项覆盖缺口账本','','仅整理已终态、完整性验证通过的记录。模型分类仍标明来源；执行错误、缺少依据和未覆盖均不能视为确认产品缺陷。未自动删除语义相近的模型意见，原始条目数不等于不重复需求数或覆盖率。','']
for row in ledger:
 lines+=['## G'+str(row['number']).zfill(3)+' · '+row['repository']+' · '+row['classification'],'',row['reason'],'','- 分类来源：'+str(row['classification_source']),'- 定位：'+str(row.get('case') or row.get('requirement') or row.get('source'))]
 if row.get('document'):lines+=['- 依据文档：'+row['document']['title']+' · '+row['document']['origin']]
 lines+=['- [执行记录](http://127.0.0.1:18890/?run='+row['run']+'&tab=flow&evidence=run)']
 for evidence in row['evidence']:lines+=['- ['+evidence['role']+']('+evidence['url']+')']
 lines+=['']
with output.with_suffix('.md').open('x') as f:f.write('\n'.join(lines))
print('Ledger entries:',len(ledger))
