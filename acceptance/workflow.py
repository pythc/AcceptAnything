"""Full acceptance orchestration. Scans are a child, never the completion signal.

Execution recipes remain reviewed code; repository input cannot supply shell commands.
Unknown repositories get an explicit readiness assessment, not a fabricated service.
"""
from copy import deepcopy
import json
from pathlib import Path
import re
import uuid

from . import projects
from .engine import ROOT, now, encode, digest
from .integrations.discovery import inventory, manifest
from .integrations.formats import require

REQUIRED = ('requirements', 'design', 'Lgenerated', 'Lscanners', 'baseline', 'cases', 'L1', 'L2', 'L3', 'L4', 'cleanup')
# Version 1 is the reviewed assessment recipe, not a generic repository recipe.
MODEL_STANDARD_IDS = ('DURATION','WINDOW','SUBMISSION','DEADLINE','DURATION-CHANGE')
TITLES = dict(requirements='需求与标准', design='模型设计用例', Lgenerated='生成用例验证', Lscanners='仓库扫描',
              baseline='环境准备', cases='用例核对', L1='构建与回归', L2='接口与数据库', L3='浏览器与业务',
              L4='性能与恢复', cleanup='环境清理', findings='缺陷归纳', gate='验收判定')


def implementation():
    base=Path(__file__).parent
    return {str(p.relative_to(base)):digest(p.read_bytes()) for p in sorted(base.rglob('*')) if p.is_file() and p.suffix in {'.py','.json','.rego','.mjs','.cjs'}}


def plan(store, repository, *, remote_source=None):
    from . import reviews
    root, files, _ = inventory(repository)
    rows = manifest(str(root), files)
    candidates = []
    for path in (ROOT/'projects').glob('*.json'):
        p = json.loads(path.read_text())
        if p.get('repository') and Path(p['repository']).resolve() == root and p.get('recipe') and 'exclusions' in p:
            candidates.append(p)
    profile = max(candidates, key=lambda p: len(p['criteria']), default=None)
    blockers = []
    if profile:
        projects.read_files(profile)
        kinds = {c['kind'] for c in profile['criteria']}
        if not {'build', 'playwright', 'k6', 'joint-restore'} <= kinds:
            blockers.append('已登记配方没有覆盖构建、浏览器、负载及联合恢复')
    else:
        blockers.append('此仓库尚无经过核验的应用启动、测试数据、负载和恢复配方；请先登记项目配方，不能用扫描替代')
    docs = [x for x in files if x in {'docs/CONTRACT.md', 'docs/REGISTRATION-AND-TIMING.md'}]
    if len(docs) != 2:
        blockers.append('缺少此验收配方要求的独立需求文档')
    record = dict(id='full-'+uuid.uuid4().hex[:16], repository=str(root), manifest=rows,
                  snapshot_digest=digest(encode(rows)), profile=profile, documents=docs,
                  recipe_digest=digest(encode({k:digest(v) for k,v in __import__('acceptance.expanded',fromlist=['recipe_files']).recipe_files().items()})),
                  orchestrator_digest=digest(Path(__file__).read_bytes()),
                  review_digest=digest(reviews.current()),
                  implementation_digest=digest(encode(implementation())),
                  stages=[dict(id=k,title=v) for k,v in TITLES.items()], blockers=blockers,
                  exclusions=profile.get('exclusions',[]) if profile else [], created_at=now())
    if remote_source: record['remote_source']=remote_source
    directory=store.root/'full-plans'; directory.mkdir(exist_ok=True)
    raw=encode(record); (directory/(record['id']+'.json')).write_bytes(encode(dict(record=record,digest=digest(raw))))
    return public_plan(record, digest(raw))


def public_plan(p, sha):
    result={k:p[k] for k in ('id','repository','snapshot_digest','stages','blockers','exclusions','documents')} | dict(
        digest=sha, file_count=len(p['manifest']), check_count=len((p['profile'] or {}).get('criteria',[])),
        review_digest=p.get('review_digest'),ready=not p['blockers'], scope='本地完整流程：独立标准、模型设计、生成用例、扫描、构建、接口、浏览器、负载和数据/文件恢复')
    if p.get('remote_source'): result['remote_source']=p['remote_source']
    return result


