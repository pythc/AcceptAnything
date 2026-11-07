"""Evidence-bound adjudication. Raw reports stay immutable; unresolved claims block.

Exact duplicates share a group, every original occurrence remains addressable.
A scanner hit alone never becomes a confirmed product defect.
"""
import ast
from collections import Counter
from copy import deepcopy
import json
from pathlib import Path,PurePosixPath
import re
import tomllib
from .runner import sha,encode
from .formats import require
from .registry import ROOT

LABELS=dict(needs_review='待复核发现',false_positive='工具误报',confirmed='已确认缺陷',test_issue='用例问题')
CATALOG=ROOT/'standards/reviews/gmah-20261018.json'


def policy(store=None,context=None):
    from .finding_reviews import latest
    return dict(version='finding-review-v2',implementation_sha256=sha(Path(__file__).read_bytes()),
                manual_reviews=latest(store,context) if store and context else [],
                catalog=json.loads(CATALOG.read_bytes()) if CATALOG.exists() else {'entries':[]},
                rules=['bandit-B101-pytest-artifact-v1','exact-claim-dedup-v1','source-bound-reviewed-evidence-v1'])


def relative(value):
    value=value or ''
    for prefix in ('/source/','/execution/workspace/'):
        if value.startswith(prefix):value=value[len(prefix):]
    p=PurePosixPath(value)
    return str(p) if value and not p.is_absolute() and '..' not in p.parts and '\\' not in value else None


def observations(record):
    out=[]
    for task in record['tasks']:
        for kind,rows in [('scanner',task.get('report',{}).get('findings',[])),('test',task.get('report',{}).get('tests',[]))]:
            for index,hit in enumerate(rows):
                if kind=='test' and (hit['status']=='passed' or (record.get('finding_review',{}).get('version')!='finding-review-v1' and hit['status']!='failed')):continue
                # Rule, location, component AND claim must agree. CWE/location alone
                # cannot establish that two different tools found the same defect.
                key=[kind,task.get('tool',task.get('format')),task.get('environment'),hit.get('rule',hit.get('suite')),relative(hit.get('path')),hit.get('line'),hit.get('component'),hit.get('name'),hit.get('detail'),hit.get('severity')]
                out.append(dict(id='F-'+str(len(out)+1).zfill(3),index=index,task_id=task['id'],kind=kind,tool=task.get('tool',task.get('format')),hit=hit,
                    report_ref=task.get('report_ref'),fingerprint=sha(encode(key))))
    return out


