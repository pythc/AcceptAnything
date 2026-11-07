from __future__ import annotations

from contextlib import asynccontextmanager
from concurrent.futures.process import BrokenProcessPool
from pathlib import Path
import json
import shlex
from urllib.parse import urlparse

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import Response, FileResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, ConfigDict, model_validator, Field
from typing import Literal

from .engine import OPA, ROOT, Store, baseline
from . import source
from . import __version__
from . import projects
from .planning.basis import MAX_DOCUMENTS, MAX_REQUIREMENTS_CHARACTERS


class Start(BaseModel):
    model_config = ConfigDict(extra="forbid")
    mode: Literal["buggy", "fixed"] | None = None
    project_id: str | None = None

    @model_validator(mode="after")
    def one_target(self):
        if (self.mode is None) == (self.project_id is None):
            raise ValueError("需要选择一个示例或已登记项目")
        return self


class FullPlan(BaseModel):
    model_config = ConfigDict(extra='forbid')
    repository: str | None = Field(default=None,min_length=1,max_length=2048)
    remote_url: str | None = Field(default=None,min_length=1,max_length=2048)
    ref_type: Literal['branch','commit'] = 'branch'
    ref: str = Field(default='',max_length=200)
    configuration: str | None = Field(default=None,max_length=2048)
    frozen_design_run: str | None = Field(default=None,pattern=r'^int-[a-f0-9]{16}$')

    @model_validator(mode='after')
    def one_source(self):
        if self.frozen_design_run:
            if self.repository or self.remote_url or self.configuration or self.ref or self.ref_type!='branch':raise ValueError('冻结设计复验使用原记录的源码，不接受其他来源或配置')
            return self
        if (self.repository is None) == (self.remote_url is None):
            raise ValueError('请选择本地路径或远程仓库地址之一')
        if self.repository is not None and (self.ref or self.ref_type != 'branch'):
            raise ValueError('本地路径不接受远程引用')
        return self


class RemoteRefs(BaseModel):
    model_config = ConfigDict(extra='forbid')
    url: str = Field(min_length=1,max_length=2048)


class FullStart(BaseModel):
    model_config = ConfigDict(extra='forbid')
    plan_id: str = Field(pattern=r'^(full|design|auto|intake)-[a-f0-9]{16}$')
    digest: str = Field(pattern=r'^[a-f0-9]{64}$')


class AutomaticDesign(BaseModel):
    model_config=ConfigDict(extra='forbid')
    intake_id: str = Field(pattern=r'^intake-[a-f0-9]{16}$')
    documents: list[str] = Field(default_factory=list,max_length=MAX_DOCUMENTS)
    requirements_text: str = Field(default='',max_length=MAX_REQUIREMENTS_CHARACTERS)
    scope: str = Field(default='',max_length=2000)


