import json,sys
from pathlib import Path
from acceptance.universal import preparation


def test_compiler_conversion_does_not_execute_shell_or_overwrite_source():
    files={'tests/ext.c','tests/kept.so'}
    valid=preparation.compile_action('(cd tests && gcc ext.c -fPIC -shared -o ext.so && ls -lah)','. ',files)
    assert valid is None
    valid=preparation.compile_action('(cd tests && gcc ext.c -fPIC -shared -o ext.so && ls -lah)'.replace('gcc','cc'),'.',files)
    assert valid['argv']==['cc','ext.c','-fPIC','-shared','-o','ext.so'] and valid['workdir']=='tests'
    for cmd in ['cd tests && cc ext.c -shared -o kept.so','cc tests/ext.c -o ../escape.so','cc tests/ext.c -o ok.so; touch bad','cc tests/ext.c -o ok.so && curl remote','cc @args -o ok.so']:
        assert preparation.compile_action(cmd,'.',files) is None


def test_only_proven_linux_conditions_are_evaluated():
    assert preparation.linux_condition("matrix.os == 'ubuntu-latest'")
    assert preparation.linux_condition("runner.os != 'Windows'")
    assert not preparation.linux_condition("matrix.os == 'macos-latest'")
    assert not preparation.linux_condition("matrix.python-version == '3.14'")
    assert not preparation.linux_condition('${{ secrets.SHOULD_RUN }}')


def test_setup_stops_before_test_and_ignores_unrelated_jobs(tmp_path):
    content='''jobs:
  test:
    steps:
    - run: pip install declared-tool
    - run: pytest
    - run: pip install lint-only
  publish:
    steps:
    - run: pip install deploy-only
'''
    files={'.github/workflows/test.yml':content,'tests/test_data.py':'try:\n import tableframe\nexcept ImportError:\n tableframe=None\ntry:\n import pathlib\nexcept ImportError:\n pass'}
    for name,text in files.items():p=tmp_path/name;p.parent.mkdir(parents=True,exist_ok=True);p.write_text(text)
    plan=preparation.discover(tmp_path,list(files),dict(path='.',provides=[],test_files=['tests/test_data.py']))
    assert [p['spec'] for p in plan['optional_packages']]==['declared-tool','tableframe']
    assert not plan['build_actions']


def test_malformed_defaults_and_non_linux_jobs_do_not_break_discovery(tmp_path):
    body='''jobs:
  windows:
    runs-on: windows-latest
    steps:
    - run: pip install windows-only
    - run: pytest
  linux:
    runs-on: ubuntu-latest
    defaults: []
    steps:
    - run: pip install ordinary
    - run: pytest
'''
    path=tmp_path/'.github/workflows/tests.yml';path.parent.mkdir(parents=True);path.write_text(body)
    result=preparation.discover(tmp_path,['.github/workflows/tests.yml'],dict(path='.',test_files=[]))
    assert [r['spec'] for r in result['optional_packages']]==['ordinary']

import asyncio
import importlib.util
import sys
import uuid
from pathlib import Path
import pytest
from acceptance.universal import scenario as old_scenario


def staged(name):
    import importlib
    return importlib.import_module('acceptance.universal.'+name)


def test_python_image_selection_respects_declared_range():
    module=staged('environment')
    images={key:dict(versions={'python':{'exit_code':0,'text':'Python '+version}}) for key,version in [('universal-python','3.11.17'),('universal-python312','3.12.15')]}
    assert module.python_image({'settings':{}},images)=='universal-python312'
    assert module.python_image({'settings':{'project':{'requires-python':'>=3.10,<3.12'}}},images)=='universal-python'
    with pytest.raises(ValueError):module.python_image({'settings':{'project':{'requires-python':'>=3.13'}}},images)


@pytest.mark.parametrize('target',['manager','entered'])
def test_exit_can_identify_manager_or_enter_step_but_not_twice(tmp_path,target):
    name='context_'+uuid.uuid4().hex+'.py'
    (tmp_path/name).write_text('class Context:\n def __enter__(self):return {"inside":True}\n def __exit__(self,*args):return None')
    request=dict(steps=[dict(id='manager',op='call',module=name,export='Context'),dict(id='entered',op='enter',target='manager')],cleanup=[dict(id='leave',op='exit',target=target)])
    module=staged('scenario');receipt=asyncio.run(module.execute(request,tmp_path));assert receipt['status']=='completed'
    assert len(receipt['cleanup'])==1 and receipt['temporary_directory_removed']
    request['cleanup'].append(dict(id='again',op='exit',target=target))
    receipt=asyncio.run(module.execute(request,tmp_path));assert receipt['status']=='error'


