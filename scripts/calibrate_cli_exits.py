"""Record real CLI output and exit status independently of its text oracle."""
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

label=sys.argv[1]
assert label in {'before','after'}
output=ROOT/'docs/design/d038'/('cli-exit-'+label);output.mkdir(exist_ok=False)
root,files,_=inventory(str(ROOT/'validation/fixtures/universal-cli-exits'));source=manifest(str(root),files)
u=discover(root,files)['units'][0]
specs=[dict(id='zero',title='正常退出与输出',argv=[],expected='ready',comparison='contains'),
       dict(id='nonzero',title='输出匹配但异常退出',argv=['--fail'],expected='ready',comparison='contains'),
       dict(id='negative',title='明确的非零退出契约',argv=['--fail'],expected=2,comparison='exit_code')]
cases=[Case.model_validate(dict(unit=u['id'],kind='cli',**c)).model_dump() for c in specs]
r=dict(id='int-d038-cli-'+label,images=locks(),context=dict(snapshot_digest=sha(encode(source))),_source_path=str(root),_harness_path=str(runtime.HARNESS),_task_timeout=900,
       universal_plan=dict(discovery=dict(units=[u])),universal_generation=dict(requirements=[dict(id='R-cli',source='README',quote=(root/'README.md').read_text(),cases=cases)]))
receipt=dict(kind='platform-calibration-not-product-finding',source_manifest=source,cases_sha256=sha(encode(cases)),stages=[])
try:
    for stage in ('prepare','business'):
        folder=output/stage;folder.mkdir();report,command=getattr(runtime,stage)(r,u,folder,lambda:False)
        receipt['stages'].append(dict(stage=stage,command=command,tests=report['tests']))
finally:
    folder=output/'cleanup';folder.mkdir();report,_=runtime.cleanup(r,folder)
    receipt['stages'].append(dict(stage='cleanup',tests=report['tests']))
    receipt['source_unchanged']=source==manifest(str(root),files)
    (output/'receipt.json').write_bytes(encode(receipt))
print(json.dumps(receipt,ensure_ascii=False))
