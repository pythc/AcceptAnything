import asyncio
import sys
import uuid
from pathlib import Path
import pytest
from acceptance.universal import scenario
from acceptance.universal.python_imports import load
from acceptance.universal.generation import validate
from acceptance.planning.models import Document


@pytest.mark.parametrize('regular',[False,True])
@pytest.mark.parametrize('layout',['src','flat'])
def test_relative_import_across_namespace_segment(tmp_path,monkeypatch,regular,layout):
    monkeypatch.setattr(sys,'path',list(sys.path))
    name='calibration_'+uuid.uuid4().hex
    base=tmp_path/'src' if layout=='src' else tmp_path
    pkg=base/name;(pkg/'namespace').mkdir(parents=True)
    if regular:(pkg/'__init__.py').write_text('')
    (pkg/'constants.py').write_text('VALUE="observed through a relative import"')
    file=pkg/'namespace'/'worker.py';file.write_text('from ..constants import VALUE\ndef read(): return VALUE\n')
    result=asyncio.run(scenario.execute(dict(steps=[dict(id='read',op='call',module=file.relative_to(tmp_path).as_posix(),export='read')],cleanup=[]),tmp_path))
    assert result['status']=='completed'
    assert result['steps'][0]['value']=='observed through a relative import'
    assert result['temporary_directory_removed'] is True


def test_import_identity_does_not_silently_reuse_another_checkout(tmp_path,monkeypatch):
    monkeypatch.setattr(sys,'path',list(sys.path));name='same_'+uuid.uuid4().hex
    a=tmp_path/'a';b=tmp_path/'b';a.mkdir();b.mkdir()
    (a/(name+'.py')).write_text('VALUE="a"')
    (b/(name+'.py')).write_text('raise RuntimeError("must not run a mismatched binding")')
    assert load(a,name+'.py').VALUE=='a'
    with pytest.raises(ValueError,match='different file'):load(b,name+'.py')
    with pytest.raises(ValueError,match='outside target'):load(b,'../a/'+name+'.py')


def test_configuration_readback_needs_an_explicit_property_basis():
    quote='This component can be reused by alternative implementations.'
    case=dict(id='case',title='构造后读回名称',unit='u',kind='scenario',expected=None,flow=dict(steps=[dict(id='obj',op='call',module='module.py',export='Settings',args=['example']),dict(id='name',op='get',target='obj',member='name')],checks=[dict(step='name',expected='example')]))
    proposal=dict(requirements=[dict(id='r',title='组件可复用',source='D1',quote=quote,cases=[case])])
    target=dict(units=[dict(id='u',runtime='python',capabilities=['scenario'])],interfaces=[dict(unit='u',path='module.py',functions=[dict(name='Settings',kind='class')])],execution_contract=dict(version=9))
    docs=[Document(id='D1',title='标准',content=quote)]
    rows,issues,_=validate(proposal,docs,target)
    assert rows[0]['cases']==[] and any('仅构造对象' in i['reason'] for i in issues)
    target['execution_contract']['version']=8
    assert len(validate(proposal,docs,target)[0][0]['cases'])==1
    target['execution_contract']['version']=9
    quote='The name property returns the supplied name, for example "example".'
    docs=[Document(id='D1',title='标准',content=quote)];proposal['requirements'][0]['quote']=quote
    rows,issues,_=validate(proposal,docs,target)
    assert len(rows[0]['cases'])==1 and not issues
