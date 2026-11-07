from copy import deepcopy
import itertools
import json

import pytest
from fastapi.testclient import TestClient

from acceptance.results import project, gate_blockers, ResultContract
from acceptance.integrations.store import IntegrationStore
from acceptance.integrations.formats import parse
from acceptance.integrations.gates import opa_decide
from acceptance.engine import OPA, Store
from acceptance.api import create_app


def record():
    return dict(id='int-'+'a'*16,status='completed',decision='allow',
        context={'snapshot_digest':'b'*64},
        profile={'tasks':[{'id':'unit'}]},
        rules_config=[{'id':'gate','tasks':['unit']}],rules=[{'id':'gate','status':'passed'}],
        tasks=[dict(id='unit',state='completed',report_ref='art-one',artifacts=['art-one'],
            report=parse('junit',b'<testsuite><testcase name="normal assertion"/></testsuite>'))])


@pytest.mark.parametrize('state,complete,rule,verified',list(itertools.product(
    ['queued','running','completed','error','cancelled','blocked'],[True,False],['passed','failed','unknown'],[True,False])))
def test_no_false_release_across_execution_evidence_rule_matrix(state,complete,rule,verified):
    r=record();r['tasks'][0]['state']=state;r['tasks'][0]['report']['complete']=complete
    r['rules'][0]['status']=rule;r['decision']='reject' if rule=='failed' else 'allow'
    before=deepcopy(r);result=project(r,verified=verified)
    expected=('reject' if rule=='failed' else 'allow') if state=='completed' and complete and rule!='unknown' and verified else 'inconclusive'
    assert result['gate']['decision']==expected
    assert r==before
    assert result['findings']['counts'].get('confirmed',0)==0
    ResultContract.model_validate(result)


@pytest.mark.parametrize('change,code',[
    (lambda r:r.update(tasks=[]),'missing_task'),
    (lambda r:r['tasks'].append(deepcopy(r['tasks'][0])),'invalid_identity'),
    (lambda r:r['profile']['tasks'].append({'id':'missing'}),'missing_task'),
    (lambda r:r.update(rules=[]),'missing_rule'),
    (lambda r:r['rules'].append(deepcopy(r['rules'][0])),'invalid_identity'),
    (lambda r:r['rules'][0].update(status='failed'),'decision_mismatch'),
    (lambda r:r['rules'][0].pop('id'),'invalid_identity'),
    (lambda r:r['tasks'][0].pop('id'),'invalid_identity'),
    (lambda r:r['rules_config'][0].update(tasks=['absent']),'missing_task'),
    (lambda r:r['rules_config'][0].update(id='other'),'missing_rule'),
    (lambda r:r['tasks'][0].pop('report'),'missing_report'),
    (lambda r:r['tasks'][0].pop('report_ref'),'missing_report'),
    (lambda r:r['tasks'][0].update(report={}), 'missing_report'),
    (lambda r:r['tasks'][0]['report'].update(complete=False),'incomplete_report'),
    (lambda r:r['tasks'][0]['report']['tests'][0].update(status='error'),'incomplete_report'),
    (lambda r:r['tasks'][0]['report']['tests'][0].update(status='skipped'),'incomplete_report'),
    (lambda r:r['tasks'][0]['report']['tests'][0].update(status='unrecognized'),'incomplete_report'),
])
def test_counterexample_blockers(change,code):
    r=record();change(r)
    assert code in {e['code'] for e in gate_blockers(r)}
    assert project(r,verified=True)['gate']['decision']=='inconclusive'


@pytest.mark.parametrize('category,expected',[('basis','missing_basis'),('environment','environment_not_ready'),('case','case_contract_error'),('platform','unsupported_capability'),('unclassified','coverage_gap')])
def test_partial_coverage_does_not_become_a_defect(category,expected):
    r=record();r['recipe_completion']={'complete':False,'kind':'declared-scope','gaps':[{'source':'requirement-1','category':category,'reason':'独立标准暂无法验证'}]}
    c=project(r,verified=True)
    assert c['coverage']['gaps'][0]['code']==expected
    assert c['gate']['decision']=='inconclusive'
    assert not c['findings']['counts']


