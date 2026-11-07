import os
import signal
import time
import uuid

from fastapi.testclient import TestClient
from acceptance.api import create_app
from acceptance.engine import Store
from acceptance.integrations.store import IntegrationStore
from acceptance.read_service import ProofReaders


def archived(root):
    store=IntegrationStore(root/'integrations')
    run=store.import_reports(str(uuid.uuid4()),'neutral',dict(repository='/neutral',revision='abc',snapshot_digest='a'*64,environment='local',scope='unit'),
        [{'id':'unit','format':'junit','raw':b'<testsuite><testcase name="ok"/></testsuite>'}],
        [dict(id='gate',kind='metric',tasks=['unit'],metric='tests.failed',threshold=0)])
    return store,run


def test_actual_proof_process_keeps_original_and_rechecks_changed_artifacts(tmp_path):
    store,run=archived(tmp_path);original=(store.path(run['id'])/'run.json').read_bytes()
    readers=ProofReaders(tmp_path)
    try:
        future=readers.submit('contract',run['id'])
        assert readers.submit('contract',run['id']) is future
        assert future.result(timeout=30)['gate']['decision']=='allow'
        (store.path(run['id'])/'artifacts'/run['tasks'][0]['report_ref']).write_text('changed')
        result=readers.submit('contract',run['id']).result(timeout=30)
        assert result['gate']['decision']=='inconclusive' and result['gate']['recorded_decision']=='allow'
        assert result['provenance']['evidence_verified_now'] is False
        assert (store.path(run['id'])/'run.json').read_bytes()==original
    finally:readers.close()


def test_api_lifespan_uses_proof_worker_and_keeps_metadata_reads_available(tmp_path):
    store,run=archived(tmp_path);app=create_app(Store(tmp_path))
    with TestClient(app) as client:
        assert app.state.proof_readers is not None
        response=client.get(f"/api/runs/{run['id']}/result-contract")
        assert response.status_code==200 and response.json()['gate']['decision']=='allow'
        assert client.get('/api/health').status_code==200
        assert client.get('/api/catalogue?limit=50').status_code==200
        assert client.get('/api/runs/int-0000000000000000').status_code==404
    assert app.state.proof_readers is None


def test_live_catalogue_does_not_scan_run_envelopes_on_request(tmp_path,monkeypatch):
    store,run=archived(tmp_path);native=Store(tmp_path);app=create_app(native)
    with TestClient(app) as client:
        indexer=app.state.history_indexer;indexer.close()  # Freeze the indexer for this assertion only.
        monkeypatch.setattr(native,'sync_history',lambda **kw: (_ for _ in ()).throw(AssertionError('HTTP synchronously traversed history')))
        response=client.get('/api/catalogue?limit=50')
        assert response.status_code==200 and response.json()['index_status']['state']=='ready'


def test_killed_proof_process_can_be_replaced_on_a_new_read(tmp_path):
    store,run=archived(tmp_path);readers=ProofReaders(tmp_path)
    try:
        assert readers.submit('contract',run['id']).result(timeout=30)['gate']['decision']=='allow'
        old=readers.pool
        # Only this test's private child process is killed; no API/worker/target.
        process=next(iter(old._processes.values()));os.kill(process.pid,signal.SIGKILL)
        deadline=time.monotonic()+5
        while not old._broken and time.monotonic()<deadline:time.sleep(.02)
        assert old._broken
        assert readers.submit('contract',run['id']).result(timeout=30)['gate']['decision']=='allow'
        assert readers.pool is not old
    finally:readers.close()
