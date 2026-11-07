"""Local repository onboarding using the existing pinned scanner adapters."""
import json
import os
from pathlib import Path
import re
import subprocess
import uuid
from .runner import collect, encode, sha
from .registry import locks, TOOLS
from .models import Profile
from .formats import require

OMIT_DIRS = {'.git', '.hg', '.svn', 'node_modules', '.venv', 'venv', '__pycache__',
             'dist', 'build', 'coverage', '.next', '.nuxt', '.cache', 'vendor',
             'target', 'var', '.idea', '.vscode'}
PRIVATE = {'.ssh', '.aws', '.gnupg', '.codex', '.netrc', '.npmrc', '.pypirc', '.git-credentials'}
SCANNER_CONFIG = {'.gitleaks.toml','.gitleaksignore','.semgrepignore','.bandit',
                  '.trivyignore','.trivyignore.yaml','trivy.yaml','.syft.yaml','.syft.yml',
                  'syft.yaml','syft.yml','.hadolint.yaml','.hadolint.yml','.shellcheckrc'}
LABELS = {'gitleaks':'密钥扫描', 'bandit':'Python 安全', 'semgrep-njsscan':'JS / TS 安全',
          'syft-cyclonedx':'软件物料清单', 'trivy-fs':'依赖漏洞', 'trivy-config':'基础设施配置',
          'hadolint':'Dockerfile 检查', 'shellcheck':'Shell 检查', 'pytest':'Python 测试', 'node-test':'Node.js 测试'}


def tracked_files(root):
    # Read Git's index only, never a project script or hook. Preserve committed
    # resources required by tests/builds without sweeping host private files in.
    env={k:v for k,v in os.environ.items() if not k.startswith('GIT_')}
    try:
        result=subprocess.run(['git','-c','core.fsmonitor=false','-c','core.hooksPath=/dev/null','-C',str(root),'ls-files','--cached','-z','--','.'],env=env,capture_output=True,timeout=60)
    except (OSError,subprocess.TimeoutExpired):return set()
    if result.returncode:return set()
    return {os.fsdecode(p) for p in result.stdout.split(b'\0') if p}


def inventory(repository):
    given = Path(repository).expanduser()
    require(given.is_absolute(), '请输入本地仓库的绝对路径')
    require(given.exists(), '仓库目录不存在')
    root = given.resolve(strict=True)
    require(root.is_dir() and root != Path(root.anchor) and root != Path.home(), '请选择具体的仓库目录')
    require(not any(p in PRIVATE for p in root.parts), '不接受凭据或工作台内部目录')
    files, excluded, total = [], {}, 0
    tracked=tracked_files(root)
    tracked_dirs={str(parent) for name in tracked for parent in Path(name).parents}
    def omit(reason): excluded[reason] = excluded.get(reason, 0) + 1
    def inaccessible(error): raise ValueError('目录不可读取：'+str(error.filename))
    for current, dirs, names in os.walk(root, followlinks=False, onerror=inaccessible):
        current = Path(current)
        kept = []
        for name in sorted(dirs):
            path = current/name
            if path.is_symlink(): omit('符号链接目录')
            elif name in {'.git','.hg','.svn'} or name in PRIVATE: omit('依赖、产物或内部目录')
            elif name in OMIT_DIRS and str(path.relative_to(root)) not in tracked_dirs: omit('依赖、产物或内部目录')
            elif name.startswith('.') and name != '.github' and str(path.relative_to(root)) not in tracked_dirs: omit('隐藏目录')
            else: kept.append(name)
        dirs[:] = kept
        for name in sorted(names):
            path = current/name
            relative = path.relative_to(root).as_posix()
            test_resource=relative in tracked and bool(set(Path(relative).parts[:-1]) & {'test','tests','fixtures','testdata','__tests__'})
            if path.is_symlink(): omit('符号链接文件'); continue
            if name in SCANNER_CONFIG:
                omit('被验收仓库的扫描器控制配置（不继承）'); continue
            if name in PRIVATE or not test_resource and (name.startswith('.env') or path.suffix.lower() in {'.pem','.key','.p12','.pfx'}):
                omit('凭据或环境私密文件'); continue
            if not path.is_file(): omit('非普通文件'); continue
            size = path.stat().st_size
            with path.open('rb') as stream: sample = stream.read(8192)
            if b'\0' in sample and relative not in tracked: omit('未跟踪的二进制文件'); continue
            require(not any(x in relative for x in ('\\', '\n', '\r', ',')) and not relative.startswith('-'), '文件名不适合容器快照：'+relative)
            files.append(relative); total += size
    require(files, '目录内没有可检查的源文件或配置文件')
    return root, sorted(files), excluded


