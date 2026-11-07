"""Read-only comparison of two verified, terminal acceptance records.

Test identifiers are matched only within the same task; generated model cases
remain separate unless their full frozen case definitions are identical.
"""
import argparse
from collections import Counter
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from acceptance.integrations.store import IntegrationStore
from acceptance.integrations.storage import file_digest


def compare(store, before_id, after_id):
    before, after = (store.snapshot(rid) for rid in (before_id, after_id))
    for record in (before, after):
        if record['status'] in {'queued', 'running'} or not record['integrity']:
            raise ValueError('Comparison requires terminal, integrity-verified records')
    old_tasks = {t['id']: t for t in before['tasks']}
    new_tasks = {t['id']: t for t in after['tasks']}
    rows = []
    for tid in sorted(old_tasks.keys() | new_tasks.keys()):
        a, b = old_tasks.get(tid, {}), new_tasks.get(tid, {})
        old_tests = {t['id']: t for t in (a.get('report') or {}).get('tests', [])}
        new_tests = {t['id']: t for t in (b.get('report') or {}).get('tests', [])}
        common = old_tests.keys() & new_tests.keys()
        transitions = Counter(old_tests[k]['status'] + ' -> ' + new_tests[k]['status'] for k in common)
        row = dict(task=tid, tool=b.get('tool', a.get('tool')),
                   before_state=a.get('state'), after_state=b.get('state'),
                   before_counts=dict(Counter(t['status'] for t in old_tests.values())),
                   after_counts=dict(Counter(t['status'] for t in new_tests.values())),
                   common_tests=len(common), added=len(new_tests.keys() - old_tests.keys()),
                   removed=len(old_tests.keys() - new_tests.keys()), transitions=dict(transitions),
                   changed=[dict(id=k, name=new_tests[k]['name'], suite=new_tests[k].get('suite'),
                                 before=old_tests[k]['status'], after=new_tests[k]['status'])
                            for k in sorted(common) if old_tests[k]['status'] != new_tests[k]['status']])
        # Matching a title is insufficient to claim the same model oracle.
        if row['tool'] == 'universal-business':
            paths = [store.path(rid) / 'outputs' / tid / 'cases.json' for rid in (before_id, after_id)]
            row['frozen_cases_identical_bytes'] = all(p.is_file() for p in paths) and file_digest(paths[0]) == file_digest(paths[1])
            row['interpretation'] = 'Model cases and their outcomes remain independently recorded; differing cases are not a controlled before/after experiment.'
        rows.append(row)
    return dict(before=before_id, after=after_id,
                same_source_snapshot=before['context']['snapshot_digest'] == after['context']['snapshot_digest'],
                source_snapshot_before=before['context']['snapshot_digest'], source_snapshot_after=after['context']['snapshot_digest'],
                interpretation='Observed status transitions are not by themselves proof of a single cause. Check frozen source, cases, dependency resolutions, and original traces.',
                tasks=rows)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--before', required=True)
    parser.add_argument('--after', required=True)
    parser.add_argument('--store', type=Path, default=ROOT / 'var/integrations')
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    result = compare(IntegrationStore(args.store), args.before, args.after)
    with args.output.open('x') as stream:
        json.dump(result, stream, ensure_ascii=False, indent=2)
    print(json.dumps(dict(before=args.before, after=args.after, same_source_snapshot=result['same_source_snapshot'], tasks=len(result['tasks']))))
