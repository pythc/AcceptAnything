"""Read-only view adapters. Native records and artifacts are never rewritten."""
from copy import deepcopy
from datetime import datetime
from pathlib import Path
import mimetypes
import json

from .engine import encode, digest
from .source import repository_id
from .integrations.discovery import LABELS


def generated_detail(integrations, record, task, hit):
    """Explain a failed assertion from its own trace, without declaring a product bug."""
    plan=record.get('test_plan') or {}
    case=next((c for c in plan.get('cases',[]) if c['name']==hit.get('name')),None)
    if task.get('tool')!='acceptance-generated' or not case:return None
    item=next((a for a in record['artifacts'] if a['name']==task['id']+'/'+case['id']+'-trace.json'),None)
    if not item:return None
    _,raw=integrations.artifact_bytes_for_record(record,item['id'])
    trace=json.loads(raw)
    assertions=[a for step in trace.get('steps',[]) for a in step.get('assertions',[]) if a.get('passed') is False]
    if not assertions:return None
    dump=lambda value:json.dumps(value,ensure_ascii=False,sort_keys=True)
    requirement=next((x for x in plan['specification']['requirements'] if x['id']==case['requirement']),{})
    model=plan.get('planner',{}).get('kind')=='model'
    label='模型草稿预期' if model else '结构化方案预期'
    title=f"{requirement.get('title',case['requirement'])}：用例预期不一致（{case['id']}）"
    inputs=[step['input'] for step in trace['steps'] if 'input' in step]
    readable=[]
    for step in inputs:
        kind=step.get('kind')
        if kind=='http':readable.append(step['method']+' '+step['path']+'，预期 HTTP '+str(step['status']))
        elif kind=='goto':readable.append('打开页面 '+step['value'])
        elif kind=='call' or 'args' in step:readable.append('调用 '+str(step.get('module',''))+' / '+str(step.get('function',''))+'，参数 '+dump(step.get('args',[])))
        elif kind in {'fill','click','check','expect_text','expect_visible','expect_url'}:readable.append(str(step.get('selector') or kind)+'：'+str(step.get('value','')))
        else:readable.append(dump(step))
    observation='步骤：'+' → '.join(readable)+'\n断言：'+dump(assertions)+'\n依据：'+case['source']['quote']
    limitation='断言失败已复现；仍需复核输入前提和方案预期，不能直接认定产品缺陷。'
    return dict(title=title,actual=observation,impact=limitation,detail=dict(
        summary=title,observation=observation,steps=['依据：'+case['source']['quote'],*readable],
        expected_value=dump([a['expected'] for a in assertions]),actual_value=dump([a['actual'] for a in assertions]),
        comparison_labels=[label,'实际返回'],primary_ref=item['id'],limitation=limitation))


