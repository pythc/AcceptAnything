"""Manifest-driven acceptance. No repository names or project supplied commands.

Supported execution adapters: Go CLI, existing Node/Python module compiler.
Detection is broader than executable support; gaps are explicit and fail closed.
"""
import json
import re
import shutil
import uuid
from pathlib import Path
from .integrations.discovery import inventory, manifest
from .integrations.runner import encode, sha, invoke
from .integrations.formats import require, parse
from .integrations.registry import locks
from .integrations.store import now
from .planning.models import Document, DraftInput, Environment, CliSpecification
from .planning.basis import MAX_DOCUMENTS, PER_DOCUMENT_CHARACTERS, MAX_TOTAL_CHARACTERS, MAX_REQUIREMENTS_CHARACTERS, limits as basis_limits, candidate_order
from .planning.verification import verified_connection, response_matches, label as model_label

STAGES=[dict(id=k,title=v) for k,v in [('baseline','仓库识别'),('design','模型设计用例'),('dependencies','依赖准备'),('scanners','仓库扫描'),('build','构建与静态检查'),('native','原生测试'),('business','业务用例'),('cleanup','环境清理')]]
SIGNALS={'go.mod':'Go','package.json':'Node.js / TypeScript','pyproject.toml':'Python','requirements.txt':'Python','Cargo.toml':'Rust','pom.xml':'Java / Maven','build.gradle':'Java / Gradle','build.gradle.kts':'Java / Gradle','composer.json':'PHP','Gemfile':'Ruby','CMakeLists.txt':'C / C++'}

def implementation():
    from .workflow import implementation as current
    return sha(encode(current()))


def save(store,record):
    directory=store.root/'automatic-plans';directory.mkdir(exist_ok=True)
    digest=sha(encode(record));(directory/(record['id']+'.json')).write_bytes(encode(dict(record=record,sha256=digest)))
    return public(record,digest)


def load(store,pid,digest=None):
    require(re.fullmatch(r'(intake|auto)-[a-f0-9]{16}',pid),'自动方案编号无效')
    path=store.root/'automatic-plans'/(pid+'.json');require(not path.is_symlink(),'方案路径非法')
    value=json.loads(path.read_bytes());p=value['record']
    require(value['sha256']==sha(encode(p)) and p['id']==pid and (digest is None or value['sha256']==digest),'自动方案摘要不符')
    return p


def check_source(p):
    root,files,_=inventory(p['repository'])
    require(manifest(str(root),files)==p['manifest'],'仓库发生变化，请重新识别并设计用例')
    return root,files


