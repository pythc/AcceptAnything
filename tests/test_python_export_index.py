import ast
from unittest.mock import patch

from acceptance.universal.discovery import python_exports


def test_many_reexports_preserve_aliases_without_reparsing_large_module(tmp_path):
    (tmp_path/'values.py').write_text('\n'.join(f'class V{i}: pass' for i in range(150)))
    (tmp_path/'api.py').write_text('\n'.join(f'from .values import V{i} as Public{i}' for i in range(150)))
    with patch('acceptance.universal.discovery.ast.parse', wraps=ast.parse) as parse:
        rows=python_exports(tmp_path,'api.py')
        assert {r['name'] for r in rows}=={f'Public{i}' for i in range(150)}
        assert parse.call_count==2
    (tmp_path/'values.py').write_text('class New: pass\n')
    assert python_exports(tmp_path,'api.py')==[]


def test_cycles_and_independent_roots_do_not_leak_cached_exports(tmp_path):
    (tmp_path/'a.py').write_text('class A: pass\nfrom .b import B\n')
    (tmp_path/'b.py').write_text('class B: pass\nfrom .a import A\n')
    assert {r['name'] for r in python_exports(tmp_path,'a.py')}=={'A','B'}
    assert {r['name'] for r in python_exports(tmp_path,'b.py')}=={'A','B'}
    other=tmp_path/'other';other.mkdir();(other/'a.py').write_text('class Different: pass\n')
    assert [r['name'] for r in python_exports(other,'a.py')]==['Different']
