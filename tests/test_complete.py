from copy import deepcopy
import json
from pathlib import Path
import pytest
from acceptance.complete import parse
from acceptance.projects import PROFILE_SCHEMA
import jsonschema


def test_local_profile_has_only_executable_criteria_and_explicit_scope():
    p=json.loads(Path('projects/assessment-local-v3.json').read_text())
    jsonschema.validate(p,PROFILE_SCHEMA)
    assert len(p['criteria'])==17
    assert not any(c['kind']=='gap' for c in p['criteria'])
    python=next(c for c in p['criteria'] if c['kind']=='python')
    assert len(python['test_names'])==24
    assert not any('native_windows' in x for x in python['test_names'])
    assert len(p['exclusions'])==3
    old=json.loads(Path('projects/assessment-expanded-v1.json').read_text())
    assert sum(c['kind']=='gap' for c in old['criteria'])==5
    assert 'exclusions' not in old


def semgrep():
    return {'version':'test','errors':[],'paths':{'scanned':['/source/server.ts']},'results':[]}


@pytest.mark.parametrize('mutation',['errors','empty','duplicate','exit','position'])
def test_semgrep_incomplete_reports_cannot_pass(mutation):
    r=semgrep();code=0
    if mutation=='errors':r['errors']=[{'message':'parse error'}]
    if mutation=='empty':r['paths']['scanned']=[]
    if mutation=='duplicate':r['paths']['scanned']*=2
    if mutation=='exit':code=2
    if mutation=='position':r['results']=[{'check_id':'x','path':'elsewhere','start':{'line':1},'extra':{'message':'bad'}}];code=1
    with pytest.raises(ValueError):parse({'kind':'semgrep'},r,code)


def test_semgrep_keeps_real_hit_without_claiming_exploit():
    r=semgrep();r['results']=[{'check_id':'eval','path':'/source/server.ts','start':{'line':4},'extra':{'message':'possible injection'}}]
    got=parse({'kind':'semgrep'},r,1)
    assert got['status']=='failed' and 'server.ts:4' in got['actual']


def zap():
    target='http://127.0.0.1:5380'
    plan=json.loads(Path('acceptance/recipes/assessment/zap-plan.json').read_text())
    return {'tool':'OWASP ZAP','version':'test','target':target,'spider_status':'100','active_status':'100','pending_passive':0,'messages':100,'urls':[target+p for p in ['/login','/register','/api/health','/api/batches','/api/auth/me','/api/admin/overview']], 'selected_rules':plan['enabled_ids'], 'excluded_rules':plan['excluded'], 'active_progress':[target,{'HostProcess':[{'Plugin':['Rule',rid,'release','Complete']} for rid in plan['enabled_ids']]}], 'native_report':{'site':[{'@name':target,'alerts':[]}]}}


@pytest.mark.parametrize('mutation',['spider','active','passive','coverage','site','exit','skipped_rule','missing_rule','duplicate_rule','changed_plan','hidden_exclusion'])
def test_zap_partial_scan_cannot_become_pass(mutation):
    r=zap();code=0
    if mutation=='spider':r['spider_status']='40'
    if mutation=='active':r['active_status']='70'
    if mutation=='passive':r['pending_passive']=1
    if mutation=='coverage':r['urls'].pop()
    if mutation=='site':r['native_report']['site'][0]['@name']='https://different.example'
    if mutation=='exit':code=1
    if mutation=='skipped_rule':r['active_progress'][1]['HostProcess'][0]['Plugin'][3]='Skipped'
    if mutation=='missing_rule':r['active_progress'][1]['HostProcess'].pop()
    if mutation=='duplicate_rule':r['active_progress'][1]['HostProcess'].append(r['active_progress'][1]['HostProcess'][0])
    if mutation=='changed_plan':r['selected_rules'].pop()
    if mutation=='hidden_exclusion':r['excluded_rules']=[]
    with pytest.raises(ValueError):parse({'kind':'zap'},r,code)


def recovery():
    return {'before_db':{'users':'1:abc'},'after_db':{'users':'1:abc'},'before_files':{'material.bin':'a'*64},'after_files':{'material.bin':'a'*64},'dump_bytes':200,'dump_sha256':'b'*64,'original_stopped':True,'replacement_running':True,'probe':{'state':'FINALIZED','files':1,'verified_files':1},'recovery_seconds':2.5}