def inspect(store,repository,remote_source=None):
    import time
    started=time.monotonic()
    root,files,omitted=inventory(repository);rows=manifest(str(root),files)
    stacks=[dict(name=SIGNALS[Path(f).name],manifest=f) for f in files if Path(f).name in SIGNALS]
    stacks += [dict(name='.NET',manifest=f) for f in files if f.endswith(('.csproj','.fsproj','.sln'))]
    entries=[]
    for f in files:
        # The Go package walker ignores directories beginning with '.' or '_'.
        if any(part.startswith(('.', '_')) for part in Path(f).parts[:-1]):continue
        if f.endswith('.go') and not f.endswith('_test.go') and re.search(r'(?m)^package main\b',(root/f).read_text(errors='replace')):
            folder=Path(f).parent.as_posix()
            if folder not in entries:entries.append(folder)
    go_roots=[s['manifest'] for s in stacks if s['manifest'].endswith('go.mod')]
    adapter='go-cli' if go_roots==['go.mod'] and len(entries)==1 else 'module' if not go_roots and any(s['name'] in {'Python','Node.js / TypeScript'} for s in stacks) else None
    interfaces=[]
    if adapter=='module':
        for f in files:
            if Path(f).suffix not in {'.py','.js','.mjs','.cjs'} or re.search(r'(^|/)(tests?|testdata|fixtures)(/|$)|test_|_test\.',f):continue
            names=re.findall(r'(?m)^(?:export\s+(?:async\s+)?function|(?:async\s+)?def)\s+([A-Za-z_$][\w$]*)\s*\(', (root/f).read_text(errors='replace'))
            if names:interfaces.append(dict(path=f,functions=names[:30]))
            if len(interfaces)>=30:break
    candidates=[dict(path=f,sha256=next(r['sha256'] for r in rows if r['path']==f),size=(root/f).stat().st_size)
        for f in files if Path(f).suffix.lower() in {'.md','.rst','.txt'} and
        (Path(f).stem.lower() in {'readme','prd','requirements','contract','specification','spec'} or f.startswith(('docs/requirements/','docs/specs/')))]
    for candidate in candidates:
        characters=len((root/candidate['path']).read_text(errors='strict'))
        candidate.update(characters=characters,excerpt_characters=min(characters,PER_DOCUMENT_CHARACTERS))
    candidates.sort(key=candidate_order)
    blockers=[]
    if not stacks:blockers.append('未找到受支持的项目清单；请提供技术栈与独立需求')
    if not adapter:blockers.append('已识别技术栈，但尚无可核验的通用执行适配器；不会套用其他项目配方')
    if adapter=='go-cli' and 'go.sum' not in files:blockers.append('Go 依赖缺少 go.sum，无法固定依赖校验')
    if adapter=='module' and not interfaces:blockers.append('未找到支持的公开模块入口；服务启动和业务接口需要独立部署契约')
    if not candidates:blockers.append('缺少独立需求依据，请粘贴需求后再设计用例；实现和测试不能作为正确答案')
    p=dict(id='intake-'+uuid.uuid4().hex[:16],kind='automatic',repository=str(root),manifest=rows,snapshot_digest=sha(encode(rows)),
        detection=dict(stacks=stacks,adapter=adapter,entrypoints=entries,interfaces=interfaces,document_candidates=candidates,basis_limits=basis_limits(),omitted=omitted,duration_ms=round((time.monotonic()-started)*1000)),
        blockers=blockers,documents=[],exclusions=[],stages=STAGES,scope='依据已确认文档设计用例；按技术栈执行适用检查',created_at=now())
    if remote_source:p['remote_source']=remote_source
    return save(store,p)


def public(p,digest):
    result={k:p[k] for k in ('id','kind','repository','scope','stages','blockers','documents','exclusions','detection','snapshot_digest')}
    result.update(digest=digest,file_count=len(p['manifest']),check_count=len(p.get('profile',{}).get('tasks',[])),ready=p['id'].startswith('auto-') and not p['blockers'])
    if p.get('remote_source'):result['remote_source']=p['remote_source']
    if p.get('specification'):result['specification']=p['specification']
    if p.get('planner'):result['planner']=p['planner']
    return result


