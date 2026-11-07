"""One bounded real GPT-6 High proposal for GMAH; no implicit retries."""
from pathlib import Path
import json,os,sys
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from acceptance.engine import ROOT
from acceptance.integrations.store import IntegrationStore
from acceptance.planning.models import DraftInput
from acceptance.planning import provider,calls
store=IntegrationStore()
os.environ['ACCEPTANCE_PLANNER_CONFIG_FILE']=str(ROOT/'var/planner-connection.json')
calls.reconcile(store)
os.environ['ACCEPTANCE_PLANNER_CONFIG_FILE']=str(ROOT/'var/planner-connection-gmah.json')
repo=ROOT/'var/integrations/gmah-pr-gate'
# HTTP shapes and DOM addresses are bindings, not expected business answers.
binding='''已审核环境和接口定位（仅调用形状，不是业务正确性的依据）：
无认证的隔离本地开发环境，自带批改 mock adapter，不发送任何外部消息。Web 与 API 同源。
POST /sessions body {user_id:string} 成功类型201 SessionState；GET /sessions/{thread_id} 成功200 SessionState。
POST /sessions/run body {thread_id?:string,user_id?:string,message:string,tool_call?:{tool_name:string,arguments:object}} 成功200 RunSessionResult。
SessionState字段 thread_id,user_id,messages数组[{role,content}],tool_results数组[{tool_name,status,output}],approval_status,pending_approvals。
RunSessionResult字段 thread_id,state,tool_result(可能null),approval_required(bool),pending_approval(可能null,字段approval_id),idempotent_replay(bool)。
POST /approvals/{approval_id}/decide body {approved_by:string,approved:bool,reason:string} 成功200 {approval:{status:字符串},state:SessionState,tool_result,idempotent_replay}。
工具类型见 TOOL 文档，其中 submission_id 使用 submission-1，rubric_version使用 v1（仓库公开示例数据），草稿draft_revision使用 ${run_id} 隔离。分数设80，反馈为中文非空字符串。
浏览器审批页路由是 /approvals，页面标题“人工审批”，每行包含approval_id；按钮文本“批准”和“拒绝”。注意 /approvals/pending 是 API JSON，/approvals 是页面。定位特定行可使用 tr:has-text("${approvalId}") button:has-text("批准")。
只用 API 或 browser 引擎。浏览器场景先http创建待审批，再goto页面、expect_visible定位对应行、click批准，最后http读取该会话状态并断言。所有断言预期须依据下面文档，不从字段形状猜答案。'''
docs=[dict(id='README',title='GMAH 公开产品说明',origin='README.md',content=(repo/'README.md').read_text()),dict(id='GRADING',title='批改系统适配规范',origin='docs/grading-integration.md',content=(repo/'docs/grading-integration.md').read_text()),dict(id='TOOL',title='工具声明',origin='configs/tools.example.json',content=(repo/'configs/tools.example.json').read_text())]
data=DraftInput(repository=str(repo),documents=docs,environment=dict(mode='service',runtime='python',entrypoint='src/agent_workflow/api/app.py',port=19300,ready_path='/healthz',recipe='gmah-v1'),scope='设计 GMAH 中文 MVP 业务验收，恰好3个场景：API普通会话消息写入读回；API保存同一反馈草稿两次验证幂等；browser高风险成绩发布经人工批准后读回状态。只覆盖文档有依据的这些范围，最多3项标准，每场景最多8步，不展开examples/matrix/boundary；不要设计性能和恢复步骤（另有受控配方）。'+binding)
path=ROOT/'docs/design/d026/model-input.json';path.write_text(data.model_dump_json(indent=2))
r=provider.draft(store,data)
(ROOT/'docs/design/d026/model-proposal.json').write_text(json.dumps(r,ensure_ascii=False,indent=2))
print(json.dumps(dict(id=r['id'],connection=r['connection']),ensure_ascii=False),flush=True)
