"""Archive only explicitly selected delivery sources, never runtime credentials."""
import argparse,difflib,hashlib,json,sys
from pathlib import Path
from zipfile import ZipFile,ZIP_DEFLATED
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
from acceptance.universal.service import implementation
p=argparse.ArgumentParser();p.add_argument('--release',required=True);args=p.parse_args();folder=ROOT/'docs/design/d040'
with ZipFile(folder/'executing-source-r1.zip') as old:
    files=set(old.namelist())
    files.update(str(p.relative_to(ROOT)) for p in (ROOT/'acceptance').rglob('*') if p.suffix in {'.py','.json','.mjs','.cjs','.rego'})
    files.update(['tests/test_universal.py','tests/test_environment_preparation.py','scripts/archive_d040_source.py','scripts/summarize_d040_batch.py','scripts/calibrate_d040_environment.py','integrations/images/universal/Dockerfile.python312'])
    files.update(['tests/test_observation_protocol.py','tests/test_model_budget.py','scripts/inspect_business_results.py','scripts/preflight_d040_inputs.py','scripts/calibrate_d040_model_budget.py','scripts/build_d040_gap_ledger.py'])
    files.update(['tests/test_local_dependency_replay.py','scripts/run_d039_repositories.py'])
    files.add('scripts/diagnose_declared_cli.py')
    files.update(str(p.relative_to(ROOT)) for p in (ROOT/'web/src').rglob('*') if p.suffix in {'.ts','.tsx','.js','.css','.mjs'})
    changes=[];raws={name:(ROOT/name).read_bytes() for name in sorted(files)}
    for name,raw in raws.items():
        before=old.read(name) if name in old.namelist() else b''
        if before!=raw:changes.extend(difflib.unified_diff(before.decode().splitlines(True),raw.decode().splitlines(True),fromfile='r1/'+name,tofile=args.release+'/'+name))
secret=(ROOT/'var/secrets/deepseek.key').read_bytes().strip()
if secret and any(secret in raw for raw in raws.values()):raise ValueError('Credential found in selected sources')
dest=folder/('executing-source-'+args.release+'.zip')
with ZipFile(dest,'x',compression=ZIP_DEFLATED) as z:
    for name,raw in raws.items():z.writestr(name,raw)
(folder/(args.release+'-source.diff')).write_text(''.join(changes))
receipt=dict(implementation_digest=implementation(),sha256=hashlib.sha256(dest.read_bytes()).hexdigest(),size=dest.stat().st_size,files={name:hashlib.sha256(raw).hexdigest() for name,raw in raws.items()})
(folder/(args.release+'-source-receipt.json')).write_text(json.dumps(receipt,indent=2))
print(json.dumps({k:receipt[k] for k in ('implementation_digest','sha256','size')}))