def design(store,intake_id,documents,requirements_text='',scope='',*,draft_id=None):
    from .planning import provider,service
    from .planning.models import DesignInput
    p=load(store,intake_id);root,files=check_source(p);d=p['detection']
    require(d['adapter'] in {'go-cli','module'},'此技术栈尚无已核验的执行适配器')
    docs=[];available={x['path']:x for x in d['document_candidates']}
    require(len(documents)<=MAX_DOCUMENTS,f'本次最多选择 {MAX_DOCUMENTS} 份依据文档，当前已选 {len(documents)} 份；请缩小本次范围')
    require(len(set(documents))==len(documents),'依据文档不能重复选择')
    for i,f in enumerate(documents):
        require(f in available,'依据必须来自已识别的文档候选，不能引用实现或测试')
        raw=(root/f).read_text(errors='strict')
        # Bound model input; excerpt identity and full-file hash remain visible.
        docs.append(Document(id='DOC'+str(i+1),title=f,origin=f+'#chars=0:'+str(min(len(raw),PER_DOCUMENT_CHARACTERS)),content=raw[:PER_DOCUMENT_CHARACTERS]))
    require(len(requirements_text)<=MAX_REQUIREMENTS_CHARACTERS,f'补充需求最多 {MAX_REQUIREMENTS_CHARACTERS:,} 字符')
    if requirements_text.strip():docs.append(Document(id='USER',title='用户独立需求',origin='用户输入',content=requirements_text.strip()))
    require(docs,'缺少独立需求依据，不能从代码反推预期；请选择需求文档或粘贴需求')
    require(sum(len(x.content) for x in docs)<=MAX_TOTAL_CHARACTERS,f'依据合计超过 {MAX_TOTAL_CHARACTERS:,} 字符，请减少文档或补充需求后再生成')
    scope=scope.strip() or ('验收文档明确描述的命令行输入、输出和错误行为；不包含库嵌入、性能SLO或外部系统' if d['adapter']=='go-cli' else '仅验收独立需求明确描述的公开模块行为；不把模块调用视为完整服务验收')
    if d['adapter']=='module':
        runtime='python' if any(s['name']=='Python' for s in d['stacks']) else 'node'
        draft=provider.draft(store,DraftInput(repository=str(root),documents=docs,scope=scope,environment=Environment(mode='module',runtime=runtime)))
        allowed={(x['path'],name) for x in d['interfaces'] for name in x['functions']}
        require(all((step['module'],step['function']) in allowed for q in draft['specification']['requirements'] for s in q['scenarios'] for step in s['steps']),'模型引用了未识别的公开模块入口')
        require(verified_connection(draft['connection']),'模型来源与响应型号尚未核验')
        check_source(p)
        prepared=service.prepare(store,DesignInput(repository=str(root),documents=docs,specification=draft['specification'],draft_id=draft['id']),remote_source=p.get('remote_source'))
        # Reuse the proven compiler and evidence chain; no project recipe.
        return dict(id=prepared['id'],digest=prepared['digest'],kind='automatic-module',detection=d,ready=prepared['ready'],scope=scope,
            repository=str(root),file_count=len(p['manifest']),check_count=len(prepared['checks']),documents=[x.title for x in docs],stages=STAGES,
            blockers=[x['title']+'：'+x['reason'] for x in prepared['blockers']],exclusions=prepared['exclusions'],specification=prepared['specification'],planner=prepared['planner'])
    require('go.sum' in files,'缺少 go.sum，无法固定依赖')
    require(locks().get('auto-go',{}).get('id'),'Go 通用执行镜像未准备')
    require(locks().get('python',{}).get('id'),'独立用例执行镜像未准备')
    environment=Environment(mode='cli',runtime='go',entrypoint=d['entrypoints'][0])
    target=dict(adapter='go-cli',entrypoint=d['entrypoints'][0],invocation='固定编译产物 + argv 数组 + stdin；无 shell，无外网')
    if draft_id:
        require(re.fullmatch(r'draft-[a-f0-9]{16}',draft_id),'草稿编号无效')
        wrapped=json.loads((store.root/'drafts'/(draft_id+'.json')).read_bytes());draft=wrapped['record']
        require(sha(encode(draft))==wrapped['sha256'] and draft['repository']==str(root) and draft['documents']==[x.model_dump() for x in docs] and draft.get('automatic_target')==target and draft['specification']['environment']==environment.model_dump(),'已有草稿与本次依据或入口不一致')
    else:
        draft=provider.draft(store,DraftInput(repository=str(root),documents=docs,scope=scope,environment=environment,automatic_target=target))
    require(verified_connection(draft['connection']),'模型来源与响应型号尚未核验')
    check_source(p)
    spec=CliSpecification.model_validate(draft['specification']);blockers=[r.title+'：'+r.reason for r in spec.requirements if r.disposition=='unresolved']
    if not any(q.scenarios for q in spec.requirements):blockers.append('没有可执行的独立用例；请补充预期和适用前提')
    from .integrations.discovery import prepare
    scan=prepare(store,str(root),network=True,tests=False)
    wrapped=json.loads((store.root/'plans'/(scan['id']+'.json')).read_bytes());profile=wrapped['record']['profile']
    exclusions=[x for x in profile['exclusions'] if x['subject'] not in {'仓库现有测试','业务流程、浏览器、性能与恢复'}]
    exclusions += [dict(subject='浏览器、接口与持久化服务',reason='本次范围为命令行行为，没有可运行 Web 服务契约；不生成无关用例'),
        dict(subject='性能与故障恢复',reason='选定依据没有响应时间/吞吐SLO、故障模型与持久化恢复标准；不推测通过'),
        dict(subject='库嵌入及未选文档功能',reason='本次仅覆盖已确认文档中的命令行场景，不声称整产品功能穷尽覆盖')]
    exclusions += [dict(subject=r.title,reason=r.reason) for r in spec.requirements if r.disposition=='excluded']
    custom=[dict(id=tid,tool='auto-go-'+tool,target='.',timeout=900 if tool in {'dependencies','native'} else 300,network='registry' if tool=='dependencies' else 'none')
        for tid,tool in [('auto-dependencies','dependencies'),('auto-build','build'),('auto-vet','vet'),('auto-native','native'),('auto-business','business'),('auto-cleanup','cleanup')]]
    tasks=custom[:1]+profile['tasks']+custom[1:]
    rules=profile['rules']+[
        dict(id=t['id']+'-fail',kind='metric',tasks=[t['id']],metric='tests.failed',operator='le',threshold=0) for t in custom]
    rules += [dict(id=t['id']+'-minimum',kind='metric',tasks=[t['id']],metric='tests.total',operator='ge',threshold=1) for t in custom]
    names=[s.id+' · '+s.title for q in spec.requirements for s in q.scenarios]
    if names:rules.append(dict(id='auto-business-required',kind='required-tests',tasks=['auto-business'],values=names))
    profile.update(name=(p.get('remote_source') or {}).get('name',root.name)+' · 自动验收',version='automatic-v1',scope=scope,tasks=tasks,rules=rules,exclusions=exclusions)
    from .integrations.models import Profile
    profile=Profile.model_validate(profile).model_dump()
    p.update(id='auto-'+uuid.uuid4().hex[:16],documents=[x.model_dump() for x in docs],scope=scope,profile=profile,specification=spec.model_dump(),
        planner=dict(kind='model',model=draft['model'],draft_id=draft['id'],connection=draft['connection'],citation_adjustments=[a for a in draft.get('citations',[]) if a['method']!='exact']),blockers=blockers,exclusions=exclusions,
        implementation_digest=implementation(),toolchain_digest=sha(encode(locks())))
    return save(store,p)


