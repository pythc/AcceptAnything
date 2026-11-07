"""Read-only verification of selected real archives and immutable baseline files."""
import argparse
from concurrent.futures import ThreadPoolExecutor
import hashlib
import json
from pathlib import Path
import time
import httpx


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--url',default='http://127.0.0.1:18890')
    parser.add_argument('--runs',nargs='+',required=True)
    parser.add_argument('--baseline',type=Path,required=True)
    parser.add_argument('--output',type=Path,required=True)
    args=parser.parse_args();result={'runs':[],'concurrent_api':[]}
    with httpx.Client(base_url=args.url,timeout=180,trust_env=False) as client:
        def verify(rid):
            started=time.monotonic();response=client.get(f'/api/runs/{rid}/result-contract');response.raise_for_status()
            contract=response.json();(args.output.parent/(rid+'-contract.json')).write_text(json.dumps(contract,ensure_ascii=False,indent=2)+'\n')
            return dict(run_id=rid,seconds=round(time.monotonic()-started,3),execution=contract['execution'],coverage=contract['coverage']['requirement_counts'],
                        recorded_decision=contract['gate']['recorded_decision'],decision=contract['gate']['decision'],verified=contract['provenance']['evidence_verified_now'])
        with ThreadPoolExecutor(max_workers=3) as pool:
            futures=[pool.submit(verify,rid) for rid in args.runs]
            for _ in range(4):
                for url in ('/api/health','/api/catalogue?limit=50','/api/jobs'):
                    start=time.monotonic();response=client.get(url);response.raise_for_status()
                    result['concurrent_api'].append({'path':url,'status':response.status_code,'ms':round((time.monotonic()-start)*1000,2)})
            result['runs']=[f.result() for f in futures]
    baseline=json.loads(args.baseline.read_text())['records_and_model_receipts']
    changed=[path for path,checksum in baseline.items() if not Path(path).is_file() or hashlib.sha256(Path(path).read_bytes()).hexdigest()!=checksum]
    result['baseline']={'files':len(baseline),'unchanged':len(baseline)-len(changed),'changed':changed}
    args.output.write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n')
    print(json.dumps(result,ensure_ascii=False,indent=2))
    assert not changed
    assert all(r['verified'] for r in result['runs'])


if __name__=='__main__':main()
