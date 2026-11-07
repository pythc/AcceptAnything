import pytest
from acceptance.universal.scenarios import validate_cli_checks,evaluate
from acceptance.universal.runtime import compare,pointer


def test_documented_error_can_assert_nonzero_without_guessing_one_specific_code():
    flow=dict(steps=[dict(id='cmd',op='cli')],cleanup=[],checks=[dict(step='cmd',pointer='/exit_code',comparison='json_schema',expected={'type':'integer','minimum':1,'maximum':255})])
    with pytest.raises(ValueError):validate_cli_checks(flow)
    validate_cli_checks(flow,structured_exit=True)
    receipt=dict(status='completed',temporary_directory_removed=True,cleanup=[],steps=[dict(id='cmd',status='completed',observable=True,value=dict(exit_code=2,stdout='',stderr='error'))])
    assert evaluate(flow,receipt,compare,pointer,validate_cli_contract=True,structured_cli_exit=True)[0]=='passed'
    receipt['steps'][0]['value']['exit_code']=0
    assert evaluate(flow,receipt,compare,pointer,validate_cli_contract=True,structured_cli_exit=True)[0]=='failed'
    flow['checks'][0]['expected']={'type':'integer'}
    with pytest.raises(ValueError,match='全部放行'):validate_cli_checks(flow,structured_exit=True)
