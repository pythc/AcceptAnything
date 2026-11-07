import json
from pathlib import Path
import pytest
from acceptance.universal import discovery,generation,service,runtime
from acceptance.planning.models import Document
from acceptance.integrations.store import IntegrationStore
from acceptance.integrations.runner import encode,sha


def repo(tmp_path,files):
    root=tmp_path/'repo';root.mkdir()
    for name,content in files.items():
        p=root/name;p.parent.mkdir(parents=True,exist_ok=True);p.write_text(content)
    return root


def test_ast_index_reexports_signatures_and_does_not_import_target(tmp_path):
    root=repo(tmp_path,{'pyproject.toml':'[project]\nname="example"\nversion="1"',
        'src/pkg/__init__.py':'from .core import transform as convert\n__all__=["convert"]',
        'src/pkg/core.py':'raise RuntimeError("MUST NOT EXECUTE")\ndef transform(value: str, limit=5, *, strict=True):\n return value',
        **{f'benchmarks/b{i}.py':'def irrelevant(): pass' for i in range(140)}})
    files=sorted(str(f.relative_to(root)) for f in root.rglob('*') if f.is_file());d=discovery.discover(root,files)
    public=next(x for x in d['interfaces'] if x['path']=='src/pkg/__init__.py')
    assert public['functions'][0]['name']=='convert'
    assert public['functions'][0]['parameters'][0]['type']=='str'
    docs=[dict(content='使用 convert(value) 进行转换。')]
    selected,receipt=discovery.relevant(d['interfaces'],docs,5)
    assert selected[0]['path']=='src/pkg/__init__.py' and receipt['total']>100


def test_independent_execution_precedes_remote_design(tmp_path,monkeypatch):
    root=repo(tmp_path,{'pyproject.toml':'[project]\nname="neutral-library"\nversion="1"','api.py':'def twice(value):return value*2','README.md':'输入整数2，返回4。'})
    store=IntegrationStore(tmp_path/'store');p=service.prepare(store,str(root))
    full=json.loads((store.root/'automatic-plans'/(p['id']+'.json')).read_bytes())['record'];tools=[t['tool'] for t in full['profile']['tasks']]
    design=tools.index('universal-design')
    assert tools.index('universal-prepare')<design and tools.index('universal-build')<design
    assert tools.index('universal-business')>design and tools[-1]=='universal-cleanup'


def test_javascript_default_and_typescript_arrow_syntax_are_discovered(tmp_path):
    root=repo(tmp_path,{'package.json':'{"name":"neutral","exports":"./index.js","types":"index.d.ts"}',
        'index.js':'export default function f(value){throw Error("not an oracle")}',
        'index.d.ts':'export default function f(value: string): string;',
        'api.ts':'export const apply = async (count: number, suffix?: string): Promise<string> => "implementation";'})
    d=discovery.discover(root,sorted(str(f.relative_to(root)) for f in root.rglob('*') if f.is_file()))
    assert any(i['path']=='index.js' and i['functions'][0]['name']=='default' for i in d['interfaces'])
    assert all(not i['path'].endswith('.d.ts') for i in d['interfaces'])
    assert any(f['name']=='apply' and f['parameters'][1]['optional'] for i in d['interfaces'] for f in i['functions'])


def test_documents_are_fully_split_without_four_file_or_prefix_loss(tmp_path):
    text=('一段可追溯的独立需求。\n'*2500)+'最后一段必须读取。'
    root=repo(tmp_path,{'README.md':text,**{f'docs/specs/{i}.md':'需求必须有依据。' for i in range(23)}})
    candidates=[dict(path=str(p.relative_to(root))) for p in sorted(root.rglob('*.md'))]
    groups=list(discovery.batches(root,candidates));parts=[p for b in groups for p in b]
    assert ''.join(p['content'] for p in parts if p['title']=='README.md')==text
    assert len({p['title'] for p in parts})==24 and all(sum(len(d['content']) for d in b)<=18000 for b in groups)


def target():
    return dict(units=[dict(id='u1',runtime='python',capabilities=['module'])],interfaces=[dict(unit='u1',path='pkg.py',functions=[dict(name='f')])])


