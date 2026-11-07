"""Provider budgets, complete large response evidence and unknown-state boundaries."""
import copy
import importlib.util
import json
import os
from pathlib import Path
import sys

import httpx
import pytest

ROOT=Path(__file__).resolve().parents[1]
DRIVERS=Path(os.environ.get('ACCEPTANCE_BUDGET_DRIVER_DIR',ROOT/'acceptance/planning'))


def module(name,monkeypatch):
    label='acceptance.planning.model_budget' if name=='model_budget' else 'acceptance.planning.d040_budget_provider'
    spec=importlib.util.spec_from_file_location(label,DRIVERS/(name+'.py'));value=importlib.util.module_from_spec(spec)
    monkeypatch.setitem(sys.modules,label,value);spec.loader.exec_module(value);return value


def capabilities(**changes):
    row=dict(id='deepseek-flash',context_window=1048576,max_output_tokens=393216,effort={'supported_levels':['low','high','max']},output_modalities=['text']);row.update(changes)
    return json.dumps({'data':[row]})


def test_budget_uses_declared_capabilities_and_large_inputs_have_no_old_byte_ceiling(monkeypatch):
    budget=module('model_budget',monkeypatch)
    messages=[dict(role='system',content='rules'),dict(role='user',content='x'*700000)]
    result=budget.calculate(capabilities(),'deepseek-flash','high',messages,'https://api.deepseek.com/models')
    assert 32768<result['selected_output_tokens']<393216
    small=budget.calculate(capabilities(),'deepseek-flash','high',[dict(role='user',content='input')],'https://api.deepseek.com/models')
    assert small['selected_output_tokens']==393216
    for invalid in [capabilities(max_output_tokens=True),capabilities(context_window=1000),capabilities(id='deepseek-v4-pro'),capabilities(effort=None),capabilities(output_modalities=None)]:
        with pytest.raises(ValueError):budget.calculate(invalid,'deepseek-flash','high',messages,'https://api.deepseek.com/models')


def test_budget_evidence_replay_rejects_parameter_and_capability_changes(monkeypatch):
    budget=module('model_budget',monkeypatch)
    wrapper=dict(model='deepseek-flash',provider='deepseek',reasoning_effort='high',system='rules',prompt={'documents':[]})
    messages=[dict(role='system',content=wrapper['system']),dict(role='user',content=json.dumps(wrapper['prompt'],ensure_ascii=False))]
    frozen=budget.calculate(capabilities(),wrapper['model'],'high',messages,'https://api.deepseek.com/models');frozen['observed_at']='2026-10-25T00:00:00Z'
    wrapper.update(generation_budget=frozen,request_parameters=dict(model=wrapper['model'],response_format={'type':'json_object'},stream=False,reasoning_effort='high',thinking={'type':'enabled'},max_tokens=frozen['selected_output_tokens']))
    receipt=dict(generation_budget=copy.deepcopy(frozen));budget.verify(wrapper,receipt)
    bad=copy.deepcopy(wrapper);bad['request_parameters']['max_tokens']=32768
    with pytest.raises(ValueError):budget.verify(bad,receipt)
    bad=copy.deepcopy(wrapper);bad['generation_budget']['context_window']+=1
    with pytest.raises(ValueError):budget.verify(bad,receipt)


@pytest.mark.parametrize('fault',['none','timeout','http400','truncated'])
def test_real_provider_path_spools_full_response_and_preserves_terminal_states(tmp_path,monkeypatch,fault):
    budget=module('model_budget',monkeypatch);provider=module('provider',monkeypatch)
    from acceptance.integrations.store import IntegrationStore
    from acceptance.planning.models import DraftInput
    from acceptance.planning import calls
    for key in ('BASE_URL','MODEL','KEY_FILE','PROVIDER','REASONING_EFFORT','TIMEOUT_SECONDS','CONFIG_FILE'):monkeypatch.delenv('ACCEPTANCE_PLANNER_'+key,raising=False)
    key=tmp_path/'key';key.write_text('test-private-model-key')
    config=tmp_path/'connection.json';config.write_text(json.dumps(dict(base_url='https://api.deepseek.com',model='deepseek-flash',provider='deepseek',reasoning_effort='high',key_file=str(key))))
    monkeypatch.setenv('ACCEPTANCE_PLANNER_CONFIG_FILE',str(config))
    repository=tmp_path/'repository';repository.mkdir();(repository/'api.py').write_text('def twice(value): return value*2')
    basis='输入整数2返回整数4。'
    documents=[dict(id='D1',title='独立依据',content=basis+'x'*160000)]+[dict(id='D'+str(i),title='背景资料',content='x'*160000) for i in range(2,5)]
    target=dict(units=[dict(id='unit',runtime='python',path='.',capabilities=['module'])],interfaces=[dict(unit='unit',path='api.py',functions=[dict(name='twice')])],execution_contract={'version':16})
    data=DraftInput(repository=str(repository),scope='数值功能验收',documents=documents,universal_target=target)
    output=dict(requirements=[dict(id='R1',title='整数输入返回结果',source='D1',quote=basis,cases=[dict(id='C1',title='输入2返回4',unit='unit',kind='module',module='api.py',function='twice',args=[2],expected=4)])])
    requests=[];raw=None
    def respond(request):
        nonlocal raw
        requests.append(request)
        if request.method=='GET':return httpx.Response(200,content=capabilities())
        body=json.loads(request.content)
        assert body['model']=='deepseek-flash' and body['reasoning_effort']=='high' and body['max_tokens']>32768
        if fault=='timeout':raise httpx.ReadTimeout('must-not-leak-secret-url')
        if fault=='http400':return httpx.Response(400,text='known rejection')
        raw=json.dumps(dict(model='deepseek-flash',choices=[dict(finish_reason='length' if fault=='truncated' else 'stop',message=dict(content=json.dumps(output),reasoning_content='r'*1200000))])).encode()
        return httpx.Response(200,content=raw,headers={'X-Request-Id':'budget-request'})
    Client=httpx.Client;monkeypatch.setattr(provider.httpx,'Client',lambda **kwargs:Client(transport=httpx.MockTransport(respond),**kwargs))
    store=IntegrationStore(tmp_path/'store')
    if fault=='none':
        result=provider.draft(store,data);assert result['connection']['verified'] and result['requirements'][0]['cases'][0]['expected']==4
    else:
        with pytest.raises(ValueError):provider.draft(store,data)
    assert [r.method for r in requests]==['GET','POST']
    receipt=json.loads(next((store.root/'model-calls').glob('*.json')).read_bytes())
    wrapper=json.loads(next((store.root/'model-inputs').glob('*.json')).read_bytes());budget.verify(wrapper,receipt)
    assert 'test-private-model-key' not in json.dumps(wrapper)
    assert wrapper['request_parameters']['max_tokens']==receipt['generation_budget']['selected_output_tokens']
    if fault in {'none','truncated'}:
        saved=(store.root/'model-responses'/receipt['response_file']).read_bytes();assert saved==raw and len(saved)>1048576
        assert not calls.pending(store)
        assert receipt['state']==('validated' if fault=='none' else 'rejected')
    else:
        assert receipt['state']==('upstream_unknown' if fault=='timeout' else 'failed')
        assert bool(calls.pending(store))==(fault=='timeout')
