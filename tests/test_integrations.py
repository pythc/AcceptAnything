import json
from pathlib import Path
import uuid
import httpx
import pytest
from fastapi.testclient import TestClient
from acceptance.integrations.formats import parse, FORMATS, fingerprint
from acceptance.integrations.models import Profile,Rule,Context
from acceptance.integrations.gates import evaluate,opa_decide
from acceptance.integrations.store import IntegrationStore
from acceptance.integrations.runner import encode,collect
from acceptance.integrations.services import Service
from acceptance.integrations import export
from acceptance.engine import OPA, Store
from acceptance.api import create_app

JUNIT=b'<testsuite tests="2" failures="1" errors="0" skipped="0"><testcase name="yes"/><testcase name="no"><failure message="expected 2, got 3">trace</failure></testcase></testsuite>'
CONTEXT=dict(repository='/test/repo',revision='abc',snapshot_digest='a'*64,environment='linux',scope='unit')
RULE=dict(id='failures',kind='metric',tasks=['unit'],metric='tests.failed',threshold=0)
SAMPLES={
'junit':JUNIT,
'playwright':{'errors':[],'suites':[{'specs':[{'title':'first','tests':[{'results':[{'status':'passed','retry':0,'duration':2}], 'projectName':'chromium'}]}]}],'stats':{'expected':1,'unexpected':0,'flaky':0,'skipped':0}},
'zap':{'@version':'2','site':[{'@name':'http://localhost','alerts':[]}]},
'allure':{'uuid':'1','name':'works','status':'passed','start':1,'stop':2,'stage':'finished'},
'sarif':{'version':'2.1.0','runs':[{'tool':{'driver':{'name':'real tool'}},'invocations':[{'executionSuccessful':True}],'results':[]}]},
'robot':b'<robot generator="Robot 7.5"><suite name="all"><test name="first"><status status="PASS" elapsed="1"/></test></suite></robot>',
 'trx':b'<TestRun xmlns="http://microsoft.com"><Results><UnitTestResult testName="ok" outcome="Passed" duration="00:00:01"/></Results><ResultSummary><Counters total="1"/></ResultSummary></TestRun>',
 'lcov':b'TN:\nSF:a.js\nDA:1,2\nDA:2,0\nBRDA:1,0,0,2\nend_of_record\n',
 'cobertura':b'<coverage lines-valid="10" lines-covered="5" branches-valid="2" branches-covered="1"/>',
 'jacoco':b'<report><counter type="LINE" missed="3" covered="7"/></report>',
 'cyclonedx':{'bomFormat':'CycloneDX','specVersion':'1.6','components':[{'type':'library','name':'foo','version':'1','licenses':[{'license':{'id':'MIT'}}]}]},
 'spdx':{'spdxVersion':'SPDX-2.3','packages':[{'SPDXID':'SPDXRef-1','name':'foo','versionInfo':'1','licenseConcluded':'MIT'}]},
 'semgrep':{'results':[],'errors':[],'paths':{'scanned':['foo.py']}},
 'bandit':{'results':[],'errors':[],'metrics':{'_totals':{'loc':2}}},
 'gitleaks':[{'RuleID':'fake','Description':'fixture','File':'test','StartLine':1,'Secret':'REDACTED'}],
 'trivy':{'SchemaVersion':2,'ArtifactName':'source','Results':[{'Target':'foo','Vulnerabilities':[]}]},
 'grype':{'matches':[],'descriptor':{'name':'grype'},'source':{'type':'directory'}},
 'npm-audit':{'auditReportVersion':2,'vulnerabilities':{},'metadata':{'dependencies':{'total':1}}},
 'pip-audit':{'dependencies':[{'name':'foo','version':'1','vulns':[]}]},
 'defectdojo':{'findings':[{'title':'fixture','severity':'High','cwe':123,'description':'details'}]},
 'eslint':[{'filePath':'foo.js','messages':[],'fatalErrorCount':0}],
 'ruff':[{'code':'F401','message':'unused','filename':'x.py','location':{'row':1}}],
 'hadolint':[{'code':'DL3006','message':'untagged','file':'Dockerfile','line':1,'level':'warning'}],
 'shellcheck':{'comments':[{'code':2086,'message':'quote','file':'x.sh','line':2,'level':'warning'}]},
 'spectral':[{'code':'title','message':'missing title','source':'api.json','range':{'start':{'line':1}}}],
 'checkov':{'summary':{'passed':1,'failed':0,'parsing_errors':0,'skipped':0},'results':{'failed_checks':[]}},
 'k6':{'metrics':{'iterations':{'values':{'count':2}},'checks':{'values':{'rate':1},'thresholds':{'rate==1':{'ok':True}}}}},
 'axe':{'testEngine':{'name':'axe-core'},'violations':[],'passes':[{'id':'label'}],'incomplete':[],'inapplicable':[]},
 'lighthouse':{'lighthouseVersion':'13','categories':{'performance':{'score':.8}},'audits':{}},
 'newman':{'run':{'executions':[{'item':{'name':'request'},'assertions':[{'assertion':'ok'}]}],'failures':[]}},
 'defectdojo-api':{'test':{'id':1},'findings':[]},
 'reportportal':{'launch':{'id':1,'status':'PASSED'},'items':[{'id':1,'name':'ok','type':'STEP','status':'PASSED','hasStats':True}]},
 'sonarqube':{'analysis':{'revision':'abc'},'project':'p','measures':{'component':{'key':'p','measures':[{'metric':'coverage','value':'40'}]}},'gate':{'projectStatus':{'status':'OK'}}},
}

