import json
from pathlib import Path
import httpx
import pytest
from acceptance.planning import provider
from acceptance.planning.config import load
from acceptance.planning.models import DraftInput
from acceptance.integrations.store import IntegrationStore


def test_gateway_deadline_is_not_assumed_safe_until_terminal_audit(connected,monkeypatch):
    config,file,data,spec,store=connected
    Client=httpx.Client
    monkeypatch.setattr(provider.httpx,'Client',lambda **kwargs:Client(transport=httpx.MockTransport(lambda r:httpx.Response(504,json={'detail':'deadline'})),**kwargs))
    with pytest.raises(ValueError,match='504'):provider.draft(store,data)
    receipt=json.loads(next((store.root/'model-calls').glob('*.json')).read_text())
    assert receipt['state']=='upstream_unknown' and not provider.status(store)['blocked']
    assert provider.status(store)['duplicate_confirmation_required']
    with pytest.raises(ValueError,match='相同输入'):provider.draft(store,data)


@pytest.fixture
def connected(tmp_path,monkeypatch):
    for key in ('BASE_URL','MODEL','KEY_FILE','PROVIDER','REASONING_EFFORT','TIMEOUT_SECONDS','CONFIG_FILE'):
        monkeypatch.delenv('ACCEPTANCE_PLANNER_'+key,raising=False)
    key=tmp_path/'key';key.write_text('private-test-key');key.chmod(0o600)
    file=tmp_path/'connection.json';config=dict(base_url='http://127.0.0.1:5005/test/v1',model='gpt-6-thinking',provider='chat2api',reasoning_effort='high',key_file=str(key),timeout_seconds=600)
    file.write_text(json.dumps(config));monkeypatch.setenv('ACCEPTANCE_PLANNER_CONFIG_FILE',str(file))
    repository=tmp_path/'repo';repository.mkdir();(repository/'math.mjs').write_text('export function accepts(value){return value>=10 && value<=20}')
    text='只接受10至20的数值，包含边界。'
    data=DraftInput(repository=str(repository),scope='数值范围',documents=[dict(id='PRD',title='独立依据',content=text)])
    spec=dict(title='生成范围验证',scope='数值范围',environment=data.environment.model_dump(),requirements=[dict(id='R1',title='数值区间',source='PRD',quote=text,scenarios=[dict(id='S1',title='边界',engine='module',dimension='boundary',boundary=dict(variable='n',minimum=10,maximum=20),steps=[dict(kind='call',module='math.mjs',function='accepts',args=['${n}'],assertions=[dict(value='${expected}')])])])])
    return config,file,data,spec,IntegrationStore(tmp_path/'store')


@pytest.mark.parametrize('fault',['none','pro','strength','missing','truncated','transport','status','oversize'])
def test_high_is_explicit_and_mismatches_fail_closed(connected,monkeypatch,fault):
    config,file,data,spec,store=connected
    requests=[]
    def respond(request):
        requests.append(request)
        body=json.loads(request.content)
        assert body['model']=='gpt-6-thinking' and body['reasoning_effort']=='high'
        assert body['auto_continue'] is False and body['stream'] is False
        assert request.headers['Authorization']=='Bearer private-test-key'
        assert 'return value>=' not in request.content.decode()
        if fault=='transport':raise httpx.ReadTimeout('private-url?secret=must-not-leak')
        if fault=='status':return httpx.Response(502,text='private-upstream-error')
        if fault=='oversize':return httpx.Response(200,content=b'x'*1048577)
        raw=dict(model='gpt-6-pro' if fault=='pro' else 'gpt-6-thinking',thinking_effort='standard' if fault=='strength' else 'extended',choices=[dict(finish_reason='length' if fault=='truncated' else 'stop',message=dict(content=json.dumps(spec)))])
        if fault=='missing':raw.pop('thinking_effort')
        return httpx.Response(200,json=raw,headers={'X-Request-Id':'gateway-test-id'})
    Client=httpx.Client
    monkeypatch.setattr(provider.httpx,'Client',lambda **kwargs:Client(transport=httpx.MockTransport(respond),**kwargs))
    if fault=='none':
        draft=provider.draft(store,data)
        assert draft['connection']['verified'] is True
        assert draft['connection']['server_request_id']=='gateway-test-id'
        assert provider.status()['label']=='GPT-6 Thinking · High'
        assert 'private-test-key' not in json.dumps(draft)
        assert 'private-test-key' not in next((store.root/'drafts').glob('*.json')).read_text()
    else:
        with pytest.raises(ValueError) as error:provider.draft(store,data)
        assert 'private-url' not in str(error.value) and 'private-upstream-error' not in str(error.value)
        assert not (store.root/'drafts').exists()
    assert len(requests)==1


@pytest.mark.parametrize('field,value',[('model','gpt-6-pro'),('reasoning_effort','medium'),('base_url','http://example.com/v1'),('base_url','https://u:p@example.com/v1')])
def test_connection_rejects_pro_wrong_strength_and_credential_url(connected,field,value):
    config,file,*_=connected;config[field]=value;file.write_text(json.dumps(config))
    with pytest.raises(ValueError):load()


