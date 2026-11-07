"""Safe local request receipts. A client timeout does not prove upstream termination."""
import json
import os
import hashlib
import fcntl
import uuid
from datetime import datetime, timezone
from pathlib import Path
from .config import load


def write(store, receipt):
    directory=store.root/'model-calls';directory.mkdir(exist_ok=True)
    path=directory/(receipt['client_request_id']+'.json')
    temp=path.with_suffix('.tmp')
    temp.write_text(json.dumps(receipt,ensure_ascii=False,indent=2)+'\n');temp.chmod(0o600)
    os.replace(temp,path)


def acknowledgement(store, path, receipt):
    """Permission to make new calls is not evidence that the old call ended."""
    if receipt.get('state') != 'upstream_unknown':return None
    audit=store.root/'model-call-authorizations'/path.name
    if not audit.is_file():return None
    try:row=json.loads(audit.read_bytes())
    except (ValueError,OSError):return None
    if (row.get('action')=='allow_new_calls_preserve_unknown'
        and row.get('client_request_id')==receipt['client_request_id']
        and row.get('receipt_sha256')==hashlib.sha256(path.read_bytes()).hexdigest()
        and row.get('authorized_by') and row.get('authorization')):return row
    return None


def authorize_continuation(store, request_id, *, authorized_by, authorization):
    """Operator-only action after explicit user authorization; never automatic retry."""
    request_id=str(uuid.UUID(request_id))
    if not authorized_by.strip() or not authorization.strip():raise ValueError('必须记录授权人和明确授权内容')
    with (store.root/'.planner.lock').open('a') as lock:
        fcntl.flock(lock.fileno(),fcntl.LOCK_EX|fcntl.LOCK_NB)
        path=store.root/'model-calls'/(request_id+'.json')
        raw=path.read_bytes();receipt=json.loads(raw)
        if receipt.get('client_request_id')!=request_id or receipt.get('state')!='upstream_unknown':
            raise ValueError('仅能对终态未知请求记录继续授权，不能绕过在途请求')
        row=dict(action='allow_new_calls_preserve_unknown',client_request_id=request_id,
                 receipt_sha256=hashlib.sha256(raw).hexdigest(),authorized_by=authorized_by,
                 authorization=authorization,authorized_at=datetime.now(timezone.utc).isoformat())
        directory=store.root/'model-call-authorizations';directory.mkdir(exist_ok=True)
        # Exclusive creation preserves the original audit event as well as the receipt.
        with (directory/path.name).open('x') as stream:
            os.chmod(stream.name,0o600);json.dump(row,stream,ensure_ascii=False,indent=2)
        return row


def pending(store, *, include_authorized=False):
    if store is None:return []
    result=[]
    for path in (store.root/'model-calls').glob('*.json'):
        receipt=json.loads(path.read_text())
        if receipt['state'] in {'pending','response_headers','upstream_unknown'}:
            if include_authorized or not acknowledgement(store,path,receipt):result.append(receipt)
    return result


def fingerprint(input_record):
    """Ignore transport budget/timestamps, retain all semantic model inputs."""
    from ..integrations.runner import encode
    keys=('model','provider','reasoning_effort','system','prompt')
    if not all(key in input_record for key in keys):raise ValueError('模型输入缺少请求身份字段')
    return hashlib.sha256(encode({key:input_record[key] for key in keys})).hexdigest()


def request_fingerprint(store,receipt):
    name=receipt.get('input_file')
    if name!=receipt['client_request_id']+'.json':return None
    path=store.root/'model-inputs'/name
    try:
        if path.is_symlink():return None
        raw=path.read_bytes()
        if hashlib.sha256(raw).hexdigest()!=receipt.get('input_sha256'):return None
        identity=fingerprint(json.loads(raw))
        if receipt.get('intent_fingerprint',identity)!=identity:return None
        return identity
    except (OSError,ValueError,TypeError):return None


def blocking(store,intent=None):
    """Unknown calls block duplicate inputs, not independent repositories/batches.

    Active calls and receipts without verifiable input identity remain globally
    blocking. No receipt or authorization is changed by this classification.
    """
    return [r for r in pending(store) if r['state']!='upstream_unknown'
            or request_fingerprint(store,r) is None
            or intent is not None and request_fingerprint(store,r)==intent]


def reconcile(store):
    unknown={r['client_request_id']:r for r in pending(store,include_authorized=True)}
    config=load()
    if not unknown or config.provider!='chat2api' or not config.audit_file:return
    path=Path(config.audit_file).expanduser()
    if not path.is_file():return
    # Bounded tail only; never expose unrelated requests or raw gateway trace data.
    with path.open('rb') as stream:
        stream.seek(0,2);end=stream.tell();start=max(0,end-16*1024*1024);stream.seek(start)
        if start:stream.readline()
        for line in stream:
            try:row=json.loads(line)
            except (ValueError,UnicodeDecodeError):continue
            cid=row.get('client_request_id');code=row.get('status')
            if cid not in unknown or type(code) is not int or not 200<=code<=599:continue
            receipt=unknown.pop(cid)
            receipt.update(state='gateway_ended',gateway_status=code,server_request_id=row.get('request_id'),
                           note='仅核对网关终态；不保证远端推理已停止，不恢复方案，也不视为验收通过')
            write(store,receipt)
