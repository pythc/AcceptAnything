"""Bounded HTTPS Git transport; repository code never runs during acquisition.

Each request gets its own detached checkout. Plans freeze the resolved commit;
execution never fetches a branch again. Credentials stay in the server environment.
"""
import json
import math
import os
from pathlib import Path
import re
import shutil
import signal
import subprocess
import tempfile
import time
from urllib.parse import urlsplit
from urllib.request import getproxies
import uuid

from .integrations.formats import require
from .integrations.runner import encode, sha
from .integrations.discovery import inventory, manifest

GIT = shutil.which('git') or 'git'


def transfer_timeout():
    try:value=float(os.environ.get('ACCEPTANCE_GIT_TRANSFER_TIMEOUT_SECONDS','1800'))
    except ValueError:raise ValueError('Git传输超时配置需为正数') from None
    require(math.isfinite(value) and value>0,'Git传输超时配置需为有限正数')
    return value


def address(value):
    require(isinstance(value, str) and len(value) <= 2048, '仓库地址无效')
    u = urlsplit(value.strip())
    require(u.scheme == 'https' and u.hostname in {'github.com', 'gitlab.com'}
            and u.netloc == u.hostname and not u.query and not u.fragment,
            '仅支持 github.com、gitlab.com 的 HTTPS 仓库地址；地址不能包含凭据、端口或查询参数')
    path = u.path.rstrip('/')
    if path.endswith('.git'): path = path[:-4]
    parts = path.lstrip('/').split('/')
    require(len(parts) >= 2 and (u.hostname == 'gitlab.com' or len(parts) == 2)
            and all(re.fullmatch(r'[A-Za-z0-9_][A-Za-z0-9_.-]*', p) and p not in {'.', '..'} for p in parts)
            and path == '/' + '/'.join(parts) and '-/tree' not in path,
            '请输入仓库根地址，分支或提交请在单独字段选择')
    return dict(url='https://' + u.hostname + path + '.git',
                provider='github' if u.hostname == 'github.com' else 'gitlab', name=parts[-1])


def reference(kind, value):
    value = value.strip()
    require(kind in {'branch', 'commit'}, '请选择分支或提交')
    if kind == 'commit':
        require(re.fullmatch(r'[a-fA-F0-9]{40}', value), '提交需要完整的40位 SHA')
        return value.lower()
    require(not value or (len(value) <= 200 and not value.startswith(('-', '/', '.'))
            and not value.endswith(('/', '.', '.lock')) and not any(x in value for x in ('..', '@{', '//'))
            and not re.search(r'[\s~^:?*\[\\\x00-\x1f\x7f]', value)
            and all(not p.startswith('.') and not p.endswith('.lock') for p in value.split('/'))), '分支名称无效')
    return value


