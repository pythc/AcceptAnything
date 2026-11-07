"""Append-only, optimistic, evidence-bound local reviews. Never rewrite run decisions."""
import fcntl,json,re
from pathlib import Path
from .runner import sha,encode
from .formats import require


def entries(store,context):
    root=store.root/'finding-reviews';out=[]
    for p in sorted(root.glob('*.json')) if root.exists() else []:
        wrapped=json.loads(p.read_bytes());event=wrapped['event'];require(sha(encode(event))==wrapped['sha256'],'人工复核日志被修改')
        if event['repository']==context.get('repository') and event['snapshot_digest']==context.get('snapshot_digest'):out.append(event)
    return out


def submit(store,rid,fid,data):
    from .adjudication import load
    record=store.snapshot(rid);require(record['integrity'],'证据完整性未通过')
    require(record['status']=='completed','请等待执行完成再复核')
    review=load(store,record);group=next((g for g in review['groups'] if fid in g['occurrence_ids']),None);require(group is not None,'发现不存在')
    selected=[x for x in review['observations'] if x['id'] in group['occurrence_ids']]
    require(data.state!='false_positive' or all(x['kind']=='scanner' for x in selected),'失败测试请按用例问题复核，不能作为扫描误报豁免')
    require(record.get('context',{}).get('files'),'缺少冻结源码，不能确认或排除缺陷')
    directory=store.root/'finding-reviews';directory.mkdir(exist_ok=True)
    with (directory/'.lock').open('a') as lock:
        fcntl.flock(lock.fileno(),fcntl.LOCK_EX)
        event=dict(repository=record['context']['repository'],snapshot_digest=record['context']['snapshot_digest'],
            fingerprint=group['fingerprint'],state=data.state,reason=data.reason,evidence_refs=data.evidence_refs,run_id=rid,
            observation_ids=group['occurrence_ids'],request_id=data.request_id,previous_revision=data.expected_revision)
        target=directory/(data.request_id+'.json')
        if target.exists():
            old=json.loads(target.read_bytes());require(old['event']==event,'同一请求编号的复核内容不同');return dict(revision=old['sha256'],recorded=True,gate_unchanged=True)
        all_entries=entries(store,record['context']);previous=[e for e in all_entries if e['fingerprint']==group['fingerprint']]
        # Chain ordering follows the explicit parent hash, never wall-clock/file order.
        parents={e['previous_revision'] for e in previous};heads=[sha(encode(e)) for e in previous if sha(encode(e)) not in parents]
        require(len(heads)<=1,'复核版本链分叉')
        require((heads[0] if heads else '')==data.expected_revision,'复核版本已变化，请刷新后再提交')
        require(set(data.evidence_refs)<=set(group['evidence_refs']) and data.evidence_refs,'须引用此发现的原始报告')
        for ref in data.evidence_refs:store.artifact_bytes_for_record(record,ref)
        digest=sha(encode(event));tmp=directory/('.'+data.request_id);tmp.write_bytes(encode(dict(event=event,sha256=digest)));tmp.replace(target)
        return dict(revision=digest,recorded=True,gate_unchanged=True,next_step='本次历史门禁不变；新一轮验收将冻结此复核及证据。')


def latest(store,context):
    events=entries(store,context);parents={e['previous_revision'] for e in events};heads=[e for e in events if sha(encode(e)) not in parents]
    for e in heads:
        r=store.snapshot(e['run_id']);require(r['integrity'],'人工复核引用的原执行证据已失效')
        for ref in e['evidence_refs']:store.artifact_bytes_for_record(r,ref)
    return heads


def history(store, rid, fid):
    """Read the append-only chain, including superseded decisions, for one finding."""
    from .adjudication import load
    record = store.snapshot(rid)
    review = load(store, record)
    group = next((g for g in review['groups'] if fid in g['occurrence_ids']), None)
    if group is None:
        raise FileNotFoundError('发现不存在')
    events = [e for e in entries(store, record.get('context', {})) if e['fingerprint'] == group['fingerprint']]
    rows = []
    parent = ''
    records = {rid: record}
    while len(rows) < len(events):
        children = [e for e in events if e['previous_revision'] == parent]
        require(len(children) == 1, '复核版本链断裂或分叉')
        event = children[0]
        parent = sha(encode(event))
        if event['run_id'] not in records:
            try:
                records[event['run_id']] = store.snapshot(event['run_id'])
            except (ValueError, FileNotFoundError):
                records[event['run_id']] = None
        original = records[event['run_id']]
        verified = bool(original and original['integrity'])
        for ref in event['evidence_refs'] if original else []:
            try:
                store.artifact_bytes_for_record(original, ref)
            except (ValueError, FileNotFoundError):
                verified = False
        rows.append(dict(revision=parent, event=event, evidence_verified_now=verified))
    return dict(run_id=rid, finding_id=fid, current_revision=parent, events=rows,
                evidence_verified_now=bool(record['integrity']), historical_decision_unchanged=True)
