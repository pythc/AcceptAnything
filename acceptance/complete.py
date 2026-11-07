"""Concrete local checks, preserving native tool reports and explicit scope."""
import json
import math
from pathlib import Path
import re
import shutil
from time import monotonic
import urllib.request
from .projects import packed, sha
from .validation import require

IMAGES = {
    'semgrep': 'sha256:529ee8a277ec8adc5b534d7c74eea0a47e9de21d62852b6ba7ac6ba9566845c3',
    'zap': 'sha256:5ccfff9a411743ab2615136a2edd7416bec9ce41572fa94e935df38c14adb2b6',
    'k6': 'sha256:e66db15b860113878fa74670e31f5e274830b7b6e42c8bff28b2f2d86a257603',
}


def parse(c, report, code):
    from .expanded import summary
    kind = c['kind']
    if kind == 'semgrep':
        require(code in (0, 1) and report.get('version') and report.get('errors') == [], 'Semgrep 未完整完成')
        paths=report['paths']['scanned']; hits=report['results']
        require(paths and len(paths)==len(set(paths)), 'Semgrep 无实际扫描文件')
        require(code == (1 if hits else 0), 'Semgrep 退出码不符')
        require(all(x.get('check_id') and x.get('path') in paths and x['start']['line']>0 and x['extra']['message'] for x in hits), 'Semgrep 缺少规则或源码位置')
        return summary('failed' if hits else 'passed', len(paths), len(hits), f'{len(paths)} 个源文件，{len(hits)} 处待复核规则命中\n'+'\n'.join(f"{x['path']}:{x['start']['line']} · {x['check_id']} · {x['extra']['message']}" for x in hits))
    if kind == 'python-sast':
        require(code in (0, 1) and report.get('errors')==[] and report['metrics']['_totals']['loc']>0, 'Bandit 未完整扫描')
        hits=report['results']; require(code==(1 if hits else 0), 'Bandit 退出码不符')
        return summary('failed' if hits else 'passed',report['metrics']['_totals']['loc'],len(hits),f"Python 静态扫描 {report['metrics']['_totals']['loc']} 行，{len(hits)} 处待复核命中\n"+'\n'.join(f"{x['filename']}:{x['line_number']} · {x['test_id']} · {x['issue_text']}" for x in hits))
    if kind == 'zap':
        require(code==0 and report['tool']=='OWASP ZAP' and report['version'] and report['target']=='http://127.0.0.1:5380', 'ZAP 目标或执行结果不符')
        require(report['spider_status']=='100' and report['active_status']=='100' and report['pending_passive']==0, 'ZAP 扫描未完成')
        plan=json.loads((Path(__file__).parent/'recipes/assessment/zap-plan.json').read_text())
        selected=report.get('selected_rules',[])
        require(sorted(selected)==sorted(plan['enabled_ids']) and report.get('excluded_rules')==plan['excluded'], 'ZAP 规则范围不符')
        progress=report.get('active_progress',[])
        require(len(progress)==2 and progress[0]==report['target'], 'ZAP 缺少规则执行记录')
        rules=[x['Plugin'] for x in progress[1]['HostProcess']]
        require(sorted(x[1] for x in rules)==sorted(selected) and all(x[3]=='Complete' for x in rules), 'ZAP 有规则跳过、超时或未完成')
        require(report['messages']>0 and all(report['target']+p in report['urls'] for p in ['/login','/register','/api/health','/api/batches','/api/auth/me','/api/admin/overview']), 'ZAP 覆盖不完整')
        sites=report['native_report']['site']; require(len(sites)==1 and sites[0]['@name']==report['target'], 'ZAP 原生报告范围不符')
        hits=sites[0]['alerts']; require(all(str(x['riskcode']) in ('0','1','2','3') and x.get('instances') and x.get('pluginid') for x in hits), 'ZAP 发现无证据')
        failed=[x for x in hits if int(x['riskcode'])>0]
        return summary('failed' if failed else 'passed',report['messages'],len(failed),f"{len(selected)} 条主动规则完成，{len(report['urls'])} 个地址、{report['messages']} 次 HTTP 请求，{len(failed)} 类安全告警\n"+'\n'.join(f"{x['pluginid']} · {x['riskdesc']} · {x['name']}\n"+'\n'.join(i['uri'] for i in x['instances']) for x in hits))
    if kind == 'k6':
        m=report['metrics']; checks=m['checks']['values']; iterations=m['iterations']['values']['count']; duration=report['state']['testRunDurationMs']
        require(code in (0, 99) and iterations>=20 and duration>=20000 and m['http_reqs']['values']['count']>=40, 'k6 未完成计划负载')
        require(math.isfinite(m['http_req_duration']['values']['p(95)']), 'k6 延迟缺失')
        require(set(m['checks']['thresholds'])=={'rate==1'} and set(m['http_req_failed']['thresholds'])=={'rate==0'} and set(m['iterations']['thresholds'])=={'count>=20'}, 'k6 阈值不符')
        predicates={'checks': checks['fails']==0, 'http_req_failed': m['http_req_failed']['values']['rate']==0, 'iterations':iterations>=20}
        ok=all(predicates.values())
        require(code==(0 if ok else 99) and all(t['ok']==predicates[k] for k in predicates for t in m[k]['thresholds'].values()), 'k6 结论不符')
        require(m['vus_max']['values']['max']==5, 'k6 并发计划不符')
        return summary('passed' if ok else 'failed',int(iterations),int(checks['fails']),f"5 并发 / 20 秒：{int(iterations)} 轮，{m['http_reqs']['values']['count']} 次请求，错误率 {m['http_req_failed']['values']['rate']:.2%}，P95 {m['http_req_duration']['values']['p(95)']:.1f} ms；仅本地性能基线")
    if kind == 'joint-restore':
        require(code==0 and report['before_db'] and report['before_db']==report['after_db'], '恢复数据库内容不一致')
        require(report['before_files'] and report['before_files']==report['after_files'], '恢复文件内容不一致')
        require(all(re.fullmatch(r'[a-f0-9]{64}',v) for v in report['before_files'].values()), '恢复文件摘要无效')
        require(report['dump_bytes']>0 and re.fullmatch(r'[a-f0-9]{64}',report['dump_sha256']), '恢复备份缺失')
        require(report['original_stopped'] is True and report['replacement_running'] is True and report['probe']['state']=='FINALIZED' and report['probe']['files']>0 and report['probe']['files']==report['probe']['verified_files'], '替代实例未通过业务读取验证')
        require(math.isfinite(report['recovery_seconds']) and report['recovery_seconds']>0, '恢复计时缺失')
        return summary('passed',len(report['before_db'])+len(report['before_files']),0,f"{len(report['before_db'])} 张表、{len(report['before_files'])} 个文件一致；替代实例可读取交卷状态和原始材料；本地恢复 {report['recovery_seconds']:.2f} 秒")
    raise ValueError('未知本地检查')