@pytest.mark.parametrize('mutation',['db','files','empty','stopped','probe','time','dump'])
def test_joint_recovery_requires_both_data_and_business_readback(mutation):
    r=recovery()
    if mutation=='db':r['after_db']={}
    if mutation=='files':r['after_files']['material.bin']='c'*64
    if mutation=='empty':r['before_files']=r['after_files']={}
    if mutation=='stopped':r['original_stopped']=False
    if mutation=='probe':r['probe']['verified_files']=0
    if mutation=='time':r['recovery_seconds']=float('nan')
    if mutation=='dump':r['dump_bytes']=0
    with pytest.raises(ValueError):parse({'kind':'joint-restore'},r,0)


def test_restore_preserves_measured_time_and_fails_on_bad_exit():
    r=recovery();assert '2.50' in parse({'kind':'joint-restore'},r,0)['actual']
    with pytest.raises(ValueError):parse({'kind':'joint-restore'},r,1)


def load_report():
    return {'state':{'testRunDurationMs':20001},'metrics':{
      'checks':{'values':{'fails':0,'passes':80},'thresholds':{'rate==1':{'ok':True}}},
      'iterations':{'values':{'count':40},'thresholds':{'count>=20':{'ok':True}}},
      'http_reqs':{'values':{'count':80}},'http_req_duration':{'values':{'p(95)':20}},
      'http_req_failed':{'values':{'rate':0},'thresholds':{'rate==0':{'ok':True}}},
      'vus_max':{'values':{'max':5}}}}


@pytest.mark.parametrize('mutation',['duration','requests','iterations','threshold','vus','exit','nan'])
def test_load_incomplete_or_changed_plan_is_not_pass(mutation):
    r=load_report();code=0
    if mutation=='duration':r['state']['testRunDurationMs']=10
    if mutation=='requests':r['metrics']['http_reqs']['values']['count']=0
    if mutation=='iterations':r['metrics']['iterations']['values']['count']=1
    if mutation=='threshold':r['metrics']['checks']['thresholds']={}
    if mutation=='vus':r['metrics']['vus_max']['values']['max']=1
    if mutation=='exit':code=99
    if mutation=='nan':r['metrics']['http_req_duration']['values']['p(95)']=float('nan')
    with pytest.raises(ValueError):parse({'kind':'k6'},r,code)


def test_load_body_assertion_failure_is_preserved_even_with_http_200():
    r=load_report();r['metrics']['checks']['values']['fails']=1;r['metrics']['checks']['thresholds']['rate==1']['ok']=False
    assert parse({'kind':'k6'},r,99)['status']=='failed'


def test_replacement_database_preserves_database_user(tmp_path,monkeypatch):
    from acceptance.expanded import Runner
    from acceptance.engine import Store
    store=Store(tmp_path/'store');run=store.create('fixed');runner=Runner(store,run)
    runner.image='frozen-image';runner.url='http://127.0.0.1:12345'
    calls=[];monkeypatch.setattr(runner,'must',lambda label,args,**kw:calls.append(args))
    runner.start_application(database='acceptance_recovery',seed=False)
    assert 'DATABASE_URL=postgresql://acceptance_test:synthetic@db:5432/acceptance_recovery' in calls[0]
    assert 'SEED_DEMO=0' in calls[0]


def test_zap_scope_accepts_origin_and_paths_but_rejects_other_targets():
    import ast,re
    tree=ast.parse(Path('acceptance/recipes/assessment/zap_scan.py').read_text())
    call=next(n for n in ast.walk(tree) if isinstance(n,ast.Call) and isinstance(n.func,ast.Attribute) and n.func.attr=='include_in_context')
    pattern=ast.literal_eval(call.args[1])
    for url in ['http://127.0.0.1:5380','http://127.0.0.1:5380/','http://127.0.0.1:5380/api/health']:
        assert re.fullmatch(pattern,url)
    for url in ['http://127.0.0.1:5381/','http://127x0x0x1:5380/','https://example.com/']:
        assert not re.fullmatch(pattern,url)
