from copy import deepcopy
import json,uuid
from pathlib import Path
import pytest
from fastapi.testclient import TestClient
from acceptance.integrations import adjudication as a
from acceptance.integrations.formats import parse
from acceptance.integrations.runner import encode,sha
from acceptance.integrations.store import IntegrationStore
from acceptance.integrations.gates import evaluate
from acceptance.integrations.api import FindingReview
from acceptance.integrations.finding_reviews import submit,latest,history


def fixture(tmp_path):
    store=IntegrationStore(tmp_path/'store');r=store.new('review calibration','executor');p=store.path(r['id'])/'source';p.mkdir()
    sources={'tests/test_rule.py':b'def test_rule():\n    assert 1 == 1\n','src/rule.py':b'assert user.is_admin\n',
        'pyproject.toml':b'[tool.pytest.ini_options]\ntestpaths=["tests"]\n[tool.hatch.build.targets.wheel]\npackages=["src/product"]\n'}
    for name,raw in sources.items():f=p/name;f.parent.mkdir(parents=True,exist_ok=True);f.write_bytes(raw)
    r.update(context=dict(repository='/calibration',snapshot_digest='a'*64,files=[dict(path=p,sha256=sha(raw)) for p,raw in sources.items()]),integrity=True)
    raw=encode(dict(results=[dict(test_id='B101',issue_text='assert detected',filename='/source/tests/test_rule.py',line_number=2,issue_severity='LOW')],errors=[],metrics={'_totals':{'loc':2}}))
    ref=store.artifact(r,'scan/report.json',raw);r['tasks']=[dict(id='scan',tool='bandit',format='bandit',state='completed',report_ref=ref,report=parse('bandit',raw),artifacts=[ref])]
    r['review_policy_ref']=store.artifact(r,'finding-review-policy.json',encode(a.policy()))
    return store,r,sources


def test_normal_pytest_assert_is_cleared_without_editing_original_report(tmp_path):
    store,r,_=fixture(tmp_path);before=deepcopy(r['tasks']);review=a.build(store,r)
    assert review['summary']==dict(raw=1,unique=1,duplicates=0,needs_review=0,false_positive=1,confirmed=0,test_issue=0,actionable=0)
    tasks=a.effective_tasks(r,review)
    rules=[dict(id='security',kind='metric',metric='findings.total',tasks=['scan'],threshold=0)]
    assert evaluate(rules,r['tasks'])[0]['status']=='failed'
    assert evaluate(rules,tasks)[0]['status']=='passed'
    assert r['tasks']==before and review['observations'][0]['evidence'][1]['sha256']


@pytest.mark.parametrize('fault',['production','line','source','missing','integrity'])
def test_uncertain_or_changed_assert_never_gets_an_exemption(tmp_path,fault):
    store,r,sources=fixture(tmp_path);p=store.path(r['id'])/'source'
    if fault=='production':r['tasks'][0]['report']['findings'][0].update(path='/source/src/rule.py',line=1)
    if fault=='line':r['tasks'][0]['report']['findings'][0]['line']=1
    if fault=='source':(p/'tests/test_rule.py').write_text('def test_rule():\n    pass\n')
    if fault=='missing':(p/'tests/test_rule.py').unlink()
    if fault=='integrity':r['integrity']=False
    if fault in {'unpackaged','root-package'}:
        raw=b'[tool.pytest.ini_options]\ntestpaths=["tests"]\n'+(b'[tool.hatch.build.targets.wheel]\npackages=["."]' if fault=='root-package' else b'')
        (p/'pyproject.toml').write_bytes(raw);next(x for x in r['context']['files'] if x['path']=='pyproject.toml')['sha256']=sha(raw)
    review=a.build(store,r)
    assert review['summary']['false_positive']==0 and review['summary']['needs_review']==1


def test_dedup_keeps_all_occurrences_and_does_not_merge_different_locations(tmp_path):
    store,r,_=fixture(tmp_path);r['tasks'].append({**deepcopy(r['tasks'][0]),'id':'scan-two'})
    review=a.build(store,r);assert review['summary']['raw']==2 and review['summary']['unique']==1 and review['summary']['duplicates']==1
    assert review['groups'][0]['occurrence_ids']==['F-001','F-002']
    r['tasks'][1]['report']['findings'][0]['line']=3
    review=a.build(store,r);assert review['summary']['unique']==2 and review['summary']['needs_review']==1


def test_dedup_does_not_clear_a_different_claim_with_same_normalized_id(tmp_path):
    store,r,_=fixture(tmp_path);first=r['tasks'][0]['report']['findings'][0]
    other={**first,'rule':'OTHER','detail':'different claim'};r['tasks'][0]['report']['findings'].append(other)
    review=a.build(store,r);tasks=a.effective_tasks(r,review)
    assert tasks[0]['report']['findings']==[other]


