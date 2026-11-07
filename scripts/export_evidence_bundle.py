"""Export verified acceptance records and explicitly selected resources as ZIP64.

No target checkout or server secrets are included implicitly. Raw evidence and
content-addressed payloads remain byte-identical, with a SHA-256 inventory.
"""
import argparse
import hashlib
import json
from pathlib import Path
import sys
import uuid
import zipfile

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from acceptance.integrations.store import IntegrationStore
from acceptance.integrations.storage import file_digest


def export(store, run_ids, output, resources=(), forbidden_values=()):
    output = Path(output).resolve()
    if output.exists() or output.is_relative_to(store.root.resolve()):
        raise ValueError('Export destination must be new and outside the evidence store')
    output.parent.mkdir(parents=True, exist_ok=True)
    selected = []
    runs = []
    for rid in run_ids:
        record = store.snapshot(rid)
        if record['status'] in {'queued', 'running'} or not record['integrity']:
            raise ValueError('Only terminal, integrity-verified records can be certified: ' + rid)
        folder = store.path(rid)
        envelope = json.loads((folder / 'run.json').read_bytes())['record']
        selected.append((f'runs/{rid}/run.json', folder / 'run.json'))
        values = [envelope.get(k) for k in ('finding_review', 'universal_plan', 'universal_generation')]
        values += [task.get('report') for task in envelope['tasks']]
        for digest in sorted({v['$payload'] for v in values if isinstance(v, dict) and set(v) == {'$payload'}}):
            selected.append((f'runs/{rid}/payloads/{digest}.json', folder / 'payloads' / (digest + '.json')))
        for artifact in record['artifacts']:
            _, path = store.verified_artifact_path(record, artifact['id'])
            selected.append((f'runs/{rid}/artifacts/{artifact["id"]}', path))
        runs.append(dict(id=rid, mode=record.get('mode'), status=record['status'], decision=record['decision'], integrity=True,
                         snapshot_digest=record.get('context', {}).get('snapshot_digest')))
    for item in resources:
        given = Path(item)
        path = given.resolve(strict=True)
        if given.is_symlink() or not path.is_file():
            raise ValueError('Resource must be an explicitly selected regular file: ' + str(path))
        name = path.relative_to(ROOT).as_posix() if path.is_relative_to(ROOT) else path.name
        selected.append(('resources/' + name, path))
    names = [name for name, _ in selected]
    if len(set(names)) != len(names):
        raise ValueError('Duplicate archive entry')
    inventory = []
    for name, path in selected:
        # Optional caller-supplied byte sentinels prevent accidental inclusion of
        # a selected secret. This is not a general secret-scanning substitute.
        longest = max(map(len, forbidden_values), default=0)
        tail = b''
        with path.open('rb') as stream:
            for chunk in iter(lambda: stream.read(1024 * 1024), b''):
                sample = tail + chunk
                if any(value and value in sample for value in forbidden_values):
                    raise ValueError('Selected evidence contains a forbidden secret: ' + name)
                tail = sample[-longest:] if longest else b''
        inventory.append(dict(path=name, size=path.stat().st_size, sha256=file_digest(path)))
    manifest = dict(schema_version=1, runs=runs, files=inventory,
                    target_source='Not implicitly included; explicit resources are inventoried',
                    scope='Frozen records, raw evidence, referenced payloads, explicitly selected resources')
    temporary=output.with_name('.bundle-'+uuid.uuid4().hex)
    try:
        with zipfile.ZipFile(temporary, 'w', compression=zipfile.ZIP_DEFLATED, compresslevel=6, allowZip64=True) as archive:
            for name, path in selected:
                archive.write(path, name)
            archive.writestr('bundle-manifest.json', json.dumps(manifest, ensure_ascii=False, indent=2, allow_nan=False))
        with zipfile.ZipFile(temporary) as archive:
            for row in inventory:
                h = hashlib.sha256()
                with archive.open(row['path']) as stream:
                    for block in iter(lambda: stream.read(1024 * 1024), b''): h.update(block)
                if h.hexdigest() != row['sha256']:
                    raise ValueError('Archive verification failed: ' + row['path'])
        # Exclusive creation prevents a concurrent export from replacing an
        # existing result, even after the initial destination check.
        import os
        os.link(temporary,output)
    finally:temporary.unlink(missing_ok=True)
    return dict(output=str(output.resolve()), bytes=output.stat().st_size, sha256=file_digest(output),
                files=len(inventory), runs=run_ids, verified=True)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--store', type=Path, default=ROOT / 'var/integrations')
    parser.add_argument('--run', action='append', required=True)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--resource', action='append', default=[])
    args = parser.parse_args()
    print(json.dumps(export(IntegrationStore(args.store), args.run, args.output, args.resource), ensure_ascii=False))


if __name__ == '__main__': main()
