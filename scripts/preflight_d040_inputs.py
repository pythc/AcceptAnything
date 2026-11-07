"""Measure actual universal prompt shapes without creating model requests."""
import json,sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
from acceptance.integrations.store import IntegrationStore
from acceptance.integrations.runner import encode
from acceptance.universal.discovery import discover,batches,relevant
from acceptance.universal.documents import enrich
from acceptance.universal.models import output_schema
from acceptance.universal.service import planning_units,EXECUTION_CONTRACT,implementation
s=IntegrationStore();rows=[]
for label,rid in [('flask','int-cc4290eb3ed94f4d'),('fastify','int-b5e17ff98d8445c4'),('sqlite-utils','int-d8e4048aab7a4b92')]:
 r=s.read(rid);root=s.path(rid)/'source';d=discover(root,[x['path'] for x in r['context']['files']]);groups,retrieval=enrich(root,list(batches(root,d['documents'])),d['document_catalog'],d['units']);sizes=[]
 for i,docs in enumerate(groups):
  interfaces,selection=relevant(d['interfaces'],docs)
  target=dict(context_version=2,units=planning_units(d['units']),interfaces=interfaces,selection=selection,execution_contract=EXECUTION_CONTRACT,types=d['types'],document_scope=retrieval['batches'][i])
  prompt=dict(documents=docs,scope=r['universal_plan']['scope'],discovery=target,output_schema=output_schema([x['id'] for x in docs]));sizes.append(len(encode(prompt)))
 assert all(n<=600000 for n in sizes)
 row=dict(name=label,batches=len(groups),request_bytes=sizes,retrieval_budget=retrieval.get('budget'));rows.append(row);print(label,len(groups),max(sizes))
Path('docs/design/d040/r3-input-budget-verification.json').write_text(json.dumps(dict(engine=implementation(),rows=rows),indent=2))