def test_normal_assertions_and_tool_errors_are_not_confirmed_defects():
    r=record();r['tasks'][0]['report']['tests'][0].update(status='error',detail='assert expected != actual')
    c=project(r,verified=True)
    assert c['execution']['test_counts']=={'error':1}
    assert c['observations'][0]['outcome']=='error'
    assert c['findings']['counts'].get('confirmed',0)==0
    assert c['gate']['decision']=='inconclusive'


def test_real_opa_honors_result_contract_guard(tmp_path):
    r=record();r['tasks'][0]['report']['tests'][0]['status']='error'
    payload={**r,'integrity':True,'contract_ready':not gate_blockers(r)}
    assert opa_decide(payload,tmp_path,OPA)=='inconclusive'


@pytest.mark.parametrize('case_status',['passed','failed','error','skipped','missing','duplicate'])
def test_requirement_denominator_case_binding_and_exclusions(case_status):
    r=record();r['universal_generation']={'requirements':[
        dict(id='R1',title='独立需求',source='D1',quote='必须返回既定结果',disposition='required',cases=[{'id':'C1'}]),
        dict(id='R2',title='真实邮件',disposition='excluded',cases=[],reason='未接入生产邮箱')
    ]}
    test=r['tasks'][0]['report']['tests'][0];test.update(name='C1 · 中文用例',status=case_status)
    if case_status=='missing':r['tasks'][0]['report']['tests']=[]
    if case_status=='duplicate':
        test['status']='passed';r['tasks'][0]['report']['tests'].append({**test,'id':'another'})
    result=project(r,verified=True)
    valid=case_status in {'passed','failed'}
    assert result['coverage']['requirement_counts']==dict(total=2,verified=int(valid),excluded=1,not_verified=int(not valid))
    assert result['requirements'][0]['case_ids']==['C1']
    if case_status!='missing':assert result['observations'][0]['case_id']=='C1'
    assert bool(gate_blockers(r)) is not valid
    assert (result['gate']['decision']=='allow') is valid


def test_nested_contract_rejects_invalid_counts_and_unsupported_reasons():
    from pydantic import ValidationError
    c=project(record(),verified=True)
    c['execution']['test_counts']['passed']=-1
    with pytest.raises(ValidationError):ResultContract.model_validate(c)
    c=project(record(),verified=True);c['gate']['reasons']=[{'code':'guess_from_english','source':'text','message':'bad'}]
    with pytest.raises(ValidationError):ResultContract.model_validate(c)


def test_explicit_case_error_category_is_kept_without_string_guessing():
    r=record();r['tasks'][0]['report']['tests'][0].update(status='error',detail=json.dumps({'gap_category':'environment','error':'assert interrupted'}))
    c=project(r,verified=True)
    assert c['observations'][0]['reasons'][0]['code']=='environment_not_ready'


def test_read_only_contract_on_api_and_tampered_evidence(tmp_path):
    import uuid
    s=IntegrationStore(tmp_path/'integrations')
    r=s.import_reports(str(uuid.uuid4()),'neutral',dict(repository='/neutral',revision='abc',snapshot_digest='a'*64,environment='local',scope='unit'),
        [{'id':'unit','format':'junit','raw':b'<testsuite><testcase name="ok"/></testsuite>'}],
        [dict(id='gate',kind='metric',tasks=['unit'],metric='tests.failed',threshold=0)])
    raw=(s.path(r['id'])/'run.json').read_bytes()
    client=TestClient(create_app(Store(tmp_path)))
    c=client.get(f"/api/runs/{r['id']}/result-contract").json()
    assert c==s.snapshot(r['id'])['result_contract']
    assert c['gate']['decision']=='allow'
    assert client.get('/api/result-contract/schema').status_code==200
    (s.path(r['id'])/'artifacts'/r['tasks'][0]['report_ref']).write_text('broken')
    c=client.get(f"/api/runs/{r['id']}/result-contract").json()
    assert c['gate']['decision']=='inconclusive' and c['gate']['recorded_decision']=='allow'
    assert (s.path(r['id'])/'run.json').read_bytes()==raw