def create(store, plan_id, sha):
    from . import reviews
    require(re.fullmatch(r'full-[a-f0-9]{16}',plan_id), '无效完整验收计划')
    path=store.root/'full-plans'/(plan_id+'.json'); require(not path.is_symlink(),'计划路径非法')
    value=json.loads(path.read_text()); p=value['record']
    require(p['id']==plan_id and value['digest']==sha==digest(encode(p)), '计划已变化，请重新识别')
    require(not p['blockers'], '完整验收尚未就绪：'+'；'.join(p['blockers']))
    if p.get('remote_source'):
        from .remote import verify
        from .integrations.store import IntegrationStore
        verify(IntegrationStore(store.root/'integrations'),p['remote_source'])
    require(p['orchestrator_digest']==digest(Path(__file__).read_bytes()), '验收编排已变化，请重新识别')
    require(p.get('review_digest')==digest(reviews.current()),'复核策略已变化，请重新识别')
    require(p.get('implementation_digest')==digest(encode(implementation())),'验收实现已变化，请重新识别')
    root,files,_=inventory(p['repository'])
    require(manifest(str(root),files)==p['manifest'],'仓库已变化，请重新识别')
    from .expanded import recipe_files
    require(p['recipe_digest']==digest(encode({k:digest(v) for k,v in recipe_files().items()})), '执行配方变化，请重新识别')
    profile=deepcopy(p['profile'])
    profile.update(id='full-'+uuid.uuid4().hex[:16], name=root.name+' · 完整验收', version='full-workflow-v2')
    projects.register(store,profile)
    run=projects.create(store,profile['id'])
    try:
        return bind_frozen_inputs(store,run,p,sha)
    except Exception as exc:
        run.update(status='error',decision='inconclusive',finished_at=now(),reasons=['冻结完整验收输入失败：'+str(exc)[:500]])
        store.save(run)
        raise


def bind_frozen_inputs(store,run,p,sha):
    from . import reviews
    root=Path(p['repository'])
    if p.get('remote_source'):
        from .remote import repository_fields
        run['remote_source']=p['remote_source']
        run['source_context']['repository'].update(repository_fields(p['remote_source']))
        store.artifact(run,'remote-source.json',encode(p['remote_source']),media_type='application/json')
    expected={x['path']:x['sha256'] for x in p['manifest']}
    require(all(expected.get(x['path'])==x['sha256'] for x in run['project_inputs']), '项目配方与确认的源码快照不一致')
    run['workflow']=dict(version=2,required_stages=list(REQUIRED), children=[], completion='pending',
                         plan=public_plan(p,sha), manifest=p['manifest'], documents=p['documents'])
    run['workflow']['plan_ref']=store.artifact(run,'full-acceptance-plan.json',encode(p),media_type='application/json')
    run['workflow']['orchestrator_ref']=store.artifact(run,'full-workflow.py',Path(__file__).read_bytes(),media_type='text/plain')
    raw=reviews.current();require(digest(raw)==p['review_digest'],'复核策略在冻结期间变化')
    run['workflow']['review_ref']=store.artifact(run,'review-catalog.json',raw,media_type='application/json')
    code=implementation();require(digest(encode(code))==p['implementation_digest'],'验收实现于冻结期间变化')
    store.artifact(run,'implementation-manifest.json',encode(code),media_type='application/json')
    # Freeze every inventoried source once. All child jobs consume this copy, even
    # if the original working directory changes while the model is thinking.
    frozen=store.path(run['id'])/'frozen-repository';frozen.mkdir()
    for row in p['manifest']:
        raw=(root/row['path']).read_bytes()
        require(digest(raw)==row['sha256'],'冻结时仓库发生变化')
        target=frozen/row['path'];target.parent.mkdir(parents=True,exist_ok=True);target.write_bytes(raw);target.chmod(row['mode'])
    store.save(run)
    return run


def run_child(store, integrations, run, child, label):
    entry=dict(id=child['id'],stage=label, source_digest=child['context']['snapshot_digest'])
    run['workflow']['children'].append(entry);store.save(run)
    integrations.execute(child['id'])
    result=integrations.snapshot(child['id'])
    require(result['integrity'],'子任务证据校验失败')
    # A subset is allowed (native recipe excludes dotfiles/Dockerfile), but every
    # file that a child did receive must be from this parent's frozen inventory.
    parent={x['path']:x['sha256'] for x in run['workflow']['manifest']}
    require(all(parent.get(x['path'])==x['sha256'] for x in result['context']['files']), '子任务源码与本次冻结快照不符')
    entry['record_digest']=digest(encode(integrations.read(child['id'])))
    entry['receipt_ref']=store.artifact(run,label+'-child-receipt.json',encode(entry),media_type='application/json')
    store.save(run)
    return result


