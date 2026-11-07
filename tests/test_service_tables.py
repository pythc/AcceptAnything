from copy import deepcopy
import json
import pytest
from acceptance.planning.models import DraftInput,ServiceTableTarget
from acceptance.planning import provider
from acceptance.integrations.store import IntegrationStore
from acceptance.integrations.runner import encode,sha


def data():
    return DraftInput(repository='/test',scope='审批流程',documents=[dict(id='R',title='审批要求',content='审批人可批准或者拒绝申请。')],
        environment=dict(mode='service',runtime='python',entrypoint='app.py'),service_table_target=dict(id='R1',title='审批流程',source='R',quote='审批人可批准或者拒绝申请。',
        engine='browser',steps=[dict(kind='click',selector='button:has-text("${action}")'),dict(kind='expect_visible',selector='#result'),
            dict(kind='http',path='/state',status=200,assertions=[dict(pointer='/status',value='${expected}')])],
        input_schema=dict(type='object',properties={'action':dict(type='string')},required=['action'],additionalProperties=False),
        result_schema=dict(type='string'),precondition='独立审批'))


def seed(store):
    d=data();output=dict(rows=[dict(inputs={'action':'批准'},expected='intentionally-wrong',title='保留模型预期',rationale='测试修订不会偷偷修正答案',basis_quote=d.documents[0].content)])
    record=dict(id='draft-0123456789abcdef',repository=d.repository,documents=[x.model_dump() for x in d.documents],
        specification=provider.decision_spec(d,output).model_dump(),projection='model-service-table-v1',model_output=output,table_target=d.service_table_target.model_dump(),
        model='test-model',prompt_sha256='p',response_sha256='r',connection=dict(verified=True))
    (store.root/'drafts').mkdir();(store.root/'drafts'/(record['id']+'.json')).write_bytes(encode(dict(record=record,sha256=sha(encode(record)))))
    return record


@pytest.mark.parametrize('fault',['unused','leak','capture'])
def test_service_model_oracle_must_be_asserted_and_cannot_be_sent_or_overwritten(fault):
    target=data().service_table_target.model_dump()
    if fault=='unused':target['steps'][-1]['assertions'][0]['value']='approved'
    if fault=='leak':target['steps'][-1]['body']={'correct_answer':'${expected}'}
    if fault=='capture':target['steps'][-1]['capture']={'expected':'/status'}
    with pytest.raises(ValueError):ServiceTableTarget.model_validate(target)


def test_locator_revision_keeps_wrong_model_oracle_and_records_parent(tmp_path):
    store=IntegrationStore(tmp_path/'store');p=seed(store);old=deepcopy(p)
    result=provider.rebind_service(store,p['id'],[dict(step=0,before=p['table_target']['steps'][0]['selector'],after='button >> text=${action}')],reason='已核实定位错误',evidence={'trace':'exact-artifact'})
    assert result['model_output']==old['model_output']
    assert result['specification']['requirements'][0]['scenarios'][0]['examples'][0]['expected']=='intentionally-wrong'
    wrapped=json.loads((store.root/'drafts'/(result['id']+'.json')).read_bytes())
    provider.validate_binding_revision(store,wrapped['record'])
    plan=dict(repository=p['repository'],documents=p['documents'],specification=result['specification'])
    proof=provider.provenance_many(store,[result['id']],plan)
    assert not proof['edited'] and proof['binding_revisions'][0]['parent_id']==p['id']
    # Rehashing a derived draft cannot hide changes to model answers.
    wrapped['record']['model_output']['rows'][0]['expected']='approved'
    with pytest.raises(ValueError,match='原始内容'):provider.validate_binding_revision(store,wrapped['record'])


def test_locator_revision_cannot_change_an_assertion(tmp_path):
    store=IntegrationStore(tmp_path/'store');p=seed(store)
    with pytest.raises(ValueError,match='断言'):provider.rebind_service(store,p['id'],[dict(step=1,before='#result',after='#anything')],reason='改断言',evidence={'trace':'x'})


def test_notification_container_can_change_but_expected_text_cannot():
    d=data();d.service_table_target.steps[1].selector='.old:has-text("已${action}")'
    p=dict(projection='model-service-table-v1',table_target=d.service_table_target.model_dump(),repository=d.repository,documents=[x.model_dump() for x in d.documents],
        specification={'scope':d.scope,'environment':d.environment.model_dump()},model_output={'rows':[dict(inputs={'action':'批准'},expected='approved',title='审批批准',rationale='批准后状态变更',basis_quote=d.documents[0].content)]})
    change=dict(step=1,before='.old:has-text("已${action}")',after='[role="alert"]:has-text("已${action}")')
    provider._binding_projection(p,[change])
    change['after']='[role="alert"]:has-text("任意结果")'
    with pytest.raises(ValueError,match='断言'):provider._binding_projection(p,[change])


def test_batch_merge_rejects_missing_reordered_or_modified_cases(tmp_path):
    store=IntegrationStore(tmp_path/'store');p=seed(store)
    plan=dict(repository=p['repository'],documents=p['documents'],specification=deepcopy(p['specification']))
    assert provider.provenance_many(store,[p['id']],plan)['edited'] is False
    plan['specification']['requirements'][0]['scenarios'][0]['examples'][0]['expected']='approved'
    with pytest.raises(ValueError,match='合并批次'):provider.provenance_many(store,[p['id']],plan)
