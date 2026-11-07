"""Registered assessment recipe: frozen inputs, disposable services, validated reports.

This is an explicit project integration, not an arbitrary shell API. Gaps are
part of its frozen plan and never count as passes. No production services run.
"""
import base64
import ipaddress
import json
import math
import os
from pathlib import Path
import re
import selectors
import socketserver
import subprocess
import threading
from time import monotonic, sleep
import urllib.request

from .projects import NODE_IMAGE, packed, sha, parse_junit
from .validation import require, one
from .progress import checks, register_cases, activity, end_activity

HERE = Path(__file__).parent / 'recipes/assessment'
CACHE = 'sha256:97a1397b413821b489db82c6d46ee89715a0d73651a2fc526969060a313504c5'
PG = 'sha256:cf78e76683b9ca8c5733cbbdce6c9262b45b6767934dd0a95e671f9a0fc20685'
PYTHON = 'sha256:d09d15e60962ca365d1cd544a48773bac9d33f2fb1b00f2aa0deec78ade7dc31'
GITLEAKS = 'sha256:c00b6bd0aeb3071cbcb79009cb16a60dd9e0a7c60e2be9ab65d25e6bc8abbb7f'
IMAGES = {'node': NODE_IMAGE, 'dependencies': CACHE, 'postgres': PG, 'python': PYTHON, 'gitleaks': GITLEAKS}


def recipe_files():
    return {**{p.name: p.read_bytes() for p in sorted(HERE.iterdir()) if p.is_file()}, 'expanded.py': Path(__file__).read_bytes(), 'complete.py': Path(__file__).with_name('complete.py').read_bytes()}


def freeze(p, b):
    b.update(recipe=p['recipe'], recipe_report_version=2, images=IMAGES, recipe_digests={k: sha(v) for k,v in recipe_files().items()}, scope=p['scope'])
    if 'exclusions' in p:
        from .complete import IMAGES as extra_images
        b.update(recipe_report_version=3, images={**IMAGES, **extra_images}, exclusions=p['exclusions'])
    for c in b['criteria']:
        c['layer'] = next(x['layer'] for x in p['criteria'] if x['id']==c['id'])
        c['executor'] = 'playwright' if c['kind']=='playwright' else 'assessment-check'
        c['impact'] = c['limitation']


def summary(status, count, failed, text, names=None):
    return {'status':status, 'tests':count, 'failed':failed, 'case_names':names or [], 'failure_text':text,
            'summary':text, 'actual':text}


def parse_report(c, raw, code):
    kind = c['kind']
    if kind == 'junit':
        result = parse_junit(raw, c['test_names'], code)
        require(set(result['files']) == {'/workspace/'+f for f in c['test_files']}, 'JUnit 文件范围不符')
        return {**result, 'summary': f"{result['tests']} 个测试，{result['failed']} 个失败", 'actual': result['failure_text'] or f"{result['tests']} 个测试通过"}
    report = json.loads(raw)
    if kind == 'python':
        require(report.get('runner')=='unittest', '不是 unittest 报告')
        cases = report['cases']; names=[x['name'] for x in cases]
        require(len(names)==len(c['test_names']) and set(names)==set(c['test_names']), 'Python 用例清单不符')
        require(all(x['status'] in ('passed','failed','error','skipped') and math.isfinite(x['duration']) and x['duration']>=0 for x in cases), 'Python 结果无效')
        failed=sum(x['status']=='failed' for x in cases); errors=sum(x['status']=='error' for x in cases); skipped=sum(x['status']=='skipped' for x in cases)
        require(report['tests']==len(cases) and report['failures']==failed and report['errors']==errors and report['skipped']==skipped, 'Python 统计不符')
        require(code==(1 if failed or errors else 0), 'Python 退出码不符')
        status='blocked' if skipped or errors else 'failed' if failed else 'passed'
        text=f'{len(cases)} 个测试，{failed} 个失败，{errors} 个错误，{skipped} 个跳过'
        return summary(status,len(cases),failed,text+'\n'+'\n'.join(x['name']+': '+x['detail'] for x in cases if x['status']!='passed'),names)
    if kind == 'npm-audit':
        require(report.get('auditReportVersion')==2 and 'error' not in report, 'npm 审计未完成')
        findings=report['vulnerabilities']; counts=report['metadata']['vulnerabilities']
        require(isinstance(findings,dict) and report['metadata']['dependencies']['total']>0, '依赖审计为空')
        require(counts['total']==len(findings) and counts['total']==sum(counts[k] for k in ['info','low','moderate','high','critical']), '审计统计不符')
        for name,v in findings.items():
            require(v['name']==name and v['via'] and v['nodes'] and v['severity'] in counts, '审计发现无效')
        require(code==(1 if findings else 0), '审计退出码不符')
        text='\n'.join(f"{k} · {v['severity']} · {v['range']}\n"+'\n'.join(x['title']+' '+x['url'] for x in v['via'] if isinstance(x,dict)) for k,v in findings.items())
        return summary('failed' if findings else 'passed',report['metadata']['dependencies']['total'],len(findings),text or '锁定依赖未报告已知漏洞',list(findings))
    if kind == 'gitleaks':
        require(isinstance(report,list), 'Gitleaks 报告无效')
        require(code==(1 if report else 0), 'Gitleaks 退出码不符')
        for hit in report:
            require(hit.get('RuleID') and hit.get('File') and type(hit.get('StartLine')) is int and hit['StartLine']>0, 'Gitleaks 发现无位置')
            require(hit.get('Secret')=='REDACTED', 'Gitleaks 未脱敏')
        text='\n'.join(f"{v['File']}:{v['StartLine']} · {v['RuleID']} · {v['Description']}" for v in report)
        return summary('failed' if report else 'passed',1,len(report),text or '扫描快照未命中密钥规则')
    if kind == 'build':
        require(code==0 and set(report)=={'outputs'}, '构建未完成')
        require(set(report['outputs'])=={'server/dist/app.js','client/dist/index.html','context-bridge/dist/index.js'}, '构建产物缺失')
        require(all(re.fullmatch(r'[a-f0-9]{64}',v) for v in report['outputs'].values()), '构建产物摘要无效')
        return summary('passed',3,0,'服务端、Web、MCP bridge 构建完成；产物摘要已封存')
    if kind == 'restore':
        require(code==0 and report['before'] and report['before']==report['after'], '恢复前后数据不一致')
        require(report['tables']==len(report['before']) and report['dump_bytes']>0 and re.fullmatch(r'[a-f0-9]{64}',report['dump_sha256']), '恢复报告无效')
        require(all(re.fullmatch(r'\d+:[a-f0-9]{32}',v) for v in report['before'].values()), '恢复指纹无效')
        return summary('passed',report['tables'],0,f"{report['tables']} 张表恢复后，行数及逐行内容摘要一致")
    from .complete import parse
    return parse(c, report, code)


