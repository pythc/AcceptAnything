"""Diagnose declarative browser inputs against a frozen run; not a full acceptance."""
import argparse,copy,json,sys,uuid
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
from acceptance.integrations.store import IntegrationStore
from acceptance.integrations.runner import encode,sha
from acceptance.integrations.registry import locks
from acceptance.universal import runtime,orchestration
from acceptance.universal.models import Case
from acceptance.universal.service import EXECUTION_CONTRACT

p=argparse.ArgumentParser(description=__doc__);p.add_argument('--run',required=True);p.add_argument('--unit',required=True);p.add_argument('--fixtures',type=Path,required=True);p.add_argument('--output',type=Path,required=True);a=p.parse_args()
s=IntegrationStore();old=s.snapshot(a.run)
if old['status']!='completed' or not old['integrity']:raise ValueError('Frozen run is not terminal and verified')
run=copy.deepcopy(old);u=runtime.unit(run,a.unit)
for key in ('universal_environment_attempts','universal_environment_choices','universal_services','universal_graphs','universal_bases','universal_fixture_preparation'):run.pop(key,None)
run.update(id='int-'+uuid.uuid4().hex[:16],images=locks(),_source_path=str(s.path(a.run)/'source'),_harness_path=str(runtime.HARNESS),_task_timeout=1200)
run['universal_plan']['execution_contract']=copy.deepcopy(EXECUTION_CONTRACT)
files=[x['path'] for x in old['context']['files']];units=run['universal_plan']['discovery']['units']
def owner(name,lang):
    rows=[v for v in units if v['runtime']==lang and (v['path']=='.' or name.startswith(v['path']+'/'))]
    return max(rows,key=lambda v:len(v['path'])) if rows else None
orchestration.discover(Path(run['_source_path']),files,units,owner)
requirements=json.loads(a.fixtures.read_bytes())
for req in requirements:req['cases']=[Case.model_validate(c).model_dump(exclude_none=False) for c in req['cases']]
run['universal_generation']={'requirements':requirements}
out=a.output.resolve();out.mkdir(exist_ok=False);receipt=dict(kind='declarative plumbing diagnostic, not full acceptance',source_run=a.run,fixture_sha256=sha(a.fixtures.read_bytes()),source_digest=old['context']['snapshot_digest'],unit=u)
try:
    for stage in ('prepare','service','fixture','business'):
        if stage=='service' and 'http' not in u['capabilities'] and not u['service_graph']['nodes']:continue
        if stage=='fixture' and u['runtime']!='python':continue
        target=out/stage;target.mkdir();report,cmd=getattr(runtime,stage)(run,u,target,lambda:False);receipt[stage]=dict(report=report,command=cmd);print(stage,[(x['name'],x['status']) for x in report['tests']],flush=True)
finally:
    target=out/'cleanup';target.mkdir();report,_=runtime.cleanup(run,target);receipt['cleanup']=report
    (out/'receipt.json').write_bytes(encode(receipt))
