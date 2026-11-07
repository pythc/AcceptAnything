"""Append-only runs with independently hash-checked artifacts and idempotent imports."""

from contextlib import contextmanager
from datetime import datetime, timezone
import fcntl
import json
from pathlib import Path
import re
import subprocess
import uuid
from time import monotonic
from .formats import require, parse
from .gates import evaluate, opa_decide
from .models import Profile, Task, Context, Rule
from .registry import TOOLS, locks, ROOT
from .runner import encode, sha, frozen_source, execute, collect
from ..engine import OPA
from .storage import compact, expand, write_json, file_digest


def now():
    return datetime.now(timezone.utc).isoformat()


class IntegrationStore:
    def __init__(self, root=None):
        self.root = Path(root or ROOT / "var/integrations").resolve()
        self.root.mkdir(parents=True, exist_ok=True)
        for folder in ("runs", "profiles"):
            (self.root / folder).mkdir(exist_ok=True)

    @property
    def history(self):
        from ..history import RecordIndex
        if not hasattr(self, '_history'): self._history = RecordIndex(self.root)
        return self._history

    @contextmanager
    def lease(self):
        with (self.root / "worker.lock").open("a+") as lock:
            try:
                fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
            except BlockingIOError:
                raise ValueError("已有集成任务在运行")
            try:
                yield
            finally:
                fcntl.flock(lock, fcntl.LOCK_UN)

    def path(self, rid):
        require(
            isinstance(rid, str) and re.fullmatch(r"int-[0-9a-f]{16}", rid),
            "无效集成执行 ID",
        )
        p = self.root / "runs" / rid
        require(not p.is_symlink(), "执行目录非法")
        if not p.is_dir():
            raise FileNotFoundError("执行不存在")
        return p

    def save(self, r):
        p = self.path(r["id"])
        temporary = p / (".record-" + uuid.uuid4().hex)
        saved=compact(p,r)
        write_json(temporary,{"record": saved, "sha256": sha(encode(saved))})
        temporary.replace(p / "run.json")
        (self.root/'history.changed').touch()

    def read_metadata(self, rid):
        value = json.loads((self.path(rid) / "run.json").read_bytes())
        r = value["record"]
        require(
            value["sha256"] == sha(encode(r)) and r["id"] == rid, "执行记录摘要不符"
        )
        return r

    def read(self, rid):
        return expand(self.path(rid),self.read_metadata(rid))

    def artifact(self, r, name, raw):
        item = dict(
            id="art-" + uuid.uuid4().hex[:16], name=name, sha256=sha(raw), size=len(raw)
        )
        (self.path(r["id"]) / "artifacts" / item["id"]).write_bytes(raw)
        r["artifacts"].append(item)
        return item["id"]

    def artifact_file(self,r,name,path):
        import shutil
        aid="art-"+uuid.uuid4().hex[:16];target=self.path(r['id'])/'artifacts'/aid
        with Path(path).open('rb') as src,target.open('wb') as dst:shutil.copyfileobj(src,dst,1024*1024)
        item=dict(id=aid,name=name,size=target.stat().st_size,sha256=file_digest(target))
        r['artifacts'].append(item);return aid

    def artifact_json(self,r,name,value):
        path=self.path(r['id'])/('.json-'+uuid.uuid4().hex)
        try:
            write_json(path,value)
            return self.artifact_file(r,name,path)
        finally:path.unlink(missing_ok=True)

    def verified_artifact_path(self,r,aid):
        item=next((a for a in r['artifacts'] if a['id']==aid),None)
        if item is None:raise FileNotFoundError('证据不存在')
        require(re.fullmatch(r'art-[a-f0-9]{16}',aid),'证据身份无效')
        path=self.path(r['id'])/'artifacts'/aid
        require(not path.is_symlink() and path.stat().st_size==item['size'] and file_digest(path)==item['sha256'],'证据被修改')
        return item,path

    def artifact_bytes(self, rid, aid):
        r = self.read(rid)
        return self.artifact_bytes_for_record(r,aid)

    def artifact_bytes_for_record(self, r, aid):
        """Use one verified record snapshot; avoid reparsing it once per artifact."""
        item = next((x for x in r["artifacts"] if x["id"] == aid), None)
        if item is None:
            raise FileNotFoundError("证据不存在")
        p = self.path(r['id']) / "artifacts" / aid
        require(
            re.fullmatch(r"art-[a-f0-9]{16}", aid) and not p.is_symlink(),
            "证据路径无效",
        )
        raw = p.read_bytes()
        require(len(raw) == item["size"] and sha(raw) == item["sha256"], "证据被修改")
        return item, raw

    def verify(self, r):
        for a in r["artifacts"]:
            self.verified_artifact_path(r, a["id"])
        require(
            len({a["id"] for a in r["artifacts"]}) == len(r["artifacts"]),
            "证据身份重复",
        )
        byid = {a["id"]: a for a in r["artifacts"]}
        for task in r["tasks"]:
            if task["state"] == "completed":
                require(task.get("report_ref") in byid, "报告证据缺失")
                _, raw = self.artifact_bytes_for_record(r, task["report_ref"])
                require(
                    parse(task["format"], raw) == task["report"],
                    "归一化结果与原始报告不符",
                )
        if r.get('test_plan'):
            from ..planning.execution import verify_archived
            verify_archived(self,r)
            if r.get('remote_source') or r['test_plan'].get('remote_source'):
                from ..remote import verify_archived as verify_remote
                verify_remote(self,r)
        if r.get('automatic_plan'):
            from ..automatic import verify_archived
            verify_archived(self,r)
        if r.get('universal_plan'):
            from ..universal.service import verify_archived
            verify_archived(self,r)
        if r.get('finding_review_ref'):
            from .adjudication import load
            load(self,{**r,'integrity':True})
        return True

    def snapshot(self, rid):
        from ..history import stamp
        record_path = self.path(rid) / 'run.json'
        before = stamp(record_path)
        r = self.read(rid)
        r["recorded_decision"] = r.get("decision", "inconclusive")
        try:
            r["integrity"] = self.verify(r)
        except (OSError, ValueError, KeyError) as exc:
            r["integrity"] = False
            r["decision"] = "inconclusive"
            r["errors"] = [*r.get("errors", []), str(exc)]
        from ..results import project
        r['result_contract'] = project(r, verified=r['integrity'])
        r['result_contract']['gate']['recorded_decision'] = r['recorded_decision']
        r['decision'] = r['result_contract']['gate']['decision']
        self.history.verified(rid,record_path,r['integrity'],expected_stamp=before)
        return r

    def sync_history(self, *, max_age=0):
        return self.history.sync((self.root/'runs').glob('int-*/run.json'), self.metadata_brief,max_age=max_age)

    def metadata_brief(self, rid):
        r = self.read_metadata(rid)
        # Only the frozen summary payload is needed. Do not parse every report,
        # re-run classifiers or traverse the frozen source for a list request.
        thin = {k:v for k,v in r.items() if k not in {'universal_plan','universal_generation','tasks'}}
        thin['tasks'] = []
        review = expand(self.path(rid),thin).get('finding_review', {})
        r = {**r, 'universal_generation': {}}
        counts = review.get('summary')
        brief = {k:r.get(k) for k in ['id','name','profile_id','status','decision','created_at','finished_at','mode']}
        context = r.get('context') or {}
        brief['context'] = {**context,'files':[],'file_count':len(context.get('files',[]))}
        catalogue = self.catalogue_brief(r, counts=counts, metadata_only=True) if r.get('onboarding_plan') and (r.get('profile_id') or '').startswith('local-') else None
        return brief,catalogue,[]

    def list(self):
        self.sync_history()
        return self.history.list()

    def register(self, data):
        profile = Profile.model_validate(data)
        collect(profile.repository, profile.files)
        require(all(t.tool in TOOLS for t in profile.tasks), "有未注册执行器")
        for t in profile.tasks:
            require(
                t.network == "none" or TOOLS[t.tool]["registry_network"],
                "执行器不允许外网",
            )
        path = self.root / "profiles" / (profile.id + ".json")
        raw = encode(profile.model_dump())
        require(not path.is_symlink(), "配置路径非法")
        if path.exists():
            require(path.read_bytes() == raw, "已登记配置不可覆盖；使用新版本 ID")
        else:
            path.write_bytes(raw)
        return profile.id

    def local_briefs(self):
        self.sync_history()
        return self.history.list(catalogue=True)

    def catalogue_brief(self,r, *, counts=None, metadata_only=False):
        from ..source import repository_id
        context=r['context']; repository=context['repository']
        commit=context.get('revision')
        if commit=='uncommitted': commit=None
        source=dict(schema_version=1,provenance='captured',captured_at=r['created_at'],
            repository=dict(id=repository_id(repository),name=Path(repository).name,path=repository,
                kind='git' if commit or context.get('branch') else 'directory',branch=context.get('branch'),commit=commit,
                remote=None,scoped_changes=None,untracked=None),
            target=dict(name=r['name'],variant='repository',kind='repository-checks',environment=context['environment'],url=None),
            scope=dict(kind='files',description=context['scope'],files=[],file_count=len(context['files']),check_count=len(r['tasks'])),
            snapshot=dict(algorithm='sha256',digest=context['snapshot_digest']),
            tooling=dict(model=(', '.join(sorted({b['connection']['actual_model'] for b in r.get('universal_generation',{}).get('batches',[]) if b.get('connection')})) or (r.get('test_plan') or r.get('automatic_plan') or {}).get('planner',{}).get('model')),executors=list(dict.fromkeys(t['tool'] for t in r['tasks'])),versions={},gate='OPA',opa_image=OPA))
        if r.get('remote_source'):
            from ..remote import repository_fields
            source['repository'].update(repository_fields(r['remote_source']))
        result=dict(id=r['id'],mode='repository',label=r['name'],status=r['status'],decision=r['decision'],
            created_at=r['created_at'],finished_at=r['finished_at'],source=source,
            check_count=sum(t['state'] in {'completed','error','cancelled'} for t in r['tasks']),
            findings_count=None,
            artifact_count=len(r['artifacts']),baseline_version=r['profile']['version'],
            report_url=f"/api/integrations/runs/{r['id']}/export/markdown")
        if not metadata_only:
            from .adjudication import load
            counts=load(self,r)['summary']
        if counts is not None: result.update(findings_count=counts['actionable'],finding_counts=counts)
        return result

    def profiles(self):
        return [
            Profile.model_validate_json(p.read_bytes()).model_dump()
            for p in sorted((self.root / "profiles").glob("*.json"))
            if not p.is_symlink()
        ]

    def create(self, profile_id, prepared_plan=None):
        require(re.fullmatch(r"[a-z][a-z0-9-]{0,63}", profile_id), "无效项目 ID")
        path = self.root / "profiles" / (profile_id + ".json")
        require(not path.is_symlink(), "配置路径非法")
        profile = Profile.model_validate_json(path.read_bytes())
        if any(t.tool == 'acceptance-generated' or t.tool.startswith(('auto-go-','universal-')) for t in profile.tasks):
            require(prepared_plan is not None and prepared_plan['profile'] == profile.model_dump(), '生成用例必须通过已确认方案启动；请重新生成并确认方案')
        r = self.new(profile.name, "executor")
        p = self.path(r["id"])
        self.stage(r, "冻结输入", "running")
        try:
            source = frozen_source(profile.repository, profile.files, p / "source")
            recipes_dir = p / "recipes"
            recipes_dir.mkdir()
            for file in [
                ROOT / "acceptance/recipes/assessment/njsscan-rules.json",
                *(ROOT / "integrations/images").glob("with-service.*"),
            ]:
                (recipes_dir / file.name).write_bytes(file.read_bytes())
                self.artifact(r, "recipe/" + file.name, file.read_bytes())
            r["context"] = {
                **source,
                "environment": profile.environment,
                "scope": profile.scope,
            }
            r.update(
                profile_id=profile.id,
                profile=profile.model_dump(),
                images=locks(),
                rules_config=[x.model_dump() for x in profile.rules],
                exclusions=[x.model_dump() for x in profile.exclusions],
                baseline_id=profile.baseline,
            )
            r["tasks"] = [
                dict(
                    **t.model_dump(),
                    state="queued",
                    environment=profile.environment,
                    format=TOOLS[t.tool]["format"],
                    started_at=None,
                    finished_at=None,
                    duration_ms=None,
                    artifacts=[],
                )
                for t in profile.tasks
            ]
            self.artifact(r, "frozen-profile.json", encode(profile.model_dump()))
            recipes = {
                str(f.relative_to(ROOT)): sha(f.read_bytes())
                for f in sorted((ROOT / "acceptance/integrations").glob("*.py"))
            }
            recipes.update(
                {
                    str(f.relative_to(ROOT)): sha(f.read_bytes())
                    for f in sorted(
                        (ROOT / "integrations/images").glob("with-service.*")
                    )
                }
            )
            recipes["acceptance/integrations/gates.rego"] = sha(
                (ROOT / "acceptance/integrations/gates.rego").read_bytes()
            )
            r["adapter_digest"] = sha(encode(recipes))
            self.artifact(r, "adapters-manifest.json", encode(recipes))
            self.artifact(r, "source-manifest.json", encode(source))
            from .adjudication import policy
            current_policy=policy(self,r['context'])
            if prepared_plan and prepared_plan.get('finding_review_policy'):
                require(prepared_plan['finding_review_policy']==current_policy,'复核策略变化，请重新确认')
            r['review_policy_ref']=self.artifact(r,'finding-review-policy.json',encode(current_policy))
            self.artifact(r, "toolchain.json", encode(r["images"]))
            r["scope_digest"] = sha(
                encode(
                    {
                        "repository": source["repository"],
                        "environment": profile.environment,
                        "scope": profile.scope,
                        "tasks": [t.model_dump() for t in profile.tasks],
                        "images": r["images"],
                        "rules": r["rules_config"],
                        "review_policy": policy(self,r['context']),
                    }
                )
            )
            self.stage(
                r, "冻结输入", "completed", str(len(source["files"])) + " 个文件已冻结"
            )
            return r
        except Exception:
            r.update(status="error", errors=["冻结输入失败"], finished_at=now())
            self.save(r)
            raise

    def new(self, name, mode, rid=None):
        rid = rid or "int-" + uuid.uuid4().hex[:16]
        p = self.root / "runs" / rid
        p.mkdir()
        (p / "artifacts").mkdir()
        r = dict(
            id=rid,
            name=name,
            mode=mode,
            status="queued",
            decision="inconclusive",
            created_at=now(),
            finished_at=None,
            context=None,
            tasks=[],
            rules=[],
            rules_config=[],
            artifacts=[],
            pipeline=[],
            errors=[],
            integrity=False,
            exclusions=[],
        )
        self.save(r)
        return r

    def stage(self, r, name, state, detail=""):
        existing = next(
            (
                s
                for s in reversed(r["pipeline"])
                if s["name"] == name and s["state"] == "running"
            ),
            None,
        )
        if existing and state != "running":
            existing.update(state=state, finished_at=now(), detail=detail)
            existing["duration_ms"] = round(
                (
                    datetime.fromisoformat(existing["finished_at"])
                    - datetime.fromisoformat(existing["started_at"])
                ).total_seconds()
                * 1000
            )
        else:
            r["pipeline"].append(
                dict(
                    name=name,
                    state=state,
                    started_at=now(),
                    finished_at=None,
                    duration_ms=None,
                    detail=detail,
                )
            )
        self.save(r)

    def cancel(self, rid):
        r = self.read(rid)
        require(r["status"] in {"queued", "running"}, "执行已经结束")
        (self.path(rid) / "cancel").touch()
        return {"id": rid, "cancel_requested": True}

    def finish(self, r):
        self.stage(r, "发现复核", "running")
        if not r.get('review_policy_ref'):
            from .adjudication import policy
            r['review_policy_ref']=self.artifact(r,'finding-review-policy.json',encode(policy(self,r.get('context',{}))))
        baseline = None
        if r.get("baseline_id"):
            baseline = self.snapshot(r["baseline_id"])
            require(
                baseline.get("scope_digest") == r.get("scope_digest"),
                "基线范围、工具、规则或环境不一致",
            )
        r["integrity"] = self.verify(r)
        from .adjudication import build,effective_tasks
        r['finding_review']=build(self,r)
        r['finding_review_ref']=self.artifact_json(r,'finding-review.json',r['finding_review'])
        evaluated_tasks=effective_tasks(r,r['finding_review'])
        r["rules"] = evaluate(r["rules_config"], evaluated_tasks, baseline)
        self.save(r)
        self.stage(r,'发现复核','completed',json.dumps(r['finding_review']['summary'],ensure_ascii=False))
        self.stage(r,'质量门禁','running')
        directory = self.path(r["id"]) / "gate"
        directory.mkdir()
        payload = {
            "integrity": r["integrity"],
            "tasks": evaluated_tasks,
            "finding_review": r['finding_review'],
            "rules": r["rules"],
        }
        if (r.get('test_plan') or {}).get('specification',{}).get('environment',{}).get('recipe')=='gmah-v1':
            from ..planning.gmah import completion
            r['recipe_completion']=completion(r)
            payload['recipe_complete']=r['recipe_completion']['complete']
        if r.get('automatic_plan'):
            from ..automatic import completion
            r['recipe_completion']=completion(r)
            payload['recipe_complete']=r['recipe_completion']['complete']
        if r.get('universal_plan'):
            from ..universal.service import completion
            r['recipe_completion']=completion(r)
            payload['recipe_complete']=r['recipe_completion']['complete']
        from ..results import gate_blockers, VERSION
        payload['result_contract_version'] = VERSION
        payload['contract_blockers'] = gate_blockers(r)
        payload['contract_ready'] = not payload['contract_blockers']
        r["decision"] = opa_decide(payload, directory, OPA)
        for p in directory.iterdir():
            self.artifact(r, p.name, p.read_bytes())
        self.stage(r, "质量门禁", "completed", r["decision"])
        r.update(
            status="cancelled"
            if any(t["state"] == "cancelled" for t in r["tasks"])
            else "completed",
            finished_at=now(),
        )
        self.save(r)

    def execute(self, rid):
        r = self.read(rid)
        p = self.path(rid)
        r["status"] = "running"
        self.save(r)
        try:
            for t in r["tasks"]:
                if (p / "cancel").exists() and t['tool'] not in {'auto-go-cleanup','universal-cleanup'}:
                    t.update(state="cancelled", error="已取消")
                    self.save(r)
                    continue
                start = monotonic()
                t.update(state="running", started_at=now())
                self.stage(r, t["id"], "running", t["tool"])
                output = p / "outputs" / t["id"]
                try:
                    if t['tool'].startswith('gmah-'):
                        require(locks()==r['images'], 'GMAH 执行镜像已变化，请重新确认方案')
                        if r.get('test_plan'):
                            from ..planning.execution import verify_plan_files
                            from ..planning.compiler import compiler_digest
                            verify_plan_files(self,r)
                            require(compiler_digest()==r['test_plan']['compiler_digest'], 'GMAH 配方已变化，请重新确认方案')
                    if t['tool'].startswith('universal-'):
                        from ..universal.service import execute as execute_universal
                        report,command=execute_universal(self,r,t,output,lambda: t['tool']!='universal-cleanup' and (p/'cancel').exists())
                    elif t['tool'].startswith('auto-go-'):
                        from ..automatic import execute as execute_automatic
                        report,command=execute_automatic(self,r,t,output,lambda: t['tool']!='auto-go-cleanup' and (p/'cancel').exists())
                    elif t['tool'] == 'acceptance-generated':
                        from ..planning.execution import execute_generated
                        report, command = execute_generated(self, r, t, output, lambda: (p/'cancel').exists())
                    else:
                        report, command = execute(
                            Task.model_validate({k: t[k] for k in Task.model_fields}),
                            p / "source",
                            output,
                            r["images"].get(TOOLS[t["tool"]]["image_key"], {}).get("id"),
                            lambda: (p / "cancel").exists(),
                        )
                    t.update(state="completed", report=report, command=command)
                except Exception as exc:
                    t.update(
                        state="cancelled" if (p / "cancel").exists() else "error",
                        error=str(exc)[:500],
                        failure={"code": "cancelled" if (p / "cancel").exists() else "environment_not_ready" if t['tool'] in {'universal-prepare', 'universal-service', 'universal-fixture'} else "model_service_error" if t['tool'] == 'universal-design' else "tool_error", "source": "executor", "exception_type": type(exc).__name__},
                    )
                for file in sorted(output.rglob("*")) if output.exists() else []:
                    if (
                        file.is_file()
                        and not file.is_symlink()
                        and file.resolve().is_relative_to(output.resolve())
                    ):
                        aid = self.artifact_file(r,t["id"] + "/" + str(file.relative_to(output)),file)
                        t["artifacts"].append(aid)
                        if (
                            file.name
                            == (
                                "report.xml"
                                if t["format"] in {"junit", "robot", "cobertura"}
                                else "report.json"
                            )
                            and file.parent == output
                        ):
                            t["report_ref"] = aid
                t.update(
                    finished_at=now(), duration_ms=round((monotonic() - start) * 1000)
                )
                self.stage(r, t["id"], t["state"], t.get("error", "报告已归一化"))
            self.finish(r)
        except Exception as exc:
            r.update(status="error", decision="inconclusive", finished_at=now())
            r["errors"].append(str(exc)[:500])
            for stage in r['pipeline']:
                if stage['state']=='running':stage.update(state='error',finished_at=r['finished_at'],detail=str(exc)[:500])
            self.save(r)
        return self.snapshot(rid)

    def import_reports(self, request_id, name, context, reports, rules):
        context = Context.model_validate(context).model_dump()
        rules = [Rule.model_validate(x).model_dump() for x in rules]
        require(re.fullmatch(r"[a-f0-9-]{36}", request_id), "导入需要 UUID request_id")
        require(
            len(reports)>0,
            "导入大小或数量超限",
        )
        ids = [x["id"] for x in reports]
        require(
            all(
                isinstance(x.get("environment", context["environment"]), str)
                and 0 < len(x.get("environment", context["environment"])) <= 160
                for x in reports
            ),
            "报告环境标签无效",
        )
        require(len(ids) == len(set(ids)), "重复报告身份")
        require(
            rules
            and all(set(x["tasks"]) <= set(ids) for x in rules)
            and set().union(*(set(x["tasks"]) for x in rules)) == set(ids),
            "导入门禁没有覆盖全部报告",
        )
        digest = sha(
            encode(
                {
                    "name": name,
                    "context": context,
                    "reports": [
                        {k: v for k, v in x.items() if k != "raw"}
                        | {"sha256": sha(x["raw"])}
                        for x in reports
                    ],
                    "rules": rules,
                }
            )
        )
        rid = "int-" + sha(request_id.encode())[:16]
        if (self.root / "runs" / rid).exists():
            r = self.read(rid)
            require(r.get("request_digest") == digest, "同一 request_id 对应不同内容")
            return self.snapshot(rid)
        r = self.new(name, "import", rid)
        r.update(
            context=context, rules_config=rules, request_digest=digest, status="running"
        )
        self.artifact(
            r,
            "import-manifest.json",
            encode(
                {
                    "context": context,
                    "rules": rules,
                    "provenance": "caller-supplied; not locally executed",
                    "reports": [
                        {k: v for k, v in row.items() if k != "raw"}
                        | {"sha256": sha(row["raw"])}
                        for row in reports
                    ],
                }
            ),
        )
        self.stage(r, "报告导入", "running")
        for row in reports:
            require(re.fullmatch(r"[a-z][a-z0-9-]{0,63}", row["id"]), "报告 ID 无效")
            t = dict(
                id=row["id"],
                tool=row["format"],
                format=row["format"],
                environment=row.get("environment", context["environment"]),
                state="error",
                artifacts=[],
                started_at=now(),
            )
            start = monotonic()
            t["report_ref"] = self.artifact(r, row["id"] + "/report", row["raw"])
            t["artifacts"].append(t["report_ref"])
            try:
                t.update(report=parse(row["format"], row["raw"]), state="completed")
            except Exception as exc:
                t["error"] = str(exc)[:500]
            t.update(finished_at=now(), duration_ms=round((monotonic() - start) * 1000))
            r["tasks"].append(t)
        self.stage(r, "报告导入", "completed")
        try:
            self.finish(r)
        except Exception as exc:
            r.update(status="error", errors=[str(exc)[:500]], finished_at=now())
            self.save(r)
        return self.snapshot(rid)

    def recover(self, exclude=(), candidates=(), scan_orphans=True):
        # Called only under the global worker lease; unrelated Docker workloads are untouched.
        errors = {}
        pending = set(candidates) - set(exclude)
        for path in (self.root/'runs').glob('int-*/run.json') if scan_orphans else ():
            try:
                item=self.read_metadata(path.parent.name)
            except (OSError,ValueError,KeyError,TypeError):
                continue  # Preserve damaged records for explicit audit, never release them.
            # Creation and durable enqueue are distinct writes. A queued record
            # has not executed and must not be killed by a startup snapshot race.
            if item["id"] not in exclude and item.get("status") == "running":
                pending.add(item['id'])
        for rid in pending:
            try:self.recover_one(rid)
            except Exception as exc:errors[rid] = str(exc)
        return errors

    def recover_one(self, rid):
        require(isinstance(rid,str) and re.fullmatch(r'int-[0-9a-f]{16}',rid), '无效恢复身份')
        filters=['--filter','label=acceptance.integration=true','--filter','label=acceptance.run='+rid]
        for listing,removal in [(['ps','-aq'],['rm','-f']),(['network','ls','-q'],['network','rm']),(['volume','ls','-q'],['volume','rm'])]:
            ids=subprocess.check_output(['docker',*listing,*filters],text=True,timeout=10).split()
            if ids:subprocess.run(['docker',*removal,*ids],stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL,timeout=20,check=True)
        try:r=self.read(rid)
        except (OSError,ValueError,KeyError,TypeError):
            # Cleanup succeeded. The job ledger can record interruption without
            # rewriting a damaged envelope or inventing its missing payloads.
            return
        if r['status'] != 'running': return
        r.update(status='error',decision='inconclusive',finished_at=now())
        r['errors'].append('执行进程中断；创建新记录复验')
        r['interruption']={'code':'interrupted','recovered_at':r['finished_at'],'cleanup':'completed'}
        for t in r['tasks']:
            if t['state'] in {'queued','running'}:
                t.update(state='error',error='执行进程中断',failure={'code':'interrupted','source':'recovery'},finished_at=r['finished_at'],duration_ms=None)
        for stage in r['pipeline']:
            if stage['state']=='running':stage.update(state='error',finished_at=r['finished_at'],duration_ms=None,detail='执行进程中断；实际结束时间未采集')
        self.save(r)
