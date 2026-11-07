"""Protocol and ambiguity regressions. Optional SDK environment uses requirements-agent.lock.txt."""
import asyncio
import base64
from concurrent.futures import ThreadPoolExecutor
from copy import deepcopy
import hashlib
import json
from pathlib import Path
import sys
import uuid

import httpx
import pytest

pytest.importorskip('mcp')
from mcp import ClientSession
from mcp.client.stdio import StdioServerParameters, stdio_client
from jsonschema import validate

from agent_tools.journal import Journal, digest
from agent_tools.models import Result, ToolFailure
from agent_tools.service import Tools, DEFINITIONS


RID = 'int-' + 'a'*16
PID = 'auto-' + 'b'*16
DIGEST = 'c'*64


def request_id():
    return str(uuid.uuid4())


def view():
    return dict(id=RID, integrity=True, source={}, job=None, pipeline=[],
                result_contract=dict(execution={'state': 'completed'}, coverage={'state': 'partial'},
                    findings={'counts': {'needs_review': 3, 'confirmed': 0}}, gate={'decision': 'inconclusive'}, provenance={}),
                findings=[{'id': 'F-001'}], artifacts=[], baseline={'criteria': []}, results=[], inspections={}, case_plans={})


class Backend:
    def __init__(self):
        self.writes = []
        self.service_id = 'service-one'
        self.lost = False
        self.status = view()
        self.rows = [{'id': f'F-{i:03}', 'review_state': state} for i, state in enumerate(['false_positive', 'needs_review', 'confirmed'], 1)]
        self.raw = '第一行\n第二行\n'.encode()
        self.artifact = dict(id='art-one', size=len(self.raw), sha256=hashlib.sha256(self.raw).hexdigest(), name='result.txt')

    def handle(self, req):
        path = req.url.path
        if req.method == 'POST':
            self.writes.append((path, json.loads(req.content)))
            if self.lost:
                raise httpx.ReadTimeout('response lost')
            if path == '/api/acceptance/plan':
                return httpx.Response(200, json={'id': PID, 'digest': DIGEST, 'ready': True, 'blockers': []})
            return httpx.Response(202, json={'id': RID, 'job_id': 'job-one'})
        if path == '/api/agent/context':
            return httpx.Response(200, json={'service_id': self.service_id, 'tools_contract': 'acceptanything-tools-v1', 'scope': 'local-self-hosted'})
        if path.endswith('/result-contract'):
            return httpx.Response(200, json={'requirements': [{'id': 'R1'}, {'id': 'R2'}], 'observations': []})
        if '/artifacts/' in path:
            # Deliberately emulate a server ignoring Range: exact chunking must still work.
            return httpx.Response(200, content=self.raw)
        if path == '/api/runs/'+RID:
            result = deepcopy(self.status)
            offset = int(req.url.params.get('offset', 0)); limit = int(req.url.params.get('limit', 1))
            result['findings'] = self.rows[offset:offset+limit]
            result['finding_page'] = dict(total=len(self.rows), snapshot_digest=digest(self.rows))
            result['artifacts'] = [self.artifact]
            return httpx.Response(200, json=result)
        return httpx.Response(404, json={'detail': 'missing'})


def tools(tmp_path, backend, **kwargs):
    client = httpx.AsyncClient(base_url='http://127.0.0.1:18890', transport=httpx.MockTransport(backend.handle))
    return Tools('http://127.0.0.1:18890', tmp_path/'journal.db', roots=[tmp_path], client=client, **kwargs)


def call(service, name, **args):
    response = asyncio.run(service.call(name, args))
    validate(response, Result.model_json_schema())
    return response


@pytest.mark.parametrize('args', [{}, {'repository': '.'}, {'repository': '/a', 'remote_url': 'https://github.com/a/b'}, {'request_id': 'invalid'}, {'unexpected': True}])
def test_invalid_writes_never_reach_backend(tmp_path, args):
    backend = Backend(); t = tools(tmp_path, backend, allow_writes=True)
    assert call(t, 'acceptance_prepare', **args)['error']['code'] == 'invalid_input'
    assert not backend.writes


def test_read_only_connection_and_path_escape(tmp_path):
    backend = Backend(); t = tools(tmp_path, backend)
    assert call(t, 'acceptance_prepare', request_id=request_id(), repository=str(tmp_path))['error']['code'] == 'permission_denied'
    t.allow_writes = True
    link = tmp_path/'escape'; link.symlink_to(tmp_path.parent)
    assert call(t, 'acceptance_prepare', request_id=request_id(), repository=str(link))['error']['code'] == 'permission_denied'
    assert not backend.writes


