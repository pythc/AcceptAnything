"""Read-only compact diagnosis of real business receipts; never rewrites outcomes."""
import argparse
import json
import sys
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from acceptance.integrations.store import IntegrationStore

parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument('run_ids', nargs='+')
args = parser.parse_args()
store = IntegrationStore()
for run_id in args.run_ids:
    run = store.read(run_id)
    cases = []
    for task in run['tasks']:
        if task['tool'] != 'universal-business':
            continue
        path = store.path(run_id) / 'outputs' / task['id'] / 'cases.json'
        if path.is_file():
            cases.extend(json.loads(path.read_bytes()))
    print(run_id, run['status'], dict(Counter(row['status'] for row in cases)))
    for row in cases:
        case = row['case']
        print(case['id'], row['status'], case['title'])
        if row['status'] == 'passed':
            continue
        actual = row.get('actual')
        if isinstance(actual, dict):
            print(' receipt:', json.dumps({k: v for k, v in actual.items()
                if k not in {'steps', 'cleanup', 'callbacks'}}, ensure_ascii=False)[:1800])
            for section in ('steps', 'cleanup', 'callbacks'):
                for event in actual.get(section, []):
                    if event.get('status') != 'completed':
                        print(' ', section, json.dumps(event, ensure_ascii=False)[:1800])
        else:
            print(' actual:', json.dumps(actual, ensure_ascii=False)[:1800])
        for check in row.get('checks', []):
            if check['status'] != 'passed':
                print(' check:', json.dumps(check, ensure_ascii=False)[:1800])