def test_connection_public_status_omits_credentials_and_private_route(connected):
    config,file,*_=connected
    public=provider.status()
    assert 'key_file' not in public and 'base_url' not in public


def test_existing_env_key_is_read_at_call_time_and_other_values_never_leave(connected,monkeypatch):
    config,file,data,spec,store=connected
    secret=Path(config['key_file']);secret.write_text('OTHER_SECRET=never-forward-this\nLOCAL_API_KEY="rotated-key"\n')
    config['key_field']='LOCAL_API_KEY';file.write_text(json.dumps(config))
    def respond(request):
        assert request.headers['authorization']=='Bearer rotated-key'
        assert 'never-forward-this' not in request.content.decode() and 'never-forward-this' not in str(request.headers)
        return httpx.Response(200,json=dict(model='gpt-6-thinking',thinking_effort='extended',choices=[dict(finish_reason='stop',message=dict(content=json.dumps(spec)))]))
    Client=httpx.Client
    monkeypatch.setattr(provider.httpx,'Client',lambda **kwargs:Client(transport=httpx.MockTransport(respond),**kwargs))
    assert provider.draft(store,data)['connection']['verified']


def test_concurrent_draft_is_rejected_before_another_request(connected,monkeypatch):
    import fcntl
    config,file,data,spec,store=connected
    monkeypatch.setattr(provider.httpx,'Client',lambda **kwargs:pytest.fail('must not send a second request'))
    with (store.root/'.planner.lock').open('a') as lock:
        fcntl.flock(lock.fileno(),fcntl.LOCK_EX|fcntl.LOCK_NB)
        with pytest.raises(ValueError,match='已有模型'):provider.draft(store,data)


def test_client_timeout_blocks_another_generation_until_exact_terminal_audit(connected,monkeypatch):
    from acceptance.planning import calls
    config,file,data,spec,store=connected
    cid='11111111-1111-4111-8111-111111111111'
    calls.write(store,dict(client_request_id=cid,state='upstream_unknown'))
    audit=file.parent/'audit.jsonl';config['audit_file']=str(audit);file.write_text(json.dumps(config))
    audit.write_text(json.dumps(dict(client_request_id='unrelated',status=200,request_id='unrelated'))+'\n')
    calls.reconcile(store)
    assert provider.status(store)['blocked'] is True
    monkeypatch.setattr(provider.httpx,'Client',lambda **kwargs:pytest.fail('unknown request must not resubmit'))
    with pytest.raises(ValueError,match='上游状态'):provider.draft(store,data)
    audit.write_text(json.dumps(dict(client_request_id=cid,status=499,request_id='exact-terminal'))+'\n')
    calls.reconcile(store)
    assert provider.status(store)['blocked'] is False
    receipt=json.loads((store.root/'model-calls'/(cid+'.json')).read_text())
    assert receipt['state']=='gateway_ended' and receipt['gateway_status']==499
    assert receipt['server_request_id']=='exact-terminal'
    assert not (store.root/'drafts').exists()


@pytest.mark.parametrize('actual,finish,valid',[
    ('deepseek-flash','stop',True),('deepseek-v4.1-flash-1017','stop',True),
    ('deepseek-v4-pro','stop',False),('deepseek-flash-pro','stop',False),
    ('deepseek-flash','length',False),('deepseek-flash',None,False),
])
def test_official_flash_is_verified_without_claiming_actual_effort(connected,monkeypatch,actual,finish,valid):
    from acceptance.planning.verification import verified_connection, response_matches
    config,file,data,spec,store=connected
    config.update(provider='deepseek',base_url='https://api.deepseek.com',model='deepseek-flash')
    file.write_text(json.dumps(config))
    requests=[]
    def respond(request):
        requests.append(request)
        assert str(request.url)=='https://api.deepseek.com/chat/completions'
        body=json.loads(request.content)
        assert body['model']=='deepseek-flash' and body['thinking']=={'type':'enabled'}
        assert body['reasoning_effort']=='high' and body['response_format']=={'type':'json_object'}
        assert 'auto_continue' not in body and 'history_disabled' not in body
        return httpx.Response(200,json=dict(model=actual,choices=[dict(finish_reason=finish,message=dict(content=json.dumps(spec)))]))
    Client=httpx.Client
    monkeypatch.setattr(provider.httpx,'Client',lambda **kwargs:Client(transport=httpx.MockTransport(respond),**kwargs))
    if valid:
        result=provider.draft(store,data);c=result['connection']
        assert verified_connection(c) and c['actual_thinking_effort'] is None
        assert '未回传实际强度' in c['verification_scope']
        assert response_matches({'model':actual},c)
        assert not response_matches({'model':'deepseek-v4-pro'},c)
        assert not verified_connection({**c,'official_endpoint':False})
        assert 'private-test-key' not in json.dumps(result)
    else:
        with pytest.raises(ValueError):provider.draft(store,data)
        assert not (store.root/'drafts').exists()
    assert len(requests)==1


