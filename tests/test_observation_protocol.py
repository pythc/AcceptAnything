"""Neutral cross-runtime contracts for observed exceptions, identity and paths."""
import asyncio
import importlib.util
import json
import os
from pathlib import Path
import subprocess
import shutil
import sys
import uuid

import pytest

ROOT = Path(__file__).resolve().parents[1]
DRIVERS = Path(os.environ.get('ACCEPTANCE_TEST_DRIVER_DIR', ROOT/'acceptance/universal')).resolve()
NODE = os.environ.get('ACCEPTANCE_TEST_NODE') or shutil.which('node')


def load_driver(name):
    label = 'acceptance.universal.test_observation_' + name
    path=DRIVERS/(name+'.py')
    if name in {'citation_indent','citations'} and 'ACCEPTANCE_TEST_DRIVER_DIR' not in os.environ:
        path=ROOT/'acceptance/planning'/(name+'.py')
    spec = importlib.util.spec_from_file_location(label, path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[label] = module
    spec.loader.exec_module(module)
    return module


@pytest.fixture(params=['python', 'node'])
def harness(request, tmp_path):
    runtime = request.param
    name = 'neutral_' + uuid.uuid4().hex + ('.py' if runtime == 'python' else '.mjs')
    source = '''from pathlib import Path
shared = {}
def object_value(): return shared
def new_value(): return {}
def echo(value): return value
def failure(): raise ValueError('closed resource')
async def delayed_failure(): raise ValueError('closed resource')
def raised_business_value(): return {'raised': True}
def make_directory(value): Path(value).mkdir(); return value
def read_file(value): return Path(value).read_bytes().hex()
def invoke(callback,value): return callback(value)
''' if runtime == 'python' else '''import fs from 'node:fs';
const shared={};
export function object_value(){return shared;}
export function new_value(){return {};}
export function echo(value){return value;}
export function failure(){throw new RangeError('closed resource');}
export async function delayed_failure(){throw new RangeError('closed resource');}
export function raised_business_value(){return {raised:true};}
export function make_directory(value){fs.mkdirSync(value);return value;}
export function read_file(value){return fs.readFileSync(value).toString('hex');}
export function invoke(callback,value){return callback(value);}
'''
    (tmp_path/name).write_text(source)

    def run(steps, cleanup=None):
        payload = dict(steps=steps, cleanup=cleanup or [])
        if runtime == 'python':
            return asyncio.run(load_driver('scenario').execute(payload, tmp_path))
        assert NODE, 'Node.js is required for the JavaScript protocol contract tests'
        program = "require(process.argv[1]).execute(JSON.parse(process.argv[2]),process.argv[3]).then(r=>console.log(JSON.stringify(r))).catch(e=>{console.error(e);process.exit(1)})"
        result = subprocess.run([NODE, '-e', program, str(DRIVERS/'scenario.cjs'), json.dumps(payload), str(tmp_path)], capture_output=True, text=True, check=True)
        return json.loads(result.stdout)

    return runtime, name, run


def call(name, identifier, export, **extra):
    return dict(id=identifier, op='call', module=name, export=export, **extra)


def test_observed_exception_is_data_and_no_exception_is_not_faked(harness):
    runtime, name, run = harness
    rows = [dict(call(name, 'failure', 'failure'), op='observe_call'),
            dict(call(name, 'delayed', 'delayed_failure'), op='observe_call'),
            dict(call(name, 'plain', 'raised_business_value'), op='observe_call')]
    result = run(rows)
    assert result['status'] == 'completed' and result['temporary_directory_removed']
    first, delayed, plain = [s['value'] for s in result['steps']]
    assert first['raised'] and delayed['raised']
    assert first['exception']['type'] == ('ValueError' if runtime == 'python' else 'RangeError')
    assert first['exception']['message'] == 'closed resource'
    assert plain == dict(raised=False, return_observable=True, value={'raised': True})
    # Host compares the observed type; merely catching an exception is not a pass.
    from acceptance.universal.scenarios import evaluate
    from acceptance.universal.runtime import compare
    from jsonpointer import resolve_pointer
    flow = dict(steps=rows, cleanup=[], checks=[dict(step='failure', pointer='/exception/type', expected='DifferentError', comparison='equals')])
    assert evaluate(flow, result, compare, resolve_pointer)[0] == 'failed'


def test_binding_error_is_not_caught_as_expected_target_exception(harness):
    _, name, run = harness
    result = run([dict(call(name, 'missing', 'absent'), op='observe_call')])
    assert result['status'] == 'error'
    assert result['steps'][0]['status'] == 'error'


def test_identity_compares_handles_and_rejects_scalar_interning(harness):
    _, name, run = harness
    rows = [call(name, 'one', 'object_value'), call(name, 'two', 'object_value'), call(name, 'three', 'new_value'),
            dict(id='same', op='identity', target='one', value={'$ref':'two'}),
            dict(id='distinct', op='identity', target='one', value={'$ref':'three'})]
    result = run(rows)
    assert result['status'] == 'completed'
    assert [s['value'] for s in result['steps'][-2:]] == [True, False]
    result = run([call(name, 'value', 'echo', args=[1]), dict(id='same', op='identity', target='value', value={'$ref':'value'})])
    assert result['status'] == 'error'


def test_path_observation_distinguishes_directory_file_and_absence(harness):
    _, name, run = harness
    rows = [call(name, 'directory', 'make_directory', args=[{'$path':'created'}]),
            dict(id='file', op='write_file', path='created/data.txt', value='text'),
            call(name, 'missing', 'echo', args=[{'$path':'missing'}])]
    rows += [dict(id='inspect_'+key, op='inspect_path', target=key) for key in ('directory','file','missing')]
    result = run(rows)
    assert result['status'] == 'completed'
    directory, file, missing = [s['value'] for s in result['steps'][-3:]]
    assert directory['is_dir'] and not directory['is_file']
    assert file['is_file'] and file['exists']
    assert not missing['exists'] and not missing['is_dir'] and not missing['is_file']


def test_path_observation_rejects_outside_paths_and_symlink_children(harness, tmp_path):
    _, name, run = harness
    (tmp_path/'escape').symlink_to(tmp_path.parent, target_is_directory=True)
    for value in (str(tmp_path.parent), str(tmp_path/'escape'/'nonexistent')):
        result = run([call(name, 'path', 'echo', args=[value]), dict(id='inspect', op='inspect_path', target='path')])
        assert result['status'] == 'error'


def test_binary_fixtures_preserve_bytes_and_reject_encoding_loss(harness):
    _,name,run=harness
    for encoding,value,expected in [('latin-1','café','636166e9'),('ascii','data','64617461'),('base64','AP+A','00ff80'),('utf-8','中文','e4b8ade69687')]:
        result=run([dict(id='file',op='write_file',path='input.dat',value=value,encoding=encoding),call(name,'bytes','read_file',args=[{'$ref':'file'}])])
        assert result['status']=='completed' and result['steps'][-1]['value']==expected
    result=run([dict(id='file',op='write_file',path='input.dat',value='中文',encoding='latin-1')])
    assert result['status']=='error'
    schemas=load_driver('scenarios')
    for invalid in ['!!==','AP+A\n','AB==']:
        with pytest.raises(ValueError,match='编码'):schemas.Step(id='file',op='write_file',path='data',value=invalid,encoding='base64')


def test_callback_reads_real_input_fields_instead_of_replacing_them_with_literals(harness):
    _,name,run=harness
    callback={'$callback':{'params':['request'],'return':{'$ref':'request','pointer':'/body/message'}}}
    for message in ['first actual input','different input']:
        result=run([call(name,'received','invoke',args=[callback,{'body':{'message':message}}])])
        assert result['status']=='completed' and result['steps'][0]['value']==message
        assert result['callbacks'][0]['return_value']['value']==message
    assert run([call(name,'missing','invoke',args=[callback,{'body':{}}])])['status']=='error'
    schemas=load_driver('scenarios')
    flow=schemas.Scenario(steps=[call(name,'received','invoke',args=[callback,{'body':{'message':'data'}}])],checks=[dict(step='received',expected='data')])
    target=dict(units=[dict(id='unit',runtime='python')],interfaces=[dict(unit='unit',path=name,functions=[dict(name='invoke')])],execution_contract={'version':14})
    with pytest.raises(ValueError,match='冻结协议'):schemas.validate_bindings(flow,target,'unit')
    target['execution_contract']['version']=15;schemas.validate_bindings(flow,target,'unit')


def test_new_protocol_is_gated_and_cleanup_cannot_swallow_exceptions():
    schemas = load_driver('scenarios')
    source = {'units':[{'id':'unit','runtime':'python'}], 'interfaces':[{'unit':'unit','path':'api.py','functions':[{'name':'open'}]}], 'execution_contract':{'version':14}}
    steps = [call('api.py', 'value', 'open'), dict(id='observed', op='observe_call', target='value', member='read')]
    flow = schemas.Scenario(steps=steps, checks=[dict(step='observed',pointer='/raised',expected=True)])
    with pytest.raises(ValueError, match='冻结协议'):
        schemas.validate_bindings(flow, source, 'unit')
    source['execution_contract']['version']=15
    schemas.validate_bindings(flow, source, 'unit')
    cleanup_flow = schemas.Scenario(steps=steps[:1], cleanup=[steps[1]], checks=[dict(step='value',expected=None)])
    with pytest.raises(ValueError, match='清理步骤'):
        schemas.validate_bindings(cleanup_flow, source, 'unit')
    source['units'][0]['runtime']='node'
    invalid=schemas.Scenario(steps=[steps[0],dict(id='ctx',op='enter',target='value')],checks=[dict(step='value',expected=None)])
    with pytest.raises(ValueError,match='JavaScript流程'):schemas.validate_bindings(invalid,source,'unit')


def test_invalid_context_is_a_protocol_error_and_business_errors_stay_unclassified(tmp_path):
    name='neutral.py';(tmp_path/name).write_text('def object_value(): return {}\ndef failure(): raise ValueError("target failure")\n')
    driver=load_driver('scenario')
    result=asyncio.run(driver.execute(dict(steps=[call(name,'value','object_value'),dict(id='ctx',op='enter',target='value')],cleanup=[]),tmp_path))
    assert result['status']=='error' and result['steps'][1]['error_origin']=='protocol'
    target_error=asyncio.run(driver.execute(dict(steps=[call(name,'fail','failure')],cleanup=[]),tmp_path))
    assert target_error['status']=='error' and 'error_origin' not in target_error['steps'][0]


def test_business_gaps_keep_individual_categories_and_old_version_grouping(monkeypatch):
    service=load_driver('service');classification=load_driver('coverage')
    from acceptance.universal import coverage
    monkeypatch.setattr(coverage,'classify',classification.classify)
    rows=[dict(name=label+' · 中文用例',status='error',detail=json.dumps(dict(gap_category=category,steps={'steps':[dict(status='error',error=label+' cause')]}))) for label,category in [('binding','case'),('target','unclassified')]]
    run=dict(universal_generation=dict(requirements=[],batches=[]),universal_plan=dict(execution_contract={'version':15},batches=[],scope='selected'),tasks=[dict(id='unit-business',tool='universal-business',state='completed',report={'tests':rows})])
    gaps=[g for g in service.completion(run)['gaps'] if g['kind']=='execution']
    assert [(g['case'],g['category']) for g in gaps]==[('binding','case'),('target','unclassified')]
    assert len(gaps[0]['observations'])==1 and 'binding cause' in gaps[0]['reason']
    run['universal_plan']['execution_contract']['version']=14
    assert len([g for g in service.completion(run)['gaps'] if g['kind']=='execution'])==1
    run['universal_plan'].pop('execution_contract')
    assert len([g for g in service.completion(run)['gaps'] if g['kind']=='execution'])==1


def test_local_command_inheritance_is_bound_to_installed_dependency_and_conflicts_are_visible():
    discover=load_driver('discovery')
    units=[dict(id='base',runtime='python',manifest='pyproject.toml',cli_commands={'runner':['/work/venv/bin/runner']},capabilities=['module','cli'],local_dependencies=[]),
           dict(id='child',runtime='python',manifest='example/pyproject.toml',cli_commands={},capabilities=['module'],local_dependencies=['base']),
           dict(id='unrelated',runtime='python',manifest='other/pyproject.toml',cli_commands={},capabilities=['module'],local_dependencies=[])]
    gaps=[];discover.link_local_commands(units,gaps)
    assert units[1]['cli_commands']=={'runner':['/work/venv/bin/runner']}
    assert units[1]['cli_origins']['runner']['manifest']=='pyproject.toml'
    assert 'cli' in units[1]['capabilities'] and not units[2]['cli_commands'] and not gaps
    # A name collision is never silently resolved according to install order.
    units[2]['cli_commands']={'runner':['/work/venv/bin/runner']}
    units[1]['cli_commands']={};units[1]['local_dependencies']=['base','unrelated']
    discover.link_local_commands(units,gaps)
    assert not units[1]['cli_commands'] and 'cli' not in units[1]['capabilities']
    assert len(gaps)==1 and '冲突' in gaps[0]['reason']


def test_nested_rst_quote_preserves_relative_indent_and_rejects_changed_text():
    citation=load_driver('citation_indent')
    source='.. code-block:: html\n\n    <ul>\n        {% if user %}\n          <li>User</li>\n        {% endif %}\n    </ul>\n'
    quote='{% if user %}\n  <li>User</li>\n{% endif %}'
    assert citation.locate_rst_literal(source,quote) is None
    found=citation.locate_rst_literal(source,quote,relative=True)
    assert found and found[2]=='rst-relative-code-indent-v2'
    assert source[found[0]:found[1]]=='        {% if user %}\n          <li>User</li>\n        {% endif %}'
    assert citation.locate_rst_literal(source,quote.replace('  <li>','<li>'),relative=True) is None
    assert citation.locate_rst_literal(source,quote.replace('User','Admin'),relative=True) is None
    assert citation.locate_rst_literal(source+source,quote,relative=True) is None


def test_ambiguous_exact_quotes_are_rejected_only_by_new_contract():
    citation=load_driver('citations');quote='the same original statement';text='First '+quote+'\nSecond '+quote
    assert citation.locate(text,quote) is not None
    assert citation.locate(text,quote,unique_exact=True) is None
    found=citation.locate(text,'Second '+quote,unique_exact=True)
    assert found and text[found[0]:found[1]]=='Second '+quote


def test_output_budget_partitions_all_focus_evidence_without_a_repository_limit(tmp_path):
    documents=load_driver('documents')
    (tmp_path/'README.md').write_text('[Guide](docs/guide.rst)');(tmp_path/'docs').mkdir()
    source=''.join('rule '+str(i)+' exact original evidence\n' for i in range(5000));(tmp_path/'docs/guide.rst').write_text(source)
    primary=[dict(title='README.md',origin='README.md#chars=0:23',content='[Guide](docs/guide.rst)')]
    groups,receipt=documents.enrich(tmp_path,[primary],documents.catalog(tmp_path,['README.md','docs/guide.rst']),[])
    focused=[d for group,scope in zip(groups,receipt['batches']) for d in group if d['id'] in scope.get('focus',scope['support'])]
    assert len(groups)>20 and ''.join(d['content'] for d in focused)==source
    assert len({d['origin'] for d in focused})==len(focused)
    for group,scope in zip(groups,receipt['batches']):
        assert sum(len(d['content']) for d in group if d['id'] in scope.get('focus',scope['support']))<=8000
        assert sum(len(d['content']) for d in group)<=45000
    assert receipt['budget']['total_scope_limit'] is None and any(s['context_omitted'] for s in receipt['batches'])


def test_mapping_like_headers_preserve_public_key_semantics():
    driver=load_driver('scenario')
    class PublicHeaders:
        def keys(self):return ['Location']
        def __getitem__(self,key):
            if key.lower()=='location':return '/next'
            raise KeyError(key)
    class Response:
        headers=PublicHeaders()
    assert driver.project(Response(),'/headers/location')=='/next'
    with pytest.raises(KeyError):driver.project(Response(),'/headers/missing')


def test_exact_status_assertions_require_the_actual_number_in_the_quote():
    schemas=load_driver('scenarios')
    flow=schemas.Scenario(steps=[call('api.py','response','request'),dict(id='code',op='get',target='response',member='status_code')],checks=[dict(step='code',expected=302)])
    with pytest.raises(ValueError,match='数值依据'):schemas.validate_status_basis(flow,'The response redirects to the login page.')
    schemas.validate_status_basis(flow,'The response has status 302 and redirects to the login page.')
    with pytest.raises(ValueError,match='数值依据'):schemas.validate_status_basis(flow,'Status 3020 is a separate code.')


def test_standard_schema_checks_dynamic_results_without_accepting_other_types():
    schemas=load_driver('scenarios');rule={'type':'integer','minimum':1,'maximum':65535}
    assert schemas.schema_matches(19876,rule)
    for bad in [0,-1,65536,True,'19876']:
        assert not schemas.schema_matches(bad,rule)
    data_schema={'type':'object','properties':{'$ref':{'type':'string'},'$id':{'type':'string'},'count':{'$ref':'#/$defs/count'}},'required':['count'],'$defs':{'count':{'type':'integer','minimum':1}}}
    assert schemas.schema_matches({'$ref':'data only','$id':'data only','count':3},data_schema)
    assert not schemas.schema_matches({'count':0},data_schema)
    for bad in [{},True,{'minimum':1},{'type':'object','$ref':'https://outside.invalid/schema'},{'type':'string','pattern':'(a+)+$'},{'type':'object','properties':{'value':{'$ref':'other.json'}}}]:
        with pytest.raises(ValueError):schemas.validate_schema(bad)
    target={'units':[{'id':'unit','runtime':'python'}],'interfaces':[{'unit':'unit','path':'api.py','functions':[{'name':'open'}]}],'execution_contract':{'version':14}}
    flow=schemas.Scenario(steps=[call('api.py','value','open')],checks=[dict(step='value',comparison='json_schema',expected=rule)])
    with pytest.raises(ValueError,match='冻结协议'):schemas.validate_bindings(flow,target,'unit')


def test_environment_selection_is_bound_to_archived_receipt_and_images(tmp_path):
    import copy
    environment=load_driver('environment')
    unit=dict(id='unit',runtime='python',provides=['public_api'])
    attempt=dict(index=0,image_key='universal-python',image='sha256:fixed',status='ready',probes=[])
    receipt=dict(unit='unit',constraint='',modules=['public_api'],selected=0,attempts=[attempt])
    class Store:
        def artifact_bytes_for_record(self,run,aid):return {},json.dumps(receipt).encode()
    run=dict(universal_plan={'discovery':{'units':[unit]}},images={'universal-python':dict(id='sha256:fixed',versions={'python':dict(exit_code=0,text='Python 3.11.17')})},tasks=[dict(id='unit-prepare',tool='universal-prepare',target='unit',state='completed')],artifacts=[dict(id='receipt',name='unit-prepare/environment-selection.json')],universal_environment_choices={'unit':0},universal_environment_attempts={'unit':[copy.deepcopy(attempt)]})
    environment.verify_selection(Store(),run)
    run['universal_environment_choices']['unit']=1
    with pytest.raises(ValueError,match='选择与原件'):environment.verify_selection(Store(),run)
    run['universal_environment_choices']['unit']=0;run['universal_environment_attempts']['unit'][0]['image']='sha256:other'
    with pytest.raises(ValueError,match='尝试与原件'):environment.verify_selection(Store(),run)


def test_ci_conditions_use_declared_linux_variant_not_assumed_latest(tmp_path):
    preparation=load_driver('preparation')
    file=tmp_path/'.github/workflows/ci.yml';file.parent.mkdir(parents=True)
    body='''jobs:
  test:
    runs-on: ${{ matrix.os }}
    strategy:
      matrix:
        os: [ubuntu-22.04]
    steps:
    - if: matrix.os != 'ubuntu-22.04'
      run: pip install inappropriate
    - if: matrix.os == 'ubuntu-22.04'
      run: pip install declared
    - run: pytest
'''
    file.write_text(body)
    result=preparation.discover(tmp_path,['.github/workflows/ci.yml'],dict(path='.',test_files=[]))
    assert [p['spec'] for p in result['optional_packages']]==['declared']
    assert result['optional_packages'][0]['origins'][0]['linux_variants']==['ubuntu-22.04']
    file.write_text(body.replace('os: [ubuntu-22.04]','os: [ubuntu-22.04, ubuntu-24.04]'))
    assert not preparation.discover(tmp_path,['.github/workflows/ci.yml'],dict(path='.',test_files=[]))['optional_packages']


@pytest.mark.parametrize('older_works',[True,False])
def test_runtime_probe_tries_declared_compatible_candidate_without_rewriting_dependencies(tmp_path,monkeypatch,older_works):
    environment=load_driver('environment')
    from acceptance.universal import runtime
    images={key:dict(id=key,versions={'python':{'exit_code':0,'text':'Python '+version}}) for key,version in [('universal-python','3.11.17'),('universal-python312','3.12.15')]}
    run={'images':images};unit={'id':'unit','settings':{'project':{'requires-python':'>=3.11'}},'provides':['example_api']}
    installed=[]
    def prepare(run,unit,out,cancelled,*,image_key):
        installed.append(image_key)
        return runtime.result_file(out,[dict(name='隔离环境与依赖准备',status='passed')]),dict(argv=['install',image_key],exit_code=0)
    def command(run,unit,args,out,cancelled,**options):
        assert options['offline'] is True
        return dict(argv=args,exit_code=0 if older_works and run['universal_environment_choices']['unit']==1 else 1),{}
    monkeypatch.setattr(runtime,'command',command)
    report,_=environment.prepare_candidates(run,unit,tmp_path,lambda:False,prepare)
    assert installed==['universal-python312','universal-python']
    assert run['universal_environment_choices']['unit']==(1 if older_works else 0)
    receipt=json.loads((tmp_path/'environment-selection.json').read_bytes())
    assert receipt['attempts'][0]['status']=='import-error'
    assert receipt['selected']==(1 if older_works else 0)
    assert [r['status'] for r in report['tests']]==(['passed'] if older_works else ['passed','error'])
    assert unit['settings']=={'project':{'requires-python':'>=3.11'}}


def test_environment_install_error_does_not_trigger_bootstrap_fallback(tmp_path):
    environment=load_driver('environment')
    images={key:dict(id=key,versions={'python':{'exit_code':0,'text':'Python '+version}}) for key,version in [('universal-python','3.11.17'),('universal-python312','3.12.15')]}
    count=[]
    def prepare(*args,**kwargs):count.append(kwargs['image_key']);raise ValueError('installation error')
    with pytest.raises(ValueError,match='installation error'):
        environment.prepare_candidates({'images':images},{'id':'unit'},tmp_path,lambda:False,prepare)
    assert count==['universal-python312']
    assert json.loads((tmp_path/'environment-selection.json').read_bytes())['selected'] is None


def test_cleanup_includes_unselected_runtime_attempts(tmp_path,monkeypatch):
    from types import SimpleNamespace
    runtime=load_driver('runtime');calls=[]
    def docker(*args,**kwargs):calls.append(args);return SimpleNamespace(returncode=1,stdout='',stderr='')
    monkeypatch.setattr(runtime,'docker',docker)
    run=dict(id='int-neutral',universal_plan={'discovery':{'units':[{'id':'unit'}]}},universal_environment_choices={'unit':1},universal_environment_attempts={'unit':[{'index':0},{'index':1}]})
    report,_=runtime.cleanup(run,tmp_path)
    removed=[args[-1] for args in calls if args[:2]==('volume','rm')]
    assert set(removed)=={'acceptance-universal-neutral-unit-work','acceptance-universal-neutral-unit-runtime-1-work'}
    assert report['tests'][0]['status']=='passed'
