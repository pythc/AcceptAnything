import time
from types import SimpleNamespace
import httpx,pytest
from acceptance.planning import model_budget
from acceptance.integrations.store import IntegrationStore
from acceptance.integrations.runner import sha


def test_partial_response_is_preserved_without_claiming_a_terminal_or_retry(tmp_path,monkeypatch):
    class Interrupted(httpx.SyncByteStream):
        def __iter__(self):
            yield b'{"choices":'
            raise httpx.ReadTimeout('remote response incomplete')
    Client=httpx.Client
    monkeypatch.setattr(model_budget.httpx,'Client',lambda **kw:Client(transport=httpx.MockTransport(lambda q:httpx.Response(200,stream=Interrupted())),**kw))
    store=IntegrationStore(tmp_path);receipt={'client_request_id':'11111111-1111-4111-8111-111111111111'}
    config=SimpleNamespace(base_url='https://api.deepseek.com',timeout_seconds=600)
    with pytest.raises(ValueError,match='未自动重试'):model_budget.receive(store,config,{},dict(model='fixed'),receipt,time.monotonic(),unbounded=True)
    raw=(store.root/'model-responses'/receipt['partial_response_file']).read_bytes()
    assert raw==b'{"choices":' and receipt['partial_response_sha256']==sha(raw)
    assert receipt['state']=='upstream_unknown' and receipt['partial_response_bytes']==len(raw)
    assert 'response_file' not in receipt