@pytest.mark.parametrize('change',[
    {'base_url':'https://api.deepseek.com.evil.test'}, {'base_url':'http://api.deepseek.com'},
    {'base_url':'https://api.deepseek.com/custom'}, {'model':'deepseek-v4-pro'},
    {'reasoning_effort':'medium'}, {'key_file':None},
])
def test_flash_official_identity_is_constrained(connected,change):
    config,file,*_=connected
    config.update(provider='deepseek',base_url='https://api.deepseek.com',model='deepseek-flash')
    config.update(change);file.write_text(json.dumps(config))
    with pytest.raises(ValueError):load()


def test_citation_indentation_is_grounded_and_input_and_response_are_preserved(connected,monkeypatch):
    from acceptance.planning.citations import verify_record
    config,file,data,spec,store=connected
    data.documents[0].content='接受数值\n  包含边界。';spec['requirements'][0]['quote']='接受数值\n包含边界。'
    def respond(request):
        return httpx.Response(200,json=dict(model='gpt-6-thinking',thinking_effort='extended',choices=[dict(finish_reason='stop',message=dict(content=json.dumps(spec)))]))
    Client=httpx.Client
    monkeypatch.setattr(provider.httpx,'Client',lambda **kwargs:Client(transport=httpx.MockTransport(respond),**kwargs))
    d=provider.draft(store,data);record=json.loads((store.root/'drafts'/(d['id']+'.json')).read_text())['record']
    assert verify_record(record) and len(d['citation_adjustments'])==1
    assert d['specification']['requirements'][0]['quote']==data.documents[0].content
    from acceptance.planning.models import Specification
    assert d['specification']['requirements'][0]['scenarios']==Specification.model_validate(spec).model_dump()['requirements'][0]['scenarios']
    inputs=next((store.root/'model-inputs').glob('*.json')).read_text()
    assert 'private-test-key' not in inputs
    assert json.loads(inputs)['prompt']['documents'][0]['content']==data.documents[0].content
    original=json.loads(next((store.root/'model-responses').glob('*.json')).read_text())
    assert json.loads(original['choices'][0]['message']['content'])==spec


def test_complete_verified_malformed_json_has_narrow_retry_marker(connected,monkeypatch):
    config,file,data,spec,store=connected
    config.update(provider='deepseek',base_url='https://api.deepseek.com',model='deepseek-flash')
    file.write_text(json.dumps(config));Client=httpx.Client
    response=dict(model='deepseek-flash',choices=[dict(finish_reason='stop',message=dict(content='{"requirements":['))])
    monkeypatch.setattr(provider.httpx,'Client',lambda **kwargs:Client(transport=httpx.MockTransport(lambda request:httpx.Response(200,json=response)),**kwargs))
    with pytest.raises(ValueError):provider.draft(store,data)
    receipt=json.loads(next((store.root/'model-calls').glob('*.json')).read_text())
    assert receipt['state']=='rejected' and receipt['rejection_kind']=='json_syntax'
    assert (store.root/'model-responses'/receipt['response_file']).exists()


def test_explicit_continuation_preserves_unknown_receipt_and_invalidates_on_change(connected):
    from acceptance.planning import calls
    _,_,_,_,store=connected
    cid='11111111-1111-4111-8111-111111111111'
    calls.write(store,dict(client_request_id=cid,state='upstream_unknown'))
    path=store.root/'model-calls'/(cid+'.json');original=path.read_bytes()
    assert provider.status(store)['blocked']
    audit=calls.authorize_continuation(store,cid,authorized_by='user',authorization='允许继续，旧请求保留未知')
    assert path.read_bytes()==original
    assert audit['action']=='allow_new_calls_preserve_unknown'
    status=provider.status(store)
    assert not status['blocked'] and status['acknowledged_unknown_requests']==[dict(client_request_id=cid,state='upstream_unknown')]
    with pytest.raises(FileExistsError):calls.authorize_continuation(store,cid,authorized_by='user',authorization='再次授权')
    calls.write(store,dict(client_request_id=cid,state='upstream_unknown',changed=True))
    assert provider.status(store)['blocked']


@pytest.mark.parametrize('state',['pending','response_headers','received','rejected'])
def test_continuation_never_acknowledges_live_or_terminal_calls(connected,state):
    from acceptance.planning import calls
    _,_,_,_,store=connected
    cid='11111111-1111-4111-8111-111111111111'
    calls.write(store,dict(client_request_id=cid,state=state))
    with pytest.raises(ValueError,match='仅能'):calls.authorize_continuation(store,cid,authorized_by='user',authorization='继续')
    assert not (store.root/'model-call-authorizations').exists()


def test_continuation_cannot_bypass_active_planner_lock(connected):
    import fcntl
    from acceptance.planning import calls
    _,_,_,_,store=connected
    cid='11111111-1111-4111-8111-111111111111'
    calls.write(store,dict(client_request_id=cid,state='upstream_unknown'))
    with (store.root/'.planner.lock').open('a') as lock:
        fcntl.flock(lock.fileno(),fcntl.LOCK_EX|fcntl.LOCK_NB)
        with pytest.raises(BlockingIOError):calls.authorize_continuation(store,cid,authorized_by='user',authorization='继续')
