"""Adapter regressions: malformed/partial results must never become passes."""
from copy import deepcopy
import json
from pathlib import Path
import pytest

from acceptance.engine import Store
from acceptance.expanded import parse_report, validate_check, freeze
from acceptance.projects import packed, sha
from acceptance.validation import Reader, validate_results


def criterion(kind):
    return {'id':'CHECK','case_id':'TC-CHECK','layer':'L1','executor':'assessment-check','required':True,'title':'Check','expected':'All approved checks pass','kind':kind,'gap':'No independent test connected','test_names':['Case.one','Case.two']}


def python_report():
    return {'runner':'unittest','tests':2,'failures':0,'errors':0,'skipped':1,'cases':[{'name':'Case.one','status':'passed','duration':.01,'detail':''},{'name':'Case.two','status':'skipped','duration':0,'detail':'native Windows required'}]}


def test_native_platform_skip_is_coverage_gap_not_pass():
    parsed=parse_report(criterion('python'),packed(python_report()),0)
    assert parsed['status']=='blocked' and 'native Windows' in parsed['actual']


@pytest.mark.parametrize('mutation',['empty','missing','duplicate','stats','unexpected','negative','exit'])
def test_python_partial_or_forged_report_is_rejected(mutation):
    raw=python_report();code=0
    if mutation=='empty':raw={}
    if mutation=='missing':raw['cases'].pop()
    if mutation=='duplicate':raw['cases'][1]=raw['cases'][0]
    if mutation=='stats':raw['skipped']=0
    if mutation=='unexpected':raw['cases'][0]['status']='unknown'
    if mutation=='negative':raw['cases'][0]['duration']=-1
    if mutation=='exit':code=1
    with pytest.raises((ValueError,KeyError)):parse_report(criterion('python'),packed(raw),code)


def test_empty_restore_never_counts_as_pass():
    with pytest.raises(ValueError):parse_report(criterion('restore'),packed({'before':{},'after':{}}),0)


def test_restore_different_rows_rejected():
    with pytest.raises(ValueError):parse_report(criterion('restore'),packed({'before':{'users':'1:'+'a'*32},'after':{'users':'0:'+'b'*32}}),0)


def test_failed_build_or_missing_output_rejected():
    for code,outputs in [(1,{}),(0,{'client/dist/index.html':'a'*64})]:
        with pytest.raises(ValueError):parse_report(criterion('build'),packed({'outputs':outputs}),code)


def test_npm_audit_errors_and_empty_metadata_rejected():
    for report in ({'error':{'code':'ENOTFOUND'}},{'auditReportVersion':2,'vulnerabilities':{},'metadata':{'dependencies':{'total':0},'vulnerabilities':{'total':0}}}):
        with pytest.raises((ValueError,KeyError)):parse_report(criterion('npm-audit'),packed(report),0)


def test_gitleaks_does_not_silently_discard_hits_or_secrets():
    hit={'RuleID':'generic-api-key','File':'/source/test.ts','StartLine':1,'Secret':'REDACTED','Description':'potential secret'}
    assert parse_report(criterion('gitleaks'),packed([hit]),1)['status']=='failed'
    with pytest.raises(ValueError):parse_report(criterion('gitleaks'),packed([hit]),0)
    hit['Secret']='unredacted'
    with pytest.raises(ValueError):parse_report(criterion('gitleaks'),packed([hit]),1)


def gap_run(tmp_path):
    store=Store(tmp_path/'store');run=store.create('fixed');c=criterion('gap')
    run['baseline']['criteria']=[c];run['baseline']['digest']='a'*64;run['target_digest']='b'*64
    receipt={'criterion_id':c['id'],'target_digest':run['target_digest'],'baseline_digest':run['baseline']['digest'],'blocked':True,'reason':c['gap']}
    ref=store.artifact(run,'CHECK-receipt.json',packed(receipt),'CHECK','application/json')
    run['results']=[{'criterion_id':'CHECK','case_id':'TC-CHECK','layer':'L1','expected':c['expected'],'attempt':1,'status':'blocked','evidence_refs':[ref]}]
    return store,run,receipt


