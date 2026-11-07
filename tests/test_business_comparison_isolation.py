import base64
import json
import pytest
from acceptance.universal import runtime
from acceptance.universal.models import Case


@pytest.mark.parametrize('actual,expected,passed',[
    ('{"records":2}',{'records':2},True),
    ('[{"id":1}]',[{'id':1}],True),
    ({'records':2},'{"records":2}',True),
    ('{"records":2}',{'records':3},False),
    ('{"records":1}',{'records':True},False),
    ('{"id":9007199254740993}',{'id':9007199254740993},True),
])
def test_json_stream_preserves_structured_values_and_type(actual,expected,passed):
    frozen=json.dumps(expected)
    assert runtime.compare(actual,expected,'json_stream') is passed
    assert json.dumps(expected)==frozen


def test_unexpected_comparison_error_is_local_and_keeps_real_receipt(tmp_path,monkeypatch):
    cases=[]
    for index,expected in enumerate([2,2,3]):
        cases.append(Case(id='C'+str(index),title='独立数据库读取',unit='u',kind='scenario',expected=None,flow=dict(steps=[dict(id='read',op='call',module='reader.py',export='read')],checks=[dict(step='read',expected=expected)])).model_dump())
    run={'universal_generation':{'requirements':[dict(id='R',source='D',quote='实际记录数为二',cases=cases)]}}
    receipt=dict(status='completed',steps=[dict(id='read',status='completed',observable=True,value=2)],cleanup=[],temporary_directory_removed=True)
    def command(run,u,argv,*args,**kwargs):
        data=json.loads(base64.b64decode(argv[-1]));assert 'checks' not in data and 'expected' not in data
        return dict(exit_code=0),dict(stdout=('ACCEPTANCE_VALUE:'+json.dumps(receipt)).encode())
    original=runtime.compare;calls=0
    def compare(*args):
        nonlocal calls
        calls+=1
        if calls==1:raise AttributeError('comparison implementation error')
        return original(*args)
    monkeypatch.setattr(runtime,'command',command);monkeypatch.setattr(runtime,'compare',compare)
    report,_=runtime.business(run,dict(id='u',runtime='python'),tmp_path,lambda:False)
    assert [t['status'] for t in report['tests']]==['error','passed','failed']
    traces=json.loads((tmp_path/'cases.json').read_text())
    assert traces[0]['actual']==receipt and traces[0]['error_type']=='AttributeError'
    assert 'AttributeError' in (tmp_path/'C0'/'driver-error.log').read_text()
