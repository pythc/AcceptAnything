from pathlib import Path
from typing import Literal
from fastapi import APIRouter, HTTPException
from fastapi.responses import Response
from pydantic import Field
from .models import Strict, Context, Rule
from .registry import catalog
from . import export


class Start(Strict):
    profile_id: str = Field(pattern=r"^[a-z][a-z0-9-]{0,63}$")


class LocalPlan(Strict):
    repository: str = Field(min_length=1, max_length=2048)
    allow_registry: bool = False
    run_tests: bool = False


class LocalStart(Strict):
    plan_id: str = Field(pattern=r"^plan-[a-f0-9]{16}$")


class SourceInput(Strict):
    repository: str = Field(min_length=1, max_length=2048)
    path: str | None = Field(default=None, max_length=2048)


class Imported(Strict):
    id: str = Field(pattern=r"^[a-z][a-z0-9-]{0,63}$")
    format: str = Field(min_length=1, max_length=50)
    content: str = Field(min_length=1)
    environment: str | None = Field(default=None, min_length=1, max_length=160)


class Import(Strict):
    request_id: str = Field(pattern=r"^[a-f0-9-]{36}$")
    name: str = Field(min_length=1)
    context: Context
    reports: list[Imported] = Field(min_length=1)
    rules: list[Rule] = Field(min_length=1)


class FindingReview(Strict):
    request_id: str = Field(pattern=r'^[a-f0-9-]{36}$')
    expected_revision: str = Field(default='',pattern=r'^(?:[a-f0-9]{64})?$')
    state: Literal['needs_review','false_positive','confirmed','test_issue']
    reason: str = Field(min_length=20,max_length=4000)
    evidence_refs: list[str] = Field(min_length=1,max_length=20)


def router(store, jobs):
    api = APIRouter(prefix="/api/integrations")
    from ..planning.models import DesignInput, DraftInput, ExecuteInput
    from ..planning import service as planning, provider

    @api.post('/runs/{rid}/findings/{fid}/review')
    def finding_review(rid:str,fid:str,body:FindingReview):
        from .finding_reviews import submit
        try:return submit(store,rid,fid,body)
        except (ValueError,KeyError,FileNotFoundError) as exc:raise HTTPException(409,str(exc)) from None

    @api.get('/runs/{rid}/findings/{fid}/reviews')
    def finding_reviews(rid: str, fid: str):
        from .finding_reviews import history
        return history(store, rid, fid)

    @api.get('/planning/status')
    def planning_status():
        return provider.status(store)

    @api.post('/planning/reconcile')
    def planning_reconcile():
        from ..planning import calls
        calls.reconcile(store)
        return provider.status(store)

    @api.get('/planning/schema')
    def planning_schema():
        return DesignInput.model_json_schema()

    @api.get('/planning/example')
    def planning_example():
        import json
        return json.loads((Path(__file__).parents[1]/'planning/examples/assessment.json').read_text())

    @api.post('/planning/sources')
    def planning_sources(body: SourceInput):
        return planning.read_source(body.repository,body.path) if body.path else planning.inspect_repository(body.repository)

    @api.post('/planning/draft')
    def planning_draft(body: DraftInput):
        return provider.draft(store,body)

    @api.post('/planning/plan')
    def planning_plan(body: DesignInput):
        return planning.prepare(store,body)

    @api.post('/planning/runs',status_code=202)
    def planning_run(body: ExecuteInput):
        return dispatch(lambda: planning.create_run(store,body.plan_id,body.digest))

    @api.get("/catalog")
    def get_catalog():
        return catalog()

    @api.get("/profiles")
    def profiles():
        return store.profiles()

    @api.get("/runs")
    def runs():
        return store.list()

    def dispatch(create):
        r = create()
        job = jobs.enqueue('integration',r['id'])
        return {'id':r['id'],'job_id':job['id']}

    @api.post("/runs", status_code=202)
    def start(body: Start):
        return dispatch(lambda: store.create(body.profile_id))

    @api.post("/local/plan")
    def local_plan(body: LocalPlan):
        from .discovery import prepare
        return prepare(store, body.repository, body.allow_registry, body.run_tests)

    @api.post("/local/runs", status_code=202)
    def local_start(body: LocalStart):
        from .discovery import create_from_plan
        return dispatch(lambda: create_from_plan(store, body.plan_id))

    @api.post("/import")
    def ingest(body: Import):
        with store.lease():
            return store.import_reports(
                body.request_id,
                body.name,
                body.context.model_dump(),
                [
                    {
                        "id": x.id,
                        "format": x.format,
                        "raw": x.content.encode(),
                        **({"environment": x.environment} if x.environment else {}),
                    }
                    for x in body.reports
                ],
                [x.model_dump() for x in body.rules],
            )

    @api.get("/runs/{rid}")
    def run(rid: str):
        return store.snapshot(rid)

    @api.post("/runs/{rid}/cancel")
    def cancel(rid: str):
        job = jobs.for_run(rid)
        return jobs.cancel(job['id']) if job else store.cancel(rid)

    @api.get("/runs/{rid}/artifacts/{aid}")
    def artifact(rid: str, aid: str):
        from urllib.parse import quote

        item, raw = store.artifact_bytes(rid, aid)
        return Response(
            raw,
            media_type="text/plain",
            headers={
                "Content-Disposition": "attachment; filename*=UTF-8''"
                + quote(Path(item["name"]).name),
                "Content-Security-Policy": "default-src 'none'; sandbox",
            },
        )

    @api.get("/runs/{rid}/export/{kind}")
    def download(rid: str, kind: str):
        if kind not in {"junit", "sarif", "markdown", "json"}:
            raise HTTPException(404, "格式不存在")
        r = store.snapshot(rid)
        from .runner import encode

        raw = encode(r) if kind == "json" else getattr(export, kind)(r)
        return Response(
            raw,
            media_type="application/octet-stream",
            headers={
                "Content-Disposition": f'attachment; filename="{rid}.{dict(junit="xml", sarif="sarif", markdown="md", json="json")[kind]}"'
            },
        )

    return api