def manifest(repository, files):
    root, captured = collect(repository, files)
    from .storage import file_digest
    return [dict(path=name, sha256=file_digest(path), size=path.stat().st_size, mode=path.stat().st_mode & 0o777)
            for name, path in sorted(captured.paths.items())]


def prepare(store, repository, network=False, tests=False):
    root, files, excluded = inventory(repository)
    rows = manifest(str(root), files)
    tasks, checks, rules, omissions = [], [], [], []
    pinned = locks()
    def add(tool, target='.'):
        spec = TOOLS[tool]
        image = pinned.get(spec['image_key'], {}).get('id')
        require(image and re.fullmatch(r'sha256:[a-f0-9]{64}', image), '执行器尚未固定镜像：'+tool)
        tid = f'check-{len(tasks)+1:02d}'
        tasks.append(dict(id=tid, tool=tool, target=target, timeout=300,
                          network='registry' if spec['registry_network'] else 'none'))
        checks.append(dict(id=tid, title=LABELS[tool], tool=tool, target=target,
                           expected='至少生成1个可识别组件' if tool=='syft-cyclonedx' else '所有已发现测试通过且至少执行1项' if tool in {'pytest','node-test'} else '无规则命中；命中需复核', network=spec['registry_network']))
        metric = 'sbom.components' if tool=='syft-cyclonedx' else 'tests.failed' if tool in {'pytest','node-test'} else 'findings.total'
        rules.append(dict(id=tid+'-gate', kind='metric', tasks=[tid], metric=metric,
                          operator='ge' if tool=='syft-cyclonedx' else 'le', threshold=1 if tool=='syft-cyclonedx' else 0))
        if tool in {'pytest','node-test'}:
            rules.append(dict(id=tid+'-minimum',kind='metric',tasks=[tid],metric='tests.total',operator='ge',threshold=1))
    suffixes = {Path(f).suffix.lower() for f in files}
    add('gitleaks')
    if '.py' in suffixes: add('bandit')
    if suffixes & {'.js','.ts','.jsx','.tsx','.mjs','.cjs','.vue'}: add('semgrep-njsscan')
    packages = any(Path(f).name in {'package-lock.json','npm-shrinkwrap.json','yarn.lock','pnpm-lock.yaml','requirements.txt','poetry.lock','Pipfile.lock','go.mod','go.sum','Cargo.lock','pom.xml','composer.lock','Gemfile.lock'} for f in files)
    if packages:
        add('syft-cyclonedx')
        if network: add('trivy-fs')
        else: omissions.append(dict(subject='依赖漏洞数据库',reason='未启用公共漏洞库网络；不纳入本次计划'))
    else:
        omissions.append(dict(subject='软件物料与依赖漏洞',reason='未发现可识别的依赖锁或安装清单；package.json/pyproject.toml单独存在不足以证明依赖覆盖，请选择包含锁文件的仓库根目录'))
    dockerfiles = [f for f in files if Path(f).name=='Dockerfile' or Path(f).name.startswith('Dockerfile.')]
    for f in dockerfiles: add('hadolint', f)
    for f in files:
        if f.endswith(('.sh','.bash')): add('shellcheck',f)
    kubernetes = any('apiVersion:' in (root/f).read_text(errors='replace') and 'kind:' in (root/f).read_text(errors='replace') for f in files if f.endswith(('.yml','.yaml')))
    if dockerfiles or '.tf' in suffixes or kubernetes or any(Path(f).name in {'docker-compose.yml','docker-compose.yaml','compose.yml','compose.yaml'} for f in files): add('trivy-config')
    if tests:
        if any(Path(f).name.startswith('test_') and f.endswith('.py') or f.endswith('_test.py') for f in files): add('pytest')
        for f in files:
            if re.search(r'\.(test|spec)\.[cm]?js$',f) and 'node:test' in (root/f).read_text(errors='replace'): add('node-test',f)
    else: omissions.append(dict(subject='仓库现有测试',reason='未选择执行；项目依赖和测试环境需单独配置'))
    if suffixes & {'.go','.rs','.java','.cs','.cpp','.c','.rb','.php'}:
        omissions.append(dict(subject='其他语言专用规则',reason='本次已接入的专用代码规则为Python和JS/TS；其他语言仅做已列出的通用检查，不声称完成语言级安全审计'))
    omissions += [dict(subject='业务流程、浏览器、性能与恢复',reason='尚未提供独立验收标准、可运行环境与测试数据；不自动声称完整产品验收'),
                  dict(subject='真实邮箱、外部身份与付费服务',reason='未配置合成替身或测试环境，不产生用例')]
    for reason, count in excluded.items(): omissions.append(dict(subject=reason,reason=f'自动排除{count}项；源文件范围见快照清单'))
    profile = Profile.model_validate(dict(id='local-'+uuid.uuid4().hex[:16],name=root.name+' · 仓库验收',repository=str(root),version='local-auto-v1',environment='本机隔离容器；源文件只读；无宿主凭据',
                                         scope='按识别技术栈执行代码、配置和物料检查；仅对已冻结计划给出结论',files=files,tasks=tasks,rules=rules,exclusions=omissions)).model_dump()
    plan = dict(id='plan-'+uuid.uuid4().hex[:16], profile=profile, checks=checks,
                snapshot_digest=sha(encode(rows)), manifest=rows, toolchain_digest=sha(encode(pinned)), file_count=len(files),bytes=sum(r['size'] for r in rows))
    directory=store.root/'plans'; directory.mkdir(exist_ok=True)
    (directory/(plan['id']+'.json')).write_bytes(encode(dict(record=plan,sha256=sha(encode(plan)))))
    return public(plan)