def test_write_replay_conflict_restart_and_exact_plan_binding(tmp_path):
    backend = Backend(); t = tools(tmp_path, backend, allow_writes=True); rid = request_id()
    args = dict(request_id=rid, repository=str(tmp_path))
    first = call(t, 'acceptance_prepare', **args)
    assert first['data']['model_design_state'] == 'not_started'
    assert call(t, 'acceptance_prepare', **args) == first
    other = tools(tmp_path, backend, allow_writes=True)
    assert call(other, 'acceptance_prepare', **args) == first
    assert len(backend.writes) == 1
    assert call(t, 'acceptance_prepare', request_id=rid, repository=str(tmp_path), ref='main')['error']['code'] == 'invalid_input'
    assert call(t, 'acceptance_prepare', request_id=rid, remote_url='https://github.com/a/b')['error']['code'] == 'conflict'
    assert call(t, 'acceptance_start', request_id=request_id(), plan_id=PID, confirmed_plan_digest='d'*64)['error']['code'] == 'permission_denied'
    t.roots = ()
    assert call(t, 'acceptance_start', request_id=request_id(), plan_id=PID, confirmed_plan_digest=DIGEST)['error']['code'] == 'permission_denied'
    t.roots = (tmp_path,)
    started = call(t, 'acceptance_start', request_id=request_id(), plan_id=PID, confirmed_plan_digest=DIGEST)
    assert started['data']['accepted'] and len(backend.writes) == 2
    backend.service_id = 'other-service'
    assert call(t, 'acceptance_start', request_id=request_id(), plan_id=PID, confirmed_plan_digest=DIGEST)['error']['code'] == 'permission_denied'


def test_lost_response_is_never_replayed(tmp_path):
    backend = Backend(); backend.lost = True; t = tools(tmp_path, backend, allow_writes=True); rid = request_id()
    args = dict(request_id=rid, repository=str(tmp_path))
    failed = call(t, 'acceptance_prepare', **args)
    assert failed['error']['code'] == 'outcome_unknown' and not failed['error']['retry_safe']
    backend.lost = False
    assert call(tools(tmp_path, backend, allow_writes=True), 'acceptance_prepare', **args) == failed
    assert len(backend.writes) == 1
    assert call(t, 'acceptance_operation', request_id=rid)['data']['response'] == failed
    assert call(t, 'acceptance_operation', request_id=rid)['data']['state'] == 'outcome_unknown'


def test_crash_after_claim_and_concurrent_claims(tmp_path):
    journal = Journal(tmp_path/'journal.db'); rid = request_id()
    def claim(_):
        try:
            return journal.claim(rid, {'input': 1})
        except ToolFailure as exc:
            return exc.error.code
    with ThreadPoolExecutor(max_workers=4) as pool:
        rows = list(pool.map(claim, range(8)))
    assert rows.count(None) == 1 and rows.count('outcome_unknown') == 7
    with pytest.raises(ToolFailure, match='尚无确定回执'):
        Journal(journal.path).claim(rid, {'input': 1})


def test_all_finding_classes_pagination_and_stale_cursor(tmp_path):
    backend = Backend(); t = tools(tmp_path, backend)
    collected=[]; cursor=None
    for _ in range(3):
        data = call(t, 'acceptance_items', run_id=RID, collection='findings', cursor=cursor, page_size=1)['data']
        collected.extend(data['items']);cursor=data['page']['next_cursor']
    assert data['page']['complete'] and len(collected) == 3 and collected[0]['review_state'] == 'false_positive'
    first = call(t, 'acceptance_items', run_id=RID, collection='findings', page_size=1)['data']
    backend.rows[0]['review_state'] = 'test_issue'
    stale = call(t, 'acceptance_items', run_id=RID, collection='findings', cursor=first['page']['next_cursor'])
    assert stale['error']['code'] == 'stale_cursor'
    wrong = call(t, 'acceptance_items', run_id=RID, collection='requirements', cursor=first['page']['next_cursor'])
    assert wrong['error']['code'] == 'invalid_input'


