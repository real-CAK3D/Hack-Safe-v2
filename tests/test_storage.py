import json

from spac3ghost import storage


def test_write_json_is_atomic_and_skips_unchanged(tmp_path):
    path = tmp_path / 'sub' / 'state.json'
    assert storage.write_json(path, {'a': 1}) is True
    assert json.loads(path.read_text()) == {'a': 1}
    mtime = path.stat().st_mtime_ns
    assert storage.write_json(path, {'a': 1}) is False  # identical: disk untouched
    assert path.stat().st_mtime_ns == mtime
    assert storage.write_json(path, {'a': 2}) is True
    assert json.loads(path.read_text()) == {'a': 2}
    assert [p.name for p in path.parent.iterdir()] == ['state.json']  # no stray temp files


def test_runtime_dir_is_separate_from_data_dir():
    from spac3ghost.paths import DATA_DIR, RUNTIME_DIR
    assert RUNTIME_DIR != DATA_DIR
