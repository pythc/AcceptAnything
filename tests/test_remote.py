import json
import os
from pathlib import Path
import subprocess

import pytest
from fastapi.testclient import TestClient

from acceptance import remote
from acceptance.api import create_app
from acceptance.engine import Store
from acceptance.integrations.store import IntegrationStore
from acceptance.integrations.runner import encode, sha
from acceptance.project_config import prepare, public
from acceptance.planning.service import create_run
from acceptance.planning import provider


@pytest.mark.parametrize('url', [
    'file:///tmp/repo','git@github.com:a/b','https://github.com.evil.test/a/b',
    'https://user:secret@github.com/a/b','https://github.com:443/a/b',
    'https://github.com/a/b?token=secret','https://github.com/a/b#main',
    'https://github.com/a/b/tree/main','https://gitlab.com/a/../b',
    'https://127.0.0.1/a/b','https://gitlab.com/a/%2e%2e/b',
])
def test_unsafe_or_non_repository_url_rejected(url):
    with pytest.raises(ValueError): remote.address(url)


def test_public_provider_addresses_and_nested_gitlab():
    assert remote.address('https://github.com/o/r/')['url']=='https://github.com/o/r.git'
    assert remote.address('https://gitlab.com/group/sub/repo.git')['provider']=='gitlab'


@pytest.mark.parametrize('kind,value',[('commit','abcd'),('commit','a'*40+'~'),('branch','-x'),('branch','main:evil'),('branch','a..b'),('branch','a.lock/b'),('branch','x\ny'),('branch','a@{1}'),('branch','a/../b')])
def test_unsafe_refs_rejected(kind,value):
    with pytest.raises(ValueError): remote.reference(kind,value)


@pytest.fixture
def transport(tmp_path,monkeypatch):
    """Real Git objects/checkout; only HTTPS transport redirected to a local fixture."""
    repo=tmp_path/'upstream';repo.mkdir()
    def g(*args):return subprocess.run(['git','-C',str(repo),*args],capture_output=True,text=True,check=True).stdout.strip()
    g('init','-q','-b','main');g('config','user.name','Acceptance Test');g('config','user.email','test@example.invalid')
    (repo/'README.md').write_text('返回输入整数的两倍。')
    (repo/'logic.py').write_text('def double(n): return n*2\n')
    g('add','.');g('commit','-qm','initial');old=g('rev-parse','HEAD')
    g('branch','feature/check');(repo/'later.txt').write_text('new version');g('add','.');g('commit','-qm','second')
    new=g('rev-parse','HEAD')
    original=remote.git;fetched=[]
    def translated(args,**kwargs):
        if args[0]=='ls-remote':
            return subprocess.run(['git',*['-c','protocol.file.allow=always'],*[(str(repo) if a.startswith('https://') else a) for a in args]],capture_output=True,text=True,check=True).stdout.strip()
        if args[0]=='fetch':
            fetched.append(args[-1])
            return subprocess.run(['git','-C',str(kwargs['cwd']),'-c','protocol.file.allow=always','fetch','--quiet','--depth=1','--no-tags',str(repo),args[-1]],capture_output=True,text=True,check=True).stdout.strip()
        return original(args,**kwargs)
    monkeypatch.setattr(remote,'git',translated)
    return repo,g,old,new,fetched


def test_branch_resolves_before_fetch_and_commit_is_detached(tmp_path,transport):
    repo,g,old,new,fetched=transport;store=IntegrationStore(tmp_path/'data')
    source=remote.checkout(store,'https://github.com/o/r','branch','feature/check')
    assert source['commit']==old and source['branch']=='feature/check' and fetched==[old]
    assert not (Path(source['repository'])/'later.txt').exists()
    remote.verify(store,source)
    explicit=remote.checkout(store,'https://gitlab.com/group/sub/r','commit',new)
    assert explicit['commit']==new and explicit['branch'] is None and source['repository']!=explicit['repository']