def analyze(record,read_source,review_policy,*,verified):
    """read_source returns only frozen, hash-checked bytes; never a live checkout."""
    manifest={x['path']:x['sha256'] for x in record.get('context',{}).get('files',[])}
    cache={};trees={}
    def source(path):
        if path not in cache:
            raw=read_source(path) if path in manifest else None
            cache[path]=raw if raw is not None and sha(raw)==manifest[path] else None
        return cache[path]
    config=source('pyproject.toml');test_roots=[];packages=[]
    if config:
        try:
            config=tomllib.loads(config.decode());tool=config.get('tool',{})
            test_roots=tool.get('pytest',{}).get('ini_options',{}).get('testpaths',[])
            packages=tool.get('hatch',{}).get('build',{}).get('targets',{}).get('wheel',{}).get('packages',[])
        except (ValueError,UnicodeError):pass
    groups={};rows=[]
    for observation in observations(record):
        hit=observation['hit'];path=relative(hit.get('path'));line=hit.get('line')
        state='needs_review';method='unverified';reason='工具报告已保存；适用前提、实际影响或可达路径尚未验证。'
        proof=[dict(kind='report',ref=observation['report_ref'])];gaps=['需复核规则适用范围、输入来源、控制措施及实际影响']
        if verified:
            body=source(path) if path else None
            if body is not None:proof.append(dict(kind='source',path=path,line=line,sha256=manifest[path]))
            test_artifact=bool(path and isinstance(test_roots,list) and isinstance(packages,list) and any(isinstance(t,str) and path.startswith(t.rstrip('/')+'/') for t in test_roots)
                and (PurePosixPath(path).name.startswith('test_') or PurePosixPath(path).name.endswith('_test.py'))
                and packages and all(isinstance(p,str) and relative(p) not in {None,'.'} and not (path==p or path.startswith(p.rstrip('/')+'/')) for p in packages))
            conventional_test=bool(path and (PurePosixPath(path).name.startswith('test_') or PurePosixPath(path).name.endswith('_test.py')))
            if body and conventional_test:
                try:
                    if path not in trees:
                        tree=ast.parse(body);lines=set()
                        for node in ast.walk(tree):
                            if isinstance(node,(ast.FunctionDef,ast.AsyncFunctionDef)) and node.name.startswith('test'):
                                lines.update(n.lineno for n in ast.walk(node) if isinstance(n,ast.Assert))
                        trees[path]=lines
                    test_artifact=test_artifact or line in trees[path]
                except (SyntaxError,ValueError):pass
            if observation['tool']=='bandit' and hit.get('rule')=='B101' and body and test_artifact:
                try:
                    if path not in trees:trees[path]={n.lineno for n in ast.walk(ast.parse(body)) if isinstance(n,ast.Assert)}
                    node=line in trees[path]
                    if node:
                        state='false_positive';method='bandit-B101-pytest-artifact-v1';gaps=[]
                        reason='AST核对为已发现测试函数中的断言或明确排除在产品包外的测试断言；不是已验证的产品安全缺陷。'
                        proof.append(dict(kind='scope',path=path,sha256=manifest[path],test_roots=test_roots,product_packages=packages,method='static-test-discovery'))
                except (SyntaxError,ValueError):pass
            catalog=review_policy.get('catalog',{})
            if catalog.get('snapshot_digest')==record.get('context',{}).get('snapshot_digest'):
                for entry in catalog.get('entries',[]):
                    match=entry['match']
                    if not all(observation.get(k,hit.get(k))==v for k,v in match.items()):continue
                    if not all(text in hit.get('detail','') for text in entry.get('detail_contains',[])):continue
                    if not all(source(p) is not None and manifest.get(p)==h for p,h in entry['sources'].items()):continue
                    state=entry['state'];require(state in LABELS,'复核状态不受支持')
                    method='source-bound-reviewed-evidence-v1';reason=entry['reason'];gaps=entry.get('proof_gaps',[])
                    proof += [dict(kind='source',path=p,sha256=h) for p,h in entry['sources'].items()]
                    proof += entry.get('evidence',[])
        else:reason='证据完整性未通过；不应用豁免或确认，保持待复核。'
        if verified:
            for entry in review_policy.get('manual_reviews',[]):
                if entry['fingerprint']==observation['fingerprint'] and entry['snapshot_digest']==record.get('context',{}).get('snapshot_digest'):
                    state=entry['state'];method='recorded-evidence-review';reason=entry['reason'];gaps=[] if state in {'confirmed','false_positive'} else ['等待补充验证']
                    proof.append(dict(kind='recorded_review',run_id=entry['run_id'],refs=entry['evidence_refs'],revision=sha(encode(entry))))
        row={k:v for k,v in observation.items() if k!='hit'}
        row.update(state=state,label=LABELS[state],method=method,reason=reason,evidence=proof,proof_gaps=gaps)
        key=row['fingerprint'];group=groups.setdefault(key,dict(id=row['id'],fingerprint=key,state=state,label=LABELS[state],occurrence_ids=[],task_ids=[],evidence_refs=[]))
        require(group['state']==state,'相同发现的复核结论不一致')
        group['occurrence_ids'].append(row['id'])
        if row['task_id'] not in group['task_ids']:group['task_ids'].append(row['task_id'])
        if row['report_ref'] not in group['evidence_refs']:group['evidence_refs'].append(row['report_ref'])
        row['group_id']=group['id'];rows.append(row)
    counts=Counter(g['state'] for g in groups.values())
    summary=dict(raw=len(rows),unique=len(groups),duplicates=len(rows)-len(groups),**{k:counts[k] for k in LABELS})
    summary['actionable']=summary['needs_review']+summary['confirmed']+summary['test_issue']
    return dict(version=review_policy['version'],policy_sha256=sha(encode(review_policy)),snapshot_digest=record.get('context',{}).get('snapshot_digest'),
                integrity_verified=verified,summary=summary,observations=rows,groups=list(groups.values()))


def build(store,record):
    policy_ref=record.get('review_policy_ref')
    frozen_policy=json.loads(store.artifact_bytes_for_record(record,policy_ref)[1]) if policy_ref else policy()
    if policy_ref and frozen_policy.get('version')==policy()['version']:require({k:v for k,v in frozen_policy.items() if k!='manual_reviews'}=={k:v for k,v in policy().items() if k!='manual_reviews'},'复核策略版本发生变化；请重新确认并执行')
    root=store.path(record['id'])/'source'
    def read(path):
        f=root/path
        if not f.is_file() or f.is_symlink() or not f.resolve().is_relative_to(root.resolve()):return None
        return f.read_bytes()
    return analyze(record,read,frozen_policy,verified=bool(record.get('integrity')))