def standard(identity='R',**kw):
    return dict(id=identity,title='返回输入的两倍',source='D',quote='返回输入整数的两倍。',cases=[dict(id='C',title='验证两倍结果',kind='module',unit='u1',module='pkg.py',function='f',args=[3],expected=6)],**kw)


def test_invalid_quote_unknown_entry_and_non_object_rows_keep_other_valid_cases():
    bad=standard('BAD');bad['quote']='文档没有这样承诺过'
    entry=standard('ENTRY');entry['cases'][0]['function']='unknown';entry['cases'][0]['id']='C2'
    rows,issues,_=generation.validate(dict(requirements=[standard(),bad,entry,None]),[Document(id='D',title='契约',content='返回输入整数的两倍。')],target())
    assert rows[0]['cases'][0]['expected']==6 and len(rows[0]['cases'])==1
    assert any(r['disposition']=='unresolved' for r in rows)
    assert len(issues)>=3


def test_boolean_and_numeric_oracles_are_not_equal_even_inside_objects():
    assert not runtime.compare({'v':True},{'v':1},'equals')
    assert runtime.compare({'v':[1,2]},{'v':[1,2]},'equals')


def test_output_selection_follows_json_pointer_instead_of_python_indexing():
    assert runtime.pointer({'a/b':{'~':6}},'/a~1b/~0')==6
    for path in ('/x/-1','/x/01'):
        with pytest.raises(ValueError):runtime.pointer({'x':[1,2]},path)


def test_python_import_alias_resolves_only_to_one_verified_path():
    t=target();t['units'][0]['path']='.';t['interfaces'][0]['path']='pkg/__init__.py'
    raw=standard();raw['cases'][0]['module']='pkg';raw['cases'][0]['args']=[7];raw['cases'][0]['expected']=14
    rows,issues,_=generation.validate(dict(requirements=[raw]),[Document(id='D',title='契约',content='返回输入整数的两倍。')],t)
    assert not issues and rows[0]['cases'][0]['module']=='pkg/__init__.py'
    assert rows[0]['cases'][0]['args']==[7] and rows[0]['cases'][0]['expected']==14


def test_local_environment_failure_does_not_block_other_units_or_scans(tmp_path,monkeypatch):
    root=repo(tmp_path,{'pyproject.toml':'[project]\nname="neutral"\nversion="1"','main.py':'def f(x):return x*2',
        'frontend/package.json':'{"name":"client","scripts":{"test":"node --test"}}','frontend/index.js':'export function f(x){return x}',
        'notes.txt':'没有独立业务依据，不调用模型。'})
    store=IntegrationStore(tmp_path/'store');p=service.prepare(store,str(root));r=service.create(store,p['id'],p['digest'])
    # No external calls; this test checks dispatcher dependency isolation, not model correctness.
    failed=r['universal_plan']['discovery']['units'][0]['id']
    def prepared(r,u,output,cancelled):
        if u['id']==failed:raise ValueError('one isolated dependency install failed')
        return runtime.result_file(output,[dict(name='prepare',status='passed')]),dict(argv=['test'],exit_code=0)
    def succeeded(r,u,output,cancelled):return runtime.result_file(output,[dict(name='execution',status='passed')]),dict(argv=['test'],exit_code=0)
    monkeypatch.setattr(runtime,'prepare',prepared)
    for method in ('build','native','business'):monkeypatch.setattr(runtime,method,succeeded)
    monkeypatch.setattr(runtime,'cleanup',lambda r,output:(runtime.result_file(output,[dict(name='cleanup',status='passed')]),dict(argv=['test'],exit_code=0)))
    import acceptance.integrations.store as module
    def scanner(t,source,output,image,cancelled):
        output.mkdir(parents=True);raw=b'[]' if t.tool=='gitleaks' else b'{"results":[]}'
        (output/'report.json').write_bytes(raw)
        from acceptance.integrations.formats import parse
        return parse('gitleaks' if t.tool=='gitleaks' else 'bandit' if t.tool=='bandit' else 'semgrep',raw),dict(argv=['test'],exit_code=0)
    monkeypatch.setattr(module,'execute',scanner)
    monkeypatch.setattr(store,'finish',lambda r:(r.update(status='completed'),store.save(r)))
    result=store.execute(r['id']);tasks=result['tasks']
    assert any(t['state']=='error' for t in tasks)
    assert tasks[-1]['tool']=='universal-cleanup' and tasks[-1]['state']=='completed'
    assert any(t['tool']=='universal-business' and t['state']=='completed' for t in tasks)
    assert next(t for t in tasks if t['id']==failed+'-business')['state']=='error'
    assert any(t['tool']=='gitleaks' and t['state']=='completed' for t in tasks)


