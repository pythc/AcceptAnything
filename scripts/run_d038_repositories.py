"""Submit three immutable public commits through the ordinary acceptance API."""
import json,time
from pathlib import Path
from urllib.request import Request,urlopen

OUT=Path(__file__).resolve().parents[1]/'docs/design/d038'
BASE='http://127.0.0.1:18890'
for attempt in range(150):
    try:
        with urlopen(BASE+'/api/health',timeout=2) as response:
            if json.load(response).get('status')=='ok':break
    except OSError:time.sleep(1)
else:raise RuntimeError('API readiness timeout')

def post(path,data):
    request=Request(BASE+path,json.dumps(data).encode(),headers={'Content-Type':'application/json'},method='POST')
    with urlopen(request,timeout=1900) as response:return json.load(response)

for label,url,commit in [
    ('primary','https://github.com/headroomlabs-ai/headroom','fbf7bc3278c11975299b9bd0a2ecf200dfd25a05'),
    ('flask','https://github.com/pallets/flask','d086db856be187255b8ec61ef409357393020f32'),
    ('fastify','https://github.com/fastify/fastify','2cbb98e25f75e23cf8dafedc9a111943f2888669')]:
    final=OUT/(label+'-final-run-id.json')
    if final.exists():
        old=json.loads(final.read_text())
        (OUT/(label+'-previous-'+old['id']+'.json')).write_text(json.dumps(old,indent=2))
    plan=post('/api/acceptance/plan',dict(remote_url=url,ref_type='commit',ref=commit))
    (OUT/(label+'-final-plan.json')).write_text(json.dumps(plan,ensure_ascii=False,indent=2))
    run=post('/api/acceptance/runs',dict(plan_id=plan['id'],digest=plan['digest']))
    final.write_text(json.dumps(run,ensure_ascii=False,indent=2))
    print(label,json.dumps(run,ensure_ascii=False),flush=True)
