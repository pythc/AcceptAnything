from pathlib import Path
from neutral_native._core import double

def test_native_extension_is_importable_from_source():
    assert double(3) == 6

def test_body_runs_only_in_native_phase():
    Path('/work/native-body-marker').write_text('executed')
    assert double(0) == 0