def model_batches(template):
    """Bound each proposal to one approved standard and an exact source excerpt."""
    docs={d['id']:d for d in template['documents']}
    batches=[]
    for requirement in template['specification']['requirements']:
        if requirement.get('disposition','required')!='required':continue
        original=docs[requirement['source']];content=original['content'];quote=requirement['quote']
        offset=content.find(quote);require(offset>=0,'标准引用不在冻结文档内')
        before=content.rfind('\n\n',0,offset);start=before+2 if before>=0 else 0
        end=content.find('\n\n',offset+len(quote));end=len(content) if end<0 else end
        if end-start>4000:start=max(0,offset-600);end=min(len(content),offset+len(quote)+1000)
        doc={**original,'content':content[start:end],'origin':original['origin']+f'#chars={start}:{end}'}
        bindings={}
        calls_by_shape={};examples=[]
        for scenario in requirement.get('scenarios',[]):
            examples.extend(scenario.get('examples',[]))
            for step in scenario.get('steps',[]):
                if step.get('kind')=='call':
                    binding={k:step[k] for k in ('module','function','args')}
                    binding['result_pointers']=list(dict.fromkeys(a.get('pointer','') for a in step['assertions']))
                    bindings[digest(encode(binding))]=binding
                    calls_by_shape[digest(encode(step))]=step
        require(len(calls_by_shape)==1 and examples,'此标准缺少已审核的单一决策表适配器')
        expected=[e['expected'] for e in examples]
        def json_type(value):
            return 'null' if value is None else 'boolean' if isinstance(value,bool) else 'number' if isinstance(value,(int,float)) else 'string' if isinstance(value,str) else 'object' if isinstance(value,dict) else 'array'
        types=sorted(set(map(json_type,expected)))
        result_schema=dict(type=types[0] if len(types)==1 else types)
        if types==['string']:result_schema['enum']=sorted(set(expected))
        target=dict(id=requirement['id'],title=requirement['title'],source=requirement['source'],quote=quote,
            priority=requirement.get('priority','P2'),call=next(iter(calls_by_shape.values())),
            input_examples=[{k:v for k,v in e.items() if k!='expected'} for e in examples[:2]],result_schema=result_schema,require_chinese=True)
        if requirement['id']=='DEADLINE':
            # The quote describes personal deadlines AFTER starting. Do not seed
            # only READY fixtures or let that prerequisite become an oracle.
            active=[e for e in examples if e.get('enrollment',{}).get('state')=='ACTIVE']
            require(active,'已审定截止适配器没有已开考输入')
            target['input_examples']=[{k:v for k,v in e.items() if k!='expected'} for e in active[:3]]
            target['precondition']='本批只检查已开考（适配器state=ACTIVE）者的个人截止和交卷状态。保持ACTIVE，可变化now、deadline及finalizedAt。未开考READY、已结束等状态另由结构化状态矩阵覆盖。依据为本文档After starting及At deadline原文，不从实现推断预期。'
            target['input_schema']=dict(type='object',required=['enrollment','now'],additionalProperties=False,properties=dict(
                enrollment=dict(type='object',required=['state','deadline','finalizedAt'],properties=dict(state={'const':'ACTIVE'},deadline={'type':'string','format':'date-time'},finalizedAt={'type':['string','null']})),now={'type':'number'}))
        batches.append(dict(id=requirement['id'],title=requirement['title'],source=requirement['source'],quote=quote,
            documents=[doc],call_bindings=list(bindings.values()),table_target=target,span=dict(path=original['origin'],start=start,end=end)))
    return batches