def validate_check(reader, result):
    c=next(c for c in reader.run['baseline']['criteria'] if c['id']==result['criterion_id'])
    item, envelope=reader.named(c['id']+'-receipt.json',result)
    require(envelope['criterion_id']==c['id'] and envelope['target_digest']==reader.run['target_digest'] and envelope['baseline_digest']==reader.run['baseline']['digest'], '报告与验收输入绑定不符')
    if envelope.get('blocked'):
        require(result['status']=='blocked' and envelope['reason'], '未覆盖记录无原因')
        if c['kind']=='gap': require(envelope['reason']==c['gap'], '缺口原因不符')
        # A blocked receipt proves only that this check did not run, never success.
        checked=summary('blocked',0,0,envelope['reason'])
    else:
        require(c['kind']!='gap', '未接入检查不得填入成功结果')
        command=reader.command(c['id'])
        require(command['target_digest']==reader.run['target_digest'] and command['baseline_digest']==reader.run['baseline']['digest'], '命令绑定不符')
        require(command['report_ref']==envelope['report_ref'] and not command['truncated'], '命令输出不完整')
        require(envelope['report_ref'] in result['evidence_refs'], '缺少原始报告引用')
        if reader.run['baseline'].get('recipe_report_version',1)>=2:
            argv=command['argv']
            if c['kind'] in ('junit','build'):
                _,built=reader.named('built-image.json')
                require(built['target_digest']==reader.run['target_digest'] and re.fullmatch(r'sha256:[a-f0-9]{64}',built['image']), '构建镜像绑定无效')
                require(command.get('runner_image')==built['image'] and built['image'] in argv, '执行了未绑定的镜像')
                if c['kind']=='junit':
                    require((argv[-2:]==['node','/recipe/root.mjs']) if c['id']=='ROOT-REGRESSION' else argv[-len(c['test_files']):]==c['test_files'], '测试命令范围不符')
            elif c['kind'] in ('python','gitleaks','npm-audit'):
                image=reader.run['baseline']['images'][{'python':'python','gitleaks':'gitleaks','npm-audit':'node'}[c['kind']]]
                require(image in argv,'工具镜像不符')
        if reader.run['baseline'].get('recipe_report_version',1)>=3:
            argv=command['argv']
            if c['kind'] in ('semgrep','zap','k6'):
                require(reader.run['baseline']['images'][c['kind']] in argv, '新增工具镜像未绑定')
            if c['kind']=='semgrep':
                require('/recipe/njsscan-rules.json' in argv and '--oss-only' in argv and '--error' in argv and '--json' in argv and argv[-1]=='/source', '静态扫描范围或规则不符')
            if c['kind']=='python':
                require(json.loads(argv[-1])==c['test_names'], 'Python 执行选择与冻结清单不符')
            if c['kind']=='python-sast':
                paths=[str(x) for x in argv if str(x).endswith('.py')]
                expected={x['path'] for x in reader.run['project_inputs'] if x['path'].endswith('.py')}
                require({p.split('/workspace/',1)[1] for p in paths if '/workspace/' in p}==expected, 'Python 静态扫描范围不符')
            if c['kind'] in ('zap','k6','joint-restore'):
                _,built=reader.named('built-image.json')
                start=reader.command('app-start')
                require(built['image'] in start['argv'] and start['exit_code']==0 and start['target_digest']==reader.run['target_digest'], '动态检查未绑定本次构建')
            if c['kind']=='joint-restore':
                probe=json.loads(reader.read(command['stdout_ref'])[1])
                report=json.loads(reader.read(envelope['report_ref'])[1])
                _,expected=reader.named('recovery-expected.json')
                require(probe==report['probe'] and probe['sha']==expected['sha'] and probe['files']==len(expected['files']), '业务恢复报告与实际读取不符')
        checked=parse_report(c,reader.read(envelope['report_ref'])[1],command['exit_code'])
        # Auxiliary build/restore commands must also have completed successfully.
        for label in envelope.get('support_commands',[]):
            cmd=reader.command(label)
            require(cmd['exit_code']==0 and not cmd['truncated'] and cmd['target_digest']==reader.run['target_digest'], '辅助命令执行失败')
        item=reader.read(envelope['report_ref'])[0]
    require(checked['status']==result['status'], '原始报告与结论不一致')
    return {'status':checked['status'], 'report':checked, 'primary_ref':item['id']}


