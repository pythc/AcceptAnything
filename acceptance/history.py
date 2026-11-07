"""Rebuildable metadata index. Index reads never attest artifact integrity."""
import base64
from contextlib import contextmanager
from datetime import datetime, timezone
import fcntl
import hashlib
import json
from pathlib import Path
import sqlite3
import time
import threading
import logging


def timestamp():
    return datetime.now(timezone.utc).isoformat()


def stamp(path):
    s = path.stat()
    return f"{s.st_ino}:{s.st_mtime_ns}:{s.st_ctime_ns}:{s.st_size}"


class RecordIndex:
    def __init__(self, root):
        self.root = Path(root)
        self.database = self.root / "history.sqlite3"
        self._last_sync = 0
        self._marker = None
        self._sync_result = None
        with self.db() as db:
            db.executescript('''
              CREATE TABLE IF NOT EXISTS entries (
                id TEXT PRIMARY KEY, stamp TEXT NOT NULL, created_at TEXT NOT NULL,
                repository_id TEXT, search TEXT NOT NULL, brief TEXT NOT NULL,
                catalogue TEXT, last_verified_at TEXT, last_valid INTEGER
              );
              CREATE INDEX IF NOT EXISTS history_order ON entries(created_at DESC,id DESC);
              CREATE INDEX IF NOT EXISTS history_repo ON entries(repository_id,created_at DESC,id DESC);
              CREATE TABLE IF NOT EXISTS children (parent_id TEXT, child_id TEXT, PRIMARY KEY(parent_id,child_id));
              CREATE TABLE IF NOT EXISTS index_meta (key TEXT PRIMARY KEY,value TEXT NOT NULL);
            ''')

    @contextmanager
    def db(self):
        db = sqlite3.connect(self.database, timeout=10)
        db.row_factory = sqlite3.Row
        db.execute("PRAGMA journal_mode=WAL")
        try:
            with db: yield db
        finally: db.close()

    def changes(self):
        def modified(path):
            try:return stamp(path)
            except FileNotFoundError:return None
        return (modified(self.root/'history.changed'), modified(self.root/'runs'))

    def sync(self, paths, project, *, max_age=0):
        """Only stat run envelopes, never recursive source/artifact traversal."""
        with (self.root / "history.lock").open("a") as lock:
            fcntl.flock(lock, fcntl.LOCK_EX)
            marker=self.changes()
            if self._sync_result is not None and marker==self._marker and time.monotonic()-self._last_sync < max_age:
                return {**self._sync_result,'updated':0}
            with self.db() as db:
                known = {r['id']: r['stamp'] for r in db.execute('SELECT id,stamp FROM entries')}
            seen = set()
            updated = 0
            for p in paths:
                rid = p.parent.name
                seen.add(rid)
                try: current = stamp(p)
                except FileNotFoundError: continue
                if known.get(rid) == current: continue
                try:
                    brief, catalogue, children = project(rid)
                except (OSError, ValueError, KeyError, TypeError, AttributeError):
                    from .source import context
                    source = context({'mode': 'unknown', 'baseline': {'scope': '记录无法读取', 'criteria': []}, 'target_digest': '未知'})
                    brief = dict(id=rid, name='损坏记录', label='损坏记录', mode='unknown', status='error', decision='inconclusive',
                        recorded_decision='inconclusive', created_at='', finished_at=None, source=source,
                        check_count=0, findings_count=None, artifact_count=0, baseline_version='未知',
                        integrity=False, record_error='记录无法读取或校验；原文件保留')
                    catalogue, children = brief, []
                # An atomic save may race the projection. Do not cache a mixed view.
                try:
                    if stamp(p) != current: continue
                except FileNotFoundError: continue
                with self.db() as db:
                    self.put(db, rid, current, brief, catalogue, children)
                updated += 1
            with self.db() as db:
                for missing in set(known) - seen:
                    db.execute('DELETE FROM entries WHERE id=?', (missing,))
                    db.execute('DELETE FROM children WHERE parent_id=?', (missing,))
                db.execute('INSERT OR REPLACE INTO index_meta VALUES(?,?)', ('synced_at', timestamp()))
            self._marker=marker
            self._last_sync=time.monotonic()
            self._sync_result={"records":len(seen),"updated":updated}
            return self._sync_result

    def put(self, db, rid, current, brief, catalogue, children):
        for value in (brief, catalogue):
            if value is None: continue
            value['recorded_decision'] = value.get('recorded_decision', value.get('decision', 'inconclusive'))
            value['decision'] = 'inconclusive'
            value['integrity'] = False
            value['verification'] = {'state': 'not_checked', 'label': '目录未重新核验原件'}
        repo = (catalogue or {}).get('source', {}).get('repository', {})
        search = json.dumps({k: v for k,v in (catalogue or brief).items() if k not in {'context','_catalogue'}}, ensure_ascii=False).casefold()
        db.execute('''INSERT INTO entries(id,stamp,created_at,repository_id,search,brief,catalogue)
          VALUES(?,?,?,?,?,?,?) ON CONFLICT(id) DO UPDATE SET stamp=excluded.stamp,
          created_at=excluded.created_at,repository_id=excluded.repository_id,search=excluded.search,
          brief=excluded.brief,catalogue=excluded.catalogue,last_verified_at=NULL,last_valid=NULL''',
          (rid,current,brief.get('created_at') or '',repo.get('id'),search,json.dumps(brief,ensure_ascii=False),json.dumps(catalogue,ensure_ascii=False) if catalogue else None))
        db.execute('DELETE FROM children WHERE parent_id=?', (rid,))
        db.executemany('INSERT OR IGNORE INTO children VALUES(?,?)', [(rid,c) for c in children])

    @staticmethod
    def decode(row, key='brief'):
        value = json.loads(row[key])
        value['verification'].update(last_verified_at=row['last_verified_at'], last_valid=None if row['last_valid'] is None else bool(row['last_valid']))
        return value

    def list(self, catalogue=False):
        key = 'catalogue' if catalogue else 'brief'
        with self.db() as db:
            return [self.decode(r,key) for r in db.execute(f'SELECT * FROM entries WHERE {key} IS NOT NULL ORDER BY created_at DESC,id DESC')]

    def get(self, rid):
        with self.db() as db:
            row=db.execute('SELECT * FROM entries WHERE id=? AND catalogue IS NOT NULL',(rid,)).fetchone()
            if row is None:raise FileNotFoundError('目录记录不存在')
            return self.decode(row,'catalogue')

    def verified(self, rid, path, valid, *, expected_stamp):
        if stamp(path) != expected_stamp: return
        with self.db() as db:
            db.execute('UPDATE entries SET last_verified_at=?,last_valid=? WHERE id=? AND stamp=?', (timestamp(),int(valid),rid,expected_stamp))

    def combined(self, other, *, limit=None, cursor=None, query='', repository='', kind='records'):
        """SQL pagination over both stores, hiding only explicitly bound children."""
        if kind not in {'records','repositories'}: raise ValueError('未知目录类型')
        if limit is not None and not 1 <= limit <= 500: raise ValueError('每页数量须在1至500之间')
        if cursor and limit is None: raise ValueError('游标需要分页大小')
        binding = hashlib.sha256(json.dumps([query,repository,kind],ensure_ascii=False).encode()).hexdigest()
        after = None
        if cursor:
            try:
                data = json.loads(base64.urlsafe_b64decode(cursor))
                if data['v'] != 1 or data['scope'] != binding or len(data['after']) != 2 or not all(isinstance(x,str) for x in data['after']): raise ValueError()
                after = data['after']
            except (ValueError, KeyError, TypeError): raise ValueError('目录游标无效或查询条件已变化')
        with self.db() as db:
            db.execute('ATTACH DATABASE ? AS integration', (str(other.database),))
            union = '''SELECT * FROM main.entries WHERE catalogue IS NOT NULL
              UNION ALL SELECT * FROM integration.entries WHERE catalogue IS NOT NULL
              AND id NOT IN (SELECT child_id FROM main.children)'''
            # JSON functions are bundled with the supported SQLite runtime.
            base = f'WITH all_entries AS ({union})'
            params = []
            where = '1=1'
            if repository:
                where += ' AND repository_id=?'; params.append(repository)
            if query:
                field = "lower(json_extract(catalogue,'$.source.repository.name') || ' ' || json_extract(catalogue,'$.source.repository.path'))" if kind=='repositories' else 'search'
                where += f" AND {field} LIKE ? ESCAPE '\\'"
                params.append('%'+query.casefold().replace('\\','\\\\').replace('%','\\%').replace('_','\\_')+'%')
            if kind == 'repositories':
                base += f''', ranked AS (SELECT *,count(*) OVER(PARTITION BY repository_id) AS run_count,
                  row_number() OVER(PARTITION BY repository_id ORDER BY created_at DESC,id DESC) AS position
                  FROM all_entries WHERE {where} AND json_extract(catalogue,'$.source.repository.path') != '')'''
                table, where = 'ranked', 'position=1'
            else: table = 'all_entries'
            total = db.execute(base+f' SELECT count(*) FROM {table} WHERE {where}',params).fetchone()[0]
            if after:
                where += ' AND (created_at < ? OR (created_at = ? AND id < ?))'
                params += [after[0],after[0],after[1]]
            sql = base+f' SELECT * FROM {table} WHERE {where} ORDER BY created_at DESC,id DESC'
            if limit is not None: sql += ' LIMIT ?'; params.append(limit+1)
            rows = list(db.execute(sql,params))
            more = limit is not None and len(rows)>limit
            rows = rows[:limit] if limit is not None else rows
            items = []
            for row in rows:
                value = self.decode(row,'catalogue')
                if kind=='repositories': value = {'id':row['repository_id'],'repository':value['source']['repository'],'latest':value,'run_count':row['run_count']}
                items.append(value)
            next_cursor = None
            if more:
                last = rows[-1]
                next_cursor = base64.urlsafe_b64encode(json.dumps({'v':1,'scope':binding,'after':[last['created_at'],last['id']]}).encode()).decode()
            return {'items':items,'total':total,'next_cursor':next_cursor,'has_more':more,'verification':'metadata_only'}


