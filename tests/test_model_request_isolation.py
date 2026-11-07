"""Unknown work remains unknown, but does not suppress unrelated acceptance."""
import json
from acceptance.planning import calls
from acceptance.integrations.store import IntegrationStore
from acceptance.integrations.runner import encode,sha


def test_unknown_input_identity_excludes_volatile_budget_but_includes_protocol(tmp_path):
    store=IntegrationStore(tmp_path);cid='11111111-1111-4111-8111-111111111111'
    data=dict(model='official',provider='deepseek',reasoning_effort='high',system='independent inputs',prompt={'documents':['A'],'protocol':18},generation_budget={'observed_at':'old'})
    folder=store.root/'model-inputs';folder.mkdir();raw=encode(data);(folder/(cid+'.json')).write_bytes(raw)
    receipt=dict(client_request_id=cid,state='upstream_unknown',input_file=cid+'.json',input_sha256=sha(raw));calls.write(store,receipt)
    before=(store.root/'model-calls'/(cid+'.json')).read_bytes()
    assert not calls.blocking(store)
    same={**data,'generation_budget':{'observed_at':'new'}}
    assert calls.blocking(store,calls.fingerprint(same))==[receipt]
    assert not calls.blocking(store,calls.fingerprint({**data,'prompt':{'documents':['B'],'protocol':18}}))
    assert not calls.blocking(store,calls.fingerprint({**data,'prompt':{'documents':['A'],'protocol':19}}))
    assert (store.root/'model-calls'/(cid+'.json')).read_bytes()==before
    assert not (store.root/'model-call-authorizations').exists()
    (folder/(cid+'.json')).write_text('{}')
    assert calls.blocking(store)==[receipt]


def test_inflight_and_unidentified_unknown_are_globally_blocking(tmp_path):
    store=IntegrationStore(tmp_path);cid='22222222-2222-4222-8222-222222222222'
    for state in ('pending','response_headers','upstream_unknown'):
        receipt=dict(client_request_id=cid,state=state);calls.write(store,receipt)
        assert calls.blocking(store,'unrelated')==[receipt]
