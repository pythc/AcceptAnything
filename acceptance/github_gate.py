"""Publish a locally verified, commit-bound decision to an existing GitHub PR.

Only commit statuses are written. This does not alter branch protection, merge,
or upload local evidence. A failed/unknown write is never automatically retried.
"""
import json
import re
import subprocess
from pathlib import Path

from .ci import receipt
from .integrations.formats import require


def publish(service, store, integrations, run_id, repository, pr_number, scope='full'):
    require(service.url == 'https://api.github.com/', '仅支持已核验的 GitHub API')
    require(re.fullmatch(r'[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+', repository), '仓库需为 owner/name')
    require(type(pr_number) is int and pr_number > 0, '需要 PR 编号')
    require(scope in {'full', 'scoped'}, '未知门禁范围')
    prefix = 'repos/' + repository
    pr = service.request(f'{prefix}/pulls/{pr_number}')
    require(pr['state'] == 'open', 'PR 已关闭')
    require(pr['base']['repo']['full_name'].lower() == repository.lower(), 'PR 仓库不符')
    revision = pr['head']['sha']
    require(re.fullmatch(r'[a-f0-9]{40}', revision), 'PR 提交格式异常')
    result = receipt(store, integrations, run_id, revision, scope)
    context = 'acceptance-agent/' + scope
    state = {'allow': 'success', 'reject': 'failure', 'inconclusive': 'error'}[result['decision']]
    body = dict(state=state, context=context,
                description={'success': '验收通过', 'failure': '验收拒绝', 'error': '验收未完成或提交不符'}[state] + ' · ' + run_id,
                target_url=f'https://github.com/{repository}/pull/{pr_number}/checks')
    # Avoid a stale success after lengthy local evidence hashing.
    latest = service.request(f'{prefix}/pulls/{pr_number}')
    require(latest['state'] == 'open' and latest['head']['sha'] == revision, 'PR 已更新，需重新验收当前提交')
    response = service.request(f'{prefix}/statuses/{revision}', 'POST', json=body)
    require(response.get('state') == state and response.get('context') == context and response.get('id'), '状态写入回执不符，请查询 GitHub 后再决定是否重试')
    verified = service.request(f'{prefix}/statuses/{revision}?per_page=100')
    require(any(row.get('id') == response['id'] and row.get('state') == state for row in verified), '状态回读失败；不要盲目重试写入')
    final = service.request(f'{prefix}/pulls/{pr_number}')
    return dict(**result, repository=repository, pr_number=pr_number, status_id=response['id'],
                status_state=state, context=context, current_head=final['head']['sha'],
                stale=final['head']['sha'] != revision or final['state'] != 'open',
                required_check_configured=None)


def main():
    import argparse
    import os
    from .engine import Store
    from .integrations.store import IntegrationStore
    from .integrations.services import Service
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('run_id')
    p.add_argument('--repository', required=True)
    p.add_argument('--pr', type=int, required=True)
    p.add_argument('--scope', choices=['full', 'scoped'], default='full')
    p.add_argument('--data', type=Path)
    p.add_argument('--output', type=Path, required=True)
    p.add_argument('--token-env', default='GITHUB_TOKEN')
    p.add_argument('--use-gh-auth', action='store_true')
    args = p.parse_args()
    if args.use_gh_auth:
        token = subprocess.run(['gh', 'auth', 'token', '--hostname', 'github.com'], capture_output=True, text=True, timeout=10)
        require(token.returncode == 0 and token.stdout.strip(), '无法读取本机 gh 授权')
        os.environ[args.token_env] = token.stdout.strip()
    service = Service('https://api.github.com', args.token_env, 'github')
    store = Store(args.data) if args.data else Store()
    try:
        result = publish(service, store, IntegrationStore(store.root/'integrations'), args.run_id, args.repository, args.pr, args.scope)
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(json.dumps(result, ensure_ascii=False, indent=2)+'\n')
        print(json.dumps({key: result[key] for key in ('revision', 'decision', 'status_id', 'stale')}, ensure_ascii=False))
        return 2 if result['stale'] else result['exit_code']
    finally:
        service.close()


if __name__ == '__main__':
    raise SystemExit(main())