class Runner:
    def __init__(self,store,run):
        self.store,self.run=store,run
        self.out=store.path(run['id'])/'execution'; self.workspace=self.out/'workspace'
        self.ns='acceptance-'+run['id']; self.net=self.ns+'-net'; self.db=self.ns+'-db'; self.app=self.ns+'-app'
        self.containers=set(); self.tags=[]; self.network=False; self.image=None; self.forward=None; self.materials=None; self.url=None
        self.dburl='postgresql://acceptance_test:synthetic@db:5432/acceptance_test'

    def command(self,label,argv,timeout=120,env=None,data=None):
        from .engine import now
        activity(self.store,self.run,label)
        started=now(); clock=monotonic(); buffers={'stdout':bytearray(),'stderr':bytearray()}; fault=None
        p=subprocess.Popen([str(x) for x in argv],stdin=subprocess.PIPE if data is not None else subprocess.DEVNULL,stdout=subprocess.PIPE,stderr=subprocess.PIPE,env=env,start_new_session=True)
        writer=None
        if data is not None:
            def write():
                try: p.stdin.write(data); p.stdin.close()
                except (OSError,BrokenPipeError): pass
            writer=threading.Thread(target=write,daemon=True);writer.start()
        try:
            with selectors.DefaultSelector() as sel:
                for k in buffers:sel.register(getattr(p,k),selectors.EVENT_READ,k)
                while sel.get_map():
                    if monotonic()-clock>timeout:raise TimeoutError('命令超时')
                    for key,_ in sel.select(.1):
                        chunk=os.read(key.fileobj.fileno(),65536)
                        if not chunk:sel.unregister(key.fileobj);continue
                        buffers[key.data].extend(chunk)
                p.wait(timeout=5)
        except (TimeoutError,ValueError,subprocess.TimeoutExpired) as exc:
            fault=str(exc)
        finally:
            if p.poll() is None:
                import signal
                os.killpg(p.pid,signal.SIGKILL);p.wait(timeout=5)
            p.stdout.close();p.stderr.close()
            if writer:writer.join(timeout=1)
        log=self.store.artifact(self.run,label+'.log',bytes(buffers['stderr'])+(fault or '').encode(),media_type='text/plain')
        raw=bytes(buffers['stdout'])
        stdout_ref=self.store.artifact(self.run,label+'-stdout.log',raw,media_type='text/plain')
        cmd={'name':label,'argv':list(map(str,argv)),'started_at':started,'finished_at':now(),'exit_code':p.returncode,'duration_ms':round((monotonic()-clock)*1000,2),'evidence_ref':log,'stdout_ref':stdout_ref,'truncated':bool(fault),'target_digest':self.run['target_digest'],'baseline_digest':self.run['baseline']['digest']}
        self.run['commands'].append(cmd);end_activity(self.store,self.run)
        if fault:raise RuntimeError(label+': '+fault)
        return raw,cmd

    def must(self,label,argv,timeout=120,data=None):
        raw,cmd=self.command(label,argv,timeout,data=data)
        require(cmd['exit_code']==0,label+' 执行失败；见命令日志')
        return raw

    def docker(self,label,image,args,network='none',environment=None,extra=None,timeout=300):
        name=self.ns+'-'+label.lower();self.containers.add(name)
        argv=['docker','run','--name',name,'--label','acceptance.run='+self.run['id'],'--network',network,'--read-only','--cap-drop','ALL','--security-opt','no-new-privileges','--pids-limit','128','--memory','3g','--cpus','2','--tmpfs','/tmp:rw,noexec,nosuid,size=4g']
        for k,v in (environment or {}).items():argv+=['--env',k+'='+v]
        argv+=(extra or [])+[image]+args
        return self.command(label,argv,timeout)

    def record(self,c,raw,cmd,support=None):
        ref=self.store.artifact(self.run,c['id']+('-junit.xml' if c['kind']=='junit' else '-raw.json'),raw,c['id'],'application/xml' if c['kind']=='junit' else 'application/json')
        cmd['report_ref']=ref
        self.store.save(self.run)
        require(bool(raw.strip()), c['id']+f" 未生成报告（退出码 {cmd['exit_code']}）；见执行日志")
        checked=parse_report(c,raw,cmd['exit_code'])
        receipt={'criterion_id':c['id'],'target_digest':self.run['target_digest'],'baseline_digest':self.run['baseline']['digest'],'report_ref':ref,'support_commands':support or []}
        receipt_ref=self.store.artifact(self.run,c['id']+'-receipt.json',packed(receipt),c['id'],'application/json')
        self.result(c,checked['status'],checked['actual'],[ref,receipt_ref,cmd['evidence_ref']],cmd['duration_ms'])

    def result(self,c,status,actual,refs,duration=None):
        self.run['results'].append({'criterion_id':c['id'],'case_id':c['case_id'],'layer':c['layer'],'attempt':1,'status':status,'duration_ms':duration,'expected':c['expected'],'actual':actual,'evidence_refs':refs})
        self.store.save(self.run)

    def blocked(self,c,reason):
        raw={'criterion_id':c['id'],'target_digest':self.run['target_digest'],'baseline_digest':self.run['baseline']['digest'],'blocked':True,'reason':reason}
        ref=self.store.artifact(self.run,c['id']+'-receipt.json',packed(raw),c['id'],'application/json')
        self.result(c,'blocked',reason,[ref])

    def setup(self):
        from .projects import integrity
        from .validation import Reader
        require(integrity(self.store,self.run,Reader(self.store,self.run)),'冻结输入不完整')
        require({k:sha(v) for k,v in recipe_files().items()}==self.run['baseline']['recipe_digests'],'编排实现变化；请重新创建执行')
        self.workspace.mkdir(parents=True)
        for row in self.run['project_inputs']:
            file=self.workspace/row['path'];file.parent.mkdir(parents=True,exist_ok=True);file.write_bytes(self.store.artifact_bytes(self.run,row['ref'])[1])
        for key,value in self.run['baseline']['images'].items():
            self.must('image-'+key,['docker','image','inspect',value,'--format','{{.Id}}'])
        for name in ('package.json','package-lock.json','server/package.json','client/package.json','context-bridge/package.json'):
            raw=self.must('cache-'+name.replace('/','-'),['docker','run','--rm','--network','none','--entrypoint','cat',CACHE,'/workspace/'+name])
            require(raw==(self.workspace/name).read_bytes(),'依赖缓存与锁文件不一致；需要重新准备依赖镜像')
        self.run['source_artifact']=self.store.artifact(self.run,'source-context.json',packed(self.run['source_context']),media_type='application/json')

    def build(self,c):
        # A fresh final stage copies only dependencies; never retain old source files.
        # Dockerfile FROM does not accept bare local image IDs. Use private per-run
        # tags, then verify the IDs; --pull=false keeps these exact local images.
        deps_tag='acceptance-input:'+self.run['id']+'-deps'
        node_tag='acceptance-input:'+self.run['id']+'-node'
        for label,image,tag in [('deps',CACHE,deps_tag),('node',NODE_IMAGE,node_tag)]:
            self.must('tag-'+label,['docker','tag',image,tag]);self.tags.append(tag)
            resolved=self.must('tag-check-'+label,['docker','image','inspect',tag,'--format','{{.Id}}']).decode().strip()
            require(resolved==image,'本地构建依赖镜像不符')
        dockerfile=f'''FROM {deps_tag} AS deps
FROM {node_tag}
WORKDIR /workspace
COPY --from=deps /workspace/node_modules ./node_modules
COPY --from=deps /workspace/server/node_modules ./server/node_modules
COPY . .
ENV NODE_NO_WARNINGS=1 HOME=/tmp
RUN --network=none npm run build
USER node
'''
        (self.workspace/'Dockerfile.acceptance').write_text(dockerfile)
        iid=self.out/'image.id'
        self.must('compile',['docker','build','--network','none','--pull=false','--iidfile',str(iid),'-f',str(self.workspace/'Dockerfile.acceptance'),str(self.workspace)],timeout=240)
        self.image=iid.read_text().strip();require(re.fullmatch(r'sha256:[a-f0-9]{64}',self.image),'未取得固定构建镜像')
        self.store.artifact(self.run,'built-image.json',packed({'image':self.image,'target_digest':self.run['target_digest']}),media_type='application/json')
        js="const fs=require('fs'),crypto=require('crypto');const paths=['server/dist/app.js','client/dist/index.html','context-bridge/dist/index.js'];console.log(JSON.stringify({outputs:Object.fromEntries(paths.map(p=>[p,crypto.createHash('sha256').update(fs.readFileSync(p)).digest('hex')]))}));"
        raw,cmd=self.docker(c['id'],self.image,['node','-e',js]);cmd['runner_image']=self.image
        self.record(c,raw,cmd,['compile'])

    def database(self):
        allids=self.must('network-list',['docker','network','ls','-q']).decode().split()
        networks=json.loads(self.must('network-inspect',['docker','network','inspect',*allids])) if allids else []
        used=[ipaddress.ip_network(x['Subnet'],strict=False) for n in networks for x in (n.get('IPAM',{}).get('Config') or []) if x.get('Subnet')]
        selected=next((f'10.254.{i}.0/28' for i in range(239,255) if not any(ipaddress.ip_network(f'10.254.{i}.0/28').overlaps(x) for x in used if x.version==4)),None)
        require(selected,'没有可用的隔离测试子网')
        self.must('network-create',['docker','network','create','--internal','--label','acceptance.run='+self.run['id'],'--subnet',selected,self.net]);self.network=True
        self.containers.add(self.db)
        self.must('database-start',['docker','run','-d','--name',self.db,'--label','acceptance.run='+self.run['id'],'--network',self.net,'--network-alias','db','--memory','512m','--cpus','1','--tmpfs','/var/lib/postgresql/data:rw,size=512m','--env','POSTGRES_USER=acceptance_test','--env','POSTGRES_PASSWORD=synthetic','--env','POSTGRES_DB=acceptance_test',PG])
        for i in range(30):
            _,cmd=self.command('database-ready-'+str(i),['docker','exec',self.db,'pg_isready','-U','acceptance_test'],10)
            if cmd['exit_code']==0:return
            sleep(.2)
        raise RuntimeError('临时数据库未就绪')

    def node(self,c):
        require(self.image,'构建失败，测试运行镜像不可用')
        env={'TEST_DATABASE_URL':self.dburl,'TEST_BIG_MATERIAL_UPLOAD':'1','REVIEW_DATABASE_URL':'postgresql://acceptance_test:synthetic@127.0.0.1:5548/acceptance_test'}
        args=['node','--import','tsx','--test','--test-concurrency=1','--test-reporter=junit',*c['test_files']]
        extra=[]
        if c['id']=='ROOT-REGRESSION':
            args=['node','/recipe/root.mjs'];extra=['--mount',f'type=bind,src={HERE},dst=/recipe,readonly']
        raw,cmd=self.docker(c['id'],self.image,args,self.net if c['layer']=='L2' else 'none',env,extra)
        cmd['runner_image']=self.image;self.record(c,raw,cmd)

    def python(self,c):
        raw,cmd=self.docker(c['id'],PYTHON,['python','/recipe/python_runner.py',json.dumps(c['test_names'])],extra=['--user','65534:65534','--mount',f'type=bind,src={self.workspace},dst=/workspace,readonly','--mount',f'type=bind,src={HERE},dst=/recipe,readonly'])
        self.record(c,raw,cmd)

    def security(self,c):
        if c['kind']=='npm-audit':
            # Only manifests enter the internet-enabled audit container, never app source or credentials.
            target=self.out/'audit-input';target.mkdir()
            for name in ['package.json','package-lock.json','server/package.json','client/package.json','context-bridge/package.json']:
                p=target/name;p.parent.mkdir(parents=True,exist_ok=True);p.write_bytes((self.workspace/name).read_bytes())
            raw,cmd=self.docker(c['id'],NODE_IMAGE,['npm','audit','--json','--ignore-scripts','--registry=https://registry.npmjs.org'],network='bridge',extra=['--user','65534:65534','--workdir','/input','--env','HOME=/tmp','--mount',f'type=bind,src={target},dst=/input,readonly'],timeout=90)
        else:
            report=self.out/'gitleaks';report.mkdir()
            # Scan only the frozen manifest; exclude the generated build recipe.
            target=self.out/'scan-input';target.mkdir()
            for row in self.run['project_inputs']:
                p=target/row['path'];p.parent.mkdir(parents=True,exist_ok=True);p.write_bytes((self.workspace/row['path']).read_bytes())
            _,cmd=self.docker(c['id'],GITLEAKS,['dir','/source','--redact=100','--no-banner','--report-format=json','--report-path=/report/findings.json'],extra=['--mount',f'type=bind,src={target},dst=/source,readonly','--mount',f'type=bind,src={report},dst=/report'])
            path=report/'findings.json';raw=path.read_bytes()
        self.record(c,raw,cmd)

    def browser_environment(self):
        env={k:os.environ[k] for k in ('HOME','PATH','TMPDIR') if k in os.environ}
        env.update(ACCEPTANCE_URL=self.url,ACCEPTANCE_RUN=self.run['id'],ACCEPTANCE_DB=self.db,ACCEPTANCE_REPORT=str(self.out/'L3'),ACCEPTANCE_COMPLETE='1' if 'exclusions' in self.run['baseline'] else '0')
        return env

    def start_application(self,database='acceptance_test',materials=None,seed=True):
        self.containers.add(self.app)
        label='app-start' if database=='acceptance_test' else 'replacement-start'
        argv=['docker','run','-d','--name',self.app,'--label','acceptance.run='+self.run['id'],'--network',self.net,'--read-only','--cap-drop','ALL','--security-opt','no-new-privileges','--memory','512m','--cpus','1','--tmpfs','/tmp:rw,noexec,nosuid,size=128m']
        env={'DATABASE_URL':self.dburl.rsplit('/',1)[0]+'/'+database,'DB_SCHEMA':'acceptance_ui','PORT':'5380','APP_ORIGIN':self.url,'PUBLIC_BASE_URL':self.url,'STORAGE_DIR':'/materials' if materials else '/tmp/materials','MAIL_TEST_SINK':'1','SEED_DEMO':'1' if seed else '0','ADMIN_EMAIL':'admin@acceptance.test','ADMIN_PASSWORD':'Acceptance-Synthetic-Only-2026','SESSION_SECRET':'Synthetic-Session-Secret-For-Local-Acceptance-Only'}
        for k,v in env.items():argv+=['--env',k+'='+v]
        args=['node','runtime.mjs']
        if 'exclusions' in self.run['baseline']:
            argv+=['--mount',f'type=bind,src={HERE},dst=/recipe,readonly']
            args=['node','--import','/recipe/provider-fixture.mjs','runtime.mjs']
        if materials:argv+=['--mount',f'type=bind,src={materials},dst=/materials']
        self.must(label,argv+[self.image]+args)

    def wait_application(self):
        for i in range(30):
            try:
                with urllib.request.urlopen(self.url+'/api/health',timeout=4) as response:
                    if response.status==200:return
            except (OSError,TimeoutError):sleep(.2)
        self.command('app-startup-diagnostics-'+self.app.rsplit('-',1)[-1],['docker','logs','--tail','80',self.app],15)
        raise RuntimeError('测试应用未就绪；见应用启动日志')

    def browser(self):
        from .engine import NODE, ROOT
        require(self.image,'构建失败，无法启动页面验证')
        self.forward=ForwardServer(self.app)
        threading.Thread(target=self.forward.serve_forever,daemon=True).start()
        self.url=f'http://127.0.0.1:{self.forward.server_address[1]}'
        if 'exclusions' in self.run['baseline']:
            self.materials=self.out/'materials';self.materials.mkdir(mode=0o777);self.materials.chmod(0o777)
        self.start_application(materials=self.materials)
        self.wait_application()
        out=self.out/'L3';out.mkdir()
        raw,cmd=self.command('playwright-L3',[str(NODE),str(ROOT/'validation/node_modules/@playwright/test/cli.js'),'test','--config',str(HERE/'playwright.config.mjs')],360,env=self.browser_environment())
        report=out/'results.json'
        self.store.parse_playwright(self.run,json.loads(report.read_bytes()),out)
        self.store.save(self.run)

    def restore(self,c):
        require(self.app in self.containers,'页面样本应用尚未创建')
        self.must('app-stop',['docker','stop','-t','15',self.app],timeout=25)
        labels=[]
        def sql(db,query):
            label='restore-sql-'+str(len(labels));labels.append(label)
            return self.must(label,['docker','exec',self.db,'psql','-U','acceptance_test','-d',db,'-At','-v','ON_ERROR_STOP=1','-c',query]).decode().strip()
        def fingerprints(db):
            names=sql(db,"SELECT tablename FROM pg_tables WHERE schemaname='acceptance_ui' ORDER BY tablename").splitlines()
            require(names,'数据库尚未准备验收样本')
            result={}
            for table in names:
                require(re.fullmatch('[a-z_]+',table),'非法表名')
                result[table]=sql(db,f'''SELECT count(*) || ':' || md5(coalesce(string_agg(row_to_json(t)::text, E'\\n' ORDER BY row_to_json(t)::text),'')) FROM acceptance_ui."{table}" t''')
            return result
        before=fingerprints('acceptance_test')
        dump=self.must('restore-dump',['docker','exec',self.db,'pg_dump','-U','acceptance_test','--format=custom','--no-owner','--no-acl','--schema=acceptance_ui','acceptance_test'])
        self.must('restore-create',['docker','exec',self.db,'createdb','-U','acceptance_test','acceptance_restore'])
        _,cmd=self.command(c['id'],['docker','exec','-i',self.db,'pg_restore','-U','acceptance_test','--dbname=acceptance_restore','--exit-on-error','--no-owner','--no-acl'],data=dump)
        after=fingerprints('acceptance_restore')
        raw=packed({'before':before,'after':after,'tables':len(before),'dump_bytes':len(dump),'dump_sha256':sha(dump)})
        self.record(c,raw,cmd,labels+['restore-dump','restore-create','app-stop'])

    def cleanup(self):
        errors=[]
        if self.forward:self.forward.shutdown();self.forward.close_all()
        for name in sorted(self.containers):
            try:self.must('cleanup-'+name,['docker','rm','-f',name],timeout=20)
            except Exception as exc:errors.append(str(exc))
        if self.network:
            try:self.must('cleanup-network',['docker','network','rm',self.net],timeout=20)
            except Exception as exc:errors.append(str(exc))
        for tag in self.tags:
            try:self.must('cleanup-tag-'+tag.rsplit('-',1)[-1],['docker','image','rm',tag],timeout=20)
            except Exception as exc:errors.append(str(exc))
        require(not errors,'；'.join(errors))