def run(r,c):
    from .expanded import HERE
    from .engine import ROOT
    mounts=['--mount',f'type=bind,src={HERE},dst=/recipe,readonly']
    kind=c['kind']
    if kind=='semgrep':
        raw,cmd=r.docker(c['id'],IMAGES['semgrep'],['semgrep','scan','--oss-only','--config','/recipe/njsscan-rules.json','--metrics','off','--disable-version-check','--no-git-ignore','--error','--json','--jobs','2','--timeout','15','/source'],extra=mounts+['--env','HOME=/tmp','--mount',f'type=bind,src={r.workspace},dst=/source,readonly'],timeout=180)
    elif kind=='python-sast':
        files=[str(r.workspace/f['path']) for f in r.run['project_inputs'] if f['path'].endswith('.py')]
        raw,cmd=r.command(c['id'],[str(ROOT/'validation/.venv/bin/bandit'),'-q','-f','json',*files],60)
    elif kind=='zap':
        require(r.app in r.containers, '应用未启动')
        name=r.ns+'-zap';r.containers.add(name)
        argv=['docker','run','--name',name,'--label','acceptance.run='+r.run['id'],'--network','container:'+r.app,'--cap-drop','ALL','--security-opt','no-new-privileges','--memory','2g','--cpus','2','--env','JAVA_OPTS=-Xmx1024m',*mounts,IMAGES['zap'],'python3','/recipe/zap_scan.py']
        raw,cmd=r.command(c['id'],argv,390)
    elif kind=='k6':
        report=r.out/'k6';report.mkdir()
        _,cmd=r.docker(c['id'],IMAGES['k6'],['run','--quiet','--no-color','/recipe/load.js'],network='container:'+r.app,extra=mounts+['--user','0:0','--mount',f'type=bind,src={report},dst=/report'],timeout=45)
        raw=(report/'summary.json').read_bytes()
    elif kind=='joint-restore':return joint_restore(r,c)
    else:raise ValueError('未知检查执行器')
    r.record(c,raw,cmd)