@pytest.mark.parametrize('change',['source','head','metadata'])
def test_drift_after_confirmation_rejected(tmp_path,transport,change):
    source=remote.checkout(IntegrationStore(tmp_path/'data'),'https://github.com/o/r','branch','main')
    root=Path(source['repository']);store=IntegrationStore(tmp_path/'data')
    if change=='source':(root/'logic.py').write_text('changed')
    if change=='head': subprocess.run(['git','-C',str(root),'symbolic-ref','HEAD','refs/heads/missing'],check=True)
    if change=='metadata':source['commit']='a'*40
    with pytest.raises(ValueError):remote.verify(store,source)


def test_submodules_symlinks_and_lfs_do_not_become_valid_source(tmp_path,transport):
    repo,g,*_=transport;store=IntegrationStore(tmp_path/'data')
    (repo/'link').symlink_to('/tmp');g('add','.');g('commit','-qm','symlink')
    with pytest.raises(ValueError,match='符号链接'):remote.checkout(store,'https://github.com/o/r','branch','main')
    assert not list((store.root/'remote-sources').iterdir())
    (repo/'link').unlink();(repo/'lfs.txt').write_text('version https://git-lfs.github.com/spec/v1\noid sha256:abc\n')
    g('add','-A');g('commit','-qm','lfs')
    with pytest.raises(ValueError,match='LFS'):remote.checkout(store,'https://github.com/o/r','branch','main')


def project_config(tmp_path):
    config=dict(schema_version=1,documents=[dict(id='PRD',path='README.md')],include_scanners=False,
      specification=dict(title='倍数验收',scope='双倍函数',environment=dict(mode='module',runtime='python'),requirements=[
        dict(id='DOUBLE',title='双倍',source='PRD',quote='返回输入整数的两倍。',scenarios=[
          dict(id='N',title='整数',engine='module',dimension='normal',steps=[dict(kind='call',module='logic.py',function='double',args=[2],assertions=[dict(value=4)])])])]))
    path=tmp_path/'project.json';path.write_text(json.dumps(config));return path


def test_remote_plan_freezes_into_existing_generated_pipeline_and_artifact(tmp_path,transport):
    store=IntegrationStore(tmp_path/'data');source=remote.checkout(store,'https://github.com/o/r','branch','main')
    config=project_config(tmp_path);p=prepare(store,source['repository'],str(config),remote_source=source)
    assert public(p)['remote_source']['commit']==source['commit']
    run=create_run(store,p['id'],p['digest'])
    assert run['remote_source']==source and run['context']['revision']==source['commit']
    assert run['tasks'][0]['tool']=='acceptance-generated'
    assert store.artifact_bytes(run['id'],run['remote_source_ref'])[1]==encode(source)
    from acceptance.unified import integration_view
    assert integration_view(store,run['id'])['source']['repository']['remote']==source['url']
    assert store.local_briefs()[0]['source']['repository']['id']==remote.repository_fields(source)['id']


def test_url_binding_reuses_only_identical_reviewed_snapshot(tmp_path,transport,monkeypatch):
    source=remote.checkout(IntegrationStore(tmp_path/'data'),'https://github.com/o/r','branch','main')
    (tmp_path/'var').mkdir();entry=dict(configuration='/server/project.json',reviewed_repository='/reviewed',snapshot_digest=source['snapshot_digest'])
    (tmp_path/'var/remote-project-configurations.json').write_text(json.dumps({source['url']:entry}))
    from acceptance import engine
    monkeypatch.setattr(engine,'ROOT',tmp_path)
    config,binding=remote.configured(None,source)
    assert config==entry['configuration'] and binding['reviewed_repository']=='/reviewed'
    with pytest.raises(ValueError,match='快照不同'):remote.configured(None,{**source,'snapshot_digest':'b'*64})