class ForwardServer(socketserver.ThreadingTCPServer):
    """Loopback-only, bounded connections into a Docker internal network."""
    allow_reuse_address=True;daemon_threads=True
    def __init__(self,app):
        self.app=app;self.processes=set();self.lock=threading.Lock();self.slots=threading.BoundedSemaphore(32)
        super().__init__(('127.0.0.1',0),ForwardHandler)
    def close_all(self):
        self.server_close()
        with self.lock:
            for p in self.processes:
                if p.poll() is None:p.kill()

class ForwardHandler(socketserver.BaseRequestHandler):
    def handle(self):
        if not self.server.slots.acquire(blocking=False):return
        p=None
        try:
            js="const s=require('net').connect(5380,'127.0.0.1');s.setTimeout(20000,()=>process.exit(1));s.on('error',()=>process.exit(1));process.stdin.pipe(s);s.pipe(process.stdout);s.on('end',()=>process.exit(0));"
            p=subprocess.Popen(['docker','exec','-i',self.server.app,'node','-e',js],stdin=subprocess.PIPE,stdout=subprocess.PIPE,stderr=subprocess.DEVNULL)
            with self.server.lock:self.server.processes.add(p)
            self.request.settimeout(25)
            def upload():
                try:
                    while chunk:=self.request.recv(65536):p.stdin.write(chunk);p.stdin.flush()
                except (OSError,BrokenPipeError):pass
                finally:
                    try:p.stdin.close()
                    except OSError:pass
            threading.Thread(target=upload,daemon=True).start()
            while chunk:=p.stdout.read1(65536):self.request.sendall(chunk)
        except OSError:pass
        finally:
            if p:
                if p.poll() is None:p.kill()
                p.wait(timeout=5);p.stdout.close()
                with self.server.lock:self.server.processes.discard(p)
            self.server.slots.release()