def test_uncovered_check_has_valid_evidence_but_cannot_turn_into_pass(tmp_path):
    store,run,_=gap_run(tmp_path)
    assert validate_results(store,run)['valid']
    run['results'][0]['status']='passed'
    assert not validate_results(store,run)['valid']


@pytest.mark.parametrize('field',['criterion_id','target_digest','baseline_digest','reason'])
def test_gap_receipt_must_match_frozen_check(tmp_path,field):
    store,run,receipt=gap_run(tmp_path)
    receipt[field]='changed'
    a=next(a for a in run['artifacts'] if a['name']=='CHECK-receipt.json')
    data=packed(receipt);(store.path(run['id'])/'artifacts'/a['file']).write_bytes(data)
    a.update(sha256=sha(data),size=len(data))
    assert not validate_results(store,run)['valid']


def test_gap_is_explicit_required_input_to_real_opa(tmp_path):
    from acceptance import projects
    from acceptance.expanded import Runner
    target=tmp_path/'target';target.mkdir();(target/'contract.md').write_text('A full check is required.\n')
    digest=sha((target/'contract.md').read_bytes())
    c={k:v for k,v in criterion('gap').items() if k not in ('case_id','executor','required')}
    c.update(test_file='contract.md',test_digest=digest,source_anchor='contract.md:1',limitation='Not connected')
    p={'id':'gap-project','name':'Gap project','recipe':'assessment-v1','scope':'Includes unresolved required check','version':'v1','repository':str(target),'files':['contract.md'],'source_path':'contract.md','source_digest':digest,'criteria':[c]}
    store=Store(tmp_path/'store');projects.register(store,p);run=projects.create(store,p['id'])
    Runner(store,run).blocked(run['baseline']['criteria'][0],c['gap']);run['status']='completed'
    assert store.check_integrity(run)
    assert validate_results(store,run)['valid']
    assert store.evaluate(run)=='inconclusive'
    run['results'][0]['status']='passed'
    assert store.evaluate(run)=='inconclusive'


def test_interrupted_cleanup_only_removes_owned_resources(tmp_path):
    import subprocess
    from acceptance.expanded import recover_runtime, NODE_IMAGE
    store=Store(tmp_path/'store');run=store.create('fixed')
    owned='acceptance-'+run['id']+'-test';other='acceptance-'+run['id']+'-unowned'
    try:
        for name,label in [(owned,run['id']),(other,'unrelated-test')]:
            subprocess.run(['docker','run','-d','--name',name,'--network','none','--label','acceptance.run='+label,'--entrypoint','node',NODE_IMAGE,'-e','setTimeout(()=>{},60000)'],capture_output=True,check=True,timeout=15)
        recover_runtime(store,run)
        assert subprocess.run(['docker','inspect',owned],capture_output=True).returncode!=0
        assert subprocess.check_output(['docker','inspect','--format','{{.State.Running}}',other],text=True).strip()=='true'
    finally:
        for name in (owned,other):subprocess.run(['docker','rm','-f',name],capture_output=True,timeout=15)


def test_large_command_output_is_complete_and_not_misreported_as_an_execution_fault(tmp_path):
    import sys
    from acceptance.expanded import Runner
    store=Store(tmp_path/'store');run=store.create('fixed');runner=Runner(store,run)
    raw,_=runner.command('large-output',[sys.executable,'-c',"import sys; sys.stdout.write('x' * (5*1024*1024))"],timeout=5)
    command=run['commands'][-1]
    assert not command['truncated'] and command['exit_code']==0
    assert store.artifact_bytes(run,command['stdout_ref'])[1]==raw==b'x'*(5*1024*1024)
