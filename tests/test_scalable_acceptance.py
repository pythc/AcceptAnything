import json
from pathlib import Path
from copy import deepcopy
import pytest
from acceptance.integrations.store import IntegrationStore
from acceptance.integrations.storage import file_digest
from acceptance.integrations.formats import parse
from acceptance.integrations.runner import encode,sha
from acceptance.universal.discovery import discover
from acceptance.universal.service import prepare


def test_streamed_artifact_has_no_32mib_size_gate_and_detects_changes(tmp_path):
    store=IntegrationStore(tmp_path/'store');r=store.new('large evidence','executor')
    source=tmp_path/'large.json'
    with source.open('wb') as f:
        f.write(b'{"payload":"')
        for _ in range(34):f.write(b'x'*1024*1024)
        f.write(b'"}')
    aid=store.artifact_file(r,'large.json',source)
    item,path=store.verified_artifact_path(r,aid)
    assert item['size']>32*1024*1024 and file_digest(path)==file_digest(source)
    with path.open('r+b') as f:f.write(b'!')
    with pytest.raises(ValueError,match='证据被修改'):store.verified_artifact_path(r,aid)


def test_payloads_are_not_duplicated_in_run_envelope_and_are_verified(tmp_path):
    store=IntegrationStore(tmp_path);r=store.new('payload calibration','executor')
    r['tasks']=[dict(id='test',report={'findings':[{'detail':'x'*200000}]})]
    store.save(r);saved=json.loads((store.path(r['id'])/'run.json').read_text())
    ref=saved['record']['tasks'][0]['report']['$payload']
    assert (store.path(r['id'])/'run.json').stat().st_size<10000
    assert store.read(r['id'])['tasks']==r['tasks']
    (store.path(r['id'])/'payloads'/(ref+'.json')).write_text('{}')
    with pytest.raises(ValueError,match='分片摘要'):store.read(r['id'])


def test_package_without_test_script_does_not_get_npm_test(tmp_path):
    root=tmp_path/'repo';root.mkdir();(root/'package.json').write_text('{"name":"tool-only"}')
    (root/'sample.test.js').write_text('export function fixture(){return 1}')
    s=IntegrationStore(tmp_path/'store');p=prepare(s,str(root))
    full=json.loads((s.root/'automatic-plans'/(p['id']+'.json')).read_text())['record']
    assert not any(t['tool']=='universal-native' for t in full['profile']['tasks'])


def test_mixed_workspace_discovers_rust_once_and_local_python_import_dependency(tmp_path):
    files={'pyproject.toml':'[project]\nname="root-package"\nversion="1"\n[build-system]\nrequires=["maturin"]',
      'core/__init__.py':'def f():return 1',
      'plugins/other/pyproject.toml':'[project]\nname="plugin"\nversion="1"',
      'plugins/other/src/plugin/__init__.py':'from core import f',
      'Cargo.toml':'[workspace]\nmembers=["crates/cli"]',
      'crates/cli/Cargo.toml':'[package]\nname="neutral-cli"\nversion="0.1.0"',
      'crates/cli/src/main.rs':'fn main() {}'}
    for name,raw in files.items():p=tmp_path/name;p.parent.mkdir(parents=True,exist_ok=True);p.write_text(raw)
    d=discover(tmp_path,sorted(files))
    assert len([u for u in d['units'] if u['runtime']=='rust'])==1
    root=next(u for u in d['units'] if u['runtime']=='python' and u['path']=='.')
    plugin=next(u for u in d['units'] if u['path']=='plugins/other')
    assert root['native_build'] and root['id'] in plugin['local_dependencies']


def test_paginated_projection_returns_every_candidate_without_native_duplication(tmp_path):
    from acceptance.unified import integration_view
    s=IntegrationStore(tmp_path/'store')
    raw=encode([{'RuleID':'calibration','Description':f'candidate {i}','File':f'src/{i}.py','StartLine':1,'Secret':'REDACTED'} for i in range(231)])
    r=s.import_reports('d055b042-e8d2-471f-b5ee-0f4817432228','pages',dict(repository='/calibration',revision='fixed',snapshot_digest='a'*64,environment='local',scope='source'),[dict(id='scan',format='gitleaks',raw=raw)],[dict(id='scan-gate',kind='metric',metric='findings.total',tasks=['scan'],threshold=0)])
    ids=[]
    for offset in (0,100,200):
        view=integration_view(s,r['id'],dict(offset=offset,limit=100,state='active'))
        assert view['finding_page']['total']==231
        assert 'finding_review' not in view['native_integration']
        assert not any(t.get('report',{}).get('findings') for t in view['native_integration']['tasks'])
        ids += [f['id'] for f in view['findings']]
    assert len(set(ids))==231
    view=integration_view(s,r['id'],dict(offset=0,limit=100,state='active',query='src/230.py'))
    assert len(view['findings'])==1 and view['findings'][0]['id']=='F-231'