def raw(v):return v if isinstance(v,bytes) else encode(v)

@pytest.mark.parametrize('kind', sorted(FORMATS))
def test_formats_have_positive_and_truncated_contracts(kind):
    report=parse(kind,raw(SAMPLES[kind]));assert report['complete'] and report['format']==kind
    with pytest.raises(Exception):parse(kind,raw(SAMPLES[kind])[:5])
    with pytest.raises(ValueError):parse(kind,b'')

@pytest.mark.parametrize('data',[b'<testsuite tests="0"/>',b'<testsuite tests="2"><testcase name="one"/></testsuite>',b'<testsuite><testcase name="same"/><testcase name="same"/></testsuite>',b'<!DOCTYPE x [<!ENTITY a SYSTEM "file:///etc/passwd">]><testsuite><testcase name="&a;"/></testsuite>',b'<testsuite><testcase name="x" time="nan"/></testsuite>',b'<testsuite><testcase name="x"><failure/><error/></testcase></testsuite>'])
def test_junit_negative(data):
    with pytest.raises(Exception):parse('junit',data)

@pytest.mark.parametrize('kind,change',[
 ('allure',lambda x:x.update(stop=0)),('sarif',lambda x:x.update(version='2.0.0')),('bandit',lambda x:x.update(errors=[{'reason':'skip'}])),('semgrep',lambda x:x.update(paths={'scanned':[]})),('gitleaks',lambda x:x[0].update(Secret='not-redacted')),('pip-audit',lambda x:x['dependencies'][0].update(skip_reason='not found')),('trivy',lambda x:x.update(Results=[])),('lighthouse',lambda x:x.update(runtimeError={'code':'failed'})),('checkov',lambda x:x['summary'].update(skipped=1)),('npm-audit',lambda x:x.update(error={'code':'ENET'})),
])
def test_report_failure_is_not_green(kind,change):
    data=json.loads(raw(SAMPLES[kind]));change(data)
    with pytest.raises(Exception):parse(kind,encode(data))


def task(report=None,state='completed'):
    return dict(id='unit',state=state,report=report or parse('junit',JUNIT),environment='linux')

def test_gate_metrics_missing_and_failed():
    assert evaluate([RULE],[task()])[0]['status']=='failed'
    r={**RULE,'metric':'coverage.branches'};assert evaluate([r],[task()])[0]['status']=='unknown'
    assert evaluate([RULE],[task(state='error')])[0]['status']=='unknown'
    assert evaluate([{**RULE,'threshold':1}],[task()])[0]['status']=='passed'


