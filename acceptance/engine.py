"""Frozen criteria, mature executors, immutable run directories and raw evidence."""
from __future__ import annotations

import base64
from datetime import datetime, timezone
import fcntl
import hashlib
import json
import mimetypes
import os
from pathlib import Path
import re
import signal
import shlex
import shutil
import subprocess
import uuid

import jsonschema
from contextlib import contextmanager
from time import monotonic

from acceptance.presentation import case_plans, inspections
from acceptance import source
from acceptance.validation import Reader, bandit_status, validate_results
from acceptance.progress import checks, register_cases, activity, end_activity

ROOT = Path(__file__).resolve().parents[1]
_bundled_node = Path.home() / ".cache/codex-runtimes/codex-primary-runtime/dependencies/node/bin/node"
NODE = Path(os.environ.get("ACCEPTANCE_NODE", str(_bundled_node) if _bundled_node.is_file() else shutil.which("node") or "node"))
OPA = "openpolicyagent/opa@sha256:35615020f7224b7da7ccfe76dc3cb93bc43aab8a3b42099f32edc42cdbca27bf"
SUITE = ROOT / "validation/tests/acceptance.spec.mjs"
BASELINE = ROOT / "standards/local-v2.json"
STAGES = {"L1": "代码与依赖", "L2": "接口与权限", "L3": "用户业务流程", "L4": "性能与恢复"}