def public(plan):
    p=plan['profile']
    return dict(id=plan['id'],repository=p['repository'],name=p['name'],file_count=plan['file_count'],bytes=plan['bytes'],snapshot_digest=plan['snapshot_digest'],checks=plan['checks'],exclusions=p['exclusions'],scope=p['scope'])


def create_from_plan(store, plan_id):
    require(re.fullmatch(r'plan-[a-f0-9]{16}',plan_id), '无效检查计划')
    path=store.root/'plans'/(plan_id+'.json'); require(not path.is_symlink(),'计划路径非法')
    record=json.loads(path.read_bytes()); plan=record['record']
    require(record['sha256']==sha(encode(plan)) and plan['id']==plan_id,'计划内容校验失败')
    profile=Profile.model_validate(plan['profile'])
    root, files, _ = inventory(profile.repository)
    require(files==profile.files and sha(encode(manifest(str(root),files)))==plan['snapshot_digest'], '仓库内容或文件范围已变化，请重新识别并确认计划')
    require(sha(encode(locks()))==plan['toolchain_digest'], '执行器版本已变化，请重新识别计划')
    store.register(profile.model_dump())
    run=store.create(profile.id)
    if run['context']['snapshot_digest']!=plan['snapshot_digest']:
        from .store import now
        run.update(status='error',decision='inconclusive',finished_at=now(),errors=['冻结期间仓库发生变化'])
        store.save(run)
        raise ValueError('冻结期间仓库发生变化，请重新识别计划')
    run['onboarding_plan']=public(plan)
    store.artifact(run,'repository-plan.json',encode(plan))
    store.save(run)
    return run