def execute(store, integrations, run):
    from .planning import provider, service, calls
    from .planning.models import DraftInput, DesignInput
    from .integrations.discovery import prepare, create_from_plan
    w=run['workflow'];frozen=store.path(run['id'])/'frozen-repository'
    run['status']='running';store.save(run)
    with store.stage(run,'requirements','读取冻结的需求原文，核对项目独立标准') as phase:
        template=json.loads((ROOT/'acceptance/planning/examples/assessment.json').read_text())
        template.update(repository=str(frozen),include_scanners=False)
        for doc in template['documents']:
            require(doc['origin'] in w['documents'],'依据不在已确认文档内')
            doc['content']=(frozen/doc['origin']).read_text()
            store.artifact(run,'basis-'+doc['id']+'.md',doc['content'].encode(),media_type='text/markdown')
        w['basis_ref']=store.artifact(run,'requirements.json',encode(template['documents']),media_type='application/json')
        phase['detail']=f"{len(template['documents'])} 份独立依据；{len(run['baseline']['criteria'])} 项已审定检查；保留原文引用"
    proposals=[]
    with store.stage(run,'design','配置的模型生成独立中文用例，不从实现推断预期') as phase:
        batches=model_batches(template)
        w['model_batches']=[dict(id=b['id'],title=b['title'],span=b['span'],status='queued') for b in batches]
        try:
            require(len(batches)==len(MODEL_STANDARD_IDS) and {b['id'] for b in batches}==set(MODEL_STANDARD_IDS),'模型必验标准集合与已审核配方不符')
            calls.reconcile(integrations)
            state=provider.status(integrations)
            w['model_status']=state
            require(not state['blocked'],'模型上次请求状态未知，尚不能发送新请求')
            for index,batch in enumerate(batches):
                row=w['model_batches'][index];row.update(status='running',started_at=now())
                phase['detail']=f"{state['label']} 分批设计 {index+1}/{len(batches)}：{batch['title']}";store.save(run)
                scope=(f"只为标准 {batch['id']}（{batch['title']}）设计模块验收。输出恰好一项requirement，id必须为{batch['id']}，"
                       f"source必须为{batch['source']}，quote必须逐字使用：{batch['quote']}。"
                       "最多3个场景、合计最多12个示例；复用给定调用形状并自行从文档确定预期。不要添加其他标准、接口、浏览器、性能或恢复用例。")
                row['input_ref']=store.artifact(run,'model-'+batch['id']+'-input.json',encode(dict(documents=batch['documents'],call_bindings=batch['call_bindings'],table_target=batch['table_target'],scope=scope,language='zh-CN')),media_type='application/json')
                store.save(run)
                draft=provider.draft(integrations,DraftInput(repository=str(frozen),documents=batch['documents'],
                    scope=scope,environment=template['specification']['environment'],call_bindings=batch['call_bindings'],table_target=batch['table_target']))
                require(verified_high(draft.get('connection',{})), '模型来源与响应型号未核验')
                requirements=draft['specification']['requirements']
                require(len(requirements)==1 and requirements[0]['id']==batch['id'] and requirements[0]['source']==batch['source'] and requirements[0]['quote']==batch['quote'] and requirements[0].get('disposition','required')=='required' and requirements[0]['scenarios'],'模型改变了必验标准、引用或验证范围')
                proposed=deepcopy(template);proposed.update(documents=batch['documents'],specification=draft['specification'],draft_id=draft['id'])
                proposals.append(proposed);w['model_connection']=draft['connection']
                row.update(status='passed',finished_at=now(),draft_id=draft['id'],connection=draft['connection'])
                row['ref']=store.artifact(run,'model-'+batch['id']+'.json',encode(draft),media_type='application/json')
                store.save(run)
            phase['detail']=f"{len(batches)} 批模型响应、独立标准及原文引用已核对"
        except (ValueError, OSError) as exc:
            phase.update(status='blocked',detail=str(exc)[:600])
            w['model_blocker']=str(exc)[:600]
            for row in w['model_batches']:
                if row['status'] in {'queued','running'}:row.update(status='blocked',reason=str(exc)[:600],finished_at=now())
            store.artifact(run,'model-blocker.json',encode(dict(reason=str(exc)[:600],status=provider.status(integrations))),media_type='application/json')
            match=re.search(r'请求 ([a-f0-9-]{36})',str(exc))
            if match:
                response=integrations.root/'model-responses'/(match[1]+'.json')
                if response.is_file() and not response.is_symlink():
                    store.artifact(run,'model-rejected-response.json',response.read_bytes(),media_type='application/json')
        store.artifact(run,'model-batches.json',encode(w['model_batches']),media_type='application/json')
    # A reviewed deterministic design is additional verification, never a
    # substitute for successful model design. Both are labelled and archived.
    proposals.append(template)
    with store.stage(run,'Lgenerated','编译需求引用、数据表和边界，执行新生成的独立测试') as phase:
        try:
            generated=[]
            errors=[]
            for proposal in proposals:
                try:
                    plan=service.prepare(integrations,DesignInput.model_validate(proposal))
                    child=service.create_run(integrations,plan['id'],plan['digest'])
                    result=run_child(store,integrations,run,child,'Lgenerated')
                    generated.append(result)
                except (ValueError,OSError) as exc:errors.append(str(exc)[:300])
            require(not errors,'；'.join(errors))
            require(all(r['status']=='completed' and r['decision'] in {'allow','reject'} for r in generated),'生成测试未完整执行')
            phase.update(status='failed' if any(r['decision']=='reject' for r in generated) else 'passed',
                         detail=f"{sum(len(t.get('report',{}).get('tests',[])) for r in generated for t in r['tasks'])} 个独立生成测试已执行；结构化方案与模型方案分别留证")
        except (ValueError, OSError) as exc:phase.update(status='blocked',detail=str(exc)[:600])
    with store.stage(run,'Lscanners','扫描固定源文件、依赖、物料与配置；不作为整体验收完成条件') as phase:
        try:
            scan=prepare(integrations,str(frozen),network=True,tests=False)
            child=create_from_plan(integrations,scan['id'])
            result=run_child(store,integrations,run,child,'Lscanners')
            require(result['status']=='completed' and result['decision'] in {'allow','reject'},'扫描执行异常或报告不完整')
            phase.update(status='failed' if result['decision']=='reject' else 'passed',detail=f"{len(result['tasks'])} 项扫描结束；继续业务、浏览器、性能和恢复验证")
        except (ValueError,OSError) as exc:phase.update(status='blocked',detail=str(exc)[:600])
    store.save(run)
    # Uses the native source archive (same confirmed bytes), dependency-complete
    # build image, temporary PostgreSQL, Playwright, k6 and joint restore.
    return projects.execute(store,run)


