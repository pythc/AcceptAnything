import json
import pytest
from acceptance.engine import Store
from acceptance.integrations.store import IntegrationStore
from acceptance.history import RecordIndex


def indexed(tmp_path, count=20):
    native=RecordIndex(tmp_path)
    other_dir=tmp_path/'integrations';other_dir.mkdir(exist_ok=True)
    other=RecordIndex(other_dir)
    with other.db() as db:
        for i in range(count):
            rid=f'int-{i:016x}'
            brief=dict(id=rid,created_at='same-time',status='completed',decision='allow',label=f'记录 {i}',source={'repository':{'id':'repo-'+str(i%3),'path':'/neutral/'+str(i%3),'name':'neutral'},'snapshot':{'digest':str(i)}})
            other.put(db,rid,'initial',dict(brief),dict(brief),[])
    return native,other


def test_sql_cursor_ties_total_filters_and_no_duplicate_pages(tmp_path):
    index,other=indexed(tmp_path,231)
    ids=[];cursor=None
    while True:
        page=index.combined(other,limit=17,cursor=cursor)
        assert page['total']==231
        ids.extend(x['id'] for x in page['items'])
        cursor=page['next_cursor']
        if not cursor:break
    assert len(ids)==len(set(ids))==231
    page=index.combined(other,limit=1)
    with pytest.raises(ValueError):index.combined(other,limit=1,cursor=page['next_cursor'],query='different')
    assert index.combined(other,query='记录 230')['total']==1
    assert index.combined(other,repository='repo-0')['total']==77
    groups=index.combined(other,kind='repositories',limit=2)
    assert groups['total']==3 and groups['has_more']
    assert all(r['run_count']==77 for r in groups['items'])
    search=index.combined(other,kind='repositories',query='/neutral/0')
    assert search['total']==1 and search['items'][0]['run_count']==77


def test_children_are_hidden_only_from_bound_parent(tmp_path):
    index,other=indexed(tmp_path)
    with index.db() as db:db.execute('INSERT INTO children VALUES(?,?)',('run-parent','int-0000000000000001'))
    assert index.combined(other)['total']==19


def test_unchanged_index_reads_do_not_open_payloads_or_verify(tmp_path,monkeypatch):
    s=IntegrationStore(tmp_path);r=s.new('index test','import')
    s.list()
    monkeypatch.setattr(s,'snapshot',lambda *a:pytest.fail('list must not verify all evidence'))
    monkeypatch.setattr(s,'metadata_brief',lambda *a:pytest.fail('unchanged envelope reparsed'))
    assert s.list()[0]['id']==r['id']


def test_changes_corruption_and_rebuild_preserve_records(tmp_path):
    s=IntegrationStore(tmp_path);r=s.new('index test','import')
    s.list();r.update(name='new title');s.save(r)
    assert s.list()[0]['name']=='new title'
    path=s.path(r['id'])/'run.json';path.write_text('{broken')
    assert s.list()[0]['record_error']
    assert path.read_text()=='{broken'
    with s.history.db() as db:db.execute('DELETE FROM entries')
    assert s.list()[0]['record_error']


def test_index_cannot_release_and_last_verification_is_not_current(tmp_path):
    from acceptance.history import stamp
    s=IntegrationStore(tmp_path);r=s.new('historical decision','import');r.update(status='completed',decision='allow');s.save(r)
    row=s.list()[0]
    assert row['decision']=='inconclusive' and row['recorded_decision']=='allow'
    p=s.path(r['id'])/'run.json';s.history.verified(r['id'],p,True,expected_stamp=stamp(p))
    row=s.list()[0]
    assert row['verification']['last_valid'] is True and row['verification']['state']=='not_checked'
    assert row['integrity'] is False and row['decision']=='inconclusive'


@pytest.mark.parametrize('cursor',['garbage','e30=','W10=','eyJ2IjoxfQ=='])
def test_bad_cursor_is_rejected(tmp_path,cursor):
    a,b=indexed(tmp_path)
    with pytest.raises(ValueError):a.combined(b,limit=10,cursor=cursor)


def test_cli_rebuilds_corrupt_indexes_without_modifying_originals(tmp_path):
    import subprocess,sys
    s=IntegrationStore(tmp_path/'integrations');r=s.new('recoverable index','import')
    raw=(s.path(r['id'])/'run.json').read_bytes()
    (s.root/'history.sqlite3').write_bytes(b'broken sqlite index')
    p=subprocess.run([sys.executable,'-m','acceptance.history','--root',str(tmp_path),'--rebuild'],capture_output=True,text=True)
    assert p.returncode==0,p.stderr
    assert s.list()[0]['id']==r['id']
    assert (s.path(r['id'])/'run.json').read_bytes()==raw
    assert next(s.root.glob('history.sqlite3.rebuild-*')).read_bytes()==b'broken sqlite index'


def test_concurrent_envelope_replacement_is_not_cached_as_verified(tmp_path):
    s=IntegrationStore(tmp_path);r=s.new('first','import')
    def change_during_read(rid):
        projection=s.metadata_brief(rid)
        newer=s.read(rid);newer['name']='replacement';s.save(newer)
        return projection
    result=s.history.sync((s.root/'runs').glob('*/run.json'),change_during_read)
    assert result['updated']==0 and not s.history.list()
    assert s.list()[0]['name']=='replacement'


def test_platform_writes_invalidate_metadata_scan_cache(tmp_path,monkeypatch):
    s=IntegrationStore(tmp_path);r=s.new('before','import')
    assert s.sync_history(max_age=60)['updated']==1
    read=s.metadata_brief
    monkeypatch.setattr(s,'metadata_brief',lambda *a:pytest.fail('unchanged directory scanned'))
    assert s.sync_history(max_age=60)['updated']==0
    monkeypatch.setattr(s,'metadata_brief',read)
    r['name']='after';s.save(r)
    assert s.sync_history(max_age=60)['updated']==1
    assert s.history.list()[0]['name']=='after'