def integration_view(integrations, rid, page=None):
    r=integrations.snapshot(rid);ctx=r.get('context') or {}
    path=ctx.get('repository','');files=ctx.get('files',[])
    source=dict(schema_version=1,provenance='captured',captured_at=r['created_at'],
        repository=dict(id=repository_id(path),name=Path(path).name or r['name'],path=path,kind='directory',
                        branch=ctx.get('branch'),commit=None if ctx.get('revision')=='uncommitted' else ctx.get('revision'),remote=None,scoped_changes=None,untracked=None),
        target=dict(name=r['name'],variant='repository',kind='repository-checks',environment=ctx.get('environment','外部导入'),url=None),
        scope=dict(kind='files',description=ctx.get('scope','所选报告范围'),files=files,check_count=len(r['tasks'])),
        snapshot=dict(algorithm='sha256',digest=ctx.get('snapshot_digest','未采集')),
        tooling=dict(model=(r.get('test_plan') or r.get('automatic_plan') or {}).get('planner',{}).get('model'),executors=list(dict.fromkeys(t.get('tool',t.get('format','报告')) for t in r['tasks'])),versions={},gate='OPA',opa_image=None))
    if r.get('remote_source'):
        from .remote import repository_fields
        source['repository'].update(repository_fields(r['remote_source']))
    criteria=[];results=[];findings=[];inspections={};checks=[];commands=[]
    selected=None;page_info=None
    if page is not None:
        from .integrations.adjudication import load
        review=load(integrations,r);groups=[g for g in review['groups'] if not page.get('state') or page.get('state')=='active' and g['state']!='false_positive' or g['state']==page['state']]
        query=page.get('query','').casefold()
        if query:
            from .integrations.adjudication import observations
            searchable={o['id']:json.dumps(o['hit'],ensure_ascii=False).casefold() for o in observations(r)}
            groups=[g for g in groups if query in g['id'].casefold() or query in searchable.get(g['id'],'')]
        offset=page.get('offset',0);limit=page.get('limit',100)
        selected={g['id'] for g in groups[offset:offset+limit]}
        if page.get('finding'):selected.add(page['finding'])
        from .integrations.runner import sha, encode
        page_info=dict(offset=offset,limit=limit,total=len(groups),has_more=offset+limit<len(groups),state=page.get('state',''),query=page.get('query',''),snapshot_digest=sha(encode(groups)))
    finding_index=0
    planned={c['id']:c for c in (r.get('onboarding_plan') or {}).get('checks',[])}
    for task in r['tasks']:
        cid=task['id'];report=task.get('report') or {};hits=report.get('findings',[]);tests=report.get('tests',[])
        failed=[t for t in tests if t['status']!='passed']
        expected=planned.get(cid,{}).get('expected','报告完整，所选检查和断言满足冻结门禁')
        title=planned.get(cid,{}).get('title') or LABELS.get(task.get('tool'),task.get('tool',task.get('format','导入报告')))
        if task.get('tool')=='acceptance-generated':
            spec=(r.get('test_plan') or {}).get('specification',{})
            model=(r.get('test_plan') or {}).get('planner',{}).get('kind')=='model'
            title='模型 · '+spec.get('title','独立用例') if model else '结构化 · 业务规则'
        executor={'acceptance-generated':'pytest · Node.js / Playwright','semgrep-njsscan':'Semgrep CE · njsscan','syft-cyclonedx':'Syft','trivy-fs':'Trivy','trivy-config':'Trivy 配置检查','node-test':'Node.js','bandit':'Bandit','gitleaks':'Gitleaks','hadolint':'Hadolint'}.get(task.get('tool'),task.get('tool',task.get('format','报告')))
        if task.get('tool')=='acceptance-generated':executor={'browser':'Playwright','openapi':'Schemathesis'}.get(task.get('target'),'pytest · Node.js')
        c=dict(id=cid,case_id='TC-'+cid,layer='L1',executor=executor,title=title,
               expected=expected,severity='medium',impact='所选检查未满足；扫描命中仍需复核实际影响',required=True)
        criteria.append(c)
        state=task['state']
        status=('error' if not report.get('complete',False) else 'failed' if hits or failed else 'passed') if state=='completed' else 'error' if state in {'error','cancelled'} else state
        refs=task.get('artifacts',[])
        actual=task.get('error') or (f"{len(tests)} 个测试，{len(failed)} 个未通过" if tests else f"{len(report.get('components',[]))} 个组件" if report.get('components') else f"{len(hits)} 项扫描命中")
        result=dict(criterion_id=cid,case_id=c['case_id'],layer='L1',attempt=1,status=status,duration_ms=task.get('duration_ms'),expected=expected,actual=actual,evidence_refs=refs)
        if state in {'completed','error','cancelled'}:results.append(result)
        checks.append(dict(criterion_id=cid,status=status,started_at=task.get('started_at'),finished_at=task.get('finished_at'),duration_ms=task.get('duration_ms')))
        detail=dict(criterion_id=cid,status=status,subject=title,steps=[expected,'执行冻结配方并保存原始报告'],
                    limitation='仅所列工具规则和测试范围；扫描命中未证明可利用，不代表完整产品验收',method=c['executor'],summary=actual,observation=actual,
                    verified=r['integrity'] and state=='completed',expected_value=expected,actual_value=actual,primary_ref=task.get('report_ref'),source_report=task.get('report_ref'))
        inspections[cid]=detail
        for hit in hits+[t for t in tests if t['status']=='failed' or t['status']!='passed' and r.get('finding_review',{}).get('version')=='finding-review-v1']:
            finding_index+=1;fid='F-'+str(finding_index).zfill(3)
            if selected is not None and fid not in selected:continue
            location=(str(hit.get('path',''))+(':'+str(hit['line']) if hit.get('line') else '')).replace('/source/','')
            observation='\n'.join(x for x in [location,hit.get('rule',''),hit.get('detail','')] if x)
            f={**result,'id':fid,'status':'failed','title':hit.get('title') or hit.get('name') or title,'severity':hit.get('severity','medium'),
               'verification':'tool-reported','impact':'工具报告的候选问题；需结合调用路径和原始证据复核','actual':observation or actual}
            f['observation_key']={k:hit.get(k) for k in ('rule','path','line')}
            findings.append(f)
            inspections[fid]={**detail,'summary':f['title'],'observation':f['actual'],'actual_value':f['actual'],'location':location,'rule':hit.get('rule')}
            generated=generated_detail(integrations,r,task,hit)
            if generated:
                f.update({k:generated[k] for k in ('title','actual','impact')})
                inspections[fid].update(generated['detail'])
        cmd=task.get('command')
        if cmd:commands.append(dict(name=cid,argv=cmd.get('argv',[]),started_at=task.get('started_at'),finished_at=task.get('finished_at'),exit_code=cmd.get('exit_code'),evidence_ref=next((a['id'] for a in r['artifacts'] if a['name']==cid+'/command.json'),None)))
    artifacts=[dict(a,media_type=mimetypes.guess_type(a['name'])[0] or 'text/plain',criterion_id=next((t['id'] for t in r['tasks'] if a['id'] in t.get('artifacts',[])),None),collected_at=r['finished_at'] or r['created_at']) for a in r['artifacts']]
    taskstages=[s for s in r['pipeline'] if s['name'] in {t['id'] for t in r['tasks']}]
    starts=[s['started_at'] for s in taskstages if s.get('started_at')];ends=[s['finished_at'] for s in taskstages if s.get('finished_at')]
    done=r['status'] not in {'queued','running'}
    stage=dict(id='L1',title='所选检查',tool='固定执行器',work='执行本次冻结的检查范围',detail='执行所选扫描及测试，不代表完整产品验收',status='running' if not done else 'failed' if any(x['status']=='failed' for x in results) else 'passed' if results and all(x['status']=='passed' for x in results) else 'error')
    if starts:stage['started_at']=min(starts)
    if done and ends:stage.update(finished_at=max(ends),duration_ms=(datetime.fromisoformat(max(ends))-datetime.fromisoformat(min(starts))).total_seconds()*1000)
    stages=[stage]
    for s in r['pipeline']:
        if s['name']=='发现复核':
            stages.append(dict(id='review',title='发现复核',tool='证据复核',work='降噪、去重与证据核验',detail=s['detail'],status='passed' if s['state']=='completed' else s['state'],**{k:s.get(k) for k in ['started_at','finished_at','duration_ms']}));continue
        if s['name'] not in {'冻结输入','质量门禁'}:continue
        stages.append(dict(id='baseline' if s['name']=='冻结输入' else 'gate',title=s['name'],tool='冻结输入' if s['name']=='冻结输入' else 'OPA',work=s['detail'],detail=s['detail'],status='passed' if s['state']=='completed' and s['name']=='冻结输入' else ('passed' if r['decision']=='allow' else 'failed' if r['decision']=='reject' else 'error') if s['state']=='completed' else s['state'],**{k:s.get(k) for k in ['started_at','finished_at','duration_ms']}))
    stages.sort(key=lambda s: {'baseline':0,'L1':1,'review':2,'gate':3}[s['id']])
    view=dict(id=rid,mode='repository',label=r['name'],status=r['status'],decision=r['decision'],recorded_decision=r.get('recorded_decision',r['decision']),result_contract=r['result_contract'],created_at=r['created_at'],finished_at=r['finished_at'],source=source,
        baseline=dict(version=(r.get('profile') or {}).get('version','所选报告'),title=r['name'],source='frozen-profile.json',scope=ctx.get('scope','所选报告'),digest=r.get('scope_digest','未采集'),criteria=criteria,exclusions=r.get('exclusions',[])),
        suite_digest=r.get('scope_digest','未采集'),target_digest=ctx.get('snapshot_digest','未采集'),results=results,findings=findings,artifacts=artifacts,commands=commands,
        reasons=r.get('errors') or [f"所选范围门禁：{r['decision']}；本记录不包含完整产品验收流程"],limits=['只执行本次冻结计划；没有运行的业务、浏览器、性能及恢复不算通过'],integrity=r['integrity'],
        inspections=inspections,case_plans={c['id']:dict(subject=c['title'],steps=[c['expected']]) for c in criteria},layers=[],pipeline=stages,display_stages=stages,check_runs=checks,
        check_count=len(results),findings_count=len(findings),artifact_count=len(artifacts),baseline_version=(r.get('profile') or {}).get('version','报告'),
        completion=dict(kind='scoped',complete=False,missing=['本记录仅证明所选检查范围，不是完整验收']),test_plan=r.get('test_plan'),native_integration=r)
    from .integrations.adjudication import apply_view
    view=apply_view(integrations,r,view)
    if page_info is not None:
        view['finding_page']=page_info
        # The report remains available as a streamed artifact; never duplicate
        # datasets into a UI envelope. All findings remain reachable by pages.
        view['native_integration']={k:r[k] for k in ['id','name','status','decision','integrity']}
        view['native_integration']['tasks']=[{k:v for k,v in t.items() if k not in {'report','artifacts'}} | {'report':{'metrics':t.get('report',{}).get('metrics',{}),'tests':t.get('report',{}).get('tests',[]) if t.get('tool') in {'universal-business','acceptance-generated'} else [],'test_count':len(t.get('report',{}).get('tests',[]))}} for t in r['tasks']]
        view['source']['scope']['file_count']=len(files)
        view['source']['scope']['files']=[]
    if done:
        for stage in view['display_stages']:
            if stage['status']=='running':stage.update(status='error',detail='执行异常结束：'+'；'.join(r.get('errors',[])))
    if r.get('universal_plan'):
        from .universal.service import present
        return present(view,r,integrations)
    if r.get('automatic_plan'):
        from .automatic import present
        return present(view,r)
    if (r.get('test_plan') or {}).get('specification',{}).get('environment',{}).get('recipe')=='gmah-v1':
        from .planning.gmah import present
        return present(view,r)
    return view