def test_generic_tasks_cannot_bypass_prepared_plan(tmp_path):
    root=repo(tmp_path,{'main.py':'def f(x):return x','README.md':'必须返回输入。'})
    store=IntegrationStore(tmp_path/'store');p=service.prepare(store,str(root));from acceptance.automatic import load
    full=load(store,p['id']);store.register(full['profile'])
    with pytest.raises(ValueError,match='已确认'):store.create(full['profile']['id'])


def test_missing_requirements_do_not_prevent_dispatch_but_do_prevent_release(tmp_path):
    root=repo(tmp_path,{'main.py':'def f(x):return x'})
    store=IntegrationStore(tmp_path/'store');p=service.prepare(store,str(root));assert p['ready'] and p['gaps']
    r=service.create(store,p['id'],p['digest']);c=service.completion(r)
    assert not c['complete'] and not c['execution_complete']


def test_framework_detection_uses_static_declarations_only(tmp_path):
    root=repo(tmp_path,{'pyproject.toml':'[project]\nname="service"\nversion="1"','app.py':'from fastapi import FastAPI as API\napp=API()\n@app.get("/items")\ndef items():return []'})
    d=discovery.discover(root,['pyproject.toml','app.py'])
    assert d['units'][0]['services'][0]['module']=='app' and 'http' in d['units'][0]['capabilities']

@pytest.mark.parametrize('kind',['cli','http'])
def test_protocol_mismatch_is_assertion_failure_and_keeps_actual(tmp_path,monkeypatch,kind):
    case=dict(id='C',title='协议预期验证',unit='u1',kind=kind,module=None,function=None,args=[],kwargs={},argv=[],stdin='',expected='ok',comparison='text',exit_code=0,method='GET',path='/',body=None,status=200,pointer='',selector=None)
    r=dict(universal_generation=dict(requirements=[dict(id='R',source='D',quote='返回正确状态和正文',cases=[case])]),universal_services={'u1':{}})
    u=dict(id='u1',runtime='go' if kind=='cli' else 'node',entries=['.'])
    response={'status':503,'value':'ok'}
    payload=b'ok' if kind=='cli' else ('ACCEPTANCE_VALUE:'+json.dumps(response)).encode()
    monkeypatch.setattr(runtime,'command',lambda *a,**kw:({'exit_code':9 if kind=='cli' else 0,'interruption':None},{'stdout':payload,'stderr':b''}))
    report,_=runtime.business(r,u,tmp_path,lambda:False)
    trace=json.loads((tmp_path/'cases.json').read_text())[0]
    assert report['tests'][0]['status']=='failed' and trace['actual']=='ok'
    assert trace.get('exit_code')==9 if kind=='cli' else trace['response']['status']==503


def test_cleanup_checks_relay_and_network_not_only_work_container(tmp_path,monkeypatch):
    from types import SimpleNamespace
    r={'id':'int-test','universal_plan':{'discovery':{'units':[{'id':'u1'}]}}}
    def fake(*args,**kwargs):
        return SimpleNamespace(returncode=0 if args[:2]==('network','inspect') else 1)
    monkeypatch.setattr(runtime,'docker',fake)
    report,_=runtime.cleanup(r,tmp_path)
    assert report['tests'][0]['status']=='error'
    from acceptance.integrations.adjudication import observations
    assert not observations(dict(tasks=[dict(id='cleanup',tool='universal-cleanup',report=report)]))


def test_optional_sbom_components_are_not_misreported_as_invalid_format():
    from acceptance.integrations.formats import parse
    with pytest.raises(ValueError,match='零组件'):
        parse('cyclonedx',b'{"bomFormat":"CycloneDX","specVersion":"1.7"}')
    with pytest.raises(ValueError,match='版本/组件无效'):
        parse('cyclonedx',b'{"bomFormat":"CycloneDX","specVersion":"1.7","components":null}')


