import json
from copy import deepcopy
from pathlib import Path
import pytest
from fastapi.testclient import TestClient
from acceptance.api import create_app
from acceptance.engine import Store
from acceptance.integrations.store import IntegrationStore
from acceptance.integrations import discovery
from acceptance.progress import checks, register_cases


@pytest.fixture
def repository(tmp_path, monkeypatch):
    root=tmp_path/'a repo';root.mkdir()
    for name,raw in {'package.json':'{"name":"sample","version":"1.0.0"}', 'package-lock.json':'{"name":"sample","lockfileVersion":3,"packages":{"": {"name":"sample","version":"1.0.0"}}}',
                     'source.js':'export const value=1;', 'test_sample.py':'def test_ok(): assert True',
                     'script.sh':'#!/bin/sh\necho ok\n', 'Dockerfile':'FROM alpine:3.22\n',
                     '.env':'PRIVATE=must-not-copy', '.gitleaks.toml':'disabled scanning', '.semgrepignore':'*', 'test.test.mjs':"import {test} from 'node:test';test('ok',()=>{});"}.items():
        (root/name).write_text(raw)
    (root/'node_modules').mkdir();(root/'node_modules/private.js').write_text('do not copy')
    (root/'outside').symlink_to(tmp_path)
    monkeypatch.setattr(discovery,'locks',lambda:{key:{'id':'sha256:'+'1'*64} for key in {'python','node','node-base','semgrep','gitleaks','trivy','syft','grype','hadolint','shellcheck'}})
    return root


def test_repository_plan_reuses_adapters_and_explicit_scope(tmp_path,repository):
    store=IntegrationStore(tmp_path/'store')
    plan=discovery.prepare(store,str(repository))
    tools={c['tool'] for c in plan['checks']}
    assert {'gitleaks','bandit','semgrep-njsscan','syft-cyclonedx','shellcheck','hadolint','trivy-config'}<=tools
    assert 'trivy-fs' not in tools and 'pytest' not in tools
    assert any(x['subject']=='依赖漏洞数据库' for x in plan['exclusions'])
    raw=json.loads((store.root/'plans'/(plan['id']+'.json')).read_bytes())['record']
    assert not {'.env','.gitleaks.toml','.semgrepignore'} & set(raw['profile']['files']) and not any('node_modules' in f or 'outside' in f for f in raw['profile']['files'])
    assert all(c['expected'] for c in plan['checks'])
    # All tasks are explicitly governed; a plan is not arbitrary shell input.
    assert {t['id'] for t in raw['profile']['tasks']}=={i for rule in raw['profile']['rules'] for i in rule['tasks']}


def test_selected_network_and_tests_are_in_frozen_plan(tmp_path,repository):
    store=IntegrationStore(tmp_path/'store')
    plan=discovery.prepare(store,str(repository),network=True,tests=True)
    assert {'trivy-fs','pytest','node-test'}<={c['tool'] for c in plan['checks']}
    record=json.loads((store.root/'plans'/(plan['id']+'.json')).read_bytes())['record']
    assert all(t['network']=='none' for t in record['profile']['tasks'] if t['tool']!='trivy-fs')
    assert next(t for t in record['profile']['tasks'] if t['tool']=='trivy-fs')['network']=='registry'


def test_package_manifest_without_dependency_inventory_is_not_an_empty_scan(tmp_path,repository):
    (repository/'package-lock.json').unlink()
    plan=discovery.prepare(IntegrationStore(tmp_path/'store'),str(repository),network=True)
    assert not {'syft-cyclonedx','trivy-fs'} & {c['tool'] for c in plan['checks']}
    assert any(x['subject']=='软件物料与依赖漏洞' and '锁文件' in x['reason'] for x in plan['exclusions'])