def create(store,pid,digest):
    p=load(store,pid,digest);require(pid.startswith('auto-') and not p['blockers'],'验收方案尚未就绪')
    check_source(p);require(p['implementation_digest']==implementation(),'验收实现变化，请重新设计方案')
    require(p['toolchain_digest']==sha(encode(locks())),'执行工具变化，请重新确认方案')
    if p.get('remote_source'):
        from .remote import verify
        verify(store,p['remote_source'])
    store.register(p['profile']);r=store.create(p['profile']['id'],prepared_plan=p)
    require(r['context']['snapshot_digest']==p['snapshot_digest'],'冻结时源码发生变化')
    r['automatic_plan']=p;r['automatic_plan_ref']=store.artifact(r,'automatic-plan.json',encode(p));r['onboarding_plan']=public(p,digest)
    draft=json.loads((store.root/'drafts'/(p['planner']['draft_id']+'.json')).read_bytes())
    r['automatic_draft_ref']=store.artifact(r,'model-draft.json',encode(draft))
    r['automatic_driver_ref']=store.artifact(r,'automatic-cli.py',Path(__file__).with_name('automatic_cli.py').read_bytes())
    client=p['planner']['connection']['client_request_id'];raw=store.root/'model-responses'/(client+'.json')
    r['automatic_response_ref']=store.artifact(r,'model-response.json',raw.read_bytes())
    if draft['record'].get('input_sha256'):
        input_bytes=(store.root/'model-inputs'/(client+'.json')).read_bytes()
        require(sha(input_bytes)==draft['record']['input_sha256'],'模型原始输入摘要不一致')
        r['automatic_input_ref']=store.artifact(r,'model-input.json',input_bytes)
    if p.get('remote_source'):
        from .remote import bind_run
        bind_run(store,r,p['remote_source'])
    store.save(r);return r