def verified_high(connection):
    # Historical call sites retain the name; the policy is now provider-specific.
    from .planning.verification import verified_connection
    return verified_connection(connection)


def coverage(store, run):
    """Re-evaluate completeness and child provenance, including on historical reads."""
    if not run.get('workflow'):return None
    from .integrations.store import IntegrationStore
    integrations=IntegrationStore(store.root/'integrations')
    stages={s['id']:s for s in run.get('pipeline',[])}
    missing=[TITLES.get(k,k) for k in run['workflow']['required_stages'] if stages.get(k,{}).get('status') not in ({'passed'} if k in {'requirements','design','baseline','cases','cleanup'} else {'passed','failed'})]
    from . import reviews
    invalid=[];child_failed=False;model_executed=False;executed_drafts=set();catalog=None
    if run['workflow'].get('version') not in {1,2} or set(run['workflow']['required_stages'])!=set(REQUIRED):
        invalid.append('完整验收流程定义不符')
    if run['workflow'].get('version')==2:
        try:
            catalog=reviews.frozen(store,run)
            require(catalog is not None,'完整流程缺少冻结复核策略')
        except (OSError,ValueError,KeyError) as exc:invalid.append(str(exc))
    children=run['workflow']['children']
    for entry in children:
        try:
            r=integrations.snapshot(entry['id'])
            require(r['integrity'] and digest(encode(integrations.read(entry['id'])))==entry.get('record_digest'),'子任务记录或证据变化')
            parent={x['path']:x['sha256'] for x in run['workflow']['manifest']}
            require(r['context']['files'] and all(parent.get(x['path'])==x['sha256'] for x in r['context']['files']), '子任务快照不符')
            require(r['status']=='completed' and r['decision'] in {'allow','reject'},'子任务未完成有效门禁')
            effective=reviews.child(run,r,catalog) if catalog and entry['stage']=='Lscanners' else None
            child_failed |= r['decision']=='reject' and not (effective and effective['non_blocking'])
            planner=(r.get('test_plan') or {}).get('planner',{})
            if entry['stage']=='Lgenerated' and planner.get('kind')=='model' and verified_high(planner.get('connection') or {}):
                model_executed=True
                executed_drafts.add(planner.get('draft_id'))
        except (OSError,ValueError,KeyError) as exc:invalid.append(str(exc)[:200])
    for label in ('Lgenerated','Lscanners'):
        if not any(c['stage']==label and c.get('record_digest') for c in children):missing.append(TITLES[label]+'报告')
    if stages.get('design',{}).get('status')=='passed':
        connection=run['workflow'].get('model_connection',{})
        if not (verified_high(connection) and model_executed):
            missing.append('模型 High 响应及其用例执行证据')
        batches=run['workflow'].get('model_batches',[])
        if (len(batches)!=len(MODEL_STANDARD_IDS) or {b['id'] for b in batches}!=set(MODEL_STANDARD_IDS) or
            len({b.get('draft_id') for b in batches})!=len(MODEL_STANDARD_IDS)):
            missing.append('五项必验标准的独立模型批次记录')
        if any(b['status']!='passed' or not verified_high(b.get('connection') or {}) or b.get('draft_id') not in executed_drafts for b in batches):
            missing.append('分批模型设计及逐批用例执行')
    blocked=[r['criterion_id'] for r in run['results'] if r['status'] not in {'passed','failed'}]
    expected={c['id'] for c in run['baseline']['criteria'] if c['required']}
    absent=expected-{r['criterion_id'] for r in run['results']}
    missing += blocked+sorted(absent)
    return dict(complete=not missing and not invalid,missing=list(dict.fromkeys(missing)),errors=invalid,child_failed=child_failed)