def test_service_without_module_exports_still_has_syntax_build_inputs(tmp_path):
    root=repo(tmp_path,{'package.json':'{"name":"web","scripts":{"start":"node server.js"}}','server.js':'require("node:http").createServer(()=>{}).listen(19300)'})
    d=discovery.discover(root,['package.json','server.js'])
    assert d['units'][0]['syntax_files']==['server.js'] and 'http' in d['units'][0]['capabilities']


def test_malformed_json_output_is_a_failed_contract_not_an_executor_crash(tmp_path,monkeypatch):
    c=dict(id='C',title='检查JSON输出',unit='u1',kind='cli',argv=[],stdin='',expected='{"ok":true}',comparison='json_stream',exit_code=None)
    r=dict(universal_generation=dict(requirements=[dict(id='R',source='D',quote='输出合法JSON',cases=[c])]))
    monkeypatch.setattr(runtime,'command',lambda *a,**kw:({'exit_code':0,'interruption':None},{'stdout':b'not json','stderr':b''}))
    report,_=runtime.business(r,dict(id='u1',runtime='go',entries=['.']),tmp_path,lambda:False)
    trace=json.loads((tmp_path/'cases.json').read_text())[0]
    assert report['tests'][0]['status']=='failed' and trace['actual']=='not json'


@pytest.mark.parametrize('stdout',[b'',b'ready'])
def test_cli_failure_without_an_exit_contract_is_an_execution_gap_not_a_defect(tmp_path,monkeypatch,stdout):
    c=dict(id='C',title='检查命令输出',unit='u1',kind='cli',argv=['serve'],stdin='',expected='ready',comparison='contains',exit_code=None)
    r=dict(universal_generation=dict(requirements=[dict(id='R',source='D',quote='命令应当输出ready',cases=[c])]))
    monkeypatch.setattr(runtime,'command',lambda *a,**kw:({'exit_code':2,'interruption':None},{'stdout':stdout,'stderr':b'application configuration missing'}))
    report,_=runtime.business(r,dict(id='u1',runtime='go',entries=['.']),tmp_path,lambda:False)
    trace=json.loads((tmp_path/'cases.json').read_text())[0]
    assert report['tests'][0]['status']=='error' and trace['exit_code']==2 and trace['actual']==stdout.decode()
    from acceptance.integrations.adjudication import observations
    assert not observations({'tasks':[dict(id='business',tool='universal-business',report=report)]})


def test_archive_replays_original_response_order_and_preserves_exact_oracles(monkeypatch):
    from copy import deepcopy
    from types import SimpleNamespace
    from acceptance.planning import verification
    monkeypatch.setattr(verification,'response_matches',lambda *args:True)
    docs=[Document(id='D',title='契约',content='返回输入整数的两倍。')]
    invalid=standard('BAD');invalid['cases']=[dict(id='C-bad',title='错误的页面断言',kind='browser',unit='u1',expected='result')]
    original=dict(requirements=[standard(),invalid])
    rows,issues,anchors=generation.validate(original,docs,target())
    assert issues and 'input_value' in issues[0]['reason']
    raw=dict(choices=[dict(message=dict(content=json.dumps(original,ensure_ascii=False)))])
    indexed=target();indexed['interfaces'][0]['auxiliary']=False
    profile=dict(tasks=[]);p=dict(profile=profile,snapshot_digest='fixed',manifest=[],gaps=[],batches=[[d.model_dump() for d in docs]],discovery=indexed)
    model_input=encode(dict(prompt=dict(discovery=indexed,documents=p['batches'][0])))
    draft=dict(documents=p['batches'][0],target=indexed,model_output=original,requirements=deepcopy(rows),issues=issues,citations=anchors,response_sha256=sha(encode(raw)),connection={},input_sha256=sha(model_input))
    # Reproduce the old optional locator representation exactly.
    for row in draft['requirements']:
        for case in row['cases']:case.pop('entry',None)
    required=deepcopy(draft['requirements'])
    for row in required:
        row['id']='B1-'+row['id']
        for c in row['cases']:c['id']='B1-'+c['id']
    record=dict(universal_plan=p,universal_plan_ref='plan',profile=profile,context=dict(snapshot_digest='fixed',files=[]),tasks=[],universal_generation=dict(requirements=required,issues=issues,batches=[dict(index=0,state='completed',draft_ref='draft',response_ref='raw',input_ref='input')]))
    artifacts={'plan':encode(p),'draft':encode(dict(record=draft,sha256=sha(encode(draft)))),'raw':encode(raw),'input':model_input}
    store=SimpleNamespace(artifact_bytes_for_record=lambda r,aid:('',artifacts[aid]))
    assert service.verify_archived(store,record)
    record['universal_generation']['requirements'][0]['cases'][0]['expected']=99
    with pytest.raises(ValueError,match='执行预期'):service.verify_archived(store,record)