def test_model_relocation_does_not_bypass_documents_or_snapshot(tmp_path):
    store=IntegrationStore(tmp_path/'data');directory=store.root/'drafts';directory.mkdir()
    draft=dict(repository='/reviewed',documents=[dict(id='PRD',content='frozen')],specification={},model='gpt-6-thinking',prompt_sha256='a'*64,response_sha256='b'*64)
    (directory/('draft-'+'a'*16+'.json')).write_bytes(encode(dict(record=draft,sha256=sha(encode(draft)))))
    plan=dict(repository='/new',documents=draft['documents'],specification={},snapshot_digest='c'*64)
    with pytest.raises(ValueError):provider.provenance(store,'draft-'+'a'*16,plan)
    plan['repository_binding']=dict(reviewed_repository='/reviewed',snapshot_digest='c'*64,remote_url='https://github.com/o/r.git',commit='d'*40)
    assert provider.provenance(store,'draft-'+'a'*16,plan)['model']=='gpt-6-thinking'
    plan['documents']=[]
    with pytest.raises(ValueError):provider.provenance(store,'draft-'+'a'*16,plan)


@pytest.mark.parametrize('change',['source','commit','branch','snapshot','artifact'])
def test_remote_archive_cannot_change_displayed_identity(tmp_path,transport,change):
    store=IntegrationStore(tmp_path/'data');source=remote.checkout(store,'https://github.com/o/r','branch','main')
    plan=prepare(store,source['repository'],str(project_config(tmp_path)),remote_source=source)
    run=create_run(store,plan['id'],plan['digest'])
    assert store.snapshot(run['id'])['integrity']
    if change=='source':run['remote_source']={**source,'url':'https://github.com/o/other.git'}
    if change=='commit':run['context']['revision']='a'*40
    if change=='branch':run['context']['branch']='other'
    if change=='snapshot':run['context']['snapshot_digest']='b'*64
    if change=='artifact':run['remote_source_ref']=run['design_ref']
    store.save(run)
    assert not store.snapshot(run['id'])['integrity']


def test_transport_disables_user_git_configuration_and_sanitizes_errors(tmp_path,monkeypatch):
    fake=tmp_path/'git';fake.write_text('#!/bin/sh\necho secret-from-upstream >&2\nexit 1\n');fake.chmod(0o700)
    monkeypatch.setattr(remote,'GIT',str(fake))
    with pytest.raises(ValueError) as e:remote.git(['ls-remote','https://github.com/o/r.git'])
    assert 'secret-from-upstream' not in str(e.value)
    fake.write_text('#!/bin/sh\nprintf "%s\\n" "$GIT_CONFIG_GLOBAL" "$GIT_TERMINAL_PROMPT" "$@"\n')
    output=remote.git(['--version'])
    assert '/dev/null\n0\n' in output and 'protocol.allow=never' in output and 'http.followRedirects=false' in output


def test_api_preserves_local_and_exclusive_remote_inputs(tmp_path,transport):
    client=TestClient(create_app(Store(tmp_path/'data')))
    refs=client.post('/api/acceptance/remote/refs',json=dict(url='https://gitlab.com/group/sub/r')).json()
    assert refs['default_branch']=='main'
    assert client.post('/api/acceptance/plan',json=dict(repository='/tmp/a',remote_url='https://github.com/o/r')).status_code==422
    assert client.post('/api/acceptance/plan',json=dict(remote_url='https://github.com/o/r',command='evil')).status_code==422
    remote_plan=client.post('/api/acceptance/plan',json=dict(remote_url='https://github.com/o/r',ref_type='branch',ref='main')).json()
    assert remote_plan['kind']=='universal' and remote_plan['ready'] and remote_plan['remote_source']['commit']==transport[3]
    assert remote_plan['universal']['batches']>=1  # Prepared is not a claim that model cases have passed.
    assert client.post('/api/acceptance/runs',json=dict(plan_id=remote_plan['id'],digest=remote_plan['digest'])).status_code==202
    local=client.post('/api/acceptance/plan',json=dict(repository=str(transport[0]))).json()
    assert local['repository']==str(transport[0]) and 'remote_source' not in local