def execute(store,run):
    from .engine import now
    runner=Runner(store,run)
    try:
        run['status']='running';store.save(run)
        with store.stage(run,'baseline','核对完整源文件、依赖锁与编排版本'):runner.setup()
        with store.stage(run,'cases','校验标准与已登记用例的对应关系') as stage:
            register_cases(store,run)
            stage['detail']=f"{len(run['baseline']['criteria'])} 项必验检查" + (f"；{len(run['baseline']['exclusions'])} 类环境范围不参与判定" if 'exclusions' in run['baseline'] else '；未覆盖项保留在门禁内')
        database_error=None
        for layer in ('L1','L2','L3','L4'):
            with store.stage(run,layer,{'L1':'构建、客户端与桥接回归、依赖和密钥扫描','L2':'临时 PostgreSQL、接口权限、上传与迁移回归','L3':'真实浏览器登录、持久化、退出与可访问名称','L4':'并发负载、数据库与文件备份恢复、替代实例读取'}[layer]) as stage:
                run['active_layer']=layer
                if layer=='L2':
                    try:runner.database()
                    except Exception as exc:database_error=str(exc)
                browser_done=False
                for c in [x for x in run['baseline']['criteria'] if x['layer']==layer]:
                    if any(r['criterion_id']==c['id'] for r in run['results']):continue
                    batch=[x for x in run['baseline']['criteria'] if x['kind']=='playwright' and x['layer']==layer and not any(r['criterion_id']==x['id'] for r in run['results'])] if c['kind']=='playwright' else [c]
                    with checks(store,run,batch):
                        try:
                            if c['kind']=='gap':runner.blocked(c,c['gap'])
                            elif database_error and layer in ('L2','L3','L4'):runner.blocked(c,database_error)
                            elif c['kind']=='build':runner.build(c)
                            elif c['kind']=='junit':runner.node(c)
                            elif c['kind']=='python':runner.python(c)
                            elif c['kind'] in ('gitleaks','npm-audit'):runner.security(c)
                            elif c['kind']=='restore':runner.restore(c)
                            elif c['kind'] in ('semgrep','python-sast','zap','k6','joint-restore'):
                                from .complete import run as execute_check
                                execute_check(runner,c)
                            elif c['kind']=='playwright' and not browser_done:
                                browser_done=True;runner.browser()
                        except Exception as exc:
                            if not any(r['criterion_id']==c['id'] for r in run['results']):runner.blocked(c,str(exc)[:600])
                current=[x for x in run['results'] if x['layer']==layer]
                for c in [x for x in run['baseline']['criteria'] if x['layer']==layer and not any(r['criterion_id']==x['id'] for r in current)]:runner.blocked(c,'前置浏览器执行未产生结果')
                current=[x for x in run['results'] if x['layer']==layer]
                stage.update(status='failed' if any(x['status']=='failed' for x in current) else 'blocked' if any(x['status']=='blocked' for x in current) else 'passed', detail=' · '.join(f'{sum(x["status"]==status for x in current)} {name}' for status,name in [('passed','通过'),('failed','失败'),('blocked','未完成')]))
        with store.stage(run,'cleanup','回收本次容器和临时网络'):runner.cleanup()
        runner=None
        run['active_layer']=None
        with store.stage(run,'findings','核实原始报告并保留断言与位置') as stage:
            store.collect_findings(run);stage['detail']=f"{len(run['findings'])} 项失败检查"
        with store.stage(run,'gate','检查必验项、执行结果及证据') as stage:
            run['status']='completed'
            try:run['decision']=store.evaluate(run)
            finally:run['status']='running'
            blocked=[r for r in run['results'] if r['status']=='blocked']
            run['reasons']=[f"{len(blocked)} 项必验检查未完成；{len(run['findings'])} 项检查失败；完整项目不能放行" if blocked else '全部已登记检查完成；详见逐项结果']
            stage.update(status='passed' if run['decision']=='allow' else 'blocked' if blocked else 'failed',detail=run['reasons'][0])
            if run.get('workflow'):
                from .workflow import coverage
                completion=coverage(store,run)
                if not completion['complete']:
                    stage.update(status='blocked',detail='完整验收未完成：'+'、'.join(completion['missing']+completion['errors']))
        run['status']='completed'
        if run.get('workflow'):
            from .workflow import coverage
            completion=coverage(store,run)
            run['workflow']['completion']='complete' if completion['complete'] else 'incomplete'
            if not completion['complete']:
                run.update(status='incomplete',decision='inconclusive',reasons=['完整验收未完成：'+'、'.join(completion['missing']+completion['errors']),*run['reasons']])
    except Exception as exc:
        run.update(status='error',decision='inconclusive',reasons=[str(exc)[:600]])
    finally:
        if runner:
            try:runner.cleanup()
            except Exception as exc:run.update(status='error',decision='inconclusive',reasons=[*run['reasons'],str(exc)[:600]])
        run['active_layer']=None;run['finished_at']=now();store.collect_findings(run);run['integrity']=store.check_integrity(run);store.save(run)


