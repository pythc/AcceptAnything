from copy import deepcopy
import pytest
from acceptance.integrations.lifecycle import prepared,DojoLifecycle

class Store:
    def __init__(self):
        self.run=dict(id='int-'+'1'*16,status='completed',integrity=True,mode='executor',scope_digest='s',
            context=dict(repository='/repo',revision='v1',snapshot_digest='a',files=[{'path':'app.py'}]),
            tasks=[dict(id='scan',tool='bandit',format='bandit',state='completed',report_ref='art-x',report=dict(complete=True,findings=[]))])
    def snapshot(self,rid):return deepcopy(self.run)|{'id':rid}
    def artifact_bytes(self,*args):return {},b'original'

class Service:
    url='http://127.0.0.1:18894/';kind='defectdojo'
    def __init__(self):self.writes=[]
    def request(self,path):return {'engagement':1}
    def dojo_import(self,*args,**kwargs):self.writes.append(kwargs);return {'test':7}
    def dojo_pull(self,tid):return {'test':{'id':7,'engagement':1},'findings':[]}

@pytest.mark.parametrize('fault',['partial','error','import','scope','integrity'])
def test_untrusted_or_partial_scans_cannot_close(fault):
    store=Store()
    if fault=='partial':store.run['tasks'][0]['report']['complete']=False
    if fault=='error':store.run['status']='error'
    if fault=='import':store.run['mode']='import'
    if fault=='scope':store.run.pop('scope_digest')
    if fault=='integrity':store.run['integrity']=False
    with pytest.raises(ValueError):prepared(store,'int-a','scan')


def test_same_scope_reimport_is_idempotent_and_drift_blocks(tmp_path):
    store=Store();service=Service();life=DojoLifecycle(tmp_path)
    life.publish(store,service,'int-a','scan',1)
    life.publish(store,service,'int-a','scan',1)
    life.publish(store,service,'int-b','scan',1)
    assert len(service.writes)==2 and service.writes[1]['close_old']
    store.run['context']['files'].append({'path':'added.py'})
    with pytest.raises(ValueError,match='范围变化'):life.publish(store,service,'int-c','scan',1)
    assert len(service.writes)==2


def test_unknown_mutation_result_is_not_retried(tmp_path,monkeypatch):
    store=Store();service=Service();life=DojoLifecycle(tmp_path)
    def fail(*args,**kw):raise TimeoutError('response lost')
    monkeypatch.setattr(service,'dojo_import',fail)
    with pytest.raises(TimeoutError):life.publish(store,service,'int-a','scan',1)
    with pytest.raises(ValueError,match='结果未知'):life.publish(store,service,'int-a','scan',1)
    assert life.list()[0]['attempts'][0]['state']=='unknown'