class IndexSynchronizer:
    """Maintain the directory off the HTTP read path, without attesting evidence."""
    def __init__(self, stores):
        self.stores=stores
        self.stopped=threading.Event()
        self.status={'state':'starting','last_success':None}
        self.refresh()
        self.thread=threading.Thread(target=self.loop,name='acceptance-history-index',daemon=True)
        self.thread.start()

    def refresh(self):
        try:
            for store in self.stores:store.sync_history(max_age=1)
            self.status={'state':'ready','last_success':timestamp()}
        except Exception:
            self.status={**self.status,'state':'error','message':'目录同步异常，保留上次索引；原件不变'}
            logging.exception('历史目录索引同步失败')

    def loop(self):
        while not self.stopped.wait(1):self.refresh()

    def close(self):
        self.stopped.set();self.thread.join(timeout=15)


def main():
    """Rebuild only disposable indexes; run envelopes and jobs are untouched."""
    import argparse
    import time
    import uuid
    from .engine import Store
    from .integrations.store import IntegrationStore
    parser=argparse.ArgumentParser(description='历史目录索引同步 / 重建；损坏数据库重建前停止本地 API 和 worker')
    parser.add_argument('--root',type=Path,required=True)
    parser.add_argument('--rebuild',action='store_true')
    args=parser.parse_args()
    stores=[Store(args.root),IntegrationStore(args.root/'integrations')]
    result=[]
    for store in stores:
        started=time.monotonic();quarantined=[]
        if args.rebuild:
            # All names are fixed derived files. Do not touch jobs.sqlite3,
            # reports, source snapshots or model-call receipts.
            with (store.root/'history.lock').open('a') as lock:
                fcntl.flock(lock,fcntl.LOCK_EX)
                suffix='.rebuild-'+uuid.uuid4().hex
                for name in ('history.sqlite3','history.sqlite3-wal','history.sqlite3-shm'):
                    path=store.root/name
                    if path.exists():
                        if path.is_symlink():raise ValueError('索引不能是符号链接')
                        saved=path.with_name(name+suffix);path.replace(saved);quarantined.append(saved.name)
        result.append({'store':store.root.name,**store.sync_history(),'seconds':round(time.monotonic()-started,3),'previous_index':quarantined})
    print(json.dumps(result,ensure_ascii=False,indent=2))


if __name__=='__main__':main()