def test_gate_baseline_license_and_required():
    assert evaluate([{**RULE,'kind':'delta'}],[task()])[0]['status']=='unknown'
    baseline={'integrity':True,'decision':'reject','tasks':[task()]}
    assert evaluate([{**RULE,'kind':'delta'}],[task()],baseline)[0]['actual']==0
    assert evaluate([dict(id='required',kind='required-tests',tasks=['unit'],values=['absent'])],[task()])[0]['status']=='unknown'
    assert evaluate([dict(id='required',kind='required-tests',tasks=['unit'],values=['no'])],[task()])[0]['status']=='failed'
    report=parse('cyclonedx',raw(SAMPLES['cyclonedx']));report['components'][0]['licenses']=['MIT OR GPL-3.0-only']
    assert evaluate([dict(id='license',kind='licenses',tasks=['unit'],values=['GPL-3.0-only'])],[task(report)])[0]['status']=='failed'
    assert evaluate([dict(id='environment',kind='environments',tasks=['unit'],values=['windows'])],[task()])[0]['status']=='failed'

@pytest.mark.parametrize('integrity,state,status,expected',[(True,'completed','passed','allow'),(True,'completed','failed','reject'),(True,'completed','unknown','inconclusive'),(False,'completed','passed','inconclusive'),(True,'error','passed','inconclusive')])
def test_real_opa_truth_table(tmp_path,integrity,state,status,expected):
    assert opa_decide({'integrity':integrity,'tasks':[task(state=state)],'rules':[{'status':status}]},tmp_path,OPA)==expected


def test_real_opa_blocks_incomplete_recipe_even_when_every_scanner_passes(tmp_path):
    assert opa_decide({'recipe_complete':False,'integrity':True,'tasks':[task(state='completed')],'rules':[{'status':'passed'}]},tmp_path,OPA)=='inconclusive'


def test_import_provenance_idempotency_tamper_and_exports(tmp_path):
    s=IntegrationStore(tmp_path);rid=str(uuid.uuid4());reports=[{'id':'unit','format':'junit','raw':JUNIT}]
    r=s.import_reports(rid,'import',CONTEXT,reports,[RULE]);assert r['decision']=='reject' and r['mode']=='import'
    assert s.import_reports(rid,'import',CONTEXT,reports,[RULE])['id']==r['id']
    with pytest.raises(ValueError):s.import_reports(rid,'changed',CONTEXT,reports,[RULE])
    assert parse('junit',export.junit(r))['metrics']['tests.failed']==1
    assert json.loads(export.sarif(r))['version']=='2.1.0'
    p=s.path(r['id'])/'artifacts'/r['tasks'][0]['report_ref'];p.write_text('tampered')
    assert s.snapshot(r['id'])['decision']=='inconclusive'


def test_import_invalid_and_missing_coverage(tmp_path):
    s=IntegrationStore(tmp_path)
    r=s.import_reports(str(uuid.uuid4()),'bad',CONTEXT,[{'id':'unit','format':'junit','raw':b'<testsuite/>'}],[RULE]);assert r['decision']=='inconclusive' and r['tasks'][0]['state']=='error'
    with pytest.raises(ValueError):s.import_reports(str(uuid.uuid4()),'bad',CONTEXT,[{'id':'unit','format':'junit','raw':JUNIT}],[])


def test_collect_rejects_links_escape_and_freezes_bytes(tmp_path):
    (tmp_path/'source.py').write_text('print(1)');(tmp_path/'link.py').symlink_to(tmp_path/'source.py')
    assert collect(tmp_path,['source.py'])[1]['source.py']==b'print(1)'
    for name in ('../escape','/etc/passwd','link.py'):
        with pytest.raises(ValueError):collect(tmp_path,[name])


def test_api_import_and_browser_origin(tmp_path):
    app=create_app(Store(tmp_path));client=TestClient(app)
    assert len(client.get('/api/integrations/catalog').json()['formats'])==33
    body={'request_id':str(uuid.uuid4()),'name':'API test','context':CONTEXT,'reports':[{'id':'unit','format':'junit','content':JUNIT.decode()}],'rules':[RULE]}
    response=client.post('/api/integrations/import',json=body);assert response.status_code==200,response.text
    r=response.json();assert r['decision']=='reject'
    assert client.get('/api/integrations/runs/'+r['id']+'/export/junit').status_code==200
    assert client.post('/api/integrations/import',json=body,headers={'Origin':'https://evil.invalid'}).status_code==403


