"""Durable at-most-once dispatch for tool writes, including uncertain responses.

The claim is committed BEFORE invoking the backend. An interrupted dispatch
stays unknown and is never replayed, including after process restart.
"""
import hashlib
import json
from pathlib import Path
import sqlite3
from contextlib import contextmanager

from .models import ToolFailure


def digest(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, ensure_ascii=False, separators=(',', ':')).encode()).hexdigest()


class Journal:
    def __init__(self, path: Path):
        path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
        self.path = path
        with self.connect() as db:
            db.execute('CREATE TABLE IF NOT EXISTS operations (request_id TEXT PRIMARY KEY, fingerprint TEXT NOT NULL, response TEXT)')
            db.execute('CREATE TABLE IF NOT EXISTS plans (service_id TEXT NOT NULL, plan_id TEXT NOT NULL, digest TEXT NOT NULL, repository TEXT, PRIMARY KEY(service_id,plan_id))')
        path.chmod(0o600)

    @contextmanager
    def connect(self):
        db = sqlite3.connect(self.path, timeout=10)
        try:
            with db:
                yield db
        finally:
            db.close()

    def claim(self, request_id, identity):
        with self.connect() as db:
            db.execute('BEGIN IMMEDIATE')
            row = db.execute('SELECT fingerprint,response FROM operations WHERE request_id=?', (request_id,)).fetchone()
            if row:
                if row[0] != digest(identity):
                    raise ToolFailure('conflict', '同一 request_id 已用于不同参数、工具或服务实例。', recovery='读取原操作；新的业务意图使用新的 UUID。')
                if row[1] is None:
                    raise ToolFailure('outcome_unknown', '请求已登记但尚无确定回执；可能仍在执行或连接已中断。', recovery='使用 acceptance_operation 查询原 request_id，并核对目录、任务或模型请求。不要换号重放。')
                return json.loads(row[1])
            db.execute('INSERT INTO operations VALUES(?,?,NULL)', (request_id, digest(identity)))
        return None

    def finish(self, request_id, response):
        with self.connect() as db:
            db.execute('UPDATE operations SET response=? WHERE request_id=? AND response IS NULL', (json.dumps(response, ensure_ascii=False), request_id))

    def get(self, request_id):
        with self.connect() as db:
            row = db.execute('SELECT response FROM operations WHERE request_id=?', (request_id,)).fetchone()
        if row is None:
            raise ToolFailure('not_found', '此工具日志中没有该 request_id。', retry_safe=True, recovery='检查所用服务和工具日志路径。日志丢失时不得推断请求未执行。')
        response = json.loads(row[0]) if row[0] else None
        unknown = response is None or (response.get('error') or {}).get('code') == 'outcome_unknown'
        return {'request_id': request_id, 'state': 'outcome_unknown' if unknown else 'recorded', 'response': response}

    def allow_plan(self, service_id, plan_id, plan_digest, repository=None):
        with self.connect() as db:
            db.execute('INSERT OR REPLACE INTO plans VALUES(?,?,?,?)', (service_id, plan_id, plan_digest, repository))

    def require_plan(self, service_id, plan_id, plan_digest):
        with self.connect() as db:
            row = db.execute('SELECT digest,repository FROM plans WHERE service_id=? AND plan_id=?', (service_id, plan_id)).fetchone()
        if row is None or row[0] != plan_digest:
            raise ToolFailure('permission_denied', '方案须由此工具日志中的 prepare 成功创建，且摘要一致。', recovery='在已授权目录重新 prepare 并核对方案。')
        return row[1]