def test_inventory_does_not_reject_project_by_file_count_or_file_size(tmp_path):
    from acceptance.integrations.discovery import inventory,manifest
    from acceptance.integrations.runner import frozen_source
    root=tmp_path/'repo';root.mkdir()
    for i in range(5002):(root/(str(i)+'.txt')).write_text('source')
    with (root/'large.txt').open('wb') as f:f.write(b'x'*(9*1024*1024))
    _,files,_=inventory(str(root))
    assert len(files)==5003 and 'large.txt' in files
    rows=manifest(str(root),files)
    copied=tmp_path/'frozen';copied.mkdir()
    context=frozen_source(str(root),files,copied)
    assert context['files']==rows
    assert file_digest(copied/'large.txt')==file_digest(root/'large.txt')


def test_http_report_import_does_not_have_a_hidden_body_size_ceiling(tmp_path):
    from uuid import uuid4
    from fastapi.testclient import TestClient
    from acceptance.api import create_app
    from acceptance.engine import Store
    raw=' '* (35*1024*1024)+'[]'
    body=dict(request_id=str(uuid4()),name='large imported scanner report',context=dict(repository='/calibration',revision='fixed',snapshot_digest='a'*64,environment='local',scope='source'),reports=[dict(id='scan',format='gitleaks',content=raw)],rules=[dict(id='scan-gate',kind='metric',metric='findings.total',tasks=['scan'],threshold=0)])
    with TestClient(create_app(Store(tmp_path/'store'))) as client:
        response=client.post('/api/integrations/import',json=body)
        assert response.status_code==200,response.text
        rid=response.json()['id']
        store=IntegrationStore(tmp_path/'store/integrations');record=store.read(rid)
        ref=record['tasks'][0]['report_ref']
        assert store.artifact_bytes(rid,ref)[1]==raw.encode()


def test_execution_errors_and_skips_are_not_defect_observations():
    from acceptance.integrations.adjudication import observations
    r=dict(tasks=[dict(id='native',tool='universal-native',report=dict(tests=[dict(name='missing dependency',status='error'),dict(name='optional provider',status='skipped'),dict(name='actual assertion',status='failed',detail='1 != 2')],findings=[]))])
    rows=observations(r)
    assert len(rows)==1 and rows[0]['hit']['name']=='actual assertion'


def test_git_snapshot_keeps_test_fixtures_and_committed_assets_without_host_credentials(tmp_path):
    import subprocess
    from acceptance.integrations.discovery import inventory
    root=tmp_path/'repo';root.mkdir()
    subprocess.run(['git','init','-q',str(root)],check=True)
    content={'tests/apps/.env':b'FOO=env\n','tests/apps/.flaskenv':b'FOO=flaskenv\n',
             'tests/fixtures/identity.key':b'fixture, not a credential',
             'assets/logo.png':b'PNG\0resource','dist/runtime.js':b'export const version=1;',
             'main.py':b'print(1)','.env':b'PRIVATE_ROOT=sentinel',
             'tests/.npmrc':b'PRIVATE_REGISTRY=sentinel'}
    for name,raw in content.items():
        p=root/name;p.parent.mkdir(parents=True,exist_ok=True);p.write_bytes(raw)
    subprocess.run(['git','-C',str(root),'add','-f','.'],check=True)
    (root/'tests'/'untracked.env').write_text('not selected')
    (root/'tests'/'.env.local').write_text('PRIVATE_LOCAL=sentinel')
    _,files,_=inventory(str(root))
    assert {'tests/apps/.env','tests/apps/.flaskenv','tests/fixtures/identity.key','assets/logo.png','dist/runtime.js'}<=set(files)
    assert not {'.env','tests/.npmrc','tests/.env.local'}&set(files)


def test_historical_optional_entry_normalization_never_changes_nested_oracles():
    from acceptance.universal.service import case_defaults,requirement_defaults
    old={'id':'C','expected':{'entry':None},'args':[{'value':1}]}
    new={**old,'entry':None}
    assert case_defaults(old)==case_defaults(new) and 'entry' not in old
    assert case_defaults(old)!=case_defaults({**old,'entry':'other'})
    assert case_defaults(old)!=case_defaults({**old,'expected':{}})
    assert requirement_defaults([{'id':'R','cases':[old]}])==requirement_defaults([{'id':'R','cases':[new]}])