def test_service_pagination_and_token_boundary(monkeypatch):
    monkeypatch.setenv('ACCEPTANCE_TEST_TOKEN','fixture-token')
    calls=[]
    def handler(request):
        calls.append(request)
        if '/tests/1/' in str(request.url):return httpx.Response(200,json={'id':1})
        if 'offset=1' in str(request.url):return httpx.Response(200,json={'count':2,'results':[{'id':2,'test':1}],'next':None})
        return httpx.Response(200,json={'count':2,'results':[{'id':1,'test':1}],'next':'https://dojo.test/api/v2/findings/?test=1&offset=1'})
    s=Service('https://dojo.test','ACCEPTANCE_TEST_TOKEN','defectdojo',httpx.MockTransport(handler))
    assert len(s.dojo_pull(1)['findings'])==2
    with pytest.raises(ValueError):s.request('https://other.test/exfiltrate')
    assert all(x.headers['Authorization']=='Token fixture-token' for x in calls);s.close()

@pytest.mark.parametrize('mode',['loop','foreign','wrong-test','short'])
def test_bad_service_pagination_fails(monkeypatch,mode):
    monkeypatch.setenv('ACCEPTANCE_TEST_TOKEN','fixture-token')
    def handler(request):
        if '/tests/' in str(request.url):return httpx.Response(200,json={'id':1})
        return httpx.Response(200,json={'count':2,'results':[{'id':1,'test':2 if mode=='wrong-test' else 1}],'next':{'loop':'api/v2/findings/?test=1&limit=100','foreign':'https://other.test/','wrong-test':None,'short':None}[mode]})
    s=Service('https://dojo.test','ACCEPTANCE_TEST_TOKEN','defectdojo',httpx.MockTransport(handler))
    with pytest.raises(ValueError):s.dojo_pull(1)
    s.close()


def test_service_write_is_not_retried_and_keeps_old_findings(monkeypatch):
    monkeypatch.setenv('ACCEPTANCE_TEST_TOKEN','fixture-token');calls=[]
    def handler(request):calls.append(request);return httpx.Response(503)
    s=Service('https://dojo.test','ACCEPTANCE_TEST_TOKEN','defectdojo',httpx.MockTransport(handler))
    with pytest.raises(ValueError):s.dojo_import(b'{}','Generic Findings Import',engagement=1)
    assert len(calls)==1 and b'close_old_findings' in calls[0].content and b'false' in calls[0].content;s.close()


def test_rp_and_sonar_contracts(monkeypatch):
    monkeypatch.setenv('ACCEPTANCE_TEST_TOKEN','fixture-token')
    def handler(request):
        path=request.url.path
        if path.endswith('/launch/9'):data={'id':9,'status':'PASSED'}
        elif path.endswith('/item'):data={'page':{'number':1,'totalElements':1,'totalPages':1},'content':[{'id':1,'name':'ok','status':'PASSED','type':'STEP'}]}
        elif path.endswith('/search'):data={'analyses':[{'key':'a','revision':'abc'}]}
        elif path.endswith('/component'):data={'component':{'key':'p','measures':[{'metric':'coverage','value':'80'}]}}
        else:data={'projectStatus':{'status':'OK'}}
        return httpx.Response(200,json=data)
    s=Service('https://service.test','ACCEPTANCE_TEST_TOKEN','reportportal',httpx.MockTransport(handler))
    assert parse('reportportal',encode(s.reportportal_pull('project',9)))['metrics']['tests.total']==1
    assert parse('sonarqube',encode(s.sonar_pull('p','main','abc')))['metrics']['sonar.coverage']==80
    with pytest.raises(ValueError):s.sonar_pull('p','main','other')
    s.close()

