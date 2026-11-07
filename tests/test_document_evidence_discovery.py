import json
from pathlib import Path
import pytest
from acceptance.universal import documents,discovery,runtime,service
from acceptance.universal.scenarios import Check


def write(tmp,files):
    for name,body in files.items():
        p=tmp/name;p.parent.mkdir(parents=True,exist_ok=True);p.write_text(body)
    return tmp,sorted(files)


def test_linked_rst_anchor_preserves_exact_source_and_scope(tmp_path):
    root,files=write(tmp_path,{'README.md':'# Utility\n[Search](https://example.test/en/stable/cli.html#search)\n## Documentation\n[All](docs/other.md)',
        'docs/cli.rst':'CLI\n===\n\n.. _search:\n\nSearch\n------\n\nSearch returns a matching row.\n\nOther\n-----\nNot relevant.',
        'docs/other.md':'# Full product\nNot all of this is in scope.'})
    groups=list(discovery.batches(root,[dict(path='README.md')]))
    units=[dict(settings={'project':{'urls':{'Documentation':'https://example.test/en/stable/'}}})]
    expanded,receipt=documents.enrich(root,groups,documents.catalog(root,files),units)
    assert len(expanded)==1 and len(expanded[0])==2
    support=expanded[0][1];assert 'matching row' in support['content'] and 'Not relevant' not in support['content']
    start,end=map(int,support['origin'].split('=')[1].split(':'))
    assert support['content']==(root/support['title']).read_text()[start:end]
    assert receipt['batches'][0]['primary']==['D1'] and receipt['batches'][0]['support']==['D2']
    assert len(receipt['catalog'])==3


def test_unknown_external_hosts_paths_and_ambiguous_anchors_are_not_guessed():
    paths={'docs/cli.rst','README.md'}
    assert documents.resolve('README.md','https://other.test/cli.html',paths,['https://example.test/']) is None
    assert documents.resolve('README.md','../secrets.md',paths,[]) is None
    assert documents.resolve('README.md','https://example.test/cli.html#x',paths,['https://example.test/'])==('docs/cli.rst','x')
    assert documents.section('# Same\n1\n# Same\n2','same') is None
    assert documents.section('hello','missing') is None


def test_explicit_toctree_cycles_do_not_repeat_or_drop_large_tail(tmp_path):
    root,files=write(tmp_path,{'README.md':'[Guide](docs/index.rst)',
        'docs/index.rst':'Guide\n=====\n\n.. toctree::\n\n   child\n   index\n',
        'docs/child.rst':('exact evidence\n'*1700)+'last observation'})
    groups,receipt=documents.enrich(root,list(discovery.batches(root,[dict(path='README.md')])),documents.catalog(root,files),[])
    assert ''.join(x['content'] for x in groups[0] if x['title']=='docs/child.rst')==(root/'docs/child.rst').read_text()
    assert len([x for x in receipt['batches'][0]['links'] if x.get('path')=='docs/index.rst'])==1


def test_nested_declared_examples_are_components_but_fixtures_are_not(tmp_path):
    root,files=write(tmp_path,{'pyproject.toml':'[project]\nname="base"\nversion="1"',
        'src/base/__init__.py':'def public():pass',
        'examples/site/pyproject.toml':'[project]\nname="site"\nversion="1"\n[build-system]\nrequires=["flit_core"]\nbuild-backend="flit_core.buildapi"',
        'examples/site/src/site/__init__.py':'from flask import Flask\nimport base\ndef create_app(config=None):\n app=Flask(__name__)\n return app',
        'tests/fixtures/pyproject.toml':'[project]\nname="ignore"\nversion="1"'})
    d=discovery.discover(root,files)
    assert len(d['units'])==2
    parent=next(u for u in d['units'] if u['path']=='.');child=next(u for u in d['units'] if u['path']=='examples/site')
    assert child['local_dependencies']==[parent['id']]
    assert child['services']==[dict(framework='Flask',module='site',attribute='create_app',factory=True,port=19300)]
    assert child['provides']==['site'] and 'http' in child['capabilities']


def test_native_bundler_stack_discovers_ancestor_environment(tmp_path):
    root,files=write(tmp_path,{'package.json':json.dumps({'scripts':{'test':'node --test'}}),
        'test/bundler/tool/package.json':json.dumps({'scripts':{'test':'node test.js'},'devDependencies':{'some-bundler':'1'}}),
        'test/bundler/tool/test.js':'console.log("native command")',
        'test/fixtures/package.json':json.dumps({'scripts':{'test':'exit 1'}})})
    d=discovery.discover(root,files);assert len(d['units'])==2
    child=next(u for u in d['units'] if u['path']!='.')
    assert child['ancestor_dependencies']==[dict(path='.',manifest='package.json')]
    assert child['native_commands']==['test']


def test_one_of_is_strict_and_cannot_silently_allow_any_value():
    assert runtime.compare('::1',['127.0.0.1','::1'],'one_of')
    assert not runtime.compare('0.0.0.0',['127.0.0.1','::1'],'one_of')
    assert not runtime.compare(True,[1,0],'one_of')
    with pytest.raises(ValueError):Check(step='address',expected=[],comparison='one_of')
    with pytest.raises(ValueError):runtime.compare('anything',[],'one_of')


def test_coverage_categories_do_not_guess_from_exception_text():
    from acceptance.universal.coverage import classify
    run={'tasks':[dict(id='prepare',tool='universal-prepare'),dict(id='test',tool='universal-native',report={'tests':[dict(name='optional extension',status='skipped',message='missing') ]})]}
    rows=classify(run,[dict(kind='execution',source='prepare',reason='failed'),dict(kind='execution',source='test',reason='some skipped'),dict(kind='requirement',reason='environment?')])
    assert [r['category'] for r in rows]==['environment','unclassified','unclassified']
    assert rows[1]['observations'][0]['name']=='optional extension'
