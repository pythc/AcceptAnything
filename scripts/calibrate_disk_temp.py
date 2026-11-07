"""Verify tempfile uses a disk-backed work volume without project patches."""
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

output=ROOT/'docs/design/d038/disk-temp-calibration';output.mkdir(exist_ok=False)
root,files,_=inventory(str(ROOT/'validation/fixtures/universal-disk-temp'));before=manifest(str(root),files)
u=discover(root,files)['units'][0]
case=Case.model_validate(dict(id='disk-temp',title='标准临时文件写入磁盘卷',unit=u['id'],kind='module',module='temp_probe.py',function='temporary_location',expected=dict(directory='/work/tmp',bytes=35*1024*1024+4,tail='tail',same_work_device=True,different_tmp_device=True))).model_dump()
r=dict(id='int-d038-disk-temp',images=locks(),context=dict(snapshot_digest=sha(encode(before))),_source_path=str(root),_harness_path=str(runtime.HARNESS),_task_timeout=900,
       universal_plan=dict(discovery=dict(units=[u])),universal_generation=dict(requirements=[dict(id='R-temp',source='README',quote=(root/'README.md').read_text(),cases=[case])]))
receipt=dict(kind='platform-calibration-not-product-finding',source_manifest=before,cases_sha256=sha(encode([case])),stages=[])
try:
    for stage in ('prepare','business'):
        target=output/stage;target.mkdir();report,cmd=getattr(runtime,stage)(r,u,target,lambda:False)
        receipt['stages'].append(dict(stage=stage,command=cmd,tests=report['tests']))
finally:
    target=output/'cleanup';target.mkdir();report,_=runtime.cleanup(r,target)
    receipt['stages'].append(dict(stage='cleanup',tests=report['tests']))
    receipt['source_unchanged']=before==manifest(str(root),files)
    (output/'receipt.json').write_bytes(encode(receipt))
print(json.dumps(receipt,ensure_ascii=False))
