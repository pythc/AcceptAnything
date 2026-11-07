"""Run immutable repositories through the ordinary API. No project recipes."""
import argparse,json,time
from pathlib import Path
from urllib.request import Request,urlopen
from urllib.error import HTTPError
OUT=Path(__file__).resolve().parents[1]/'docs/design/d039'
BASE='http://127.0.0.1:18890'
parser=argparse.ArgumentParser();parser.add_argument('--batch',default='');parser.add_argument('--local-snapshot',action='store_true');parser.add_argument('--frozen-design-batch',help='Use original responses from an explicitly selected completed batch');args=parser.parse_args()
if args.frozen_design_batch and args.local_snapshot:parser.error('frozen design already binds its original repository')
suffix='-'+args.batch if args.batch else ''
def post(path,data):
    try:
        with urlopen(Request(BASE+path,json.dumps(data).encode(),headers={'Content-Type':'application/json'},method='POST'),timeout=1900) as r:return json.load(r)
    except HTTPError as e:
        print('API error',e.code,e.read().decode(),flush=True);raise
for _ in range(120):
    try:
        with urlopen(BASE+'/api/health',timeout=2) as r:
            if json.load(r)['status']=='ok':break
    except OSError:time.sleep(1)
else:raise RuntimeError('API not ready')
for label,url,sha in [
 ('flask','https://github.com/pallets/flask','d086db856be187255b8ec61ef409357393020f32'),
 ('fastify','https://github.com/fastify/fastify','2cbb98e25f75e23cf8dafedc9a111943f2888669'),
 ('sqlite-utils','https://github.com/simonw/sqlite-utils','9c66bafa52ae23d40499c74b0db3b635bcddb876')]:
    data=dict(remote_url=url,ref_type='commit',ref=sha)
    if args.local_snapshot:data=dict(repository=json.loads((OUT/(label+'-source.json')).read_text())['repository'])
    if args.frozen_design_batch:
        previous=json.loads((OUT/(label+'-'+args.frozen_design_batch+'-run.json')).read_text())
        data=dict(frozen_design_run=previous['id'])
    plan=post('/api/acceptance/plan',data)
    with (OUT/(label+suffix+'-plan.json')).open('x') as f:json.dump(plan,f,ensure_ascii=False,indent=2)
    run=post('/api/acceptance/runs',dict(plan_id=plan['id'],digest=plan['digest']))
    with (OUT/(label+suffix+'-run.json')).open('x') as f:json.dump(run,f,ensure_ascii=False,indent=2)
    print(label,run,flush=True)
