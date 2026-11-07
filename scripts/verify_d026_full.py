"""Freeze reviewed model batches and dispatch the actual GMAH acceptance via Huey."""
from pathlib import Path
import json,sys
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from acceptance.engine import ROOT
from acceptance.integrations.store import IntegrationStore
from acceptance.project_config import prepare,public
from acceptance.planning.service import create_run
from acceptance.jobs import Jobs
repo=ROOT/'var/integrations/gmah-pr-gate';out=ROOT/'docs/design/d026'
a=json.loads((out/'table-api-proposal.json').read_text());b=json.loads((out/'table-browser-bound-proposal.json').read_text())
spec=dict(title='GMAH 本地 MVP 业务验收',scope='GMAH 本地 MVP：模型设计审批接口和页面用例，生产构建、仓库回归、代码及依赖扫描，会话负载和 Redis/PostgreSQL 重启恢复；外部模型、QQ、远程 MCP 与真实批改系统不在本次范围。',
 environment=a['specification']['environment'],requirements=a['specification']['requirements']+b['specification']['requirements'])
config=dict(schema_version=1,documents=[dict(id='README',path='README.md',title='GMAH 公开审批功能',anchor='#审批',excerpt='- 审批：查看 pending approval，并批准或拒绝。')],
 specification=spec,draft_ids=[a['id'],b['id']],include_scanners=True)
p=ROOT/'projects/gmah-local-mvp.json';p.write_text(json.dumps(config,ensure_ascii=False,indent=2))
store=IntegrationStore();plan=prepare(store,str(repo),str(p))
(out/'confirmed-plan.json').write_text(json.dumps(public(plan),ensure_ascii=False,indent=2))
run=create_run(store,plan['id'],plan['digest'])
job=Jobs(ROOT/'var/jobs').enqueue('integration',run['id'])
result=dict(id=run['id'],job_id=job['id'],plan_id=plan['id'],snapshot_digest=plan['snapshot_digest'],case_count=len(plan['cases']),tasks=len(run['tasks']))
(out/'full-run.json').write_text(json.dumps(result,ensure_ascii=False,indent=2));print(json.dumps(result),flush=True)
# Register only this exact repository path. New entry runs the reviewed model cases
# again, and explicitly labels reuse; it does not pretend to regenerate them.
mapping=ROOT/'var/project-configurations.json';existing=json.loads(mapping.read_text()) if mapping.exists() else {};existing[str(repo)]=str(p);mapping.write_text(json.dumps(existing,ensure_ascii=False,indent=2))