@pytest.mark.parametrize('change',['modified','added','deleted','mode','toolchain','plan'])
def test_plan_drift_prevents_execution(tmp_path,repository,monkeypatch,change):
    store=IntegrationStore(tmp_path/'store');plan=discovery.prepare(store,str(repository))
    if change=='modified': (repository/'source.js').write_text('changed')
    if change=='added': (repository/'new.js').write_text('new')
    if change=='deleted': (repository/'source.js').unlink()
    if change=='mode': (repository/'source.js').chmod(0o700)
    if change=='toolchain': monkeypatch.setattr(discovery,'locks',lambda:{})
    if change=='plan':
        p=store.root/'plans'/(plan['id']+'.json');record=json.loads(p.read_bytes());record['record']['profile']['name']='tampered';p.write_text(json.dumps(record))
    monkeypatch.setattr(store,'create',lambda *_:pytest.fail('drift must be rejected before creating a run'))
    with pytest.raises(ValueError): discovery.create_from_plan(store,plan['id'])


def test_frozen_copy_is_bound_to_confirmed_plan(tmp_path,repository,monkeypatch):
    store=IntegrationStore(tmp_path/'store');plan=discovery.prepare(store,str(repository))
    run=discovery.create_from_plan(store,plan['id'])
    assert run['context']['snapshot_digest']==plan['snapshot_digest']
    assert run['onboarding_plan']['id']==plan['id']
    (repository/'source.js').write_text('new version after freeze')
    assert (store.path(run['id'])/'source/source.js').read_text()=='export const value=1;'
    assert not (store.path(run['id'])/'source/.env').exists()


def test_onboarded_repository_appears_in_main_catalogue(tmp_path,repository):
    store=Store(tmp_path/'api');integrations=IntegrationStore(store.root/'integrations')
    plan=discovery.prepare(integrations,str(repository));run=discovery.create_from_plan(integrations,plan['id'])
    client=TestClient(create_app(store));data=client.get('/api/catalogue').json()
    brief=next(x for x in data['runs'] if x['id']==run['id'])
    assert brief['mode']=='repository'
    assert brief['source']['snapshot']['digest']==plan['snapshot_digest']
    assert brief['report_url'].endswith('/export/markdown')
    assert data['repositories'][0]['latest']['id']==run['id']


@pytest.mark.parametrize('path',['relative','.','/','~'])
def test_rejects_ambiguous_or_broad_paths(tmp_path,path):
    with pytest.raises(ValueError): discovery.prepare(IntegrationStore(tmp_path/'store'),path)


def test_local_api_rejects_shell_options_and_cross_origin(tmp_path,repository):
    client=TestClient(create_app(Store(tmp_path/'api')))
    route='/api/integrations/local/plan'
    assert client.post(route,json={'repository':str(repository),'command':'anything'}).status_code==422
    assert client.post(route,json={'repository':str(repository)},headers={'Origin':'https://elsewhere.invalid'}).status_code==403
    response=client.post(route,json={'repository':str(repository)})
    assert response.status_code==200 and response.json()['checks']
    assert client.post('/api/integrations/local/runs',json={'plan_id':'../../escape'}).status_code==422


def test_progress_never_counts_running_as_a_final_result(tmp_path):
    store=Store(tmp_path/'runs');run=store.create('fixed');criterion=run['baseline']['criteria'][0]
    with checks(store,run,[criterion]):
        published=store.read(run['id'])
        assert published['check_runs'][0]['status']=='running'
        assert published['results']==[]
        run['results'].append({'criterion_id':criterion['id'],'status':'passed'})
    assert store.read(run['id'])['check_runs'][0]['status']=='passed'


def test_progress_exception_and_case_registration(tmp_path):
    store=Store(tmp_path/'runs');run=store.create('fixed');criterion=run['baseline']['criteria'][0]
    with pytest.raises(RuntimeError):
        with checks(store,run,[criterion]): raise RuntimeError('runner unavailable')
    assert run['check_runs'][0]['status']=='error' and run['results']==[]
    register_cases(store,run)
    _,raw=store.artifact_bytes(run,run['case_registration_ref'])
    record=json.loads(raw)
    assert set(record['plans'])=={c['id'] for c in run['baseline']['criteria']}
    run['baseline']['criteria'].append(deepcopy(criterion))
    with pytest.raises(ValueError,match='重复'):register_cases(store,run)
