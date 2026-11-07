import httpx
import pytest
from acceptance.integrations.services import Service
from acceptance.github_gate import publish


@pytest.mark.parametrize('decision,state', [('allow','success'),('reject','failure'),('inconclusive','error')])
def test_status_roundtrip_is_bound_to_pr_head(monkeypatch, decision, state):
    monkeypatch.setenv('TEST_GH_TOKEN','synthetic')
    sha='a'*40;requests=[]
    def handle(request):
        requests.append(request)
        if '/pulls/' in request.url.path:
            return httpx.Response(200,json={'state':'open','base':{'repo':{'full_name':'owner/repo'}},'head':{'sha':sha}})
        if request.method=='POST':return httpx.Response(201,json={'id':12,'state':state,'context':'acceptance-agent/full'})
        return httpx.Response(200,json=[{'id':12,'state':state}])
    def receipt(*args):
        assert args[3:]==(sha,'full')
        return dict(decision=decision,revision=sha,exit_code={'allow':0,'reject':1,'inconclusive':2}[decision])
    monkeypatch.setattr('acceptance.github_gate.receipt',receipt)
    service=Service('https://api.github.com','TEST_GH_TOKEN','github',httpx.MockTransport(handle))
    try:
        result=publish(service,None,None,'run-example','owner/repo',1)
        assert result['status_state']==state and not result['stale']
        posts=[r for r in requests if r.method=='POST']
        assert len(posts)==1 and posts[0].url.path.endswith('/statuses/'+sha)
    finally:service.close()


def test_moved_head_does_not_publish_old_success(monkeypatch):
    monkeypatch.setenv('TEST_GH_TOKEN','synthetic');reads=[]
    def handle(request):
        assert request.method=='GET';reads.append(request)
        return httpx.Response(200,json={'state':'open','base':{'repo':{'full_name':'owner/repo'}},'head':{'sha':('a' if len(reads)==1 else 'b')*40}})
    monkeypatch.setattr('acceptance.github_gate.receipt',lambda *a:{'decision':'allow'})
    service=Service('https://api.github.com','TEST_GH_TOKEN','github',httpx.MockTransport(handle))
    try:
        with pytest.raises(ValueError,match='已更新'):publish(service,None,None,'run-x','owner/repo',1)
    finally:service.close()


def test_unknown_write_is_not_retried(monkeypatch):
    monkeypatch.setenv('TEST_GH_TOKEN','synthetic');posts=[]
    def handle(request):
        if request.method=='POST':
            posts.append(request);raise httpx.ReadTimeout('unknown outcome')
        return httpx.Response(200,json={'state':'open','base':{'repo':{'full_name':'owner/repo'}},'head':{'sha':'a'*40}})
    monkeypatch.setattr('acceptance.github_gate.receipt',lambda *a:{'decision':'allow'})
    service=Service('https://api.github.com','TEST_GH_TOKEN','github',httpx.MockTransport(handle))
    try:
        with pytest.raises(httpx.ReadTimeout):publish(service,None,None,'run-x','owner/repo',1)
        assert len(posts)==1
    finally:service.close()