def git(args, *, cwd=None, provider=None, timeout=90, watch=None):
    # Disable system/user URL rewriting, helpers, hooks, LFS smudge and prompts.
    # Fixed askpass reads only the matching server-side token, never URL input.
    env = {k:v for k,v in os.environ.items() if not k.startswith('GIT_')}
    env.update(GIT_CONFIG_NOSYSTEM='1', GIT_CONFIG_GLOBAL=os.devnull,
               GIT_TERMINAL_PROMPT='0', GIT_LFS_SKIP_SMUDGE='1', LC_ALL='C')
    # libcurl Git does not inherit macOS System Settings proxies by itself.
    # Honor the same operator-owned proxy Python uses; never accept one from input.
    proxy = getproxies().get('https')
    if proxy: env.setdefault('https_proxy', proxy)
    token = os.environ.get('ACCEPTANCE_GITHUB_TOKEN' if provider == 'github' else 'ACCEPTANCE_GITLAB_TOKEN', '') if provider else ''
    command = [GIT, '-c', 'core.hooksPath=' + os.devnull, '-c', 'credential.helper=',
               '-c', 'http.followRedirects=false', '-c', 'protocol.allow=never', '-c', 'protocol.https.allow=always']
    with tempfile.TemporaryDirectory(prefix='acceptance-git-') as temp:
        if token:
            ask = Path(temp)/'askpass.py'
            ask.write_text('#!/usr/bin/env python3\nimport os,sys\nprint("oauth2" if "Username" in sys.argv[1] else os.environ["ACCEPTANCE_TRANSPORT_TOKEN"])\n')
            ask.chmod(0o700)
            env.update(GIT_ASKPASS=str(ask), ACCEPTANCE_TRANSPORT_TOKEN=token)
        with tempfile.TemporaryFile() as out, tempfile.TemporaryFile() as err:
            process = subprocess.Popen(command + list(args), cwd=cwd, env=env,
                stdin=subprocess.DEVNULL, stdout=out, stderr=err, start_new_session=True)
            deadline = time.monotonic() + timeout
            try:
                while process.poll() is None:
                    require(time.monotonic() < deadline, '远程仓库操作超时，请检查网络或凭据')
                    time.sleep(0.05)
                out.seek(0); err.seek(0)
                data = out.read(); error = err.read()
                # Do not reflect upstream diagnostic bodies, which may contain secrets.
                require(process.returncode == 0, 'Git操作失败：仓库/分支/提交不存在，或网络、权限不可用；未执行验收')
                return data.decode('utf-8', errors='strict').strip()
            finally:
                if process.poll() is None:
                    os.killpg(process.pid, signal.SIGKILL); process.wait()


def refs(url):
    target = address(url)
    raw = git(['ls-remote', '--symref', target['url'], 'HEAD', 'refs/heads/*'], provider=target['provider'])
    branches=[]; default=None
    for line in raw.splitlines():
        if line.startswith('ref: refs/heads/') and line.endswith('\tHEAD'):
            default=line.split('\t')[0][len('ref: refs/heads/'):]
        elif '\trefs/heads/' in line:
            commit, branch=line.split('\trefs/heads/', 1)
            if re.fullmatch('[a-f0-9]{40}', commit): branches.append(dict(name=branch, commit=commit))
    require(branches and default, '远程仓库为空或默认分支不可读取')
    return dict(**target, default_branch=default, branches=branches, truncated=False)


def checkout(store, url, kind, ref):
    target=address(url); ref=reference(kind,ref)
    transfer_seconds=transfer_timeout()
    advertised=refs(target['url'])
    if kind == 'branch':
        ref=ref or advertised['default_branch']
        # Resolve first, then fetch precisely that SHA; branch movement cannot change intent.
        match=next((b for b in advertised['branches'] if b['name']==ref),None)
        if match is None:
            rows=git(['ls-remote','--heads',target['url'],'refs/heads/'+ref],provider=target['provider']).splitlines()
            match=next((dict(commit=row.split('\t')[0]) for row in rows if row.endswith('\trefs/heads/'+ref)),None)
        require(match is not None, '所选分支不存在')
        commit=match['commit']
    else: commit=ref
    base=store.root/'remote-sources'/('src-'+uuid.uuid4().hex[:16]); base.mkdir(parents=True)
    root=base/'repository'
    started=time.monotonic()
    try:
        git(['init','--quiet','--template=',str(root)])
        git(['remote','add','origin',target['url']],cwd=root)
        git(['fetch','--quiet','--depth=1','--no-tags','origin',commit],cwd=root,provider=target['provider'],watch=base,timeout=transfer_seconds)
        resolved=git(['rev-parse','--verify','FETCH_HEAD^{commit}'],cwd=root)
        require(resolved==commit, '远程提交解析不一致')
        # Inspect the index before checkout; never create escaping symlinks or submodules.
        tree=git(['ls-tree','-r',commit],cwd=root)
        require(not any(row.startswith(('120000 ', '160000 ')) for row in tree.splitlines()),
                '此仓库包含符号链接或子模块，当前隔离接入未支持；未执行验收')
        git(['checkout','--quiet','--detach',commit],cwd=root,watch=base,timeout=transfer_seconds)
        _,files,_=inventory(str(root)); rows=manifest(str(root),files)
        source=dict(schema_version=1,id=base.name,**target,requested_kind=kind,requested_ref=ref,
                    branch=ref if kind=='branch' else None,commit=commit,repository=str(root),
                    snapshot_digest=sha(encode(rows)),file_count=len(rows),duration_ms=round((time.monotonic()-started)*1000),
                    submodules='not-initialized',lfs='not-downloaded',transfer_timeout_seconds=transfer_seconds)
        source['transport_sha256']=sha(Path(__file__).read_bytes())
        # LFS pointers are not source bytes; never claim the missing objects were checked.
        require(not any((root/p).read_bytes().startswith(b'version https://git-lfs.github.com/spec/v1') for p in files),
                '此仓库包含 Git LFS 对象，当前接入未下载对象；未执行验收')
        (base/'source.json').write_bytes(encode(dict(record=source,sha256=sha(encode(source)))))
        return source
    except Exception:
        shutil.rmtree(base)
        raise


