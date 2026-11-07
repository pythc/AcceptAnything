"""Regression checks for false-completion, source drift and cross-run evidence."""
from copy import deepcopy
import json
from pathlib import Path
import pytest
from fastapi.testclient import TestClient
from acceptance.engine import Store, encode, digest
from acceptance import workflow
from acceptance.api import create_app
from acceptance.integrations.store import IntegrationStore
from acceptance.unified import integration_view
from acceptance.unified import workflow_view


def completed_run():
    return dict(workflow=dict(version=1,required_stages=list(workflow.REQUIRED),children=[],manifest=[]),
                pipeline=[dict(id=k,status='passed') for k in workflow.REQUIRED],
                baseline=dict(criteria=[dict(id='BUSINESS',required=True)]),results=[dict(criterion_id='BUSINESS',status='passed')])


@pytest.mark.parametrize('omission',['design','L2','L3','L4','cleanup'])
def test_missing_required_layer_cannot_be_complete(tmp_path,omission):
    store=Store(tmp_path);run=completed_run()
    run['pipeline']=[s for s in run['pipeline'] if s['id']!=omission]
    c=workflow.coverage(store,run)
    assert c['complete'] is False and workflow.TITLES[omission] in c['missing']


def test_scan_and_generated_stages_need_real_child_receipts(tmp_path):
    c=workflow.coverage(Store(tmp_path),completed_run())
    assert not c['complete'] and '仓库扫描报告' in c['missing'] and '生成用例验证报告' in c['missing']


def test_environment_failure_is_unfinished_not_omission(tmp_path):
    run=completed_run();run['results'][0]['status']='blocked'
    assert 'BUSINESS' in workflow.coverage(Store(tmp_path),run)['missing']


def test_unregistered_repository_gets_actionable_readiness_blocker(tmp_path):
    repo=tmp_path/'repo';repo.mkdir();(repo/'app.js').write_text('export const ready=true')
    plan=workflow.plan(Store(tmp_path/'store'),str(repo))
    assert not plan['ready'] and plan['blockers'] and plan['stages'][-1]['id']=='gate'
    with pytest.raises(ValueError,match='尚未就绪'):
        workflow.create(Store(tmp_path/'store'),plan['id'],plan['digest'])


@pytest.mark.parametrize('change',['source','plan','recipe'])
def test_full_plan_requires_same_sources_and_recipe(tmp_path,monkeypatch,change):
    from acceptance import projects,expanded
    repo=tmp_path/'repo';(repo/'docs').mkdir(parents=True)
    for name in ('CONTRACT.md','REGISTRATION-AND-TIMING.md'):(repo/'docs'/name).write_text('independent requirement')
    profiles=tmp_path/'templates/projects';profiles.mkdir(parents=True)
    profile=dict(id='test',repository=str(repo),recipe='assessment-v1',exclusions=[],criteria=[dict(kind=k) for k in ('build','playwright','k6','joint-restore')])
    (profiles/'profile.json').write_text(json.dumps(profile));monkeypatch.setattr(workflow,'ROOT',profiles.parent)
    monkeypatch.setattr(projects,'read_files',lambda p:None)
    store=Store(tmp_path/'store');p=workflow.plan(store,str(repo))
    if change=='source':(repo/'docs/CONTRACT.md').write_text('changed')
    if change=='recipe':monkeypatch.setattr(expanded,'recipe_files',lambda:{'changed':b'yes'})
    if change=='plan':
        path=store.root/'full-plans'/(p['id']+'.json');v=json.loads(path.read_text());v['record']['blockers']=[];v['record']['repository']='/'
        path.write_text(json.dumps(v))
    with pytest.raises(ValueError):workflow.create(store,p['id'],p['digest'])


def scoped_record(integrations):
    r=integrations.new('scope scan','local')
    r.update(context=dict(repository='/tmp/repo',revision='uncommitted',scope='source scan',environment='isolated',snapshot_digest='a'*64,files=[]),profile={'version':'test'})
    integrations.save(r);return r


def test_scoped_record_uses_canonical_detail_and_never_full_complete(tmp_path):
    store=Store(tmp_path/'store');integrations=IntegrationStore(store.root/'integrations');r=scoped_record(integrations)
    client=TestClient(create_app(store));response=client.get('/api/runs/'+r['id'])
    assert response.status_code==200
    view=response.json()
    assert view['completion']==dict(kind='scoped',complete=False,missing=['本记录仅证明所选检查范围，不是完整验收'])
    assert view['source']['repository']['path']=='/tmp/repo' and 'display_stages' in view