def test_manual_review_is_bound_idempotent_and_optimistic(tmp_path):
    store,r,_=fixture(tmp_path);r['status']='completed';store.save(r)
    data=FindingReview(request_id=str(uuid.uuid4()),state='needs_review',reason='Manual review with exact evidence and known source scope.',evidence_refs=[r['tasks'][0]['report_ref']])
    result=submit(store,r['id'],'F-001',data);assert result['recorded'] and result['gate_unchanged']
    assert submit(store,r['id'],'F-001',data)==dict(revision=result['revision'],recorded=True,gate_unchanged=True)
    with pytest.raises(ValueError,match='版本'):submit(store,r['id'],'F-001',data.model_copy(update={'request_id':str(uuid.uuid4())}))
    with pytest.raises(ValueError):submit(store,r['id'],'F-001',data.model_copy(update={'request_id':str(uuid.uuid4()),'expected_revision':result['revision'],'evidence_refs':['other']}))
    assert latest(store,r['context'])[0]['state']=='needs_review'
    frozen=a.policy(store,r['context']);assert len(frozen['manual_reviews'])==1
    r['review_policy_ref']=store.artifact(r,'next-policy.json',encode(frozen))
    assert a.build(store,r)['observations'][0]['method']=='recorded-evidence-review'
    changed={**r['context'],'snapshot_digest':'b'*64};assert latest(store,changed)==[]


def test_review_history_retains_superseded_opinions_and_validates_chain(tmp_path):
    store,r,_=fixture(tmp_path);r['status']='completed';store.save(r)
    evidence=[r['tasks'][0]['report_ref']]
    first=FindingReview(request_id=str(uuid.uuid4()),state='needs_review',reason='First exact evidence review requires further independent verification.',evidence_refs=evidence)
    a=submit(store,r['id'],'F-001',first)
    second=first.model_copy(update=dict(request_id=str(uuid.uuid4()),expected_revision=a['revision'],state='test_issue',reason='Independent verification identifies a specific problem with this test.'))
    b=submit(store,r['id'],'F-001',second)
    chain=history(store,r['id'],'F-001')
    assert chain['current_revision']==b['revision']
    assert [row['event']['state'] for row in chain['events']]==['needs_review','test_issue']
    assert all(row['evidence_verified_now'] for row in chain['events'])
    assert chain['historical_decision_unchanged']
    with pytest.raises(FileNotFoundError):history(store,r['id'],'F-missing')
    path=store.root/'finding-reviews'/(first.request_id+'.json')
    raw=json.loads(path.read_bytes());raw['event']['reason']='tampered';path.write_text(json.dumps(raw))
    with pytest.raises(ValueError):history(store,r['id'],'F-001')


def test_tampered_review_and_frozen_source_fail_integrity(tmp_path):
    store,r,_=fixture(tmp_path);r['finding_review']=a.build(store,r);r['finding_review_ref']=store.artifact(r,'finding-review.json',encode(r['finding_review']));store.save(r)
    assert store.snapshot(r['id'])['integrity']
    r['finding_review']['summary']['confirmed']=12;store.save(r)
    assert not store.snapshot(r['id'])['integrity']


def test_real_opa_uses_reviewed_counts_and_preserves_raw_hits(tmp_path):
    store,r,_=fixture(tmp_path)
    r['rules_config']=[dict(id='no-issues',kind='metric',tasks=['scan'],metric='findings.total',threshold=0)]
    r['exclusions']=[];store.save(r);store.finish(r)
    checked=store.snapshot(r['id'])
    assert checked['integrity'] and checked['decision']=='allow'
    assert len(checked['tasks'][0]['report']['findings'])==1
    assert checked['finding_review']['summary']['false_positive']==1
    # A new product assert at a different location remains blocking.
    r2=store.new('unsafe','executor');r2.update(context=deepcopy(r['context']),integrity=True,exclusions=[],rules_config=r['rules_config'])
    import shutil
    shutil.copytree(store.path(r['id'])/'source',store.path(r2['id'])/'source')
    raw=encode(dict(results=[dict(test_id='B101',issue_text='product assert',filename='/source/src/rule.py',line_number=1,issue_severity='LOW')],errors=[],metrics={'_totals':{'loc':1}}))
    ref=store.artifact(r2,'scan/report.json',raw)
    r2['tasks']=[dict(id='scan',tool='bandit',format='bandit',state='completed',report_ref=ref,report=parse('bandit',raw),artifacts=[ref])]
    store.save(r2);store.finish(r2)
    assert store.snapshot(r2['id'])['decision']=='reject'


def test_new_review_policy_or_source_does_not_reuse_old_confirmation(tmp_path):
    store,r,_=fixture(tmp_path);p=store.path(r['id'])/'source'/'tests/test_rule.py'
    r['finding_review']=a.build(store,r);r['finding_review_ref']=store.artifact(r,'finding-review.json',encode(r['finding_review']));store.save(r)
    p.write_text('def test_rule():\n    assert False\n')
    checked=store.snapshot(r['id']);assert not checked['integrity']
    assert a.load(store,checked)['summary']['needs_review']==1


@pytest.mark.parametrize('config',[b'',b'[tool.hatch.build.targets.wheel]\npackages=["."]'])
def test_normal_test_assert_is_framework_independent_even_without_hatch(tmp_path,config):
    store,r,_=fixture(tmp_path);p=store.path(r['id'])/'source'/'pyproject.toml';p.write_bytes(config)
    next(x for x in r['context']['files'] if x['path']=='pyproject.toml')['sha256']=sha(config)
    review=a.build(store,r)
    assert review['summary']['false_positive']==1
