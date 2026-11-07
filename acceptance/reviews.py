"""Source-bound scanner adjudication, separate from immutable tool outcomes.

Only an exact reviewed observation can be non-blocking. Source changes, new
rules/locations, test failures and missing evidence remain blocking.
"""
from copy import deepcopy
import json
from pathlib import Path
from urllib.parse import urlparse
from defusedxml import ElementTree

CATALOG = Path(__file__).resolve().parents[1]/'standards/reviews/assessment-20261018.json'
LABELS = dict(false_positive='工具误报',test_issue='用例问题',risk='风险待处理',needs_review='待复核',mixed='包含不同结论')


def current():
    return CATALOG.read_bytes()


def frozen(store, run):
    ref=run.get('workflow',{}).get('review_ref')
    if not ref:return None
    from .engine import digest
    _,raw=store.artifact_bytes(run,ref)
    if digest(raw)!=run['workflow']['plan']['review_digest']:
        raise ValueError('复核目录与冻结验收计划不符')
    return json.loads(raw)


def path(value):
    value=value or ''
    for prefix in ('/source/','/execution/workspace/'):
        if prefix in value:return value.split(prefix,1)[1]
    return value


def assess(hits, catalog, manifest, extra_sources=None):
    if not catalog or not hits:return None
    sources={x['path']:x['sha256'] for x in manifest}
    sources.update(extra_sources or {})
    from .engine import digest,encode
    context_matches=catalog.get('context_digest')==digest(encode(manifest))
    known={(e['rule'],e['path'],e['line']):e for e in catalog['entries']} if context_matches else {}
    rows=[]
    for hit in hits:
        key=(hit.get('rule'),path(hit.get('path')),hit.get('line'))
        entry=known.get(key)
        if entry and sources.get(entry['path'])==entry['source_sha256']:
            row={**deepcopy(entry),'matched':True}
        else:
            row=dict(rule=key[0],path=key[1],line=key[2],verdict='needs_review',category='needs_review',
                     reason='没有与规则、位置和本次源码摘要完全匹配的复核；不自动豁免。',matched=False)
        rows.append(row)
    cleared=sum(x['verdict']=='not_actionable' for x in rows)
    kinds={x['category'] for x in rows}
    category=next(iter(kinds)) if len(kinds)==1 else 'mixed'
    return dict(category=category,label=LABELS[category],raw_count=len(rows),non_actionable=cleared,
                pending=len(rows)-cleared,non_blocking=cleared==len(rows),rows=rows,
                reason=f'{len(rows)} 条原始命中；{cleared} 条复核不成立，{len(rows)-cleared} 条仍阻断。')


def native_hits(kind, raw):
    report=json.loads(raw)
    if kind=='gitleaks':return [dict(rule=x['RuleID'],path=x['File'],line=x['StartLine']) for x in report]
    if kind=='semgrep':return [dict(rule=x['check_id'],path=x['path'],line=x['start']['line']) for x in report['results']]
    if kind=='python-sast':return [dict(rule=x['test_id'],path=x['filename'],line=x['line_number']) for x in report['results']]
    if kind=='npm-audit':return [dict(rule='dependency',path='package-lock.json',line=None) for x in report['vulnerabilities']]
    if kind=='zap':
        hits=[]
        for site in report['native_report']['site']:
            for alert in site['alerts']:
                if int(alert['riskcode'])<=0:continue
                if alert['pluginid']=='10096':
                    hits += [dict(rule='10096',path='/generated-asset'+urlparse(instance['uri']).path,line=None) for instance in alert['instances']]
                else:hits.append(dict(rule=alert['pluginid'],path='server/src/http.ts',line=40))
        return hits
    return []


def native(store, run, result, catalog=None):
    catalog=catalog or frozen(store,run)
    if not catalog:return None
    c=next(c for c in run['baseline']['criteria'] if c['id']==result['criterion_id'])
    manifest=run['workflow']['manifest']
    if c['id']=='ROOT-REGRESSION':
        from .engine import digest,encode
        if catalog.get('context_digest')!=digest(encode(manifest)):return None
        issue=catalog['test_issues'];sources={x['path']:x['sha256'] for x in manifest}
        if not all(sources.get(p)==sha for p,sha in issue['sources'].items()):return None
        ref=next((a['id'] for a in run['artifacts'] if a['id'] in result['evidence_refs'] and a['name']==c['id']+'-junit.xml'),None)
        if not ref:return None
        tree=ElementTree.fromstring(store.artifact_bytes(run,ref)[1])
        failed=[x.attrib.get('name') for x in tree.iter('testcase') if x.find('failure') is not None or x.find('error') is not None]
        if failed and set(failed)<=set(issue['names']):
            return dict(category='test_issue',label=LABELS['test_issue'],non_blocking=False,reason=issue['reason'],rows=[],raw_count=len(failed),non_actionable=0,pending=len(failed))
        return None
    if c['kind'] not in {'gitleaks','semgrep','python-sast','npm-audit','zap'}:return None
    ref=next((a['id'] for a in run['artifacts'] if a['id'] in result['evidence_refs'] and a['name']==c['id']+'-raw.json'),None)
    if not ref:return None
    raw=store.artifact_bytes(run,ref)[1];extra={}
    if c['kind']=='zap':
        from base64 import b64decode
        from hashlib import sha256
        report=json.loads(raw)
        candidates={instance['uri'] for site in report['native_report']['site'] for alert in site['alerts'] if alert['pluginid']=='10096' for instance in alert['instances']}
        for asset in report.get('timestamp_assets',[]):
            if asset['uri'] not in candidates or not asset['uri'].startswith(report['target']+'/assets/'):continue
            body=b64decode(asset['body_base64'],validate=True)
            if len(body)<=1024*1024 and sha256(body).hexdigest()==asset['sha256']:
                extra['/generated-asset'+urlparse(asset['uri']).path]=asset['sha256']
    return assess(native_hits(c['kind'],raw),catalog,manifest,extra)


def child(run, child_record, catalog):
    """Re-evaluate the frozen child rules, never rewrite its report or decision."""
    from .integrations.gates import evaluate
    tasks=deepcopy(child_record['tasks']);reviews={}
    for task in tasks:
        report=task.get('report') or {}
        reviewed=assess(report.get('findings',[]),catalog,run['workflow']['manifest'])
        if reviewed:
            reviews[task['id']]=reviewed
            report['metrics']['findings.total']=reviewed['pending']
    results=evaluate(child_record['profile']['rules'],tasks)
    return dict(non_blocking=bool(results) and all(r['status']=='passed' for r in results),tasks=reviews,rules=results)