def load(store,record):
    if not record.get('integrity'):return build_unverified(record)
    if record.get('finding_review_ref'):
        result=json.loads(store.artifact_bytes_for_record(record,record['finding_review_ref'])[1])
        require(result==record.get('finding_review'),'复核结果与原始复核证据不一致')
        original=observations(record)
        require([(x['id'],x['fingerprint'],x['report_ref']) for x in original]==[(x['id'],x['fingerprint'],x['report_ref']) for x in result['observations']],'复核未完整绑定本次原始报告')
        require(result['snapshot_digest']==record.get('context',{}).get('snapshot_digest'),'复核源码快照不一致')
        policy_value=json.loads(store.artifact_bytes_for_record(record,record['review_policy_ref'])[1])
        require(sha(encode(policy_value))==result['policy_sha256'],'冻结复核策略不一致')
        checked={}
        for row in result['observations']:
            for proof in row['evidence']:
                if proof.get('kind') not in {'source','scope'}:continue
                name=relative(proof.get('path'));require(name is not None,'复核源码路径无效')
                if name not in checked:
                    f=store.path(record['id'])/'source'/name
                    require(f.is_file() and not f.is_symlink() and f.resolve().is_relative_to((store.path(record['id'])/'source').resolve()),'复核源码缺失')
                    checked[name]=sha(f.read_bytes())
                require(checked[name]==proof['sha256'],'复核源码摘要不一致')
        return result
    # Read-only contemporary review of old evidence; never rewrite old decisions.
    return build(store,record)


def build_unverified(record):
    return analyze(record,lambda _:None,policy(),verified=False)


def effective_tasks(record,review):
    tasks=deepcopy(record['tasks']);rows={r['id']:r for r in review['observations']};positions=observations(record)
    cleared=set();seen=set()
    for p in positions:
        if p['kind']!='scanner':continue
        if rows[p['id']]['state']=='false_positive' or p['fingerprint'] in seen:cleared.add((p['task_id'],p['index']))
        seen.add(p['fingerprint'])
    for task in tasks:
        report=task.get('report')
        if not report:continue
        report['findings']=[f for i,f in enumerate(report.get('findings',[])) if (task['id'],i) not in cleared]
        report['metrics']['findings.total']=len(report['findings'])
        for level in ['critical','high','medium','low','info','unknown']:
            report['metrics']['findings.'+level]=sum(f['severity']==level for f in report['findings'])
    return tasks


def apply_view(store,record,view):
    review=load(store,record);byid={x['id']:x for x in review['observations']};groups={g['id']:g for g in review['groups']}
    visible=[];bytask={t['id']:[] for t in record['tasks']}
    for row in review['observations']:bytask[row['task_id']].append(row)
    for f in view['findings']:
        row=byid[f['id']];group=groups[row['group_id']]
        detail=view['inspections'][f['id']]
        conclusion=dict(category=row['state'],label=row['label'],reason=row['reason'],non_blocking=row['state']=='false_positive',
            raw_count=len(group['occurrence_ids']),non_actionable=int(row['state']=='false_positive'),pending=int(row['state']=='needs_review'),
            rows=[dict(reason=p.get('description',row['reason']),**p) for p in row['evidence']])
        f.update(review=conclusion,review_state=row['state'],fingerprint=row['fingerprint'],occurrences=group['occurrence_ids'],
            occurrence_tasks=group['task_ids'],evidence_refs=group['evidence_refs'])
        detail.update(review=conclusion,validation_method=row['method'],proof_gaps=row['proof_gaps'],occurrences=group['occurrence_ids'])
        if f['id']==row['group_id']:visible.append(f)
    for result in view['results']:
        rows=bytask[result['criterion_id']]
        if not rows:continue
        pending=sum(x['state']!='false_positive' for x in rows)
        result['raw_status']=result['status']
        result['actual']+=f'；复核后 {pending} 条待处理，{len(rows)-pending} 条工具误报'
        if result['status']=='failed' and pending==0 and record.get('finding_review_ref'):result['status']='passed'
        inspection=view['inspections'][result['criterion_id']]
        inspection.update(actual_value=result['actual'],summary=result['actual'],status=result['status'])
    counts=review['summary'];view.update(findings=visible,finding_counts=counts,findings_count=counts['actionable'],
        review_provenance='冻结复核' if record.get('finding_review_ref') else '按当前策略只读复核；历史门禁保持原结论',
        finding_review_ref=record.get('finding_review_ref'))
    from .finding_reviews import latest
    manual={e['fingerprint']:sha(encode(e)) for e in latest(store,record.get('context',{}))}
    for f in view['findings']:f['review_revision']=manual.get(f['fingerprint'],'')
    return view
