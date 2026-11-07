"""Replay already accepted model cases unchanged, as diagnostic evidence, without a model call."""
import argparse,json,shutil,sys,uuid
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
from acceptance.integrations.store import IntegrationStore
from acceptance.integrations.runner import sha,encode
from acceptance.integrations.discovery import inventory,manifest
from acceptance.universal import runtime,service
p=argparse.ArgumentParser();p.add_argument('--run',required=True);p.add_argument('--output',required=True);p.add_argument('--current-protocol',action='store_true',help='仅诊断：保留原用例输入/预期，使用当前协议接线并记录版本差异');a=p.parse_args()
s=IntegrationStore();original=s.snapshot(a.run)
if original['status']!='completed' or not original['integrity']:raise ValueError('Source record must be complete and verified')
out=Path(a.output).resolve();out.mkdir(parents=True,exist_ok=False)
r=json.loads(json.dumps(original));r['id']='int-'+uuid.uuid4().hex[:16]
r['_source_path']=str(s.path(a.run)/'source');r['_harness_path']=str(out/'harness')
shutil.copytree(ROOT/'acceptance/universal',out/'harness',ignore=shutil.ignore_patterns('__pycache__'))
case_hash=sha(encode(r['universal_generation']));engine=service.implementation()
original_contract=r['universal_plan']['execution_contract']
if a.current_protocol:r['universal_plan']['execution_contract']=service.EXECUTION_CONTRACT
results=dict(mode='frozen-case-diagnostic-replay',source_run=a.run,source_snapshot=original['context']['snapshot_digest'],case_sha256=case_hash,implementation_digest=engine,original_execution_contract=original_contract,replay_execution_contract=r['universal_plan']['execution_contract'],stages=[])
(out/'frozen-cases.json').write_bytes(encode(r['universal_generation']))
try:
 for u in r['universal_plan']['discovery']['units']:
  if not any(c['unit']==u['id'] for q in r['universal_generation']['requirements'] for c in q['cases']):continue
  for name,fn in [('prepare',runtime.prepare),('build',runtime.build),('business',runtime.business)]:
   dest=out/(u['id']+'-'+name);dest.mkdir()
   try:
    report,cmd=fn(r,u,dest,lambda:False)
    results['stages'].append(dict(unit=u['id'],stage=name,report=report,command=cmd))
   except Exception as e:
    results['stages'].append(dict(unit=u['id'],stage=name,error=str(e)));break
finally:
 dest=out/'cleanup';dest.mkdir();report,cmd=runtime.cleanup(r,dest);results['cleanup']=report
 results['oracles_unchanged']=case_hash==sha(encode(r['universal_generation']))
 files=[x['path'] for x in original['context']['files']];results['source_unchanged']=sha(encode(manifest(r['_source_path'],files)))==original['context']['snapshot_digest']
 results['implementation_unchanged']=engine==service.implementation()
 (out/'result.json').write_bytes(encode(results))
 print(json.dumps(dict(output=str(out),checks=[(x['stage'],[(t['name'],t['status']) for t in x.get('report',{}).get('tests',[])]) for x in results['stages']],oracles_unchanged=results['oracles_unchanged'],source_unchanged=results['source_unchanged']),ensure_ascii=False),flush=True)