def test_focus_batches_cover_every_span_without_repeating_output_scope(tmp_path):
    module=staged('documents')
    files={'README.md':'[Guide](docs/index.rst)','docs/index.rst':'Guide\n=====\n.. toctree::\n\n   first\n   second\n','docs/first.rst':'first\n'*4000,'docs/second.rst':'second\n'*4000}
    for name,body in files.items():p=tmp_path/name;p.parent.mkdir(parents=True,exist_ok=True);p.write_text(body)
    from acceptance.universal.discovery import batches
    groups,receipt=module.enrich(tmp_path,list(batches(tmp_path,[dict(path='README.md')])),module.catalog(tmp_path,list(files)),[])
    focused=[]
    for group,scope in zip(groups,receipt['batches']):
        focused.extend(d for d in group if d['id'] in scope.get('focus',scope['support']))
    for name in ('docs/first.rst','docs/second.rst'):
        rows=[d for d in focused if d['title']==name]
        assert ''.join(d['content'] for d in rows)==files[name]
    assert len({d['origin'] for d in focused})==len(focused)
    assert sum(s['primary_review'] for s in receipt['batches'])==1
    assert module.section('# Target\n```python\n# Target\n```\nanswer\n# Next\nend','target')==(0,39)

import importlib.util
from pathlib import Path
from acceptance.universal import runtime


def test_optional_dependency_failure_is_recorded_and_other_actions_continue(tmp_path,monkeypatch):
    from acceptance.universal import environment
    seen=[]
    def call(run,unit,argv,out,*args,**kwargs):
        seen.append(argv)
        # Both modules are absent. The first cannot install; the second can.
        code=1 if 'optional-0-probe'==out.name or 'optional-1-probe'==out.name or out.name=='optional-0-install' else 0
        return dict(exit_code=code,argv=argv),{}
    monkeypatch.setattr(runtime,'command',call);monkeypatch.setattr(runtime,'docker',lambda *a,**k:None)
    plan=dict(optional_packages=[dict(spec=n,origins=[dict(kind='optional-import')]) for n in ('missing_one','present_two')],build_actions=[dict(argv=['cc','native.c','-o','native.so'],workdir='tests',output='tests/native.so')])
    result=environment.execute(dict(id='int-neutral'),dict(id='unit',environment_preparation=plan),tmp_path,lambda:False)
    assert [a['status'] for a in result['actions']]==['error','prepared','prepared']
    assert (tmp_path/'optional-preparation.json').is_file()
    assert seen[-1][-4:]==['cc','native.c','-o','native.so']

from acceptance.planning.citation_indent import locate_rst_literal


def test_uniform_wrapper_indent_preserves_relative_code_and_string_spaces():
    text='Heading\n=======\n\n.. code-block:: python\n\n    def f():\n        return "a  b"\n\nNext paragraph\n'
    quote='def f():\n    return "a  b"'
    span=locate_rst_literal(text,quote);assert span and text[span[0]:span[1]]=='    def f():\n        return "a  b"'
    assert locate_rst_literal(text,'def f():\n    return "a b"') is None
    assert locate_rst_literal(text,'def f():\nreturn "a  b"') is None
    assert locate_rst_literal(text,quote.replace('return','print')) is None


def test_plain_text_duplicate_and_outside_block_are_rejected():
    quote='line one\nline two'
    block='.. code-block:: text\n\n    line one\n    line two\n'
    assert locate_rst_literal('    line one\n    line two',quote) is None
    assert locate_rst_literal(block+block,quote) is None
    assert locate_rst_literal(block+'other\n    line three','line two\nother') is None


def test_syntax_failure_and_optional_setup_do_not_block_independent_business(tmp_path,monkeypatch):
    from acceptance.universal import service,runtime
    from acceptance.integrations.store import IntegrationStore
    root=tmp_path/'repo';root.mkdir();(root/'pyproject.toml').write_text('[project]\nname="neutral"\nversion="1"')
    (root/'main.py').write_text('def identity(value):return value')
    store=IntegrationStore(tmp_path/'records');plan=service.prepare(store,str(root));run=service.create(store,plan['id'],plan['digest'])
    prepare=next(t for t in run['tasks'] if t['tool']=='universal-prepare')
    prepare.update(state='completed',report={'tests':[dict(name='隔离环境与依赖准备',status='passed'),dict(name='可选准备 · unavailable',status='error')]})
    build=next(t for t in run['tasks'] if t['tool']=='universal-build');build.update(state='error',error='unrelated syntax failure')
    fixture=next(t for t in run['tasks'] if t['tool']=='universal-fixture')
    fixture.update(state='completed',report={'tests':[dict(name='无本地构建夹具',status='passed')]})
    business=next(t for t in run['tasks'] if t['tool']=='universal-business')
    monkeypatch.setattr(runtime,'business',lambda *args:('executed',{}))
    assert service.execute(store,run,business,tmp_path/'result',lambda:False)[0]=='executed'
    assert not service.completion(run)['complete']
    prepare['report']['tests'][0]['status']='error'
    with pytest.raises(ValueError,match='前置条件'):service.execute(store,run,business,tmp_path/'result2',lambda:False)


