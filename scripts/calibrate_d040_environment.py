"""Diagnostic only: exercise generic discovery and preparation on an immutable source."""
import argparse,json,sys
from pathlib import Path
from collections import Counter
ROOT=Path(__file__).resolve().parents[1];sys.path[:0]=[str(ROOT),str(ROOT/'var/d040-tools'),str(ROOT/'tools/d040-staging')]
import preparation
from acceptance.universal import runtime
from acceptance.universal.discovery import discover
from acceptance.integrations.discovery import inventory,manifest
from acceptance.integrations.registry import locks
from acceptance.integrations.runner import encode,sha
p=argparse.ArgumentParser();p.add_argument('repository');p.add_argument('--output',required=True);a=p.parse_args();out=Path(a.output);out.mkdir(exist_ok=False)
root,files,_=inventory(a.repository);before=manifest(root,files);d=discover(root,files);u=next(x for x in d['units'] if x['runtime']=='python' and x['path']=='.')
prepared=preparation.discover(root,files,u);u['test_dependencies']+=list(dict.fromkeys(x['spec'] for x in prepared['optional_packages']))
images=locks();image=json.loads(runtime.docker('image','inspect','acceptance-universal-python:d040').stdout)[0]
images['universal-python']={'id':image['Id']}
r=dict(id='int-d040-environment-calibration',images=images,context=dict(snapshot_digest=sha(encode(before))),_source_path=str(root),_harness_path=str(runtime.HARNESS),_task_timeout=1200,universal_plan=dict(discovery=dict(units=[u])))
receipt=dict(kind='environment-calibration-not-full-acceptance',source_manifest=before,unit=u,preparation=prepared,image=image['Id'],stages=[])
try:
 output=out/'prepare';output.mkdir();report,cmd=runtime.prepare(r,u,output,lambda:False);receipt['stages'].append(dict(stage='prepare',command=cmd,tests=report['tests']))
 for i,action in enumerate(prepared['build_actions']):
  output=out/('compile-'+str(i));output.mkdir();argv=['/bin/sh','-c','cd "$1" && shift && exec "$@"','acceptance','/work/repo/'+action['workdir'],*action['argv']]
  cmd,_=runtime.command(r,u,argv,output,lambda:False);receipt['stages'].append(dict(stage='compile',action=action,command=cmd))
 output=out/'native';output.mkdir();report,cmd=runtime.native(r,u,output,lambda:False);receipt['stages'].append(dict(stage='native',command=cmd,counts=dict(Counter(t['status'] for t in report['tests'])),nonpass=[t for t in report['tests'] if t['status']!='passed']))
finally:
 output=out/'cleanup';output.mkdir();report,_=runtime.cleanup(r,output);receipt['stages'].append(dict(stage='cleanup',tests=report['tests']));receipt['source_unchanged']=manifest(root,files)==before;(out/'receipt.json').write_bytes(encode(receipt))
print(json.dumps({k:v for k,v in receipt.items() if k in {'kind','image','stages','source_unchanged'}},ensure_ascii=False))