def test_completed_execution_never_becomes_release(tmp_path):
    backend = Backend(); t = tools(tmp_path, backend)
    data = call(t, 'acceptance_status', run_id=RID)['data']
    assert data['execution']['state'] == 'completed' and data['gate']['decision'] == 'inconclusive'
    assert data['findings']['counts']['confirmed'] == 0


def test_raw_evidence_chunks_preserve_bytes_and_bind_digest(tmp_path):
    backend = Backend(); t = tools(tmp_path, backend); args=dict(run_id=RID,artifact_id='art-one',expected_sha256=backend.artifact['sha256'],length=5)
    offset=0;raw=bytearray()
    while True:
        response=call(t,'acceptance_evidence',**args,offset=offset)
        assert response['ok'],response
        data=response['data'];raw.extend(base64.b64decode(data['bytes_base64']))
        if data['complete']:break
        offset=data['next_offset']
    assert raw==backend.raw
    assert call(t,'acceptance_evidence',**{**args,'expected_sha256':'0'*64})['error']['code']=='invalid_evidence'
    backend.raw=b'corrupt'
    assert call(t,'acceptance_evidence',**{**args,'length':65536})['error']['code']=='invalid_evidence'


@pytest.mark.parametrize('url',['https://127.0.0.1:18890','http://localhost:18890','http://evil.example','http://user:pass@127.0.0.1','http://127.0.0.1/api'])
def test_backend_cannot_redirect_agent_to_remote_service(tmp_path,url):
    with pytest.raises(ValueError):Tools(url,tmp_path/'j.db')


def test_real_stdio_sdk_roundtrip_and_error_schema(tmp_path):
    async def run():
        params=StdioServerParameters(command=sys.executable,args=['-m','agent_tools','--journal',str(tmp_path/'stdio.db')],cwd=str(Path(__file__).parents[1]))
        async with stdio_client(params) as (read,write):
            async with ClientSession(read,write) as session:
                await session.initialize();listed=await session.list_tools()
                assert len(listed.tools)==len(DEFINITIONS)==12
                for tool in listed.tools:
                    assert tool.inputSchema['additionalProperties'] is False and tool.outputSchema
                    assert tool.outputSchema['$defs'].get('Error')
                out=await session.call_tool('acceptance_status',{'run_id':'../escape'})
                assert out.isError and out.structuredContent['error']['code']=='invalid_input'
                validate(out.structuredContent,Result.model_json_schema())
    asyncio.run(run())


def test_real_api_prepare_start_cancel_uses_isolated_store(tmp_path):
    """Exercise existing business entry points; no worker or model is started."""
    from acceptance.api import create_app
    from acceptance.engine import Store
    from acceptance.jobs import Jobs

    repo = tmp_path/'repo'; repo.mkdir()
    (repo/'pyproject.toml').write_text('[project]\nname="agent-tool-calibration"\nversion="1.0"')
    (repo/'api.py').write_text('raise RuntimeError("MUST NOT IMPORT")\ndef twice(n): return n*2\n')
    (repo/'README.md').write_text('twice 的输入为整数 2 时，输出必须为整数 4。')
    before = {p.name: p.read_bytes() for p in repo.iterdir()}
    backend_root = tmp_path/'backend'
    app = create_app(Store(backend_root))

    async def run():
        client = httpx.AsyncClient(base_url='http://127.0.0.1:18890', transport=httpx.ASGITransport(app=app))
        t = Tools('http://127.0.0.1:18890', tmp_path/'real.db', roots=[repo], allow_writes=True, client=client)
        try:
            prepared = await t.call('acceptance_prepare', dict(request_id=request_id(), repository=str(repo)))
            assert prepared['ok'], prepared
            plan = prepared['data']['plan']
            args = dict(request_id=request_id(), plan_id=plan['id'], confirmed_plan_digest=plan['digest'])
            started = await t.call('acceptance_start', args)
            assert started['ok'], started
            assert await t.call('acceptance_start', args) == started
            job_id = started['data']['job_id']
            cancelled = await t.call('acceptance_cancel', dict(request_id=request_id(), job_id=job_id))
            assert cancelled['ok'], cancelled
            events = await t.call('acceptance_events', dict(job_id=job_id))
            assert events['ok'] and events['data']['items']
        finally:
            await t.close()
    asyncio.run(run())
    jobs = Jobs(backend_root/'jobs').list()
    assert len(jobs) == 1 and jobs[0]['state'] == 'cancelled'
    assert before == {p.name: p.read_bytes() for p in repo.iterdir()}