def test_artifact_endpoint_does_not_return_another_run_artifact(tmp_path):
    store=Store(tmp_path/'store');integrations=IntegrationStore(store.root/'integrations');one=scoped_record(integrations);two=scoped_record(integrations)
    aid=integrations.artifact(two,'private.txt',b'other-run');integrations.save(two)
    client=TestClient(create_app(store))
    assert client.get(f"/api/runs/{one['id']}/artifacts/{aid}").status_code==404
    assert client.get(f"/api/runs/{two['id']}/artifacts/{aid}").content==b'other-run'


def test_no_shell_command_or_recipe_input_via_full_entry(tmp_path):
    client=TestClient(create_app(Store(tmp_path)))
    assert client.post('/api/acceptance/plan',json={'repository':'/tmp/repo','command':'touch /tmp/prohibited'}).status_code==422
    assert client.post('/api/acceptance/plan',json={'repository':'/tmp/repo'},headers={'Origin':'https://untrusted.example'}).status_code==403


def test_running_workflow_stage_projection_preserves_actual_status_and_time(tmp_path,monkeypatch):
    run=completed_run()
    run.update(status='running',id='run-'+'a'*12,inspections={},results=[],findings=[],artifacts=[],reasons=[],check_runs=[])
    run['pipeline']=[dict(id='design',status='blocked',detail='upstream unknown',started_at='2026-10-18T00:00:00Z',duration_ms=12)]
    before=deepcopy(run)
    view=workflow_view(Store(tmp_path),None,run)
    stage=next(s for s in view['display_stages'] if s['id']=='design')
    assert stage['status']=='blocked' and stage['duration_ms']==12 and stage['detail']=='upstream unknown'
    assert next(s for s in view['display_stages'] if s['id']=='L3')['status']=='queued'
    assert run==before


def test_child_report_tampering_blocks_full_completion(tmp_path):
    store=Store(tmp_path);integrations=IntegrationStore(store.root/'integrations');r=scoped_record(integrations)
    run=completed_run()
    run['workflow']['children']=[dict(id=r['id'],stage='Lscanners',record_digest=digest(encode(integrations.read(r['id']))))]
    # Tampering with the record after sealing its exact parent receipt is not
    # repaired by regenerating a matching outer storage checksum.
    r['name']='relabelled after seal';integrations.save(r)
    c=workflow.coverage(store,run)
    assert not c['complete'] and c['errors']


def test_model_stage_success_without_real_high_case_evidence_is_not_complete(tmp_path):
    run=completed_run()
    c=workflow.coverage(Store(tmp_path),run)
    assert '模型 High 响应及其用例执行证据' in c['missing']
    assert '五项必验标准的独立模型批次记录' in c['missing']


@pytest.mark.parametrize('field,value',[('actual_model','gpt-6-pro'),('actual_thinking_effort','standard'),('requested_model','gpt-6-pro'),('reasoning_effort','medium'),('finish_reason','length'),('verified',False)])
def test_every_model_batch_requires_exact_high_identity(field,value):
    connection=dict(provider='chat2api',requested_model='gpt-6-thinking',reasoning_effort='high',actual_model='gpt-6-thinking',actual_thinking_effort='extended',finish_reason='stop',verified=True)
    assert workflow.verified_high(connection)
    connection[field]=value
    assert not workflow.verified_high(connection)


def test_failed_model_design_is_not_a_completed_verification_layer(tmp_path):
    run=completed_run();next(s for s in run['pipeline'] if s['id']=='design')['status']='failed'
    assert '模型设计用例' in workflow.coverage(Store(tmp_path),run)['missing']


def test_model_batches_preserve_exact_sources_and_exclude_real_mail():
    template=json.loads(Path('acceptance/planning/examples/assessment.json').read_text());before=deepcopy(template)
    batches=workflow.model_batches(template)
    expected={r['id'] for r in template['specification']['requirements'] if r.get('disposition','required')=='required'}
    assert {b['id'] for b in batches}==expected and 'REAL-MAIL' not in expected
    sources={d['origin']:d['content'] for d in template['documents']}
    for batch in batches:
        span=batch['span'];doc=batch['documents'][0]
        assert doc['content']==sources[span['path']][span['start']:span['end']]
        assert batch['quote'] in doc['content']
        assert all(set(b)=={'module','function','args','result_pointers'} for b in batch['call_bindings'])
    assert template==before