def workflow_view(store, integrations, run):
    if not run.get('workflow'):
        run['completion']=dict(kind='scoped',complete=False,missing=['历史记录按原冻结范围判定，未采集完整流程声明'])
        return run
    from .workflow import TITLES, coverage
    from . import reviews
    merged=deepcopy(run)
    catalog=reviews.frozen(store,run)
    review_by_id={}
    if catalog:
        for result in run['results']:
            review=reviews.native(store,run,result,catalog)
            if review:review_by_id[result['criterion_id']]=review
    for index,child in enumerate(run['workflow']['children']):
        view=integration_view(integrations,child['id']); prefix=f"child-{index}-"
        def cid(x):return prefix+x
        if catalog and child['stage']=='Lscanners':
            reviewed=reviews.child(run,view['native_integration'],catalog)
            review_by_id.update({cid(k):v for k,v in reviewed['tasks'].items()})
        # Artifact IDs are globally random; retain bytes in the owning store and
        # route downloads using the exact recorded owner, never arbitrary paths.
        for a in view['artifacts']:merged['artifacts'].append({**a,'owner_run':child['id'],'owner_label':'生成用例' if child['stage']=='Lgenerated' else '仓库扫描','criterion_id':cid(a['criterion_id']) if a['criterion_id'] else None})
        for c in view['baseline']['criteria']:merged['baseline']['criteria'].append({**c,'id':cid(c['id']),'case_id':cid(c['case_id']),'layer':child['stage']})
        for r in view['results']:merged['results'].append({**r,'criterion_id':cid(r['criterion_id']),'case_id':cid(r['case_id']),'layer':child['stage']})
        for f in view['findings']:
            fid='F-'+str(len(merged['findings'])+1).zfill(3)
            merged['findings'].append({**f,'id':fid,'criterion_id':cid(f['criterion_id']),'case_id':cid(f['case_id']),'layer':child['stage']})
            if catalog and child['stage']=='Lscanners':
                reviewed=reviews.assess([f['observation_key']],catalog,run['workflow']['manifest'])
                merged['findings'][-1]['review']=reviewed
            merged['inspections'][fid]={**view['inspections'].get(f['id'],view['inspections'][f['criterion_id']]),'criterion_id':cid(f['criterion_id'])}
        for key,d in view['inspections'].items():
            if not key.startswith('F-'):merged['inspections'][cid(key)]={**d,'criterion_id':cid(d['criterion_id'])}
        for c in view['check_runs']:merged.setdefault('check_runs',[]).append({**c,'criterion_id':cid(c['criterion_id'])})
        if view.get('test_plan'):
            merged.setdefault('test_plans',[]).append(dict(plan=view['test_plan'],execution=view['native_integration']))
            if not merged.get('test_plan') or view['test_plan'].get('planner',{}).get('kind')=='model':
                merged['test_plan']=view['test_plan'];merged['native_integration']=view['native_integration']
    records={s['id']:s for s in run.get('pipeline',[])}
    for result in merged['results']:
        reviewed=review_by_id.get(result['criterion_id'])
        if not reviewed:continue
        result['review']=reviewed
        if result['status']=='failed' and reviewed['non_blocking']:
            result.update(raw_status='failed',status='passed')
        detail=merged['inspections'].get(result['criterion_id'])
        if detail:detail.update(review=reviewed,raw_status=detail['status'],status=result['status'])
    for finding in merged['findings']:
        if 'review' not in finding and finding['criterion_id'] in review_by_id:
            finding['review']=review_by_id[finding['criterion_id']]
        if finding.get('review'):
            detail=merged['inspections'].get(finding['id'])
            if detail:detail['review']=finding['review']
    merged['display_stages']=[{**dict(id=key,title=title,tool='验收编排',work=title,status='queued' if run['status'] in {'queued','running'} else 'not_run',detail='等待执行'),**records.get(key,{})} for key,title in TITLES.items()]
    c=coverage(store,run)
    merged['completion']={**c,'kind':'full'}
    if run['status'] not in {'running','queued'} and not c['complete']:
        merged.update(status='incomplete',decision='inconclusive',reasons=['完整验收未完成：'+'、'.join(c['missing']+c['errors']),*run['reasons']])
    merged.update(check_count=len(merged['results']),findings_count=len(merged['findings']),artifact_count=len(merged['artifacts']))
    merged['review_summary']=dict(non_actionable=sum(bool(f.get('review',{}).get('non_blocking')) for f in merged['findings']),pending=sum(not f.get('review',{}).get('non_blocking',False) for f in merged['findings']),
        raw_failed=sum(r.get('raw_status',r['status'])=='failed' for r in merged['results']))
    if catalog:
        for stage in merged['display_stages']:
            rows=[r for r in merged['results'] if r['layer']==stage['id']]
            if rows and stage['status'] in {'passed','failed'}:
                stage['raw_status']=stage['status']
                stage['status']='failed' if any(r['status']=='failed' for r in rows) else 'passed' if all(r['status']=='passed' for r in rows) else stage['status']
                cleared=sum(r.get('raw_status')=='failed' and r['status']=='passed' for r in rows)
                stage['detail']=f"{sum(r['status']=='passed' for r in rows)} 通过 · {sum(r['status']=='failed' for r in rows)} 仍阻断；{cleared} 项原始命中经复核不成立"
            if stage['id']=='findings' and stage['status']=='passed':
                stage['detail']=f"{len(merged['findings'])} 条原始观察；{merged['review_summary']['pending']} 条待处理，{merged['review_summary']['non_actionable']} 条复核不成立；不等同独立漏洞数量"
    return merged