def create_app(store=None):
    store = store or Store()
    from .integrations.store import IntegrationStore
    from .integrations.api import router
    integrations = IntegrationStore(store.root / "integrations")
    from .jobs import Jobs
    jobs = Jobs(store.root / "jobs")

    @asynccontextmanager
    async def lifespan(app):
        try:
            with store.lease():
                store.recover(exclude={j['run_id'] for j in jobs.list(active=True)})
        except RuntimeError:
            pass
        try:
            with integrations.lease():
                integrations.recover(exclude={j['run_id'] for j in jobs.list(active=True)})
        except ValueError:
            pass
        from .read_service import ProofReaders
        from .history import IndexSynchronizer
        indexer=IndexSynchronizer([store,integrations]);app.state.history_indexer=indexer
        readers=ProofReaders(store.root);app.state.proof_readers=readers
        try:yield
        finally:
            app.state.proof_readers=None
            readers.close()
            indexer.close();app.state.history_indexer=None

    app = FastAPI(title="验收 Agent", version=__version__, lifespan=lifespan)
    app.state.store = store
    app.state.proof_readers = None
    app.state.history_indexer = None
    app.include_router(router(integrations, jobs))

    @app.get('/api/agent/context')
    def agent_context():
        from .engine import digest
        return {'service_id': digest(str(store.root.resolve()).encode()),
                'tools_contract': 'acceptanything-tools-v1', 'scope': 'local-self-hosted'}

    @app.exception_handler(BrokenProcessPool)
    async def proof_interrupted(request, exc):
        return Response('核验进程中断，原件保留；请重新核验',status_code=503,headers={'Retry-After':'1'})

    def unified_run(rid,page=None):
        from .read_service import project_view
        readers=app.state.proof_readers
        view=readers.submit('view',rid,page).result() if readers else project_view(store,integrations,rid,page)
        view['job'] = jobs.for_run(rid)
        return view

    def unified_artifact(rid,aid):
        if rid.startswith('int-'):return integrations.artifact_bytes(rid,aid)
        r=store.read(rid)
        if any(a['id']==aid for a in r['artifacts']):return store.artifact_bytes(r,aid)
        # Search only children bound to this parent, not other local runs.
        for child in r.get('workflow',{}).get('children',[]):
            cr=integrations.read(child['id'])
            if any(a['id']==aid for a in cr['artifacts']):return integrations.artifact_bytes(child['id'],aid)
        raise FileNotFoundError('证据不属于此验收')

    @app.post('/api/acceptance/plan')
    def full_plan(body: FullPlan):
        if body.frozen_design_run:
            from .universal.replay import prepare as replay_prepare
            return replay_prepare(integrations,body.frozen_design_run)
        from .workflow import plan
        from .project_config import prepare, public, registered_configuration
        remote_source=None; binding=None; repository=body.repository
        if body.remote_url:
            from . import remote
            remote_source=remote.checkout(integrations,body.remote_url,body.ref_type,body.ref)
            repository=remote_source['repository']
            configuration,binding=remote.configured(integrations,remote_source,body.configuration) if body.configuration else (None,None)
        else:
            configuration=body.configuration
        if configuration:
            return public(prepare(integrations,repository,configuration,remote_source=remote_source,repository_binding=binding))
        from .universal.service import prepare as universal_prepare
        return universal_prepare(integrations,repository,remote_source=remote_source)

    @app.post('/api/acceptance/automatic/design')
    def automatic_design(body: AutomaticDesign):
        from .automatic import design
        return design(integrations,body.intake_id,body.documents,body.requirements_text,body.scope)

    @app.post('/api/acceptance/remote/refs')
    def remote_refs(body: RemoteRefs):
        from .remote import refs
        return refs(body.url)

    @app.post('/api/acceptance/runs',status_code=202)
    def full_start(body: FullStart):
        from .workflow import create
        if body.plan_id.startswith('intake-'):
            raise ValueError('尚未生成并确认独立需求用例，不能只运行扫描')
        if body.plan_id.startswith('auto-'):
            from .automatic import load,create as create_automatic
            prepared=load(integrations,body.plan_id,body.digest)
            if prepared.get('kind')=='universal':
                from .universal.service import create as create_universal
                run=create_universal(integrations,body.plan_id,body.digest)
            else:run=create_automatic(integrations,body.plan_id,body.digest)
            job=jobs.enqueue('integration',run['id'])
        elif body.plan_id.startswith('design-'):
            from .planning.service import create_run
            run=create_run(integrations,body.plan_id,body.digest)
            job=jobs.enqueue('integration',run['id'])
        else:
            run=create(store,body.plan_id,body.digest)
            job=jobs.enqueue('native',run['id'])
        return {'id':run['id'],'job_id':job['id']}

    @app.get('/api/jobs')
    def list_jobs():
        return jobs.list()

    @app.post('/api/jobs/{job_id}/cancel')
    def cancel_job(job_id: str):
        return jobs.cancel(job_id)

    @app.get('/api/jobs/{job_id}/events')
    def job_events(job_id: str, after: int = 0, limit: int = 100):
        return jobs.events(job_id,after,limit)

    @app.middleware("http")
    async def protect_local_writes(request: Request, call_next):
        host = request.headers.get("host", "").split(":")[0]
        if host not in ("127.0.0.1", "localhost", "testserver"):
            return Response("仅接受本地 Host", status_code=403)
        if request.method not in ("GET", "HEAD", "OPTIONS"):
            origin = request.headers.get("origin")
            if origin and urlparse(origin).netloc != request.headers.get("host"):
                return Response("仅允许同源操作", status_code=403)
            if not request.headers.get("content-type", "").startswith("application/json"):
                return Response("需要 JSON", status_code=415)
        response = await call_next(request)
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["Cache-Control"] = "no-store"
        return response

    @app.exception_handler(FileNotFoundError)
    async def missing(request, exc):
        return Response("记录或证据不存在", status_code=404)

    @app.exception_handler(ValueError)
    async def invalid(request, exc):
        return Response(str(exc), status_code=409)

    @app.get("/api/health")
    def health():
        return {"status": "ok", "scope": "local-and-remote-repository-plans", "version": __version__}

    @app.get("/api/baseline")
    def get_baseline():
        return baseline()

    @app.get("/api/target")
    def get_target(mode: Literal["buggy", "fixed"] = "fixed"):
        return source.capture(ROOT, mode, baseline()["criteria"], OPA)

    def repository_groups(runs):
        groups = {}
        for run in runs:
            repository = run["source"]["repository"]
            if not repository["path"]:
                continue
            group = groups.setdefault(repository["id"], {"id": repository["id"], "repository": repository, "latest": run, "run_count": 0})
            group["run_count"] += 1
        return list(groups.values())

    @app.get("/api/repositories")
    def repositories():
        return repository_groups(catalogue_runs())

    def catalogue_runs():
        if app.state.history_indexer is None:
            store.sync_history(max_age=1)
            integrations.sync_history(max_age=1)
        return store.history.combined(integrations.history)['items']

    @app.get("/api/catalogue")
    def catalogue(limit: int | None = None, cursor: str | None = None, query: str = '', repository: str = '', kind: str = 'records'):
        if app.state.history_indexer is None:
            store.sync_history(max_age=1)
            integrations.sync_history(max_age=1)
        page = store.history.combined(integrations.history,limit=limit,cursor=cursor,query=query,repository=repository,kind=kind)
        page['index_status']=app.state.history_indexer.status if app.state.history_indexer else {'state':'ready'}
        if kind == 'repositories':
            return {'runs':[], 'repositories':page.pop('items'), **page}
        runs = page.pop('items')
        return {'runs':runs,'repositories':repository_groups(runs),**page}

    @app.get('/api/runs/{run_id}/result-contract')
    def result_contract(run_id: str):
        if app.state.proof_readers:
            return app.state.proof_readers.submit('contract',run_id).result()
        if run_id.startswith('int-'):
            return integrations.snapshot(run_id)['result_contract']
        from .results import native_project
        return native_project(unified_run(run_id))

    @app.get('/api/catalogue/records/{run_id}')
    def catalogue_record(run_id: str):
        selected=integrations if run_id.startswith('int-') else store
        selected.path(run_id)
        try:return selected.history.get(run_id)
        except FileNotFoundError:
            selected.sync_history()
            return selected.history.get(run_id)

    @app.get('/api/result-contract/schema')
    def result_contract_schema():
        from .results import ResultContract
        return ResultContract.model_json_schema()

    @app.get("/api/projects")
    def registered_projects():
        return projects.profiles(store)

    @app.get("/api/runs")
    def list_runs():
        return store.list()

    @app.post("/api/runs", status_code=202)
    def start(body: Start):
        run = projects.create(store, body.project_id) if body.project_id is not None else store.create(body.mode)
        job = jobs.enqueue('native',run['id'])
        return {'id':run['id'],'job_id':job['id']}

    @app.get("/api/runs/{run_id}")
    def get_run(run_id: str, offset:int=0, limit:int=100, state:str='active', finding:str='', q:str=''):
        if offset<0 or limit<1:raise HTTPException(422,'分页参数无效')
        if state not in {'','active','needs_review','confirmed','false_positive','test_issue'}:raise HTTPException(422,'复核分类无效')
        return unified_run(run_id,dict(offset=offset,limit=limit,state=state,finding=finding,query=q))

    @app.get('/api/runs/{run_id}/history')
    def finding_history(run_id: str):
        from .integrations.lifecycle import DojoLifecycle
        unified_run(run_id)  # validate the requested run identity
        children = [run_id]
        if not run_id.startswith('int-'):
            children += [c['id'] for c in store.read(run_id).get('workflow',{}).get('children',[])]
        lifecycle = DojoLifecycle(integrations.root / 'lifecycle')
        records = {row['key']:row for rid in children for row in lifecycle.list(rid)}
        return list(records.values())

    @app.get("/api/runs/{run_id}/artifacts/{artifact_id}")
    def get_artifact(run_id: str, artifact_id: str, download: bool = False):
        from urllib.parse import quote
        if run_id.startswith('int-'):
            r=integrations.read(run_id);item,path=integrations.verified_artifact_path(r,artifact_id)
            import mimetypes
            media=mimetypes.guess_type(item['name'])[0] or 'application/octet-stream'
            safe=media if media in {'application/json','text/plain','text/markdown','image/png','image/jpeg'} else 'application/octet-stream'
            return FileResponse(path,media_type=safe,filename=item['name'] if download or safe=='application/octet-stream' else None,headers={'Content-Security-Policy':"default-src 'none'; sandbox"})
        item, data = unified_artifact(run_id, artifact_id)
        item={**item,'media_type':item.get('media_type','text/plain')}
        safe_media = {"application/json", "text/plain", "text/markdown", "image/png", "image/jpeg"}
        media = item["media_type"] if item["media_type"] in safe_media else "application/octet-stream"
        disposition = "attachment" if download or media == "application/octet-stream" else "inline"
        return Response(data, media_type=media, headers={"Content-Disposition": disposition + "; filename*=UTF-8''" + quote(item["name"]), "Content-Security-Policy": "default-src 'none'; sandbox"})

    @app.get("/api/runs/{run_id}/report")
    def report(run_id: str, request: Request):
        if run_id.startswith('int-'):
            from .integrations.adjudication import load,observations
            r=integrations.snapshot(run_id);review=load(integrations,r)
            def markdown():
                yield f"# {r['name']}\n\n执行：{r['id']}\n\n结论：{r['decision']}\n\n完整性：{r['integrity']}\n\n"
                yield '发现统计：'+json.dumps(review['summary'],ensure_ascii=False)+'\n\n'
                groups={g['id']:g for g in review['groups']};rows={x['id']:x for x in review['observations']}
                for o in observations(r):
                    row=rows[o['id']]
                    if row['group_id']!=o['id']:continue
                    hit=o['hit'];yield f"- {o['id']} · {row['label']} · {hit.get('title',hit.get('name',''))} · {hit.get('path','')}:{hit.get('line','')}：{row['reason']}\n"
                for t in r['tasks']:
                    yield f"\n## {t['id']} · {t['state']}\n\n{t.get('error','')}\n"
                    for test in t.get('report',{}).get('tests',[]):yield f"- {test['status']} · {test['name']}\n"
                yield '\n## 原始证据\n'
                for a in r['artifacts']:yield f"- [{a['name']}]({str(request.base_url).rstrip('/')}/api/runs/{run_id}/artifacts/{a['id']}?download=true) · {a['sha256']}\n"
            return StreamingResponse(markdown(),media_type='text/markdown',headers={'Content-Disposition':f'attachment; filename="{run_id}.md"'})
        if store.read(run_id).get('workflow'):
            r=unified_run(run_id)
            base_url=str(request.base_url).rstrip('/')
            text=f"# {r['label']}\n\n执行：{r['id']}\n\n结论：{r['decision']}\n\n完整性：{r['completion']}\n\n仓库：{r['source']['repository']['path']}\n\n"
            repository=r['source']['repository']
            if repository.get('remote'):
                text+=f"远程仓库：{repository['remote']}\n\n选择版本：{repository.get('requested_kind','branch')} · {repository.get('requested_ref') or repository.get('branch') or '未采集'}\n\n冻结提交：{repository.get('commit') or '未采集'}\n\n源码快照：{r['source']['snapshot']['digest']}\n\n"
            if r.get('review_summary'):
                text+='复核后有效结果结合本次冻结复核目录；工具原始报告、原始失败与子门禁没有改写。\n\n'
            if r.get('finding_counts'):
                text+='发现统计（去重后）：'+json.dumps(r['finding_counts'],ensure_ascii=False)+'\n\n'
                text+='\n'.join(f"- {f['id']} · {f['review']['label']} · {f['title']}：{f['review']['reason']}" for f in r['findings'])+'\n\n'
            text+='\n'.join('- '+reason for reason in r['reasons'])+'\n\n'
            for result in r['results']:
                text+=f"## {result['criterion_id']} · {result['status']}\n\n预期：{result['expected']}\n\n实际：{result['actual']}\n\n"
                if result.get('review'):
                    review=result['review']
                    text+=f"原始状态：{result.get('raw_status',result['status'])}\n\n复核分类：{review['label']}\n\n复核结论：{review['reason']}\n\n"
                    text+='\n'.join('- '+row['reason'] for row in review['rows'])+'\n\n'
                text+='\n'.join(f"- [原始证据 {aid}]({base_url}/api/runs/{run_id}/artifacts/{aid}?download=true)" for aid in result['evidence_refs'])+'\n\n'
            for a in r['artifacts']:text+=f"- [{a['name']}]({base_url}/api/runs/{run_id}/artifacts/{a['id']}?download=true) · {a['sha256']}\n"
            return Response(text,media_type='text/markdown',headers={'Content-Disposition':f'attachment; filename="{run_id}.md"'})
        r = store.snapshot(run_id)
        labels = {"allow": "所选基线通过", "reject": "未通过", "inconclusive": "无法下结论"}
        b = r["baseline"]
        base_url = str(request.base_url).rstrip("/")
        artifact_url = lambda ref: f"{base_url}/api/runs/{run_id}/artifacts/{ref}?download=true"
        text = f"# 验收报告 · {r['id']}\n\n结论：{labels[r['decision']]}\n\n"
        text += "原因：" + "；".join(r["reasons"]) + "\n\n"
        text += f"原始记录结论：{labels[r['recorded_decision']]}\n\n当前适用性：{r['applicability']['reason']}\n\n报告语义校验：{'通过' if r['validation']['valid'] else '未通过'}\n\n"
        text += f"目标：{r['label']} · {r['mode']}\n\n执行状态：{r['status']}\n\n创建时间：{r['created_at']}\n\n结束时间：{r['finished_at'] or '未结束'}\n\n"
        src = r["source"]; repo = src["repository"]
        text += f"## 仓库与版本\n\n目录：{repo['path'] or '未采集'}\n\n分支：{repo['branch'] or '未采集'}\n\n提交：{repo['commit'] or ('尚无提交 / 本地目录' if src['provenance'] == 'captured' else '历史未采集')}\n\n文件快照：{src['snapshot']['digest']}\n\n采集时间：{src['captured_at'] or '历史未采集'}\n\n验收范围：{src['scope']['description']}\n\n"
        for file in src["scope"]["files"]:
            text += f"- {file['path']} · SHA-256 {file['sha256']}\n"
        if r.get("source_artifact"):
            text += f"\n[验收目标快照]({artifact_url(r['source_artifact'])})\n\n"
        text += f"## 验收依据\n\n基线版本：{b['version']}\n\n来源：{b['source']}\n\n范围：{b['scope']}\n\n基线摘要：{b['digest']}\n\n测试集摘要：{r['suite_digest']}\n\n目标摘要：{r['target_digest']}\n\n策略摘要：{b['policy_digest']}\n\nOPA 镜像：{OPA}\n\n内容校验：{'相符' if r['integrity'] else '未通过或未完成'}\n\n"
        for a in r["artifacts"]:
            if a["name"] in ("gate-input.json", "gate-result.json"):
                text += f"- [{a['name']}]({artifact_url(a['id'])}) · {a['id']}\n"
        text += "\n## 流水线\n\n"
        for stage in r.get("pipeline", []):
            duration = f"{stage['duration_ms'] / 1000:.3f} s" if stage.get("duration_ms") is not None else "未记录"
            text += f"- {stage['id']} · {stage['status']} · {duration} · {stage['detail']}\n  - 开始 {stage['started_at']}；结束 {stage.get('finished_at') or '未结束'}\n"
        if not r.get("pipeline"):
            text += "历史记录未单独采集完整阶段耗时；保留已有分层时间记录。\n"
        text += "\n## 结果\n\n"
        for x in r["results"]:
            actual = "\n".join("    " + line for line in x["actual"].splitlines())
            text += f"### {x['criterion_id']} · {x['status']}\n\n用例：{x['case_id']} · 第 {x['attempt']} 次执行 · {x['layer']}\n\n预期：{x['expected']}\n\n实际：\n\n{actual}\n\n"
            detail = r["inspections"].get(x["criterion_id"])
            if detail:
                text += f"发生经过：{detail['summary']}\n\n验证方法：{detail['method']} · 原始报告核对：{'相符' if detail['verified'] else '未核实'}\n\n复现步骤（冻结用例）：\n\n"
                text += "\n".join(f"{i+1}. {step}" for i, step in enumerate(detail['steps'])) + "\n\n"
                text += f"验证范围：{detail['limitation']}\n\n"
                if detail.get("location"):
                    text += f"定位：{detail['location']}\n\n"
                if detail.get("source_report"):
                    text += f"[执行器原始报告]({artifact_url(detail['source_report'])})\n\n"
            text += "证据：" + " · ".join(f"[{ref}]({artifact_url(ref)})" for ref in x["evidence_refs"]) + "\n\n"
        text += "\n\n## 缺口与限制\n\n" + "\n".join("- " + x for x in r["limits"] + r["reasons"])
        text += "\n\n## 证据目录\n\n" + "\n".join(f"- [{a['name']}]({artifact_url(a['id'])}) · {a['id']} · 文件 {a['file']} · {a['size']} bytes · SHA-256 {a['sha256']}" for a in r["artifacts"])
        text += "\n\n## 复验\n\n在工作台对相同目标创建新执行，并核对基线与测试集摘要一致。旧记录和输出目录保留只读。以下为原执行命令，仅用于核对，不要原地覆盖历史输出。\n\n"
        for command in r.get("commands", []):
            text += f"- {command['name']} · 退出码 {command['exit_code']} · [执行日志]({artifact_url(command['evidence_ref'])})\n"
            if command.get("argv"):
                text += "\n    " + shlex.join(command["argv"]) + "\n\n"
        return Response(text, media_type="text/markdown", headers={"Content-Disposition": f'attachment; filename="{run_id}.md"'})

    trace_assets = ROOT / 'validation/node_modules/playwright-core/lib/vite/traceViewer'
    if trace_assets.is_dir():
        app.mount('/trace-viewer', StaticFiles(directory=trace_assets,html=True),name='playwright-trace')
    dist = ROOT / "web/dist/client"
    if dist.exists():
        app.mount("/", StaticFiles(directory=dist, html=True), name="frontend")
    return app


app = create_app()