def verify(store, source):
    require(re.fullmatch(r'src-[a-f0-9]{16}',source['id']), '远程来源编号无效')
    base=store.root/'remote-sources'/source['id']
    require(not base.is_symlink() and not (base/'repository').is_symlink(), '远程来源路径非法')
    value=json.loads((base/'source.json').read_bytes())
    require(value['record']==source and value['sha256']==sha(encode(source)), '远程来源记录已变化')
    require(source['transport_sha256']==sha(Path(__file__).read_bytes()), '远程接入实现已变化，请重新拉取')
    require(str(base/'repository')==source['repository'], '远程工作区不匹配')
    require(git(['rev-parse','HEAD'],cwd=source['repository'])==source['commit'], '远程工作区提交已变化，请重新拉取')
    require(not git(['status','--porcelain','--untracked-files=all'],cwd=source['repository']), '远程工作区已变化，请重新拉取')
    _,files,_=inventory(source['repository'])
    require(sha(encode(manifest(source['repository'],files)))==source['snapshot_digest'], '远程源码快照已变化')


def configured(store, source, configuration=None):
    """Only a server-reviewed mapping can relocate a previously approved model plan."""
    from .engine import ROOT
    path=ROOT/'var/remote-project-configurations.json'
    entry=json.loads(path.read_text()).get(source['url']) if path.exists() else None
    if not entry or configuration: return configuration,None
    require(entry['snapshot_digest']==source['snapshot_digest'],
            '远程版本与已审定业务配方的源码快照不同，请先重新审定该版本的验收方案')
    return entry['configuration'],dict(reviewed_repository=entry['reviewed_repository'],
        snapshot_digest=source['snapshot_digest'],remote_url=source['url'],commit=source['commit'])


def bind_run(store, run, source):
    require(run['context']['revision']==source['commit'] and run['context']['snapshot_digest']==source['snapshot_digest'],
            '实际冻结源码与远程提交不一致')
    run['remote_source']=source
    run['context']['branch']=source['branch']
    run['remote_source_ref']=store.artifact(run,'remote-source.json',encode(source))


def verify_archived(store, run):
    """Check frozen provenance only; historical evidence never fetches live Git."""
    source=run.get('remote_source')
    planned=(run.get('test_plan') or {}).get('remote_source')
    require(source==planned, '远程来源与冻结方案不一致')
    if not source: return
    require(json.loads(store.artifact_bytes_for_record(run,run['remote_source_ref'])[1])==source,
            '远程来源证据不一致')
    context=run['context']
    require(context['revision']==source['commit'] and context['repository']==source['repository']
            and context['snapshot_digest']==source['snapshot_digest'] and context.get('branch')==source['branch'],
            '远程提交、分支或源码快照与执行上下文不一致')


def repository_fields(source):
    from .source import repository_id
    return dict(id=repository_id(source['url']),name=source['name'],kind='git',
                remote=source['url'],commit=source['commit'],branch=source['branch'],
                requested_kind=source['requested_kind'],requested_ref=source['requested_ref'])
