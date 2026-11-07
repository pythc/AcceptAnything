import pytest
from acceptance.universal.scenarios import Scenario,validate_bindings,evaluate
from acceptance.universal.runtime import compare,pointer


def flow(check):
    return dict(steps=[dict(id='cmd',op='cli',entry='sample',argv=[])],checks=[dict(step='cmd',**check)])


def target(version=12):
    return dict(units=[dict(id='u',runtime='python',entries=['sample'])],interfaces=[],execution_contract=dict(version=version))


@pytest.mark.parametrize('check',[
    dict(expected='[{"id":1}]',comparison='json_stream'),
    dict(expected='success',comparison='contains'),
    dict(pointer='/stdout/id',expected=1),
    dict(pointer='/exit_code',expected=True),
    dict(pointer='/stdout',expected=1),
])
def test_invalid_cli_observation_rejected_without_rewriting(check):
    obj=Scenario.model_validate(flow(check));before=obj.model_dump_json()
    with pytest.raises(ValueError):validate_bindings(obj,target(),'u')
    assert obj.model_dump_json()==before
    validate_bindings(obj,target(11),'u')  # Historical contract remains unchanged.
    status,checks=evaluate(obj.model_dump(),{},compare,pointer,validate_cli_contract=True)
    assert status=='error' and checks[0]['reason']


@pytest.mark.parametrize('check,expected_status',[
    (dict(pointer='/stdout',expected=[{'id':1}],comparison='json_stream'),'passed'),
    (dict(pointer='/stdout',expected=[{'id':2}],comparison='json_stream'),'failed'),
    (dict(pointer='/exit_code',expected=0),'passed'),
    (dict(expected=dict(exit_code=0,stdout='[{"id":1}]',stderr='')),'passed'),
])
def test_real_cli_receipt_is_compared_only_at_declared_path(check,expected_status):
    obj=Scenario.model_validate(flow(check));validate_bindings(obj,target(),'u')
    receipt=dict(status='completed',steps=[dict(id='cmd',status='completed',observable=True,value=dict(exit_code=0,stdout='[{"id":1}]',stderr=''))],cleanup=[],temporary_directory_removed=True)
    status,checks=evaluate(obj.model_dump(),receipt,compare,pointer,validate_cli_contract=True)
    assert status==expected_status
