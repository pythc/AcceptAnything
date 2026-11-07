"""Same frozen oracle before/after preparing standard registered resources."""
import json,sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from acceptance.universal import runtime
from acceptance.universal.discovery import discover
from acceptance.universal.models import Case
from acceptance.integrations.discovery import inventory,manifest
from acceptance.integrations.registry import locks
from acceptance.integrations.runner import encode,sha

output=ROOT/'docs/design/d038/tokenizer-resource-calibration';output.mkdir(exist_ok=False)
root,files,_=inventory(str(ROOT/'validation/fixtures/universal-tokenizer-resources'));before=manifest(str(root),files)
u=discover(root,files)['units'][0]
case=Case.model_validate(dict(id='encodings',title='注册编码在断网环境可用',unit=u['id'],kind='module',module='tokenizer_probe.py',function='registered_encodings_ready',expected=True)).model_dump()
r=dict(id='int-d038-tokenizer-resources',images=locks(),context=dict(snapshot_digest=sha(encode(before))),_source_path=str(root),_harness_path=str(runtime.HARNESS),_task_timeout=900,
       universal_plan=dict(discovery=dict(units=[u])),universal_generation=dict(requirements=[dict(id='R-vocabulary',source='README',quote=(root/'README.md').read_text(),cases=[case])]))
receipt=dict(kind='platform-calibration-not-product-finding',source_manifest=before,cases_sha256=sha(encode([case])),stages=[])
try:
    target=output/'prepare';target.mkdir();report,cmd=runtime.prepare(r,u,target,lambda:False);receipt['stages'].append(dict(stage='prepare',command=cmd,tests=report['tests']))
    target=output/'before';target.mkdir();report,cmd=runtime.business(r,u,target,lambda:False);receipt['stages'].append(dict(stage='before',command=cmd,tests=report['tests']))
    name,_=runtime.names(r,u)
    runtime.docker('cp',str(ROOT/'scripts/python_tokenizer_resources.py'),name+':/work/prewarm.py')
    runtime.docker('network','connect','bridge',name)
    try:
        target=output/'resources';target.mkdir();cmd,_=runtime.command(r,u,['/work/venv/bin/python','-P','/work/prewarm.py'],target,lambda:False,timeout=900,offline=False)
        receipt['stages'].append(dict(stage='resource-preparation',command=cmd))
    finally:runtime.docker('network','disconnect','bridge',name)
    target=output/'after';target.mkdir();report,cmd=runtime.business(r,u,target,lambda:False);receipt['stages'].append(dict(stage='after',command=cmd,tests=report['tests']))
finally:
    target=output/'cleanup';target.mkdir();report,_=runtime.cleanup(r,target);receipt['stages'].append(dict(stage='cleanup',tests=report['tests']))
    receipt['source_unchanged']=before==manifest(str(root),files)
    (output/'receipt.json').write_bytes(encode(receipt))
print(json.dumps(receipt,ensure_ascii=False))
