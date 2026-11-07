"""Commit-bound CI decision. Never trusts caller-supplied imported provenance."""
import re
import subprocess
from pathlib import Path
from .integrations.formats import require
from .integrations.runner import sha,encode


def commit_matches(repository, revision, files):
    require(re.fullmatch(r'[a-f0-9]{40}|[a-f0-9]{64}',revision),'需要完整 Git 提交 SHA')
    root=Path(repository).resolve()
    def git(*args):
        result=subprocess.run(['git','-C',str(root),*args],capture_output=True,timeout=10)
        require(result.returncode==0,'无法验证提交内文件；未跟踪文件或错误仓库不能用于 PR 放行')
        return result.stdout
    top=Path(git('rev-parse','--show-toplevel').decode().strip()).resolve()
    prefix=root.relative_to(top).as_posix()
    require(git('rev-parse',revision+'^{commit}').decode().strip()==revision,'Git 对象不是指定提交')
    require(files,'缺少冻结文件清单')
    for row in files:
        name=row['path'] if prefix=='.' else prefix+'/'+row['path']
        require(sha(git('show',revision+':'+name))==row['sha256'],'冻结源码与提交不符：'+row['path'])
        mode=git('ls-tree',revision,'--',name).decode().split()[0]
        if 'mode' in row:
            require((mode=='100755')==bool(row['mode']&0o111),'冻结文件执行权限与提交不符：'+row['path'])
    return True


def receipt(store, integrations, rid, revision, required_scope='full'):
    from .unified import integration_view,workflow_view
    reasons=[]
    try:
        if rid.startswith('int-'):
            original=integrations.read(rid)
            require(original['mode']=='executor','外部导入结果不能作为本地提交验证')
            context=original['context'];files=context['files']
            view=integration_view(integrations,rid)
            repository=context['repository'];captured=context['revision']
        else:
            original=store.read(rid)
            view=workflow_view(store,integrations,store.snapshot(rid))
            repository=view['source']['repository']['path'];captured=view['source']['repository']['commit']
            files=original.get('workflow',{}).get('manifest',[])
        require(captured==revision,'执行时提交与 CI 请求提交不一致')
        commit_matches(repository,revision,files)
        require(view['status']=='completed' and view['integrity'],'执行未完成或证据校验失败')
        require(view['decision'] in {'allow','reject'},'门禁没有确定结论')
        require(required_scope in {'full','scoped'},'未知门禁范围')
        if required_scope=='full':
            require(view.get('completion',{}).get('kind')=='full' and view['completion']['complete'],'只有扫描或配置范围结果，未完成完整验收')
        decision=view['decision'];reasons=view['reasons']
        evidence_digest=sha(encode(sorted((a['id'],a['sha256']) for a in view['artifacts'])))
    except (ValueError,OSError,KeyError,subprocess.SubprocessError) as exc:
        decision='inconclusive';reasons=[str(exc)];evidence_digest=None
    return dict(run_id=rid,revision=revision,required_scope=required_scope,decision=decision,
        exit_code={'allow':0,'reject':1,'inconclusive':2}[decision],reasons=reasons,evidence_digest=evidence_digest,
        github_check=dict(name='验收 Agent · '+required_scope,head_sha=revision,status='completed',
            conclusion='success' if decision=='allow' else 'failure',external_id=rid,
            output=dict(title={'allow':'验收通过','reject':'验收拒绝','inconclusive':'验收未完成或身份不符'}[decision],summary='\n'.join(reasons)[:60000])))