def digest(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def now() -> str:
    return datetime.now(timezone.utc).isoformat()


def encode(value) -> bytes:
    return (json.dumps(value, ensure_ascii=False, indent=2) + "\n").encode()


def baseline():
    raw = BASELINE.read_bytes()
    if digest(raw) != BASELINE.with_suffix(".sha256").read_text().strip():
        raise ValueError("冻结标准摘要不匹配")
    value = json.loads(raw)
    jsonschema.validate(value, json.loads((ROOT / "standards/baseline.schema.json").read_text()))
    ids = [c["id"] for c in value["criteria"]]
    if len(set(ids)) != len(ids):
        raise ValueError("重复验收标准 ID")
    return {**value, "digest": digest(raw)}


def historical_baseline(run):
    """Trust only explicitly registered contract revisions, not today's files."""
    value = run["baseline"]
    registry = json.loads((ROOT / "standards/versions/registry.json").read_text())
    entry = registry[value["digest"]]
    raw = (ROOT / "standards/versions" / entry["file"]).read_bytes()
    if digest(raw) != value["digest"] or {**json.loads(raw), "digest": digest(raw)} != value:
        raise ValueError("历史标准与已登记版本不符")
    return value


def flatten(suites):
    for suite in suites:
        yield from suite.get("specs", [])
        yield from flatten(suite.get("suites", []))


class Store:
    def __init__(self, root: Path | None = None):
        self.root = (root or Path(os.environ.get("ACCEPTANCE_DATA", str(ROOT / "var")))).resolve()
        self.runs = self.root / "runs"
        self.runs.mkdir(parents=True, exist_ok=True)

    @property
    def history(self):
        from .history import RecordIndex
        if not hasattr(self, '_history'): self._history = RecordIndex(self.root)
        return self._history

    def path(self, run_id):
        if not re.fullmatch(r"run-[0-9a-f]{12}", run_id):
            raise FileNotFoundError("执行不存在")
        p = self.runs / run_id
        if not p.is_dir() or p.is_symlink():
            raise FileNotFoundError("执行不存在")
        return p

    def save(self, run):
        p = self.path(run["id"])
        temp = p / (".record-" + uuid.uuid4().hex)
        temp.write_bytes(encode({"record": run, "record_digest": digest(encode(run))}))
        temp.replace(p / "run.json")
        (self.root/'history.changed').touch()

    def read(self, run_id):
        value = json.loads((self.path(run_id) / "run.json").read_text())
        if not isinstance(value, dict):
            raise ValueError("执行记录不是有效对象")
        # Records created during the first local integration calibration are legacy.
        # They are readable for audit, but never treated as verified release records.
        if "record" not in value:
            value["decision"] = "inconclusive"
            value["reasons"] = ["初次校准记录未封存；需重新执行"]
            value["legacy"] = True
            return value
        if value.get("record_digest") != digest(encode(value["record"])):
            raise ValueError("执行记录内容校验失败")
        if not isinstance(value["record"], dict):
            raise ValueError("执行记录结构无效")
        if value["record"].get("id") != run_id:
            raise ValueError("执行记录与目录身份不符")
        return value["record"]

    def list(self):
        self.sync_history()
        return self.history.list()

    def sync_history(self, *, max_age=0):
        return self.history.sync(self.runs.glob('run-*/run.json'), self.metadata_brief,max_age=max_age)

    def metadata_brief(self, rid):
        from copy import deepcopy
        r = self.read(rid)
        ctx = deepcopy(source.context(r))
        ctx['scope']['file_count'] = len(ctx['scope'].get('files',[]))
        ctx['scope']['files'] = []
        item = {k:r[k] for k in ('id','mode','status','decision','created_at','label','finished_at')}
        item.update(source=ctx,check_count=len(r['results']),findings_count=len(r['findings']),
            artifact_count=len(r['artifacts']),baseline_version=r['baseline']['version'])
        children = [c['id'] for c in r.get('workflow',{}).get('children',[])]
        if children:
            # These old envelopes did not freeze aggregate child counts. The
            # index must not mislabel parent-only counts as complete totals.
            item.update(check_count=None,findings_count=None,artifact_count=None,
                        count_note='旧组合记录未封存聚合计数；打开详情核对')
        return item,dict(item),children

    def recover(self, exclude=(), candidates=(), scan_orphans=True):
        # Called only while holding the process-wide runner lease at startup.
        errors = {}
        paths = self.runs.glob('run-*/run.json') if scan_orphans else (self.runs/rid/'run.json' for rid in candidates if re.fullmatch(r'run-[0-9a-f]{12}',rid))
        for path in paths:
            try:
                brief=self.read(path.parent.name)
            except (OSError,ValueError,KeyError,TypeError):
                continue  # Startup recovery is not an audit of terminal evidence.
            if brief["id"] not in exclude and brief["status"] == "running":
                r = self.read(brief["id"])
                r.update(status="error", decision="inconclusive", finished_at=now(), reasons=["服务中断；需创建新的执行记录复验"])
                for stage in r.get("pipeline", []):
                    if stage["status"] == "running":
                        stage.update(status="error", finished_at=r["finished_at"], detail="服务中断，未完成此阶段")
                for check in r.get("check_runs", []):
                    if check["status"] == "running":
                        check.update(status="error", finished_at=r["finished_at"], duration_ms=None)
                if r.get("current_activity"):
                    r["current_activity"].update(finished_at=r["finished_at"], interrupted=True)
                r["active_layer"] = None
                if r["baseline"].get("recipe"):
                    try:
                        from .expanded import recover_runtime
                        recover_runtime(self, r)
                        r["reasons"].append("本次中断执行的容器和网络已回收")
                    except Exception as exc:
                        errors[r['id']] = '本次环境清理尚未确认：'+str(exc)[:240]
                        continue  # Retain running state so the next recovery retries cleanup.
                self.save(r)
        return errors

    def create(self, mode):
        if mode not in ("buggy", "fixed"):
            raise ValueError("仅支持固定的本地演示夹具")
        b = baseline()
        if digest(SUITE.read_bytes()) != b["suite_digest"]:
            raise ValueError("冻结测试集发生变化，需形成新测试版本")
        if digest((ROOT / "validation/fixture.py").read_bytes()) != b["fixture_digest"]:
            raise ValueError("演示目标实现发生变化，需形成新基线")
        if digest((ROOT / "acceptance/policy.rego").read_bytes()) != b["policy_digest"]:
            raise ValueError("冻结门禁策略发生变化")
        if digest((ROOT / "validation/static-samples" / (mode + ".py")).read_bytes()) != b["sample_digests"][mode]:
            raise ValueError("静态检测目标发生变化")
        run_id = "run-" + uuid.uuid4().hex[:12]
        p = self.runs / run_id
        p.mkdir()
        (p / "artifacts").mkdir()
        run = {"id": run_id, "mode": mode, "label": "缺陷版" if mode == "buggy" else "修正版", "status": "queued", "decision": "inconclusive", "created_at": now(), "finished_at": None,
               "baseline": b, "suite_digest": b["suite_digest"], "target_digest": digest(encode({"fixture": b["fixture_digest"], "mode": mode})),
               "results": [], "findings": [], "artifacts": [], "reasons": [], "commands": [], "integrity": False,
               "active_layer": None, "layer_runs": [], "pipeline": [],
               "limits": ["本地夹具；结论仅适用于当前八项基线", "性能与恢复未执行", "证据为本机采集，未接入可信签名"]}
        run["source_context"] = source.capture(ROOT, mode, b["criteria"], OPA)
        run["record_version"] = 2
        run["inputs"] = {}
        for key, name, data in [
            ("baseline", "frozen-standard.json", BASELINE.read_bytes()),
            ("suite", "frozen-suite.mjs", SUITE.read_bytes()),
            ("fixture", "frozen-target.py", (ROOT / "validation/fixture.py").read_bytes()),
            ("policy", "frozen-policy.rego", (ROOT / "acceptance/policy.rego").read_bytes()),
            ("sample", "frozen-sample.py", (ROOT / "validation/static-samples" / (mode + ".py")).read_bytes()),
        ]:
            run["inputs"][key] = self.artifact(run, name, data)
        self.save(run)
        return run

    def artifact(self, run, name, data, criterion_id=None, media_type=None):
        artifact_id = "art-" + uuid.uuid4().hex[:12]
        filename = artifact_id + Path(name).suffix
        (self.path(run["id"]) / "artifacts" / filename).write_bytes(data)
        item = {"id": artifact_id, "name": Path(name).name, "file": filename, "sha256": digest(data), "size": len(data), "media_type": media_type or mimetypes.guess_type(name)[0] or "application/octet-stream", "criterion_id": criterion_id, "collected_at": now()}
        run["artifacts"].append(item)
        return artifact_id

    def artifact_bytes(self, run, artifact_id):
        item = next((a for a in run["artifacts"] if a["id"] == artifact_id), None)
        if not item:
            raise FileNotFoundError("证据未登记")
        path = self.path(run["id"]) / "artifacts" / item["file"]
        if path.is_symlink() or path.resolve().parent != (self.path(run["id"]) / "artifacts").resolve():
            raise ValueError("非法证据路径")
        data = path.read_bytes()
        if len(data) != item["size"] or digest(data) != item["sha256"]:
            raise ValueError("证据文件已改变，校验失败")
        return item, data

    def check_integrity(self, run, reader=None):
        reader = reader or Reader(self, run)
        if run.get("project_id"):
            from .projects import integrity
            return integrity(self, run, reader)
        try:
            b = historical_baseline(run)
            if run["suite_digest"] != b["suite_digest"]:
                return False
            if run.get("record_version", 1) >= 2:
                expected_inputs = {"baseline": b["digest"], "suite": b["suite_digest"], "fixture": b["fixture_digest"], "policy": b["policy_digest"], "sample": b["sample_digests"][run["mode"]]}
                if set(run["inputs"]) != set(expected_inputs) or any(digest(reader.read(run["inputs"][key])[1]) != value for key, value in expected_inputs.items()):
                    return False
            if run["target_digest"] != digest(encode({"fixture": b["fixture_digest"], "mode": run["mode"]})):
                return False
            if run.get("source_context") and not source.matches(run["source_context"], b, run["mode"]):
                return False
            if run.get("source_artifact"):
                if json.loads(reader.read(run["source_artifact"])[1]) != run["source_context"]:
                    return False
            artifact_ids = {a["id"] for a in run["artifacts"]}
            artifacts = {a["id"]: a for a in run["artifacts"]}
            criteria = {c["id"]: c for c in b["criteria"]}
            if len(artifact_ids) != len(run["artifacts"]):
                return False
            for a in run["artifacts"]:
                reader.read(a["id"])
            for r in run["results"]:
                if not set(r["evidence_refs"]).issubset(artifact_ids):
                    return False
                c = criteria.get(r["criterion_id"])
                if not c or any(r.get(k) != c[k] for k in ("case_id", "layer", "expected")):
                    return False
                if any(artifacts[ref]["criterion_id"] not in (None, r["criterion_id"]) for ref in r["evidence_refs"]):
                    return False
            return bool(run["artifacts"])
        except (OSError, ValueError, KeyError, TypeError, jsonschema.ValidationError):
            return False

    def applicability(self, run):
        if run.get("project_id"):
            from .projects import applicability
            return applicability(self, run)
        try:
            b = baseline()
            matches = run["baseline"] == b and digest(SUITE.read_bytes()) == b["suite_digest"] and digest((ROOT / "validation/fixture.py").read_bytes()) == b["fixture_digest"] and digest((ROOT / "acceptance/policy.rego").read_bytes()) == b["policy_digest"] and digest((ROOT / "validation/static-samples" / (run["mode"] + ".py")).read_bytes()) == b["sample_digests"][run["mode"]]
            return {"matches": matches, "reason": "与当前验收输入一致" if matches else "当前标准或目标已变化；历史结论不能用于当前版本放行"}
        except (OSError, ValueError, KeyError, TypeError, jsonschema.ValidationError):
            return {"matches": False, "reason": "当前验收输入无法核实"}

    def snapshot(self, run_id, details=True):
        run = self.read(run_id)
        reader = Reader(self, run)
        validation = validate_results(self, run, reader)
        run["recorded_decision"] = run["decision"]
        run["applicability"] = self.applicability(run)
        run["validation"] = {"valid": validation["valid"], "errors": validation["errors"], "validator_version": "1"}
        if run["status"] in ("completed", "error", "incomplete"):
            run["integrity"] = self.check_integrity(run, reader)
            invalid = not run["integrity"] or not validation["valid"] or run.get("legacy")
            if run["decision"] == "allow" and any(r["status"] != "passed" for r in run["results"]):
                invalid = True
            if invalid:
                run["decision"] = "inconclusive"
                run["reasons"] = ["标准或证据校验不通过；不能据此放行", *validation["errors"]]
                for stage in run.get("pipeline", []):
                    if stage["id"] == "gate":
                        stage.update(recorded_status=stage["status"], status="error", detail=run["reasons"][0])
        for result in run["results"]:
            check = validation["checks"].get(result["criterion_id"], {})
            result["verified"] = check.get("valid", False)
            if not result["verified"]:
                result.update(reported_status=result["status"], status="error", validation_error=check.get("reason", "检查结果无法核实"))
        run["findings"] = [f for f in run["findings"] if validation["checks"].get(f["criterion_id"], {}).get("valid")]
        run["layers"] = []
        for key, name in STAGES.items():
            results = [r for r in run["results"] if r["layer"] == key]
            expected = {c["id"] for c in run["baseline"]["criteria"] if c["layer"] == key and c["required"]}
            state = "not_run"
            if results:
                state = "failed" if any(r["status"] == "failed" for r in results) else "passed" if all(r["status"] == "passed" for r in results) else "blocked" if all(r["status"] in ("passed", "blocked") for r in results) else "error"
                if {r["criterion_id"] for r in results} != expected and state == "passed":
                    state = "error"
            if run.get("active_layer") == key and run["status"] == "running":
                state = "running"
            run["layers"].append({"id": key, "name": name, "status": state, "count": len(results), "failed": sum(r["status"] == "failed" for r in results)})
        if details:
            run["inspections"] = inspections(self, run, validation, reader)
            run["case_plans"] = case_plans(run)
        run["source"] = source.context(run)
        run.update(check_count=len(run["results"]), findings_count=len(run["findings"]), artifact_count=len(run["artifacts"]), baseline_version=run["baseline"]["version"])
        return run

    @contextmanager
    def stage(self, run, stage_id, detail):
        item = {"id": stage_id, "status": "running", "started_at": now(), "finished_at": None, "detail": detail}
        run.setdefault("pipeline", []).append(item)
        started = monotonic()
        self.save(run)
        try:
            yield item
            if item["status"] == "running":
                item["status"] = "passed"
        except Exception as exc:
            item.update(status="error", detail=str(exc)[:600])
            raise
        finally:
            item.update(finished_at=now(), duration_ms=round((monotonic() - started) * 1000, 2))
            self.save(run)

    def collect_findings(self, run):
        criteria = {c["id"]: c for c in run["baseline"]["criteria"]}
        verified = validate_results(self, run)["checks"]
        run["findings"] = []
        for result in run["results"]:
            if result["status"] == "failed" and verified.get(result["criterion_id"], {}).get("valid"):
                c = criteria[result["criterion_id"]]
                run["findings"].append({"id": "F-" + str(len(run["findings"]) + 1).zfill(3), "title": c["title"], "severity": c["severity"], "verification": "observed", "impact": c["impact"], **result})

    def command(self, run, label, argv, timeout=75, env=None):
        activity(self, run, label)
        started_at = now()
        p = subprocess.Popen([str(x) for x in argv], cwd=ROOT, env=env, stdout=subprocess.PIPE, stderr=subprocess.PIPE, start_new_session=True)
        timed_out = False
        try:
            stdout, stderr = p.communicate(timeout=timeout)
        except subprocess.TimeoutExpired:
            timed_out = True
            try:
                os.killpg(p.pid, signal.SIGTERM)
            except ProcessLookupError:
                pass
            try:
                stdout, stderr = p.communicate(timeout=5)
            except subprocess.TimeoutExpired:
                os.killpg(p.pid, signal.SIGKILL)
                stdout, stderr = p.communicate(timeout=5)
        ref = self.artifact(run, label + ".log", stdout + stderr, media_type="text/plain")
        run["commands"].append({"name": label, "argv": [str(x) for x in argv], "started_at": started_at, "finished_at": now(), "exit_code": p.returncode, "evidence_ref": ref})
        end_activity(self, run)
        if timed_out:
            raise RuntimeError(label + " 执行超时；已终止本次执行器进程组")
        return p.returncode, ref

    def parse_playwright(self, run, report, report_path):
        report_name = "playwright-" + report_path.name + "-results.json"
        report_ref = self.artifact(run, report_name, (report_path / "results.json").read_bytes(), media_type="application/json")
        criteria = {c["id"]: c for c in run["baseline"]["criteria"] if c["executor"] == "playwright"}
        for spec in flatten(report.get("suites", [])):
            cid = spec.get("title", "").split(":", 1)[0]
            if cid not in criteria:
                continue
            c = criteria[cid]
            tests = spec.get("tests", [])
            attempts = tests[0].get("results", []) if len(tests) == 1 else []
            status = attempts[0].get("status", "error") if len(attempts) == 1 else "error"
            if status not in ("passed", "failed", "skipped"):
                status = "error"
            observed = attempts[0] if attempts else {}
            refs = [self.artifact(run, cid + "-result.json", encode({"title": spec.get("title"), "status": status, "result": observed, "source_report": report_ref}), cid, "application/json")]
            for a in observed.get("attachments", []):
                if a.get("path"):
                    path = Path(a["path"]).resolve()
                    # Only accept artifacts generated inside this attempt's report directory.
                    if not path.is_relative_to(report_path.resolve()) or not path.is_file() or path.is_symlink():
                        status = "error"
                        continue
                    refs.append(self.artifact(run, path.name, path.read_bytes(), cid, a.get("contentType")))
                elif a.get("body"):
                    refs.append(self.artifact(run, a["name"] + ".json", base64.b64decode(a["body"], validate=True), cid, a.get("contentType")))
            error = observed.get("error", {}).get("message", "")
            error = re.sub(r"\x1b\[[0-9;]*m", "", error)
            run["results"].append({"criterion_id": cid, "case_id": c["case_id"], "layer": c["layer"], "attempt": 1, "status": status, "duration_ms": observed.get("duration", 0), "expected": c["expected"], "actual": error or ("断言通过" if status == "passed" else "未取得有效断言结果"), "evidence_refs": refs})

    def evaluate(self, run):
        reader = Reader(self, run)
        validation = validate_results(self, run, reader)
        content_integrity = self.check_integrity(run, reader)
        policy = ROOT / "acceptance/policy.rego"
        if content_integrity:
            if run.get("inputs", {}).get("policy"):
                item, _ = reader.read(run["inputs"]["policy"])
                policy = self.path(run["id"]) / "artifacts" / item["file"]
            else:
                policy = ROOT / "standards/versions" / (run["baseline"]["version"] + ".rego")
            if digest(policy.read_bytes()) != run["baseline"]["policy_digest"]:
                raise ValueError("历史门禁策略摘要不符")
        payload = {"content_integrity": content_integrity, "integrity": content_integrity and validation["valid"], "validation": {"valid": validation["valid"], "errors": validation["errors"]}, "complete": run["status"] == "completed", "required": [c["id"] for c in run["baseline"]["criteria"] if c["required"]], "results": [{**r, "verified": validation["checks"].get(r["criterion_id"], {}).get("valid", False)} for r in run["results"]]}
        if run.get('workflow'):
            from .workflow import coverage
            from . import reviews
            coverage_result=coverage(self,run)
            payload['workflow']=coverage_result
            payload['complete'] = payload['complete'] and coverage_result['complete']
            payload['integrity'] = payload['integrity'] and not coverage_result['errors']
            catalog=reviews.frozen(self,run)
            reviewed=[]
            if catalog:
                for row in payload['results']:
                    review=reviews.native(self,run,row,catalog)
                    if review:
                        reviewed.append(dict(criterion_id=row['criterion_id'],raw_status=row['status'],review=review))
                        if row['status']=='failed' and review['non_blocking']:
                            row.update(raw_status=row['status'],status='passed',review_ref=run['workflow']['review_ref'])
                payload['adjudication']=reviewed
            payload['required'].append('WORKFLOW-CHILDREN')
            payload['results'].append(dict(criterion_id='WORKFLOW-CHILDREN',status='failed' if coverage_result['child_failed'] else 'passed',
                verified=not coverage_result['errors'],evidence_refs=[x.get('receipt_ref') for x in run['workflow']['children'] if x.get('receipt_ref')]))
        p = subprocess.run(["docker", "run", "--rm", "--network", "none", "--read-only", "--cap-drop", "ALL", "--security-opt", "no-new-privileges", "-i", "-v", str(policy) + ":/policy.rego:ro", OPA, "eval", "--format=json", "--stdin-input", "-d", "/policy.rego", "data.release.decision"], input=encode(payload), capture_output=True, timeout=30)
        if p.returncode:
            raise RuntimeError("OPA 门禁执行失败")
        decision = json.loads(p.stdout)["result"][0]["expressions"][0]["value"]
        if decision not in ("allow", "reject", "inconclusive"):
            raise ValueError("无效门禁结果")
        self.artifact(run, "gate-input.json", encode(payload), media_type="application/json")
        self.artifact(run, "gate-result.json", p.stdout, media_type="application/json")
        return decision

    def execute(self, run_id):
        run = self.read(run_id)
        if run["status"] != "queued":
            raise ValueError("历史执行只读；请创建新的执行记录复验")
        if run.get('workflow'):
            from .workflow import execute
            from .integrations.store import IntegrationStore
            integrations=IntegrationStore(self.root/'integrations')
            with integrations.lease():
                return execute(self,integrations,run)
        if run.get("project_id"):
            from .projects import execute
            return execute(self, run)
        try:
            run["status"] = "running"
            self.save(run)
            out = self.path(run_id) / "execution"
            out.mkdir()
            with self.stage(run, "baseline", "校验冻结标准、测试集、目标与门禁策略") as phase:
                b = baseline()
                if run["baseline"] != b:
                    raise ValueError("执行绑定的基线与冻结标准不符")
                frozen = [(SUITE, b["suite_digest"]), (ROOT / "validation/fixture.py", b["fixture_digest"]), (ROOT / "acceptance/policy.rego", b["policy_digest"]), (ROOT / "validation/static-samples" / (run["mode"] + ".py"), b["sample_digests"][run["mode"]])]
                if any(digest(path.read_bytes()) != expected for path, expected in frozen):
                    raise ValueError("冻结执行输入发生变化")
                if not source.matches(run["source_context"], b, run["mode"]):
                    raise ValueError("验收源文件快照与冻结目标不符")
                run["source_artifact"] = self.artifact(run, "source-context.json", encode(run["source_context"]), media_type="application/json")
                phase["detail"] = f"{b['version']} · 标准、测试集、目标、策略摘要相符"
            with self.stage(run, "cases", "核对用例与标准绑定，按层安排执行") as phase:
                register_cases(self, run)
                if len({c["case_id"] for c in b["criteria"]}) != len(b["criteria"]):
                    raise ValueError("用例绑定重复")
                phase["detail"] = f"已绑定 {len(b['criteria'])} 项冻结用例 · " + " / ".join(f"{layer} {sum(c['layer'] == layer for c in b['criteria'])} 项" for layer in ("L1", "L2", "L3"))
            with self.stage(run, "L1", "Bandit B602 · 扫描当前版本的静态样本") as phase:
                run["active_layer"] = "L1"
                run["layer_runs"].append({"layer": "L1", "started_at": now()})
                self.save(run)
                with checks(self, run, [c for c in b["criteria"] if c["layer"] == "L1"]):
                    sample = ROOT / "validation/static-samples" / (run["mode"] + ".py")
                    check_started = monotonic()
                    code, logref = self.command(run, "bandit", [ROOT / "validation/.venv/bin/bandit", "-q", "-t", "B602", str(sample), "-f", "json", "-o", str(out / "bandit.json")])
                    check_duration = round((monotonic() - check_started) * 1000, 2)
                    report = json.loads((out / "bandit.json").read_text())
                    ref = self.artifact(run, "bandit.json", (out / "bandit.json").read_bytes(), "SEC-SHELL", "application/json")
                    try:
                        status = bandit_status(report, code, str(sample))
                    except (ValueError, KeyError, TypeError, jsonschema.ValidationError):
                        status = "error"
                    c = next(c for c in run["baseline"]["criteria"] if c["id"] == "SEC-SHELL")
                    run["results"].append({"criterion_id": c["id"], "case_id": c["case_id"], "layer": c["layer"], "attempt": 1, "status": status, "duration_ms": check_duration, "expected": c["expected"], "actual": "Bandit 执行不完整，检查原始报告与日志" if status == "error" else f"Bandit B602：{len(report.get('results', []))} 条发现", "evidence_refs": [ref, logref]})
                    run["layer_runs"][-1]["finished_at"] = now()
                    self.save(run)
                    phase.update(status=status, detail=run["results"][-1]["actual"])
            port = 18891
            command = shlex.join([str(ROOT / "validation/.venv/bin/python"), str(ROOT / "validation/fixture.py"), "--mode", run["mode"], "--port", str(port)])
            env = {**os.environ, "PATH": str(NODE.parent) + os.pathsep + os.environ.get("PATH", "")}
            for layer in ("L2", "L3"):
                with self.stage(run, layer, "Playwright · " + STAGES[layer]) as phase:
                    run["active_layer"] = layer
                    run["layer_runs"].append({"layer": layer, "started_at": now()})
                    self.save(run)
                    stage = out / layer
                    stage.mkdir()
                    config = stage / "playwright.config.mjs"
                    config.write_text("import base from " + json.dumps((ROOT / "validation/playwright.config.mjs").as_uri()) + ";\nexport default {...base,testDir:" + json.dumps(str(SUITE.parent)) + ",outputDir:" + json.dumps(str(stage / "artifacts")) + ",reporter:[['json',{outputFile:" + json.dumps(str(stage / "results.json")) + "}]],use:{...base.use,baseURL:'http://127.0.0.1:" + str(port) + "'},webServer:{command:" + json.dumps(command) + ",url:'http://127.0.0.1:" + str(port) + "/health',reuseExistingServer:false,timeout:10000}};\n")
                    ids = [re.escape(c["id"]) for c in run["baseline"]["criteria"] if c["layer"] == layer]
                    with checks(self, run, [c for c in b["criteria"] if c["layer"] == layer]):
                        code, _ = self.command(run, "playwright-" + layer, [NODE, ROOT / "validation/node_modules/playwright/cli.js", "test", "--config", config, "--grep", "(" + "|".join(ids) + "):"], env=env)
                        report = json.loads((stage / "results.json").read_text())
                        self.parse_playwright(run, report, stage)
                        run["layer_runs"][-1]["finished_at"] = now()
                        self.save(run)
                        if code not in (0, 1) or report.get("errors"):
                            raise RuntimeError("Playwright 未完整执行，检查执行日志")
                        results = [r for r in run["results"] if r["layer"] == layer]
                        complete = {r["criterion_id"] for r in results} == {c["id"] for c in b["criteria"] if c["layer"] == layer} and len({r["criterion_id"] for r in results}) == len(results)
                        phase.update(status="error" if not complete or any(r["status"] not in ("passed", "failed") for r in results) else "failed" if any(r["status"] == "failed" for r in results) else "passed", detail=f"{len(results)} 项检查 · {sum(r['status'] == 'passed' for r in results)} 通过 / {sum(r['status'] == 'failed' for r in results)} 失败" + ("；结果不完整或重复" if not complete else ""))
            run["active_layer"] = None
            with self.stage(run, "findings", "按失败检查关联缺陷与证据") as phase:
                self.collect_findings(run)
                phase["detail"] = f"归纳 {len(run['findings'])} 条缺陷；保留标准、用例和原始证据引用"
            with self.stage(run, "gate", "OPA · 核对完整性与必验结果") as phase:
                # Keep the last published checkpoint running until OPA returns.
                run["status"] = "completed"
                try:
                    run["decision"] = self.evaluate(run)
                finally:
                    run["status"] = "running"
                run["reasons"] = ["全部适用必验项通过；结论仅限当前基线" if run["decision"] == "allow" else "必验项存在失败" if run["decision"] == "reject" else "必验项或证据不完整"]
                phase.update(status="passed" if run["decision"] == "allow" else "failed" if run["decision"] == "reject" else "error", detail=run["reasons"][0])
            run["status"] = "completed"
        except Exception as exc:
            run.update(status="error", decision="inconclusive", reasons=[str(exc)[:600]])
        finally:
            run["active_layer"] = None
            self.collect_findings(run)
            run["finished_at"] = now()
            run["integrity"] = self.check_integrity(run)
            self.save(run)

    def lease(self):
        lease = (self.root / "runner.lock").open("a")
        try:
            fcntl.flock(lease, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            lease.close()
            raise RuntimeError("已有验收执行正在运行") from None
        return lease
