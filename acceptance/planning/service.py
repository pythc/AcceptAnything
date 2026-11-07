import json
from pathlib import Path
import uuid
from . import compiler
from ..integrations.discovery import inventory, manifest, prepare as scan_plan
from ..integrations.runner import sha,encode
from ..integrations.formats import require
from ..integrations.models import Profile
from ..integrations.registry import ROOT,locks


def prepare(store,data,*,repository_binding=None,remote_source=None):
    plan=compiler.compile_plan(data)
    if remote_source:
        require(remote_source['snapshot_digest']==plan['snapshot_digest'],'远程源码与生成方案不一致')
        plan['remote_source']=remote_source
    if repository_binding:
        require(repository_binding['snapshot_digest']==plan['snapshot_digest'],'迁移方案与已审定源码快照不同')
        plan['repository_binding']=repository_binding
    from ..integrations.adjudication import policy
    plan['finding_review_policy']=policy(store,dict(repository=plan['repository'],snapshot_digest=plan['snapshot_digest']))
    if data.draft_id:
        from .provider import provenance
        plan['planner']=provenance(store,data.draft_id,plan)
    elif data.draft_ids:
        from .provider import provenance_many
        plan['planner']=provenance_many(store,data.draft_ids,plan)
    tasks=[];rules=[]
    if data.include_scanners:
        scan=scan_plan(store,data.repository,network=data.specification.environment.recipe=='gmah-v1')
        path=store.root/'plans'/(scan['id']+'.json')
        scanned=json.loads(path.read_bytes())['record']
        require(scanned['snapshot_digest']==plan['snapshot_digest'],'生成期间代码发生变化，请重新设计')
        tasks=scanned['profile']['tasks'];rules=scanned['profile']['rules']
        plan['checks']=scan['checks']+plan['checks']
        plan['exclusions'] += [e for e in scan['exclusions'] if e['subject'] not in {'业务流程、浏览器、性能与恢复','仓库现有测试','真实邮箱、外部身份与付费服务'}]
    for check in plan['checks']:
        if 'engine' not in check: continue
        tasks.append(dict(id=check['id'],tool='acceptance-generated',target=check['engine'],timeout=300,network='none'))
        rules.append(dict(id=check['id']+'-failed',kind='metric',tasks=[check['id']],metric='tests.failed',operator='le',threshold=0))
        rules.append(dict(id=check['id']+'-count',kind='metric',tasks=[check['id']],metric='tests.total',operator='ge',threshold=len(check['case_ids'])))
        if check['engine']!='openapi':
            rules.append(dict(id=check['id']+'-required',kind='required-tests',tasks=[check['id']],values=['test_'+c for c in check['case_ids']]))
        else:
            rules.append(dict(id=check['id']+'-required',kind='required-tests',tasks=[check['id']],values=compiler.planned_operations(plan,check)))
    if data.specification.environment.recipe=='gmah-v1':
        for tool,title,count in [('gmah-build','生产构建',1),('gmah-regression','仓库原有回归',248),('gmah-performance','会话创建与读回负载',3),('gmah-recovery','服务重启与业务数据恢复',1)]:
            tasks.append(dict(id=tool,tool=tool,target='.',timeout=300,network='none'))
            rules.extend([dict(id=tool+'-failed',kind='metric',tasks=[tool],metric='tests.failed',operator='le',threshold=0),
                          dict(id=tool+'-count',kind='metric',tasks=[tool],metric='tests.total',operator='ge',threshold=count)])
            plan['checks'].append(dict(id=tool,title=title,tool=tool,expected='完整执行且满足冻结门禁'))
        plan['exclusions'].append(dict(subject='GMAH 外部业务边界',reason='使用仓库自带批改 mock adapter；原有9条需 MODEL_API_KEY 的外部模型测试不收集，QQ、真实通知和远程 MCP 不在本次本地 MVP 范围。负载门限为工程检查预算，并非产品容量承诺。'))
    plan['scanner_toolchain_digest']=sha(encode(locks()))
    if tasks:
        plan['profile']=Profile.model_validate(dict(id='local-design-'+uuid.uuid4().hex[:12],name=plan['name'],repository=plan['repository'],
            version='requirements-v1',environment='隔离目标容器；独立测试驱动；合成数据',scope=plan['scope'],files=[r['path'] for r in plan['manifest']],
            tasks=tasks,rules=rules,exclusions=plan['exclusions'])).model_dump()
    return compiler.save(store,plan)