def recover_runtime(store, run):
    """Reclaim only resources with this interrupted run's exact ownership label."""
    runner=Runner(store,run)
    require(re.fullmatch(r"run-[a-f0-9]{12}",run['id']), '无效执行身份')
    ownership='acceptance.run='+run['id']
    ids=runner.must('recover-containers',['docker','ps','-aq','--filter','label='+ownership]).decode().split()
    for index,cid in enumerate(ids):
        require(re.fullmatch(r'[a-f0-9]{12,64}',cid),'容器身份无效')
        runner.must('recover-container-'+str(index),['docker','rm','-f',cid],timeout=20)
    ids=runner.must('recover-networks',['docker','network','ls','-q','--filter','label='+ownership]).decode().split()
    for index,nid in enumerate(ids):
        require(re.fullmatch(r'[a-f0-9]{12,64}',nid),'网络身份无效')
        runner.must('recover-network-'+str(index),['docker','network','rm',nid],timeout=20)
    for suffix,image in [('deps',CACHE),('node',NODE_IMAGE)]:
        tag='acceptance-input:'+run['id']+'-'+suffix
        raw,cmd=runner.command('recover-tag-inspect-'+suffix,['docker','image','inspect',tag,'--format','{{.Id}}'])
        if cmd['exit_code']==0:
            require(raw.decode().strip()==image,'构建标签已指向其他镜像，保留原状')
            runner.must('recover-tag-'+suffix,['docker','image','rm',tag],timeout=20)
