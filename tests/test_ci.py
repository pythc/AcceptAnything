import subprocess
import pytest
from acceptance.ci import commit_matches,receipt
from acceptance.integrations.runner import sha
from acceptance.engine import Store
from acceptance.integrations.store import IntegrationStore


def gitrepo(tmp_path):
    root=tmp_path/'repo';root.mkdir()
    def git(*args):return subprocess.check_output(['git','-C',str(root),*args]).decode().strip()
    git('init','-q');git('config','user.email','synthetic@example.invalid');git('config','user.name','Synthetic control')
    (root/'app.py').write_text('value=1\n');git('add','app.py');git('commit','-qm','control')
    return root,git('rev-parse','HEAD')


def test_commit_binding_detects_dirty_or_untracked_source(tmp_path):
    root,rev=gitrepo(tmp_path)
    files=[dict(path='app.py',sha256=sha(b'value=1\n'),mode=0o644)]
    assert commit_matches(str(root),rev,files)
    files[0]['sha256']=sha(b'value=2\n')
    with pytest.raises(ValueError,match='冻结源码'):commit_matches(str(root),rev,files)
    files[0]['path']='untracked.py'
    with pytest.raises(ValueError,match='无法验证'):commit_matches(str(root),rev,files)


def test_missing_or_imported_record_never_passes(tmp_path):
    store=Store(tmp_path/'state');integrations=IntegrationStore(store.root/'integrations')
    result=receipt(store,integrations,'int-'+'a'*16,'b'*40)
    assert result['exit_code']==2 and result['github_check']['conclusion']=='failure'
    run=integrations.new('imported','import');integrations.save(run)
    result=receipt(store,integrations,run['id'],'b'*40)
    assert result['exit_code']==2 and '导入' in result['reasons'][0]