def test_direct_reference_supplies_basis_without_expanding_focus(tmp_path):
    module=staged('documents');files={'README.md':'# Product\n[Feature](docs/guide.md)','docs/guide.md':'# Feature\nSee [Detailed contract](reference.md).','docs/reference.md':'# Detailed contract\nBad input returns 400.'}
    for name,body in files.items():p=tmp_path/name;p.parent.mkdir(parents=True,exist_ok=True);p.write_text(body)
    from acceptance.universal.discovery import batches
    groups,receipt=module.enrich(tmp_path,list(batches(tmp_path,[dict(path='README.md')])),module.catalog(tmp_path,list(files)),[])
    assert len(groups)==1
    focus={d['title'] for d in groups[0] if d['id'] in receipt['batches'][0]['focus']}
    assert focus=={'docs/guide.md'}
    assert any(d['title']=='docs/reference.md' and '400' in d['content'] for d in groups[0])


def test_rst_heading_underlines_are_not_markdown_fences():
    module=staged('documents');text='Parent\n======\n\nIntro\n`````\nText\n\n.. _target:\n\nChild\n-----\nAnswer\n'
    found=module.section(text,'target',markdown=False)
    assert found and text[found[0]:found[1]].endswith('Answer\n')


def test_native_skips_remain_skips_and_command_counts_are_separate(tmp_path):
    from acceptance.universal.native_observations import node_spec
    from acceptance.universal.runtime import result_file
    text='✔ passed (1ms)\n﹣ not applicable (0.2ms) # version condition\nℹ tests 2\nℹ suites 0\nℹ pass 1\nℹ fail 0\nℹ cancelled 0\nℹ skipped 1\nℹ todo 0\nℹ duration_ms 2.2\n'
    report=node_spec(text);assert report['unexecuted_names_complete'] and report['totals']['pass']==1
    assert result_file(tmp_path,report['unexecuted'])['tests'][0]['status']=='skipped'
    assert node_spec(text.replace('ℹ tests 2','ℹ tests 3')) is None
    assert node_spec(text+text) is None


def test_model_interface_view_excludes_native_tests_but_keeps_example_component(tmp_path):
    from acceptance.universal.discovery import discover,relevant
    files={'pyproject.toml':'[project]\nname="base"\nversion="1"','src/base/__init__.py':'def public():pass','tests/test_feature.py':'def test_public():pass',
        'examples/site/pyproject.toml':'[project]\nname="site"\nversion="1"\n[build-system]\nrequires=["flit_core"]\nbuild-backend="flit_core.buildapi"','examples/site/src/site/__init__.py':'def create_app():pass'}
    for name,body in files.items():p=tmp_path/name;p.parent.mkdir(parents=True,exist_ok=True);p.write_text(body)
    indexed=discover(tmp_path,list(files));view,selection=relevant(indexed['interfaces'],[dict(content='public create_app test_public')])
    assert {x['path'] for x in view}=={'src/base/__init__.py','examples/site/src/site/__init__.py'}
    assert selection['auxiliary_omitted']==1 and len(indexed['interfaces'])==3


def test_matrix_runner_must_explicitly_include_linux(tmp_path):
    from acceptance.universal import preparation
    path=tmp_path/'.github/workflows/ci.yml';path.parent.mkdir(parents=True)
    body='''jobs:
  test:
    runs-on: ${{ matrix.os }}
    strategy:
      matrix:
        os: [windows-latest]
    steps:
    - run: pip install windowsonly
    - run: pytest
'''
    path.write_text(body);unit=dict(path='.',test_files=[])
    assert preparation.discover(tmp_path,['.github/workflows/ci.yml'],unit)['optional_packages']==[]
    path.write_text(body.replace('windows-latest','ubuntu-latest'))
    assert preparation.discover(tmp_path,['.github/workflows/ci.yml'],unit)['optional_packages'][0]['spec']=='windowsonly'