def joint_restore(r,c):
    """Quiesce original, backup with pg_dump + copytree, then replace from backups."""
    from .expanded import PG
    from .engine import NODE, ROOT
    labels=[]
    def sql(db,query):
        label='joint-sql-'+str(len(labels));labels.append(label)
        return r.must(label,['docker','exec',r.db,'psql','-U','acceptance_test','-d',db,'-At','-v','ON_ERROR_STOP=1','-c',query]).decode().strip()
    def fingerprints(db):
        names=sql(db,"SELECT tablename FROM pg_tables WHERE schemaname='acceptance_ui' ORDER BY tablename").splitlines()
        require(names,'没有待恢复的数据库')
        result={}
        for table in names:
            require(re.fullmatch('[a-z_]+',table),'非法表名')
            result[table]=sql(db,f'''SELECT count(*) || ':' || md5(coalesce(string_agg(row_to_json(t)::text, E'\\n' ORDER BY row_to_json(t)::text),'')) FROM acceptance_ui."{table}" t''')
        return result
    def files(root):
        result={}
        for p in sorted(root.rglob('*')):
            require(not p.is_symlink(),'文件快照不接受符号链接')
            if p.is_file():result[str(p.relative_to(root))]=sha(p.read_bytes())
        return result
    require(r.materials is not None and r.materials.exists(),'没有上传文件目录')
    expected=json.loads((r.out/'L3/recovery-expected.json').read_text())
    r.store.artifact(r.run,'recovery-expected.json',packed(expected),c['id'],'application/json')
    r.must('joint-stop',['docker','stop','-t','15',r.app],timeout=25)
    started=monotonic()
    before=fingerprints('acceptance_test');before_files=files(r.materials)
    require(any(k.endswith('.bin') for k in before_files) or len(before_files)>1,'没有候选人材料样本')
    backup=r.out/'backup-files';shutil.copytree(r.materials,backup)
    dump=r.must('joint-dump',['docker','exec',r.db,'pg_dump','-U','acceptance_test','--format=custom','--no-owner','--no-acl','--schema=acceptance_ui','acceptance_test'])
    r.must('joint-create',['docker','exec',r.db,'createdb','-U','acceptance_test','acceptance_recovery'])
    r.must('joint-import',['docker','exec','-i',r.db,'pg_restore','-U','acceptance_test','--dbname=acceptance_recovery','--exit-on-error','--no-owner','--no-acl'],data=dump)
    after=fingerprints('acceptance_recovery')
    restored=r.out/'restored-files';shutil.copytree(backup,restored);restored.chmod(0o777)
    after_files=files(restored)
    old=r.app;r.app=r.ns+'-replacement'
    r.start_application(database='acceptance_recovery',materials=restored,seed=False)
    r.forward.app=r.app
    r.wait_application()
    env={**r.browser_environment(), 'ACCEPTANCE_EXPECTED':str(r.out/'L3/recovery-expected.json')}
    raw,cmd=r.command(c['id'],[str(NODE),str(ROOT/'acceptance/recipes/assessment/recovery-probe.mjs')],60,env=env)
    probe=json.loads(raw)
    original=r.must('joint-original-stopped',['docker','inspect',old,'--format','{{.State.Running}}']).decode().strip()=='false'
    replacement=r.must('joint-replacement-running',['docker','inspect',r.app,'--format','{{.State.Running}}']).decode().strip()=='true'
    r.record(c,packed({'before_db':before,'after_db':after,'before_files':before_files,'after_files':after_files,'dump_bytes':len(dump),'dump_sha256':sha(dump),'original_stopped':original,'replacement_running':replacement,'probe':probe,'recovery_seconds':round(monotonic()-started,3)}),cmd,labels+['joint-stop','joint-dump','joint-create','joint-import','joint-original-stopped','joint-replacement-running'])