def create_run(store, plan_id, digest):
    plan,actual=compiler.read(store,plan_id)
    require(digest==actual,'确认的方案版本不匹配')
    if plan.get('remote_source'):
        from ..remote import verify
        verify(store,plan['remote_source'])
    from ..integrations.adjudication import policy
    require(plan.get('finding_review_policy')==policy(store,dict(repository=plan['repository'],snapshot_digest=plan['snapshot_digest'])),'复核策略或人工复核版本变化，请重新确认方案')
    require(not plan['blockers'] and plan['cases'],'仍有未设计或待确认的必验标准')
    if plan.get('project_configuration'):
        config=plan['project_configuration']
        require(sha(Path(config['path']).read_bytes())==config['sha256'],'项目配置已变化，请重新确认方案')
    root,files,_=inventory(plan['repository'])
    require(files==[r['path'] for r in plan['manifest']] and sha(encode(manifest(str(root),files)))==plan['snapshot_digest'],'仓库内容已变化，请重新生成方案')
    require(compiler.dependencies()==plan['toolchain'] and compiler.compiler_digest()==plan['compiler_digest'] and sha(encode(locks()))==plan['scanner_toolchain_digest'], '生成器或执行器版本已变化，请重新生成方案')
    store.register(plan['profile'])
    run=store.create(plan['profile']['id'],prepared_plan=plan)
    if run['context']['snapshot_digest']!=plan['snapshot_digest']:
        from ..integrations.store import now
        run.update(status='error',decision='inconclusive',finished_at=now(),errors=['冻结期间代码发生变化'])
        store.save(run);raise ValueError('冻结期间代码发生变化')
    run['onboarding_plan']=dict(id=plan_id,repository=plan['repository'],checks=plan['checks'],scope=plan['scope'])
    run['test_plan']=plan
    if plan.get('remote_source'):
        from ..remote import bind_run
        bind_run(store,run,plan['remote_source'])
    run['design_digest']=actual
    run['design_ref']=store.artifact(run,'acceptance-plan.json',encode(plan))
    directory=store.path(run['id'])/'generated';directory.mkdir()
    for name,content in plan['generated'].items():
        (directory/name).write_text(content)
        store.artifact(run,'generated/'+name,content.encode())
    for file in compiler.RUNTIME.iterdir():
        if file.suffix in {'.py','.cjs'}:
            (directory/file.name).write_bytes(file.read_bytes())
            store.artifact(run,'driver/'+file.name,file.read_bytes())
    (directory/'plan.json').write_bytes(encode(plan))
    for doc in plan['documents']: store.artifact(run,'basis/'+doc['id']+'.txt',doc['content'].encode())
    for name,content in plan.get('recipe_files',{}).items():
        store.artifact(run,'recipe/'+name,content.encode())
    planner=plan.get('planner',{})
    for did in planner.get('draft_ids',[]) or ([planner['draft_id']] if planner.get('draft_id') else []):
        raw=(store.root/'drafts'/(did+'.json')).read_bytes()
        record=json.loads(raw)['record']
        store.artifact(run,'model/'+did+'.json',raw)
        if record.get('binding_revision'):
            from .provider import validate_binding_revision
            validate_binding_revision(store,record)
            parent=record['binding_revision']['parent_id']
            store.artifact(run,'model/'+parent+'.json',(store.root/'drafts'/(parent+'.json')).read_bytes())
        cid=record.get('connection',{}).get('client_request_id')
        if cid:
            receipt=json.loads((store.root/'model-calls'/(cid+'.json')).read_bytes())
            response=(store.root/'model-responses'/(cid+'.json')).read_bytes()
            require(sha(response)==receipt['response_sha256'],'模型原始响应摘要不一致')
            store.artifact(run,'model/'+cid+'-response.json',response)
            if record.get('input_sha256'):
                input_bytes=(store.root/'model-inputs'/(cid+'.json')).read_bytes()
                require(sha(input_bytes)==record['input_sha256']==receipt['input_sha256'],'模型原始输入摘要不一致')
                store.artifact(run,'model/'+cid+'-input.json',input_bytes)
    run['generated_manifest']={p.name:sha(p.read_bytes()) for p in directory.iterdir() if p.is_file()}
    run['generated_manifest_ref']=store.artifact(run,'generated-manifest.json',encode(run['generated_manifest']))
    store.save(run)
    return run


def inspect_repository(repository):
    root,files,_=inventory(repository)
    docs=[p for p in files if Path(p).suffix in {'.md','.txt'}]
    return dict(repository=str(root),documents=docs,files=[p for p in files if Path(p).suffix in {'.py','.js','.mjs','.ts','.cjs'}])


def read_source(repository,path):
    root,files,_=inventory(repository)
    require(path in files and Path(path).suffix in {'.md','.txt','.json'},'请选择仓库范围内的文本依据')
    return dict(id='basis',title=path,origin=path,content=(root/path).read_text())
