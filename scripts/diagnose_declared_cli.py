"""Replay one declared CLI in a fresh isolated environment, never alter a run.

This diagnostic retains actual streams and cleanup. It is not an extra passed
acceptance case and does not accept executable shell text or a new command.
"""
import argparse,copy,json,sys,uuid
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
from acceptance.integrations.store import IntegrationStore
from acceptance.integrations.runner import encode,sha
from acceptance.universal import runtime

p=argparse.ArgumentParser(description=__doc__)
p.add_argument('--run',required=True);p.add_argument('--unit',required=True)
p.add_argument('--entry',required=True);p.add_argument('--output',type=Path,required=True)
p.add_argument('arguments',nargs=argparse.REMAINDER);a=p.parse_args()
s=IntegrationStore();original=s.snapshot(a.run)
if original['status']!='completed' or not original['integrity']:raise ValueError('Original evidence is not terminal and verified')
run=copy.deepcopy(original);unit=runtime.unit(run,a.unit)
for key in ('universal_environment_attempts','universal_environment_choices','universal_services'):run.pop(key,None)
command=runtime.cli_command(unit,a.entry)
if not a.arguments or a.arguments[0]!='--':raise ValueError('CLI arguments must follow --')
run['id']='int-'+uuid.uuid4().hex[:16]
run.update(_source_path=str(s.path(a.run)/'source'),_harness_path=str(s.path(a.run)/'universal-driver'),_task_timeout=3600)
output=a.output.resolve();output.mkdir()
record=dict(kind='independent diagnostic; not an acceptance result',source_run=a.run,
            snapshot_digest=original['context']['snapshot_digest'],unit=a.unit,entry=a.entry,
            argv=[*command,*a.arguments[1:]],diagnostic_id=run['id'],script_sha256=sha(Path(__file__).read_bytes()))
try:
    prepared=output/'prepare';prepared.mkdir()
    report,_=runtime.prepare(run,unit,prepared,lambda:False);record['prepare']=report
    if any(row['status']!='passed' for row in report['tests'] if not row['name'].startswith('可选准备 · ')):raise ValueError('Diagnostic base environment is not ready')
    executed=output/'command';executed.mkdir()
    result,streams=runtime.command(run,unit,record['argv'],executed,lambda:False)
    record['command']=result
finally:
    cleaned=output/'cleanup';cleaned.mkdir()
    report,_=runtime.cleanup(run,cleaned);record['cleanup']=report
    record['files']={str(f.relative_to(output)):dict(sha256=sha(f.read_bytes()),size=f.stat().st_size) for f in output.rglob('*') if f.is_file()}
    (output/'receipt.json').write_bytes(encode(record))
print(json.dumps({key:record[key] for key in ('source_run','diagnostic_id','command')},ensure_ascii=False))
