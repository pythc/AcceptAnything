"""Reproducible metadata benchmark, with isolated synthetic records and no model calls."""
import argparse
from concurrent.futures import ThreadPoolExecutor
import json
from pathlib import Path
import platform
import statistics
import subprocess
import sys
import tempfile
import time

sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from fastapi.testclient import TestClient
from acceptance.api import create_app
from acceptance.engine import Store
from acceptance.integrations.store import IntegrationStore
from acceptance.integrations.storage import write_json
from acceptance.integrations.runner import encode, sha


def percentile(values):
    return sorted(values)[int((len(values)-1)*.95)]


def benchmark(count, samples):
    with tempfile.TemporaryDirectory(prefix='acceptance-history-benchmark-') as folder:
        root=Path(folder);native=Store(root);integration=IntegrationStore(root/'integrations')
        started=time.monotonic()
        for i in range(count):
            rid=f'int-{i:016x}';directory=integration.root/'runs'/rid;directory.mkdir()
            record=dict(id=rid,name=f'合成目录基准 {i}',mode='executor',profile_id='local-benchmark',status='completed',decision='inconclusive',
                created_at=f'2026-01-01T00:00:{i%60:02d}Z',finished_at=None,profile={'version':'benchmark-v1'},onboarding_plan={'checks':[]},tasks=[],artifacts=[],
                context={'repository':f'/synthetic/repository-{i%100}','revision':'benchmark','snapshot_digest':'a'*64,'environment':'metadata-only','scope':'目录分页性能；不证明任何业务能力','files':[]})
            write_json(directory/'run.json',{'record':record,'sha256':sha(encode(record))})
        generated=time.monotonic()-started
        started=time.monotonic();native.sync_history();integration.sync_history();cold=time.monotonic()-started
        client=TestClient(create_app(native));values=[]
        for _ in range(samples):
            start=time.monotonic();page=client.get('/api/catalogue?limit=50');values.append(time.monotonic()-start)
            assert page.status_code==200 and page.json()['total']==count and len(page.json()['runs'])==50
        all_ids=[];cursor=None
        while True:
            response=client.get('/api/catalogue',params={'limit':500,**({'cursor':cursor} if cursor else {})}).json()
            all_ids += [r['id'] for r in response['runs']]
            cursor=response['next_cursor']
            if not cursor:break
        assert len(all_ids)==len(set(all_ids))==count
        query=f'合成目录基准 {count-1}';start=time.monotonic()
        search=client.get('/api/catalogue',params={'limit':50,'query':query}).json()
        search_s=time.monotonic()-start;assert search['total']==1
        # Exercise concurrent HTTP catalogue and health reads. Real historical
        # evidence verification is measured separately, not simulated here.
        def query_once(_):
            start=time.monotonic();r=client.get('/api/catalogue?limit=50');assert r.status_code==200
            assert client.get('/api/health').status_code==200
            return time.monotonic()-start
        with ThreadPoolExecutor(max_workers=3) as pool:concurrent=list(pool.map(query_once,range(12)))
        return dict(records=count,generated_seconds=round(generated,3),cold_index_seconds=round(cold,3),
            samples=samples,first_page_size=50,warm_api_p50_ms=round(statistics.median(values)*1000,2),warm_api_p95_ms=round(percentile(values)*1000,2),
            warm_api_max_ms=round(max(values)*1000,2),search_ms=round(search_s*1000,2),all_pages_unique=len(set(all_ids)),
            concurrent_catalogue_and_health_p95_ms=round(percentile(concurrent)*1000,2),index_bytes=integration.history.database.stat().st_size)


def main():
    parser=argparse.ArgumentParser();parser.add_argument('--output',type=Path,required=True);parser.add_argument('--samples',type=int,default=30)
    args=parser.parse_args();assert args.samples>=20
    def sysctl(name):
        p=subprocess.run(['sysctl','-n',name],capture_output=True,text=True);return p.stdout.strip() if p.returncode==0 else None
    result={'host':{'platform':platform.platform(),'python':platform.python_version(),'cpu':sysctl('machdep.cpu.brand_string'),'memory_bytes':sysctl('hw.memsize'),'storage':'local macOS temporary directory; SQLite WAL'},
            'scope':'synthetic metadata; TestClient HTTP requests, no target or model execution', 'results':[]}
    for count in (1000,10000):
        row=benchmark(count,args.samples);result['results'].append(row);print(json.dumps(row),flush=True)
        args.output.write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n')


if __name__=='__main__':main()