def table_input():
    from acceptance.planning.models import DraftInput
    template=json.loads(Path('acceptance/planning/examples/assessment.json').read_text());batch=workflow.model_batches(template)[0]
    return DraftInput(repository=template['repository'],documents=batch['documents'],scope='独立决策表',table_target=batch['table_target'])


def test_decision_table_keeps_model_answers_instead_of_manufacturing_passes():
    from acceptance.planning.provider import decision_spec
    data=table_input();spec=decision_spec(data,{'rows':[{'inputs':{'hours':25},'expected':True,'title':'错误预期保留','rationale':'用于验证不会按实现修正答案','basis_quote':data.table_target.quote}]})
    scenario=spec.requirements[0].scenarios[0]
    assert scenario.examples[0]=={'hours':25,'expected':True}  # intentionally wrong model answer is preserved
    assert scenario.steps[0].function=='isDurationHours' and spec.requirements[0].quote==data.table_target.quote


@pytest.mark.parametrize('row',[{'inputs':{'other':24},'expected':True},{'inputs':{'hours':24},'expected':'true'},{'inputs':{'hours':24,'expected':True},'expected':True}])
def test_decision_table_rejects_wrong_binding_or_result_type(row):
    from acceptance.planning.provider import decision_spec
    with pytest.raises(ValueError):decision_spec(table_input(),{'rows':[row]})


def test_generated_failure_explains_exact_trace_without_claiming_product_bug(tmp_path):
    from acceptance.unified import generated_detail
    integrations=IntegrationStore(tmp_path);r=scoped_record(integrations)
    r['test_plan']=dict(planner={'kind':'model'},specification={'requirements':[dict(id='DEADLINE',title='截止规则')]},
        cases=[dict(id='C0001',name='test_C0001',requirement='DEADLINE',source={'quote':'At deadline no further writes.'})])
    trace=dict(steps=[dict(input={'args':[{'state':'READY'},1999]},assertions=[dict(expected=True,actual=False,passed=False)])])
    aid=integrations.artifact(r,'generated-pytest/C0001-trace.json',encode(trace))
    result=generated_detail(integrations,r,dict(id='generated-pytest',tool='acceptance-generated'),dict(name='test_C0001'))
    assert result['detail']['primary_ref']==aid
    assert result['detail']['expected_value']=='[true]' and result['detail']['actual_value']=='[false]'
    assert 'READY' in result['actual'] and '不能直接认定产品缺陷' in result['impact']
    assert result['detail']['comparison_labels']==['模型草稿预期','实际返回']
    assert generated_detail(integrations,r,dict(id='unrelated',tool='acceptance-generated'),dict(name='test_C0001')) is None


def deadline_input():
    from acceptance.planning.models import DraftInput
    template=json.loads(Path('acceptance/planning/examples/assessment.json').read_text())
    batch=next(b for b in workflow.model_batches(template) if b['id']=='DEADLINE')
    return DraftInput(repository=template['repository'],documents=batch['documents'],scope='截止规则',table_target=batch['table_target'])


def test_deadline_design_no_longer_seeds_only_unstarted_candidates():
    data=deadline_input()
    assert {e['enrollment']['state'] for e in data.table_target.input_examples}=={'ACTIVE'}
    assert len({e['now'] for e in data.table_target.input_examples})==3
    assert all('expected' not in e for e in data.table_target.input_examples)


def test_old_model_ready_true_cases_are_rejected_before_execution_and_not_repaired():
    from acceptance.planning.provider import decision_spec
    data=deadline_input();row=dict(inputs={**deepcopy(data.table_target.input_examples[0])},expected=True,title='原始错误前提',rationale='在截止前允许写入',basis_quote=data.table_target.quote)
    row['inputs']['enrollment']['state']='READY';before=deepcopy(row)
    with pytest.raises(ValueError,match='适用前提'):decision_spec(data,{'rows':[row]})
    assert row==before


@pytest.mark.parametrize('fault',['english','quote'])
def test_model_explanations_are_chinese_and_quotes_are_original(fault):
    from acceptance.planning.provider import decision_spec
    data=deadline_input();row=dict(inputs=deepcopy(data.table_target.input_examples[0]),expected=True,title='截止前允许写入',rationale='已开考且未截止',basis_quote=data.table_target.quote)
    if fault=='english':row.update(title='Before deadline',rationale='Writes should be open')
    else:row['basis_quote']='这不是需求里的原文，不得假造依据'
    with pytest.raises(ValueError):decision_spec(data,{'rows':[row]})