def verify_archived(store,r):
    p=r['automatic_plan']
    require(json.loads(store.artifact_bytes_for_record(r,r['automatic_plan_ref'])[1])==p,'冻结自动方案不一致')
    require(r['profile']==p['profile'],'执行配置与冻结方案不一致')
    expected=[{k:t[k] for k in p['profile']['tasks'][0]} for t in r['tasks']]
    require(expected==p['profile']['tasks'],'执行任务与冻结方案不一致')
    require(p['snapshot_digest']==r['context']['snapshot_digest'] and p['manifest']==r['context']['files'],'自动方案源码不一致')
    draft=json.loads(store.artifact_bytes_for_record(r,r['automatic_draft_ref'])[1]);record=draft['record']
    require(sha(encode(record))==draft['sha256'] and record['specification']==p['specification'] and record['documents']==p['documents'],'模型原始用例或依据被改变')
    if record.get('input_sha256'):
        require(sha(store.artifact_bytes_for_record(r,r['automatic_input_ref'])[1])==record['input_sha256'],'模型原始输入不一致')
    raw=json.loads(store.artifact_bytes_for_record(r,r['automatic_response_ref'])[1])
    require(sha(encode(raw))==record['response_sha256'] and response_matches(raw,record['connection']) and record['connection']==p['planner']['connection'],'模型原始响应不一致')
    require(json.loads(raw['choices'][0]['message']['content'])==record['model_output'] and raw['choices'][0]['finish_reason']=='stop','模型响应未完整结束')
    from .planning.provider import cli_spec
    data=DraftInput(repository=record['repository'],documents=record['documents'],scope=record['specification']['scope'],environment=record['specification']['environment'],automatic_target=record['automatic_target'])
    from .planning.citations import ground
    projected,anchors,errors=ground(cli_spec(data,record['model_output']),data.documents)
    require(not errors and projected.model_dump()==p['specification'],'方案与模型输出不一致')
    if 'citations' in record:require(anchors==record['citations'],'引用定位证据不一致')
    CliSpecification.model_validate(p['specification'])
    docs={x['id']:x['content'] for x in p['documents']}
    require(all(x['source'] in docs and x['quote'] in docs[x['source']] for x in p['specification']['requirements']),'需求引用失效')
    if p.get('remote_source'):
        from .remote import verify_archived as verify_remote
        # Normalize the plan field for the existing immutable remote provenance verifier.
        verify_remote(store,{**r,'test_plan':p})
    return True


def junit(path,name,success,detail=''):
    from xml.etree.ElementTree import Element,SubElement,tostring
    suite=Element('testsuite',name='自动验收',tests='1',failures='0' if success else '1');case=SubElement(suite,'testcase',name=name,classname='automatic')
    if not success:SubElement(case,'failure',message=detail[:2000]).text=detail[:10000]
    path.write_bytes(tostring(suite,encoding='utf-8'))


