"""Generate independent small decision tables; reviewed flow bindings contain no branch answers."""
from pathlib import Path
import json,sys,os
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from acceptance.engine import ROOT
from acceptance.planning.models import DraftInput
from acceptance.planning import provider,calls
from acceptance.integrations.store import IntegrationStore
os.environ['ACCEPTANCE_PLANNER_CONFIG_FILE']=str(ROOT/'var/planner-connection-gmah.json')
store=IntegrationStore();calls.reconcile(store)
repo=ROOT/'var/integrations/gmah-pr-gate'
quote='- 审批：查看 pending approval，并批准或拒绝。'
# Exact product documentation is the oracle; interface enum merely defines result shape.
content='\n'.join([quote,'高风险工具必须带审批策略、幂等键和审计元数据。','正式成绩发布必须人工审批。'])
# All three quoted sentences are excerpts, not expectations derived from implementation.
original=(repo/'README.md').read_text();grading=(repo/'docs/grading-integration.md').read_text()
doc=dict(id='README',title='GMAH 公开审批功能',origin='README.md#审批',content=quote)
start=dict(kind='http',method='POST',path='/sessions/run',body=dict(user_id='${run_id}',message='${feedback}',tool_call=dict(tool_name='publish_grade',arguments=dict(submission_id='submission-1',rubric_version='v1',score='${score}',feedback_markdown='${feedback}'))),status=200,assertions=[dict(pointer='/approval_required',value=True),dict(pointer='/tool_result',value=None)],capture=dict(thread='/thread_id',approval='/pending_approval/approval_id'))
for engine in ['api','browser']:
 arg='approved' if engine=='api' else 'action'
 props=dict(score=dict(type='number',minimum=0,maximum=100),feedback=dict(type='string',minLength=1,maxLength=100))
 props[arg]=dict(type='boolean') if engine=='api' else dict(type='string',enum=['批准','拒绝'])
 if engine=='api':middle=[dict(kind='http',method='POST',path='/approvals/${approval}/decide',body=dict(approved_by='验收复核员',approved='${approved}',reason='验收验证'),status=200,assertions=[dict(pointer='/state/approval_status',value='${expected}')])]
 else:middle=[dict(kind='goto',value='/'),dict(kind='click',selector='li[role="menuitem"]:has-text("审批")'),dict(kind='expect_visible',selector='tr:has-text("${approval}")'),dict(kind='click',selector='tr:has-text("${approval}") >> xpath=.//button[translate(normalize-space(.), " ", "")="${action}"]'),dict(kind='expect_visible',selector='[role="alert"]:has-text("已${action}")')]
 steps=[start,*middle,dict(kind='http',method='GET',path='/sessions/${thread}',status=200,assertions=[dict(pointer='/approval_status',value='${expected}')])]
 target=dict(id='APPROVAL-'+engine.upper(),title='人工审批'+('接口' if engine=='api' else '浏览器')+'流程',source='README',quote=quote,engine=engine,steps=steps,
   input_schema=dict(type='object',additionalProperties=False,required=list(props),properties=props),result_schema=dict(type='string',enum=['approved','rejected']),
   precondition='本地人工审批：模型设计恰好4行；必须覆盖批准和拒绝，以及分数0和100边界。score是0至100的合法分数；feedback中文非空。'+('approved是审批人作出的布尔决策。' if engine=='api' else 'action为审批人点击的中文按钮。')+'expected是会话最终审批状态，接口类型枚举approved/rejected。正确分支对应关系由产品原文决定。所有流程是先发起审批、人工决策、读回会话，步骤形状已审核。')
 data=DraftInput(repository=str(repo),scope=target['title'],documents=[doc],environment=dict(mode='service',runtime='python',entrypoint='src/agent_workflow/api/app.py',ready_path='/healthz',recipe='gmah-v1'),service_table_target=target)
 (ROOT/f'docs/design/d026/table-{engine}-input.json').write_text(data.model_dump_json(indent=2))
 result=provider.draft(store,data)
 (ROOT/f'docs/design/d026/table-{engine}-proposal.json').write_text(json.dumps(result,ensure_ascii=False,indent=2))
 print(json.dumps(dict(engine=engine,id=result['id'],connection=result['connection']),ensure_ascii=False),flush=True)
