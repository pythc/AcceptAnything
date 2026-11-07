"""Generate a real Chinese API/browser proposal against an independent contract."""
from pathlib import Path
import json,os,sys,uuid
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from acceptance.engine import ROOT
from acceptance.integrations.store import IntegrationStore
from acceptance.planning.models import DraftInput
from acceptance.planning.provider import draft
from verify_d025 import APP
os.environ.setdefault('ACCEPTANCE_PLANNER_CONFIG_FILE',str(ROOT/'var/planner-connection.json'))
repo=ROOT/'var/d025-controls'/('model-'+uuid.uuid4().hex[:8]);repo.mkdir(parents=True)
(repo/'app.py').write_text('BROKEN=False\n'+APP)
contract='''# 项目创建验收契约
本范围仅验证独立隔离的合成服务，测试不使用外部邮箱和真实账号。
服务使用 HTTP，GET /health 返回200及 {"ready":true}。
匿名 POST /items（JSON {"name":"任意测试名称"}）必须返回403及 {"error":"forbidden"}。
POST /login 不需要凭据，本合成服务为调用方建立编辑者会话，返回200及 {"role":"editor"}，Set-Cookie 保存 session；这里只验证会话传递，不声称验证密码认证。
携带此 Cookie 的编辑者 POST /items，JSON请求体的name为名称，返回201及 {"id":"生成的项目编号","name":"请求的名称"}。
GET /items/{id} 是详情页面，#name元素显示创建时的名称。重复打开该页面后仍显示同一名称。
每个流程使用唯一名称以隔离数据。页面与接口联合步骤共享同一浏览器上下文，会自动保留 Cookie；接口返回的id可以capture后用于页面地址。
'''
(repo/'验收契约.md').write_text(contract)
data=DraftInput.model_validate(dict(repository=str(repo),documents=[dict(id='CONTRACT',title='项目创建独立契约',origin='验收契约.md',content=contract)],
 scope='设计两类中文验收场景：匿名创建拒绝（API）；编辑者会话登录、接口创建、捕获编号、页面展示、重新打开后的名称读回（同一 browser 场景含 http 与页面断言）。仅按文档规定行为；不猜其他路由，不生成性能或恢复场景。',
 environment=dict(mode='service',runtime='python',entrypoint='app.py')))
result=draft(IntegrationStore(),data)
result.update(repository=str(repo),documents=[d.model_dump() for d in data.documents])
(ROOT/'docs/design/d025/model-proposal.json').write_text(json.dumps(result,ensure_ascii=False,indent=2))
print(json.dumps({k:result[k] for k in ('id','model','connection')},ensure_ascii=False))
