"""Real provider budget calibration; synthetic fixture, not repository acceptance."""
import json,os,sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
os.environ.setdefault('ACCEPTANCE_PLANNER_CONFIG_FILE',str(ROOT/'var/planner-connection.json'))
from acceptance.integrations.store import IntegrationStore
from acceptance.planning.models import DraftInput
from acceptance.planning import provider
from acceptance.planning.model_budget import verify
folder=ROOT/'docs/design/d040/model-budget-calibration';repository=folder/'repository';repository.mkdir(parents=True)
(repository/'api.py').write_text('def twice(value):\n    return value*2\n')
text='对整数输入2调用twice函数，正确返回整数4。'
(repository/'README.md').write_text(text)
data=DraftInput(repository=str(repository),scope='仅校准真实模型预算与原件绑定，不作为三仓验收',documents=[dict(id='D1',title='独立数值契约',content=text)],universal_target=dict(units=[dict(id='unit',runtime='python',path='.',capabilities=['module'])],interfaces=[dict(unit='unit',path='api.py',functions=[dict(name='twice')])],execution_contract={'version':16}))
s=IntegrationStore();draft=provider.draft(s,data);cid=draft['connection']['client_request_id'];wrapper=json.loads((s.root/'model-inputs'/(cid+'.json')).read_bytes());receipt=json.loads((s.root/'model-calls'/(cid+'.json')).read_bytes());verify(wrapper,receipt)
result=dict(scope='synthetic calibration; not target project acceptance',client_request_id=cid,draft=draft['id'],connection=draft['connection'],budget={k:v for k,v in wrapper['generation_budget'].items() if k!='raw_response'},request_parameters=wrapper['request_parameters'],usage=draft.get('usage'),issues=draft['issues'])
(folder/'receipt.json').write_text(json.dumps(result,ensure_ascii=False,indent=2));print(json.dumps(dict(request=cid,max_tokens=result['request_parameters']['max_tokens'],actual_model=draft['connection']['actual_model'],finish_reason=draft['connection']['finish_reason']),ensure_ascii=False))
for directory in ['model-inputs','model-responses','model-calls']:(folder/(directory+'.json')).write_bytes((s.root/directory/(cid+'.json')).read_bytes())
(folder/'draft.json').write_bytes((s.root/'drafts'/(draft['id']+'.json')).read_bytes())
