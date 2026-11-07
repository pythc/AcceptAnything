"""Import a selected source file with its real regular/namespace package identity."""
import importlib
import importlib.util
import sys
from pathlib import Path


def load(root, name):
    root = Path(root).resolve()
    path = (root / name).resolve()
    if not path.is_relative_to(root) or not path.is_file() or path.suffix != '.py':
        raise ValueError('module outside target or unavailable')
    # A namespace segment need not have __init__.py. Keep walking to find the
    # highest regular package instead of losing the prefix at the first gap.
    base = root / 'src' if path.is_relative_to(root / 'src') else root
    for parent in path.parents:
        if parent == root:
            break
        if (parent / '__init__.py').is_file():
            base = parent.parent
    parts = list(path.relative_to(base).with_suffix('').parts)
    if parts[-1] == '__init__':
        parts.pop()
    if not parts or not all(part.isidentifier() for part in parts):
        raise ValueError('module has no unambiguous Python import identity')
    for entry in reversed([str(base), str(root / 'src'), str(root)]):
        if entry not in sys.path:
            sys.path.insert(0, entry)
    identity = '.'.join(parts)
    spec = importlib.util.find_spec(identity)
    if not spec or not spec.origin or Path(spec.origin).resolve() != path:
        raise ValueError('import resolved a different file than the frozen binding')
    module = importlib.import_module(identity)
    origin = getattr(module, '__file__', None)
    if not origin or Path(origin).resolve() != path:
        raise ValueError('import resolved a different file than the frozen binding')
    return module
