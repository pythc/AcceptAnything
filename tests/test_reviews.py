from copy import deepcopy
import json
from types import SimpleNamespace
import pytest
from acceptance import reviews
from acceptance.engine import digest,encode


def fixture():
    hit=dict(rule='secret',path='/source/test.ts',line=4)
    entry=dict(rule='secret',path='test.ts',line=4,source_sha256='a'*64,verdict='not_actionable',category='false_positive',reason='显式测试夹具')
    manifest=[dict(path='test.ts',sha256='a'*64)]
    return hit,dict(entries=[entry],context_digest=digest(encode(manifest))),manifest


@pytest.mark.parametrize('change',['source','rule','path','line'])
def test_review_never_clears_changed_sources_or_observations(change):
    hit,catalog,manifest=fixture()
    assert reviews.assess([hit],catalog,manifest)['non_blocking']
    if change=='source':manifest[0]['sha256']='b'*64
    elif change=='line':hit[change]=5
    else:hit[change]='different'
    reviewed=reviews.assess([hit],catalog,manifest)
    assert not reviewed['non_blocking'] and reviewed['pending']==1


def test_one_reviewed_hit_cannot_hide_a_new_hit_or_rewrite_the_report():
    hit,catalog,manifest=fixture();hits=[hit,{**hit,'line':5}];before=deepcopy(hits)
    reviewed=reviews.assess(hits,catalog,manifest)
    assert reviewed['non_actionable']==1 and reviewed['pending']==1 and not reviewed['non_blocking']
    assert before==hits


def test_frozen_review_rejects_strategy_replacement():
    raw=b'{"entries":[]}'
    store=SimpleNamespace(artifact_bytes=lambda run,ref:({},raw))
    run=dict(workflow=dict(review_ref='ref',plan={'review_digest':'0'*64}))
    with pytest.raises(ValueError,match='冻结验收计划'):reviews.frozen(store,run)
    run['workflow']['plan']['review_digest']=digest(raw)
    assert reviews.frozen(store,run)=={'entries':[]}


def test_effective_child_rules_keep_native_findings_and_fail_on_unknown():
    hit,catalog,manifest=fixture()
    profile=dict(rules=[dict(id='gate',kind='metric',tasks=['scan'],metric='findings.total',operator='le',threshold=0)])
    record=dict(profile=profile,tasks=[dict(id='scan',state='completed',report=dict(complete=True,findings=[hit],metrics={'findings.total':1}))])
    before=deepcopy(record);run=dict(workflow={'manifest':manifest})
    assert reviews.child(run,record,catalog)['non_blocking']
    assert record==before
    record['tasks'][0]['report']['findings'].append({**hit,'line':5})
    assert not reviews.child(run,record,catalog)['non_blocking']
    record['tasks'][0]['state']='error'
    assert not reviews.child(run,record,catalog)['non_blocking']


def test_timestamp_review_is_per_asset_not_shared_across_urls():
    report=dict(native_report={'site':[{'alerts':[dict(pluginid='10096',riskcode='1',instances=[dict(uri='http://localhost/assets/a.js'),dict(uri='http://localhost/assets/b.js')])]}]})
    hits=reviews.native_hits('zap',json.dumps(report).encode())
    assert hits[0]['path']!=hits[1]['path']
    catalog=dict(entries=[dict(rule='10096',path=hits[0]['path'],line=None,source_sha256='a'*64,verdict='not_actionable',category='false_positive',reason='已核对算术常量')],context_digest=digest(encode([])))
    reviewed=reviews.assess(hits,catalog,[],{hits[0]['path']:'a'*64})
    assert reviewed['pending']==1 and not reviewed['non_blocking']


def test_review_invalidated_when_related_code_changes_outside_the_reported_file():
    hit,catalog,manifest=fixture()
    manifest.append(dict(path='production-config.ts',sha256='b'*64))
    assert not reviews.assess([hit],catalog,manifest)['non_blocking']
