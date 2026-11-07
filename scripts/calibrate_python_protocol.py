"""Real disposable-runtime calibration; never a product acceptance record."""
import sys,json
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from acceptance.universal import runtime
from acceptance.universal.discovery import discover
from acceptance.universal.models import Case
from acceptance.integrations.discovery import inventory,manifest
from acceptance.integrations.registry import locks
from acceptance.integrations.runner import encode,sha

source=ROOT/'validation/fixtures/universal-python-protocol'
output=ROOT/'docs/design/d038/python-protocol-calibration'
output.mkdir(parents=True,exist_ok=False)
root,files,_=inventory(str(source));before=manifest(str(root),files)
u=discover(root,files)['units'][0]
specs=[dict(id='dataclass',title='标准结构返回',kind='module',module='app.py',function='request_summary',args=[3],expected={'method':'GET','value':6}),
       dict(id='pydantic',title='模型JSON和字段选择',kind='module',module='app.py',function='model_summary',args=[3],pointer='/value',expected=6),
       dict(id='http-large',title='大响应完整字段',kind='http',path='/large',pointer='/tail',expected='完整末尾'),
       dict(id='browser',title='真实页面标题',kind='browser',path='/',selector='h1',expected='验收校准')]
cases=[Case.model_validate(dict(unit=u['id'],**c)).model_dump() for c in specs]
r=dict(id='int-d038-python-protocol',images=locks(),context=dict(snapshot_digest=sha(encode(before))),_source_path=str(root),_harness_path=str(runtime.HARNESS),_task_timeout=900,
       universal_plan=dict(discovery=dict(units=[u])),universal_generation=dict(requirements=[dict(id='R-protocol',source='README',quote=(root/'README.md').read_text(),cases=cases)]))
receipt=dict(kind='platform-calibration-not-product-finding',source_manifest=before,cases_sha256=sha(encode(cases)),stages=[])
try:
    for stage in ('prepare','build','service','business'):
        target=output/stage;target.mkdir()
        report,cmd=getattr(runtime,stage)(r,u,target,lambda:False)
        receipt['stages'].append(dict(stage=stage,command=cmd,tests=report['tests']))
finally:
    target=output/'cleanup';target.mkdir()
    report,_=runtime.cleanup(r,target)
    receipt['stages'].append(dict(stage='cleanup',tests=report['tests']))
    receipt['source_unchanged']=before==manifest(str(root),files)
    (output/'receipt.json').write_bytes(encode(receipt))
print(json.dumps(receipt,ensure_ascii=False))