@pytest.mark.parametrize('mode',['timeout','cancel'])
def test_real_executor_interrupts_and_cleans_containers(tmp_path,mode):
    import threading,time,subprocess
    repo=tmp_path/'repo';repo.mkdir();(repo/'slow.test.mjs').write_text("import test from 'node:test';test('slow',async()=>{await new Promise(r=>setTimeout(r,30000));});")
    s=IntegrationStore(tmp_path/'data')
    profile=dict(id='interruption',name='interruption',repository=str(repo),version='v1',environment='docker',scope='isolated timeout test',files=['slow.test.mjs'],tasks=[dict(id='unit',tool='node-test',target='slow.test.mjs',timeout=1 if mode=='timeout' else 40)],rules=[RULE])
    s.register(profile);r=s.create('interruption');results=[]
    thread=threading.Thread(target=lambda:results.append(s.execute(r['id'])));thread.start()
    if mode=='cancel':
        for _ in range(100):
            if s.read(r['id'])['tasks'][0]['state']=='running':break
            time.sleep(.02)
        s.cancel(r['id'])
    thread.join(timeout=20);assert not thread.is_alive()
    assert results[0]['decision']=='inconclusive'
    assert results[0]['tasks'][0]['state']==('cancelled' if mode=='cancel' else 'error')
    assert not subprocess.check_output(['docker','ps','-aq','--filter','label=acceptance.run='+r['id']]).strip()


def test_no_silent_pass_for_skipped_tests_or_missing_sarif_execution():
    report=parse('junit',b'<testsuite><testcase name="skipped"><skipped/></testcase></testsuite>');assert not report['complete']
    d=dict(SAMPLES['sarif']);d['runs']=[{'tool':{'driver':{'name':'scanner'}},'results':[]}]
    assert not parse('sarif',encode(d))['complete']


def test_playwright_retries_are_preserved():
    d=json.loads(raw(SAMPLES['playwright']));d['suites'][0]['specs'][0]['tests'][0]['results']=[{'status':'failed','retry':0,'duration':1,'errors':[{'message':'failed once'}]},{'status':'passed','retry':1,'duration':1}];d['stats'].update(expected=0,flaky=1)
    r=parse('playwright',encode(d));assert r['metrics']['tests.flaky']==1 and len(r['tests'][0]['attempts'])==2
    assert evaluate([dict(id='flaky',kind='metric',tasks=['unit'],metric='tests.flaky',threshold=0)],[task(r)])[0]['status']=='failed'


def test_unknown_duration_cannot_pass_latency_gate():
    for kind in ('junit', 'reportportal', 'newman', 'sonarqube'):
        report = parse(kind, raw(SAMPLES[kind]))
        assert 'tests.duration_ms' not in report['metrics']
        rule = dict(id='latency', kind='metric', tasks=['unit'], metric='tests.duration_ms', threshold=1)
        assert evaluate([rule], [task(report)])[0]['status'] == 'unknown'


def test_required_test_duplicate_names_need_stable_id():
    report = parse('junit', b'<testsuite><testcase name="same" classname="a"><failure/></testcase><testcase name="same" classname="b"/></testsuite>')
    rule = dict(id='required', kind='required-tests', tasks=['unit'], values=['same'])
    assert evaluate([rule], [task(report)])[0]['status'] == 'unknown'
    rule['values'] = [report['tests'][0]['id']]
    assert evaluate([rule], [task(report)])[0]['status'] == 'failed'


def test_snapshot_preserves_executable_mode(tmp_path):
    from acceptance.integrations.runner import frozen_source
    source = tmp_path / 'source'; source.mkdir()
    script = source / 'script.sh'; script.write_text('#!/bin/sh\nexit 0\n'); script.chmod(0o755)
    destination = tmp_path / 'snapshot'
    result = frozen_source(source, ['script.sh'], destination)
    assert result['files'][0]['mode'] == 0o755
    assert (destination / 'script.sh').stat().st_mode & 0o777 == 0o755


def test_import_environment_matrix_is_bound_to_request(tmp_path):
    s = IntegrationStore(tmp_path); request_id = str(uuid.uuid4())
    reports = [{'id': env, 'format': 'junit', 'environment': env, 'raw': b'<testsuite><testcase name="ok"/></testsuite>'} for env in ('chromium', 'firefox')]
    rules = [dict(id='matrix', kind='environments', tasks=['chromium', 'firefox'], values=['chromium', 'firefox'])]
    run = s.import_reports(request_id, 'matrix', CONTEXT, reports, rules)
    assert run['decision'] == 'allow'
    reports[1]['environment'] = 'chromium'
    with pytest.raises(ValueError): s.import_reports(request_id, 'matrix', CONTEXT, reports, rules)
    run = s.import_reports(str(uuid.uuid4()), 'missing environment', CONTEXT, reports, rules)
    assert run['decision'] == 'reject'
