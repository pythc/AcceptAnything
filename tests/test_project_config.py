import json
from pathlib import Path
import pytest
from acceptance.project_config import prepare,public
from acceptance.integrations.store import IntegrationStore
from acceptance.planning.service import create_run


def config(tmp_path):
    repo=tmp_path/'library';repo.mkdir()
    (repo/'math.py').write_text('def double(n): return n*2\n')
    (repo/'需求.txt').write_text('返回输入整数的两倍。')
    manifest={'schema_version':1,'documents':[{'id':'PRD','path':'需求.txt'}], 'include_scanners':False,
      'specification':{'title':'倍数校验','scope':'整数倍数函数','environment':{'mode':'module','runtime':'python'},'requirements':[{
        'id':'DOUBLE','title':'双倍','source':'PRD','quote':'返回输入整数的两倍。','scenarios':[{
          'id':'INTEGER','title':'整数','engine':'module','dimension':'normal','steps':[{
            'kind':'call','module':'math.py','function':'double','args':[2],'assertions':[{'value':4}]}]}]}]}}
    path=tmp_path/'external.json';path.write_text(json.dumps(manifest));return repo,path,manifest


def test_external_config_uses_arbitrary_independent_documents(tmp_path):
    repo,path,data=config(tmp_path);store=IntegrationStore(tmp_path/'data')
    plan=prepare(store,str(repo),str(path))
    assert public(plan)['kind']=='configured' and plan['ready']
    run=create_run(store,plan['id'],plan['digest'])
    assert store.snapshot(run['id'])['integrity']
    assert run['test_plan']['documents'][0]['origin']=='需求.txt'
    assert run['test_plan']['project_configuration']['content']==data


def test_configuration_drift_blocks_execution(tmp_path):
    repo,path,data=config(tmp_path);store=IntegrationStore(tmp_path/'data')
    plan=prepare(store,str(repo),str(path));path.write_text('{}')
    with pytest.raises(ValueError,match='配置已变化'):create_run(store,plan['id'],plan['digest'])


@pytest.mark.parametrize('fault',['path','tool','gate','duplicate'])
def test_invalid_project_inputs_rejected(tmp_path,fault):
    repo,path,data=config(tmp_path)
    if fault=='path':data['documents'][0]['path']='../external.json'
    if fault=='tool':
        data['tasks']=[{'id':'fake','tool':'host-shell'}];data['rules']=[{'id':'gate','kind':'metric','tasks':['fake'],'metric':'tests.failed'}]
    if fault=='gate':data['tasks']=[{'id':'test','tool':'pytest'}]
    if fault=='duplicate':data['tasks']=[{'id':'generated-pytest','tool':'pytest'}]
    path.write_text(json.dumps(data))
    with pytest.raises(ValueError):prepare(IntegrationStore(tmp_path/'data'),str(repo),str(path))