def test_real_planning_context_keeps_large_discovery_out_of_model_protocol(tmp_path,monkeypatch):
    root=repo(tmp_path,{'pyproject.toml':'[project]\nname="neutral"\nversion="1"\n[tool.unrelated]\nlarge="'+('x'*700000)+'"',
        'api.py':'def double(value):return value*2','README.md':'返回输入整数的两倍。'})
    store=IntegrationStore(tmp_path/'store');p=service.prepare(store,str(root));r=service.create(store,p['id'],p['digest'])
    assert len(r['universal_plan']['discovery']['units'][0]['settings']['tool']['unrelated']['large'])==700000
    class ReachedModel(Exception):pass
    def draft(store,data):
        assert len(encode(data.universal_target))<600000
        assert data.universal_target['execution_contract']['setup']
        assert data.documents[0].content=='返回输入整数的两倍。'
        raise ReachedModel()
    monkeypatch.setattr(service.provider,'draft',draft)
    task=next(t for t in r['tasks'] if t['tool']=='universal-design')
    with pytest.raises(ReachedModel):service.execute(store,r,task,tmp_path/'output',lambda:False)


def test_preparation_resolves_local_runtime_deps_without_their_test_extras(tmp_path,monkeypatch):
    from types import SimpleNamespace
    root=repo(tmp_path,{'plugin/pyproject.toml':'[project]\nname="plugin"\nversion="1"'})
    dep=dict(id='base',runtime='python',path='.',test_extra='dev')
    u=dict(id='plugin',runtime='python',path='plugin',test_extra='test',test_dependencies=[],local_dependencies=['base'],test_files=['plugin/tests/test_api.py'])
    r=dict(id='int-calibration',images={'universal-python':{'id':'fixed','versions':{'python':{'exit_code':0,'text':'Python 3.12.15'}}}},_source_path=str(root),_harness_path=str(tmp_path),context={'snapshot_digest':'fixed'},universal_plan={'discovery':{'units':[dep,u]}})
    events=[]
    def docker(*args,**kwargs):
        events.append(('docker',args))
        return SimpleNamespace(stdout='[{"NetworkSettings":{"Networks":{}}}]',stderr='',returncode=0)
    def command(run,unit,args,out,cancelled,**kwargs):
        assert kwargs.get('offline') is False
        events.append(('command',args))
        return dict(exit_code=2 if '--collect-only' in args else 0,argv=args),dict(stdout=b'',stderr=b'')
    monkeypatch.setattr(runtime,'docker',docker);monkeypatch.setattr(runtime,'command',command)
    out=tmp_path/'output';out.mkdir();report,_=runtime.prepare(r,u,out,lambda:False)
    install=next(args for kind,args in events if kind=='command' and '--report' in args)
    assert '/work/repo/.' in install and '.[test]' in install and not any('[dev]' in str(x) for x in install)
    collected=next(i for i,(kind,args) in enumerate(events) if kind=='command' and '--collect-only' in args)
    disconnected=next(i for i,(kind,args) in enumerate(events) if kind=='docker' and args[:2]==('network','disconnect'))
    assert collected<disconnected and report['tests'][0]['status']=='passed'
    environment=json.loads((out/'environment.json').read_text())
    assert environment['collection_probe']['exit_code']==2


@pytest.mark.parametrize('offline',[True,False])
def test_formal_commands_bind_explicit_offline_environment(tmp_path,monkeypatch,offline):
    captured=[]
    def invoke(argv,timeout,output,cancelled,**kwargs):
        captured.extend(argv);(output/'stderr.log').write_bytes(b'')
        return {'interruption':None,'exit_code':0},b''
    monkeypatch.setattr(runtime,'invoke',invoke)
    runtime.command({'id':'int-calibration'},{'id':'u1','path':'.'},['python','-V'],tmp_path,lambda:False,offline=offline)
    assert ('HF_HUB_OFFLINE=1' in captured)==offline
    assert ('TRANSFORMERS_OFFLINE=1' in captured)==offline


