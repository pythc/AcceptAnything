"""Verify selected immutable run inputs, cleanup, and explicit model authorization."""
import argparse,hashlib,json,subprocess,sys
from pathlib import Path
from urllib.request import urlopen
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
from acceptance.integrations.store import IntegrationStore
from acceptance.integrations.discovery import manifest
from acceptance.integrations.runner import sha,encode
from acceptance.planning import calls
from acceptance.universal.service import implementation
p=argparse.ArgumentParser();p.add_argument('--batch',required=True);p.add_argument('--output',required=True);a=p.parse_args();s=IntegrationStore();result={'runs':[]}
for file in sorted((ROOT/'docs/design/d039').glob('*-'+a.batch+'-run.json')):
 rid=json.loads(file.read_text())['id'];r=s.snapshot(rid)
 if r['status']!='completed' or not r['integrity']:raise ValueError('not terminal and verified: '+rid)
 names=[x['path'] for x in r['context']['files']];repository=r['context']['repository']
 source_ok=sha(encode(manifest(repository,names)))==r['context']['snapshot_digest']
 frozen_ok=sha(encode(manifest(str(s.path(rid)/'source'),names)))==r['context']['snapshot_digest']
 dirty=subprocess.check_output(['git','-C',repository,'status','--porcelain','--untracked-files=all'],text=True)
 remaining={kind:subprocess.check_output(['docker',kind,'ls',*(['-a'] if kind=='container' else []),'--filter','label=acceptance.run='+rid,'-q'],text=True).splitlines() for kind in ('container','volume','network')}
 entry=dict(repository=file.name.removesuffix('-'+a.batch+'-run.json'),id=rid,status=r['status'],decision=r['decision'],integrity=r['integrity'],source_unchanged=source_ok,frozen_source_unchanged=frozen_ok,git_clean=not dirty,remaining_runtime=remaining,implementation_unchanged=r['universal_plan']['implementation_digest']==implementation(),finding_summary=r['finding_review']['summary'])
 if not source_ok or not frozen_ok or dirty or any(remaining.values()) or not entry['implementation_unchanged']:raise ValueError(json.dumps(entry))
 result['runs'].append(entry)
audit=json.loads((ROOT/'docs/design/d039/release4-model-authorization.json').read_bytes());old=s.root/'model-calls'/(audit['client_request_id']+'.json');oldraw=old.read_bytes()
result['old_model_request']=dict(id=audit['client_request_id'],state=json.loads(oldraw)['state'],receipt_unchanged=hashlib.sha256(oldraw).hexdigest()==audit['receipt_sha256'])
if not result['old_model_request']['receipt_unchanged'] or result['old_model_request']['state']!='upstream_unknown':raise ValueError('unknown receipt changed')
result['blocking_model_requests']=[dict(id=r['client_request_id'],state=r['state']) for r in calls.pending(s)]
with urlopen('http://127.0.0.1:18890/api/health',timeout=5) as response:result['health']=json.load(response)
with Path(a.output).open('x') as f:json.dump(result,f,ensure_ascii=False,indent=2)
print(json.dumps(result,ensure_ascii=False,indent=2))