def execute(store,r,t,output,cancelled):
    output.mkdir(parents=True);p=r['automatic_plan'];base=store.path(r['id']);cache=base/'automatic-cache';cache.mkdir(exist_ok=True)
    action=t['tool'].removeprefix('auto-go-');source=base/'source';name='acceptance-auto-'+uuid.uuid4().hex[:16]
    if action=='cleanup':
        import time
        started=time.monotonic();shutil.rmtree(cache)
        for filename in ('automatic-binary','automatic-driver.py','automatic-cases.json'):
            path=base/filename
            if path.exists():path.unlink()
        command=dict(argv=['internal:remove-run-cache'],exit_code=0,duration_ms=round((time.monotonic()-started)*1000),interruption=None)
        (output/'command.json').write_bytes(encode(command))
        (output/'cleanup.json').write_bytes(encode(dict(cache_removed=not cache.exists(),temporary_binary_removed=not (base/'automatic-binary').exists(),containers='docker --rm; request-scoped names')))
        junit(output/'report.xml','临时执行缓存清理',not cache.exists())
        return parse('junit',(output/'report.xml').read_bytes()),command
    require(p['implementation_digest']==implementation(),'自动执行器发生变化，停止执行')
    image=r['images']['auto-go']['id'];env=['-e','GOTOOLCHAIN=local','-e','GOMODCACHE=/cache/mod','-e','GOCACHE=/cache/build','-e','CGO_ENABLED=0','-e','GOFLAGS=-mod=readonly']
    argv=['docker','run','--rm','--name',name,'--network','bridge' if action=='dependencies' else 'none','--memory','1536m','--cpus','2','--pids-limit','256','--read-only','--cap-drop','ALL','--security-opt','no-new-privileges','--tmpfs','/tmp:rw,exec,size=512m','-v',str(source)+':/source:ro','-v',str(cache)+':/cache','-v',str(output)+':/output','-w','/source']
    if action=='business':
        frozen=base/'automatic-driver.py'
        frozen.write_bytes(store.artifact_bytes_for_record(r,r['automatic_driver_ref'])[1]);specfile=base/'automatic-cases.json';specfile.write_bytes(encode(p['specification']))
        binary=base/'automatic-binary';require(binary.is_file() and sha(binary.read_bytes())==r['automatic_binary_sha256'],'编译产物丢失或被改变')
        argv += ['-v',str(binary)+':/app:ro','-v',str(frozen)+':/driver.py:ro','-v',str(specfile)+':/cases.json:ro',r['images']['python']['id'],'python','/driver.py']
    else:
        command={'dependencies':['go','mod','download'],'build':['go','build','-o','/output/app','./'+p['detection']['entrypoints'][0]],'vet':['go','vet','./...'],
            'native':['gotestsum','--junitfile','/output/report.xml','--jsonfile','/output/events.jsonl','--','-count=1','-timeout=600s','./...']}[action]
        argv+=env+[image]+command
    command,_=invoke(argv,t['timeout'],output,cancelled,container=name);(output/'command.json').write_bytes(encode(command))
    require(command['interruption'] is None,'执行中断：'+str(command['interruption']))
    if action=='native' and command['exit_code']!=0:
        events=[json.loads(line) for line in (output/'events.jsonl').read_text().splitlines() if line.strip()]
        require(any(e.get('Test') and e.get('Action')=='run' for e in events),'Go 原生测试未能启动或包构建失败；查看 stdout.log 与 events.jsonl，不能算作测试已执行')
    if action=='build' and command['exit_code']==0:
        binary=base/'automatic-binary';shutil.copyfile(output/'app',binary);binary.chmod(0o555);r['automatic_binary_sha256']=sha(binary.read_bytes())
        (output/'binary-digest.json').write_bytes(encode(dict(sha256=r['automatic_binary_sha256'],size=binary.stat().st_size)));(output/'app').unlink()
    if action not in {'native','business'}:junit(output/'report.xml',dict(dependencies='依赖校验与准备',build='构建命令行程序',vet='Go 静态检查')[action],command['exit_code']==0,(output/'stderr.log').read_text(errors='replace'))
    report=parse('junit',(output/'report.xml').read_bytes())
    require(report['tests'],'执行器没有执行任何测试')
    failed=any(x['status'] in {'failed','error'} for x in report['tests'])
    require((command['exit_code']!=0)==failed,'进程退出状态与测试报告不符')
    return report,command


def completion(r):
    missing=[t['id'] for t in r['tasks'] if t['state']!='completed' or not t.get('report_ref')]
    if any(t.get('report',{}).get('complete') is False for t in r['tasks']):missing.append('存在未完整执行的报告（跳过或执行异常）')
    business=next((t for t in r['tasks'] if t['tool']=='auto-go-business'),{})
    planned={s['id']+' · '+s['title'] for q in r['automatic_plan'].get('specification',{}).get('requirements',[]) for s in q['scenarios']}
    if planned!={x['name'] for x in business.get('report',{}).get('tests',[])}:missing.append('模型用例未逐项完整执行')
    if not r['automatic_plan']['planner']['connection'].get('verified'):missing.append('实际模型未核验')
    if r['automatic_plan']['blockers']:missing+=r['automatic_plan']['blockers']
    return dict(kind='declared-scope',complete=not missing,missing=missing,scope=r['automatic_plan']['scope'])