def test_build_resource_policy_validates_operator_parallelism_without_size_gates(monkeypatch):
    monkeypatch.delenv('ACCEPTANCE_COMPILER_JOBS',raising=False)
    assert runtime.resource_policy()=={'version':1,'temporary_directory':'/work/tmp','compiler_jobs':1}
    monkeypatch.setenv('ACCEPTANCE_COMPILER_JOBS','7')
    assert runtime.resource_policy()['compiler_jobs']==7
    for invalid in ('0','-1','auto','1.5'):
        monkeypatch.setenv('ACCEPTANCE_COMPILER_JOBS',invalid)
        with pytest.raises(ValueError):runtime.resource_policy()


def test_install_failure_keeps_resource_evidence_before_cleanup(tmp_path,monkeypatch):
    from types import SimpleNamespace
    root=repo(tmp_path,{'pyproject.toml':'[project]\nname="neutral"\nversion="1"'})
    u={'id':'u1','path':'.','runtime':'python','test_files':[],'test_dependencies':[]}
    r=dict(id='int-calibration',images={'universal-python':{'id':'fixed','versions':{'python':{'exit_code':0,'text':'Python 3.12.15'}}}},_source_path=str(root),_harness_path=str(tmp_path),context={'snapshot_digest':'fixed'})
    events=[]
    def docker(*args,**kwargs):
        events.append(args)
        return SimpleNamespace(stdout='[{"NetworkSettings":{"Networks":{}}}]',stderr='',returncode=0)
    def command(run,unit,args,out,cancelled,**kwargs):
        return dict(exit_code=1 if '--report' in args else 0,argv=args),dict(stdout=b'',stderr=b'compilation failed')
    monkeypatch.setattr(runtime,'docker',docker);monkeypatch.setattr(runtime,'command',command)
    out=tmp_path/'output';out.mkdir()
    with pytest.raises(ValueError,match='依赖安装失败'):runtime.prepare(r,u,out,lambda:False)
    start=next(args for args in events if args[0]=='run')
    assert 'TMPDIR=/work/tmp' in start and 'CARGO_BUILD_JOBS=1' in start
    assert (out/'resources.json').is_file()
    captured=json.loads((out/'resources.json').read_text())
    assert 'memory' in captured and 'disk' in captured and 'configuration' in captured
    probe=next(i for i,args in enumerate(events) if args[:2]==('exec',runtime.names(r,u)[0]))
    disconnect=next(i for i,args in enumerate(events) if args[:2]==('network','disconnect'))
    assert probe<disconnect


def test_partial_tokenizer_preparation_does_not_block_collection(tmp_path,monkeypatch):
    from types import SimpleNamespace
    root=repo(tmp_path,{'pyproject.toml':'[project]\nname="neutral"\nversion="1"'})
    u={'id':'u1','path':'.','runtime':'python','test_files':['tests/test_api.py'],'test_dependencies':[]}
    r=dict(id='int-calibration',images={'universal-python':{'id':'fixed','versions':{'python':{'exit_code':0,'text':'Python 3.12.15'}}}},_source_path=str(root),_harness_path=str(tmp_path),context={'snapshot_digest':'fixed'})
    seen=[]
    monkeypatch.setattr(runtime,'docker',lambda *a,**k:SimpleNamespace(stdout='[{"NetworkSettings":{"Networks":{}}}]',stderr='',returncode=0))
    def command(run,unit,args,out,cancelled,**kwargs):
        seen.append(args)
        return dict(exit_code=1 if '/harness/python_tokenizer_resources.py' in args else 0,argv=args),dict(stdout=b'',stderr=b'')
    monkeypatch.setattr(runtime,'command',command)
    out=tmp_path/'output';out.mkdir();report,_=runtime.prepare(r,u,out,lambda:False)
    env=json.loads((out/'environment.json').read_text())
    assert env['resource_preparation']['command']['exit_code']==1
    assert any('--collect-only' in args for args in seen)
    assert report['tests'][0]['status']=='passed'
