"""Real Bandit executions -> real DefectDojo lifecycle; synthetic source only."""
from pathlib import Path
import json, os, sys, uuid
sys.path.insert(0,str(Path(__file__).resolve().parents[3]))
import httpx
from acceptance.integrations.services import Service
from acceptance.integrations.store import IntegrationStore
from acceptance.integrations.lifecycle import DojoLifecycle
from acceptance.integrations.runner import encode

root=Path(__file__).resolve().parents[3]
work=root/'var/integrations/defectdojo'
env=dict(line.split('=',1) for line in (work/'local.env').read_text().splitlines())
with httpx.Client(base_url='http://127.0.0.1:18894',timeout=60,trust_env=False) as client:
    r=client.post('/api/v2/api-token-auth/',json={'username':'admin','password':env['DD_ADMIN_PASSWORD']})
    if r.status_code!=200:raise RuntimeError('Dojo authentication HTTP '+str(r.status_code))
    os.environ['ACCEPTANCE_LOCAL_DOJO_TOKEN']=r.json()['token']
service=Service('http://127.0.0.1:18894','ACCEPTANCE_LOCAL_DOJO_TOKEN','defectdojo')
try:
    pt=service.request('api/v2/product_types/?limit=1')['results'][0]['id']
    product=service.request('api/v2/products/',method='POST',json={'name':'D025 lifecycle '+uuid.uuid4().hex[:8],'description':'Synthetic Bandit controls only','prod_type':pt})
    engagement=service.request('api/v2/engagements/',method='POST',json={'name':'Same-scope regression','product':product['id'],'target_start':'2026-10-18','target_end':'2026-10-18','status':'In Progress','engagement_type':'CI/CD'})
    store=IntegrationStore();lifecycle=DojoLifecycle(store.root/'lifecycle')
    repo=work/('fixture-'+uuid.uuid4().hex[:8]);repo.mkdir()
    profile={'id':'local-d025-lifecycle-'+uuid.uuid4().hex[:8],'name':'DefectDojo 生命周期校准','repository':str(repo),'version':'d025','environment':'isolated-bandit','scope':'fixture.py; fixed Bandit rules','files':['fixture.py'],'tasks':[{'id':'bandit','tool':'bandit','target':'.','timeout':120,'network':'none'}],'rules':[{'id':'high','kind':'metric','tasks':['bandit'],'metric':'findings.total','threshold':0}]}
    (repo/'fixture.py').write_text('answer = 42\n')
    store.register(profile)
    observations=[]
    for label,bad in [('首次发现',True),('重复扫描',True),('原路径修复',False),('再次出现',True)]:
        (repo/'fixture.py').write_text('import subprocess\nsubprocess.call("echo synthetic", shell=True)\n' if bad else 'answer = 42\n')
        with store.lease():
            run=store.create(profile['id']);run=store.execute(run['id'])
        receipt=lifecycle.publish(store,service,run['id'],'bandit',engagement['id'])
        again=lifecycle.publish(store,service,run['id'],'bandit',engagement['id'])
        assert again['run_id']==run['id']
        rows=receipt['findings'];active=[x for x in rows if x['active']]
        assert bool(active)==bad,(label,rows)
        observations.append(dict(label=label,run_id=run['id'],decision=run['decision'],finding_ids=[x['id'] for x in rows],active_ids=[x['id'] for x in active],test_url=receipt['test_url']))
    assert observations[0]['finding_ids']==observations[1]['finding_ids']==observations[2]['finding_ids']==observations[3]['finding_ids']
    summary=dict(engagement=engagement['id'],verified=True,observations=observations,source='four real isolated Bandit executions; synthetic fixture; no production change')
    out=root/'docs/design/d025/defectdojo-lifecycle.json';out.write_bytes(encode(summary));print(json.dumps(summary,ensure_ascii=False))
finally:
    service.close();os.environ.pop('ACCEPTANCE_LOCAL_DOJO_TOKEN',None)