def present(view,r):
    p=r['automatic_plan'];groups={'dependencies':['auto-dependencies'],'scanners':[t['id'] for t in r['tasks'] if not t['tool'].startswith('auto-go-')],'build':['auto-build','auto-vet'],'native':['auto-native'],'business':['auto-business'],'cleanup':['auto-cleanup']}
    stages=[dict(id='baseline',title='仓库识别',status='passed',detail=f"{len(p['manifest'])} 个文件；技术栈与入口来自清单和声明"),dict(id='design',title='模型设计用例',status='passed',duration_ms=p['planner']['connection']['duration_ms'],detail=model_label(p['planner']['connection'])+'；中文用例来自已确认文档，设计发生在启动前')]
    if 'duration_ms' in p['detection']:stages[0]['duration_ms']=p['detection']['duration_ms']
    for definition in STAGES[2:]:
        tasks=[t for t in r['tasks'] if t['id'] in groups[definition['id']]];states={t['state'] for t in tasks}
        status='running' if 'running' in states else 'blocked' if states & {'error','cancelled'} else 'passed' if states=={'completed'} else 'queued'
        if status=='passed' and any(any(x['status'] in {'failed','error'} for x in t.get('report',{}).get('tests',[])) or t.get('report',{}).get('findings') for t in tasks):status='failed'
        stages.append(dict(id=definition['id'],title=definition['title'],status=status,duration_ms=sum(t.get('duration_ms') or 0 for t in tasks),detail=f"{sum(t['state']=='completed' for t in tasks)}/{len(tasks)} 项已执行",check_ids=[t['id'] for t in tasks]))
    extra=[s for s in view['display_stages'] if s['id'] in {'review','gate'}]
    view.update(stages=stages+extra,pipeline=stages+extra,display_stages=stages+extra,completion=completion(r),automatic_plan=p,
        reasons=r.get('errors') or [p['scope']+'；完整性与质量结论分别判定'],limits=[x['subject']+'：'+x['reason'] for x in p['exclusions']])
    for stage in stages[2:]:
        group=[t for t in r['tasks'] if t['id'] in groups[stage['id']]]
        starts=[t['started_at'] for t in group if t.get('started_at')];ends=[t['finished_at'] for t in group if t.get('finished_at')]
        if starts:stage['started_at']=min(starts)
        if ends and all(t['state'] not in {'queued','running'} for t in group):stage['finished_at']=max(ends)
        for criterion in view['baseline']['criteria']:
            if criterion['id'] in groups[stage['id']]:criterion['layer']=stage['id']
    titles=dict(zip(['auto-dependencies','auto-build','auto-vet','auto-native','auto-business','auto-cleanup'],['依赖校验与准备','构建命令行程序','Go 静态检查','原生 Go 回归','模型设计的业务用例','临时环境清理']))
    for criterion in view['baseline']['criteria']:
        if criterion['id'] in titles:criterion.update(title=titles[criterion['id']],executor='Go / gotestsum' if criterion['id']!='auto-business' else '独立 CLI 用例执行器')
    # Existing plan detail component consumes this shape; keep original raw contract too.
    cases=[dict(id=s['id'],name=s['title'],requirement=q['id'],source=q['source'],quote=q['quote'],engine='cli',dimension=s['dimension'],steps=[s]) for q in p['specification']['requirements'] for s in q['scenarios']]
    view['test_plan']=dict(id=p['id'],planner=p['planner'],documents=p['documents'],specification=p['specification'],cases=cases,generated=[],coverage=[],environment=p['specification']['environment'])
    return view
