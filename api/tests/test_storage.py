"""Storage-level tests (also runnable without starting Flask)."""

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from storage import CsvStore, Conflict, SaveFailed, ValidationError, is_number  # noqa: E402


def make(tmp_path, content, name='people.csv'):
    path = tmp_path / name
    path.write_bytes(content)
    return CsvStore(str(tmp_path)), path


def test_storage_write_and_history(tmp_path):
    store, path = make(tmp_path, b'id,name\n001,Alice\n002,Bob\n')
    first = store.query('people.csv')
    response = store.update_cell('people.csv', 0, 'name', 'Alicia', first['version'])
    assert response['changed'] and response['version'] != first['version']
    assert path.read_bytes() == b'id,name\n001,Alicia\n002,Bob\n'
    assert store.history('people.csv')[0]['new'] == 'Alicia'
    assert len(list((tmp_path / 'backups').iterdir())) == 1


def test_storage_stale_version_is_refused(tmp_path):
    store, path = make(tmp_path, b'id,name\n1,Alice\n2,Bob\n')
    old = store.query('people.csv')['version']
    path.write_bytes(b'id,name\n0,Outside\n1,Alice\n2,Bob\n')
    with pytest.raises(Conflict):
        store.update_cell('people.csv', 1, 'name', 'Wrong', old)
    assert b'Wrong' not in path.read_bytes()


def test_storage_rebase_row_ids(tmp_path):
    store, path = make(tmp_path, b'id,name\n1,Alice\n2,Bob\n3,Carol\n')
    store.delete_row('people.csv', 0, store.query('people.csv')['version'])
    assert [r['id'] for r in store.query('people.csv')['rows']] == [0, 1]
    newstore = CsvStore(str(tmp_path))
    assert [r['id'] for r in newstore.query('people.csv')['rows']] == [0, 1]
    assert newstore.query('people.csv')['rows'][0]['cells'][1] == 'Bob'


def test_storage_quote_all(tmp_path):
    source = b'"id","name"\r\n"001","A, B"\r\n'
    store, path = make(tmp_path, source)
    store.update_cell('people.csv', 0, 'name', 'Hello', store.query('people.csv')['version'])
    assert path.read_bytes() == b'"id","name"\r\n"001","Hello"\r\n'


def test_storage_blank_lines_no_final_newline(tmp_path):
    source = b'id,name\r\n\r\n1,Alice\r\n\r\n2,Bob\r\n'
    store, path = make(tmp_path, source)
    store.update_cell('people.csv', 0, 'name', 'Alicia', store.query('people.csv')['version'])
    assert path.read_bytes() == source.replace(b'Alice', b'Alicia')
    nofinal = tmp_path / 'nofinal.csv'
    nofinal.write_bytes(b'id,name\n1,Alice')
    store.update_cell('nofinal.csv', 0, 'name', 'Alicia', store.query('nofinal.csv')['version'])
    assert nofinal.read_bytes() == b'id,name\n1,Alicia'


def test_storage_bom_latin1(tmp_path):
    source = b'\xef\xbb\xbf' + 'id,name\n1,Café\n'.encode()
    store, path = make(tmp_path, source)
    store.update_cell('people.csv', 0, 'name', 'Alicia', store.query('people.csv')['version'])
    assert path.read_bytes().startswith(b'\xef\xbb\xbf')
    latin = tmp_path / 'latin.csv'
    latin.write_bytes('id,name\n1,Café\n'.encode('latin-1'))
    store.update_cell('latin.csv', 0, 'name', 'René', store.query('latin.csv')['version'])
    assert 'René'.encode('latin-1') in latin.read_bytes()


def test_storage_numeric_grammar(tmp_path):
    store, path = make(tmp_path, b'id,score\n1,100\n2,200\n')
    for invalid in ('1_000', 'inf', 'nan', 'abc', '1e999'):
        assert not is_number(invalid)
        with pytest.raises(ValidationError):
            store.update_cell('people.csv', 0, 'score', invalid, store.query('people.csv')['version'])
    assert path.read_bytes() == b'id,score\n1,100\n2,200\n'
    store.update_cell('people.csv', 0, 'score', '1e3', store.query('people.csv')['version'])
    assert store.query('people.csv')['columns'][1]['type'] == 'number'


def test_storage_failed_save_invalidates_cache(tmp_path, monkeypatch):
    store, path = make(tmp_path, b'id,name\n1,Alice\n')
    token = store.query('people.csv')['version']
    def locked(*args):
        raise PermissionError(13, 'File in use')
    monkeypatch.setattr('storage.os.replace', locked)
    with pytest.raises(SaveFailed):
        store.update_cell('people.csv', 0, 'name', 'Bob', token)
    assert store.query('people.csv')['rows'][0]['cells'][1] == 'Alice'
    assert path.read_bytes() == b'id,name\n1,Alice\n'
    assert not list(tmp_path.glob('*.tmp'))


def test_storage_duplicate_headers_rejected(tmp_path):
    store, path = make(tmp_path, b'x,x\n1,2\n')
    with pytest.raises(ValidationError, match='Repeated column'):
        store.query('people.csv')


def test_storage_backup_isolation(tmp_path):
    store, path = make(tmp_path, b'id,score\n1,100\n')
    other = tmp_path / 'people.old.csv'
    other.write_bytes(path.read_bytes())
    for i in range(6):
        store.update_cell('people.csv', 0, 'score', str(101 + i), store.query('people.csv')['version'])
    for i in range(2):
        store.update_cell('people.old.csv', 0, 'score', str(201 + i), store.query('people.old.csv')['version'])
    backups = [p.name for p in (tmp_path / 'backups').iterdir()]
    assert len([p for p in backups if p.startswith('people.') and not p.startswith('people.old.')]) == 5
    assert len([p for p in backups if p.startswith('people.old.')]) == 2


def test_storage_multiline_quoted_cell(tmp_path):
    source = b'"id","notes"\r\n"1","first\r\nsecond"\r\n'
    store, path = make(tmp_path, source)
    assert store.query('people.csv')['rows'][0]['cells'][1] == 'first\r\nsecond'
    store.update_cell('people.csv', 0, 'id', '2', store.query('people.csv')['version'])
    assert path.read_bytes() == source.replace(b'"1"', b'"2"')


def test_history_failure_does_not_claim_data_write_failed(tmp_path, monkeypatch):
    store, path = make(tmp_path, b'id,name\n1,Alice\n')
    monkeypatch.setattr(store, '_log', lambda *args, **kwargs: 'History could not be written')
    result = store.update_cell('people.csv', 0, 'name', 'Bob', store.query('people.csv')['version'])
    assert result['changed'] is True
    assert result['warning'] == 'History could not be written'
    assert b'Bob' in path.read_bytes()
