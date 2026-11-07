"""Observe Node's spec reporter without claiming invented inner test records."""
import re

ANSI=re.compile(r'\x1b\[[0-?]*[ -/]*[@-~]')


def node_spec(text):
    clean=ANSI.sub('',text);totals={};skips=[]
    for line in clean.splitlines():
        metric=re.fullmatch(r'ℹ (tests|suites|pass|fail|cancelled|skipped|todo|duration_ms) ([0-9.]+)',line.strip())
        if metric:
            key,value=metric.groups()
            if key in totals:return None  # Multiple streams need separate reports.
            totals[key]=float(value) if key=='duration_ms' else int(value)
        item=re.match(r'^\s*﹣ (.+?) \(([0-9.]+)ms\)(?: # (.*))?$',line)
        if item:
            name,duration,reason=item.groups();skips.append(dict(name=name,duration_ms=float(duration),status='skipped',detail=reason or 'Node 原生报告标记跳过；原因见项目原始记录'))
    required={'tests','pass','fail','cancelled','skipped','todo'}
    if not required<=totals.keys() or totals['tests']!=sum(totals[k] for k in ('pass','fail','cancelled','skipped','todo')):return None
    return dict(format='node-spec',totals=totals,unexecuted=skips,unexecuted_names_complete=len(skips)==totals['skipped']+totals['todo'])
