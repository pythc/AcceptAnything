"""Explicit local project profiles and a bounded, offline Node test adapter.

The web API selects registered profiles only. It never accepts shell commands,
host mounts or credentials. Only listed source files enter a disposable runner.
"""
from copy import deepcopy
import hashlib
import json
import math
import os
from pathlib import Path, PurePosixPath
import re
import selectors
import subprocess
from time import monotonic
import uuid

from defusedxml import ElementTree
from defusedxml.common import DefusedXmlException
from xml.etree.ElementTree import ParseError
import jsonschema

from . import source
from .validation import require, one
from .progress import checks, register_cases

NODE_IMAGE = "sha256:ebfe2f90462722a7a4de65e91990e97fe0d401c70e0e762c5b53302f905ec1c1"
PROFILE_SCHEMA = {
    "type": "object", "additionalProperties": False,
    "required": ["id", "name", "repository", "version", "files", "source_path", "source_digest", "criteria"],
    "properties": {
        "id": {"type": "string", "pattern": "^[a-z][a-z0-9-]{0,63}$"}, "name": {"type": "string", "minLength": 1},
        "recipe": {"const": "assessment-v1"}, "scope": {"type": "string"},
        "exclusions": {"type": "array", "items": {"type": "object", "additionalProperties": False, "required": ["subject", "reason"], "properties": {"subject": {"type": "string", "minLength": 1}, "reason": {"type": "string", "minLength": 1}}}},
        "repository": {"type": "string", "minLength": 1}, "version": {"type": "string", "minLength": 1},
        "files": {"type": "array", "minItems": 1, "uniqueItems": True, "items": {"type": "string"}},
        "source_path": {"type": "string"}, "source_digest": {"type": "string", "pattern": "^[a-f0-9]{64}$"},
        "criteria": {"type": "array", "minItems": 1, "items": {"type": "object", "additionalProperties": False,
            "required": ["id", "title", "expected", "test_file", "test_digest", "test_names", "source_anchor"],
            "properties": {"kind": {"enum": ["junit", "python", "build", "gitleaks", "npm-audit", "restore", "playwright", "gap", "semgrep", "zap", "k6", "joint-restore", "python-sast"]}, "layer": {"enum": ["L1", "L2", "L3", "L4"]}, "limitation": {"type": "string"}, "gap": {"type": "string"}, "test_files": {"type": "array", "items": {"type": "string"}}, **{k: {"type": "string", "minLength": 1} for k in ["title", "expected", "test_file", "source_anchor"]},
                "id": {"type": "string", "pattern": "^[A-Z][A-Z0-9_-]{0,63}$"},
                "test_digest": {"type": "string", "pattern": "^[a-f0-9]{64}$"},
                "test_names": {"type": "array", "minItems": 1, "uniqueItems": True, "items": {"type": "string", "minLength": 1}}}}},
    },
}


def sha(raw):
    return hashlib.sha256(raw).hexdigest()


def packed(value):
    return (json.dumps(value, ensure_ascii=False, indent=2) + "\n").encode()


def profile_path(store, project_id):
    require(isinstance(project_id, str) and re.fullmatch(r"[a-z][a-z0-9-]{0,63}", project_id), "项目 ID 无效")
    return store.root / "projects" / (project_id + ".json")


def profile(store, project_id):
    path = profile_path(store, project_id)
    require(not path.is_symlink(), "项目配置不能是符号链接")
    value = json.loads(path.read_bytes())
    jsonschema.validate(value, PROFILE_SCHEMA)
    require(value["id"] == project_id, "项目身份不符")
    return value


def profiles(store):
    values = []
    for path in sorted((store.root / "projects").glob("*.json")):
        try:
            p = profile(store, path.stem)
            values.append({"id": p["id"], "name": p["name"], "repository": p["repository"], "version": p["version"], "check_count": len(p["criteria"]), "adapter": p.get("recipe", "node-junit"), "scope": p.get("scope", "所列业务规则回归；容器无外部网络"), "test_count": sum(len(c["test_names"]) for c in p["criteria"])})
        except (OSError, ValueError, jsonschema.ValidationError):
            continue
    return values


def read_files(p):
    root = Path(p["repository"]).resolve(strict=True)
    require(root.is_dir(), "项目目录不存在")
    files = {}
    for relative in p["files"]:
        parts = PurePosixPath(relative)
        require(not parts.is_absolute() and ".." not in parts.parts and str(parts) == relative and "\\" not in relative and not relative.startswith("-"), "文件路径必须是规范的项目相对路径")
        require(not any(part.startswith(".") for part in parts.parts) and parts.suffix in ({".ts", ".mjs", ".js", ".json", ".md", ".vue", ".css", ".svg", ".html", ".sql", ".py", ".txt"} if p.get("recipe") else {".ts", ".mjs", ".js", ".json", ".md"}), "只接受显式列出的代码与文档文件")
        path = root / relative
        require(all(not candidate.is_symlink() for candidate in [path, *path.parents] if candidate != root.parent), "快照不接受符号链接")
        require(path.resolve(strict=True).is_relative_to(root) and path.is_file(), "快照文件越界或不是普通文件")
        files[relative] = path.read_bytes()
    require(p["source_path"] in files and sha(files[p["source_path"]]) == p["source_digest"], "验收来源文档已变化；需要确认新版本")
    ids = [c["id"] for c in p["criteria"]]
    require(len(set(ids)) == len(ids), "重复验收标准")
    for c in p["criteria"]:
        require(c["test_file"] in files and sha(files[c["test_file"]]) == c["test_digest"], "测试代码已变化；不能沿用原标准")
    return root, files


def register(store, value):
    jsonschema.validate(value, PROFILE_SCHEMA)
    read_files(value)
    path = profile_path(store, value["id"])
    path.parent.mkdir(exist_ok=True)
    if path.exists():
        require(path.read_bytes() == packed(value), "项目已登记；更新标准需要新的配置版本及明确修订")
    else:
        path.write_bytes(packed(value))
    return value["id"]


def create(store, project_id):
    from .engine import ROOT, OPA, now
    p = profile(store, project_id)
    root, files = read_files(p)
    policy = (ROOT / "acceptance/policy.rego").read_bytes()
    manifest = [{"path": name, "sha256": sha(raw), "size": len(raw)} for name, raw in sorted(files.items())]
    tests = {c["test_file"]: c["test_digest"] for c in p["criteria"]}
    criteria = [{**c, "case_id": "TC-" + c["id"], "layer": "L1", "executor": "node-junit", "severity": "medium", "impact": "所选项目回归要求未满足；实际影响需结合失败断言复核", "required": True} for c in p["criteria"]]
    b = {"version": p["version"], "title": p["name"], "source": p["source_path"], "source_digest": p["source_digest"], "scope": "所列业务规则回归；不代表完整 Web/API/安全验收", "criteria": criteria, "suite_digest": sha(packed(tests)), "policy_digest": sha(policy), "test_digests": tests, "runner_image": NODE_IMAGE}
    if p.get("recipe"):
        from .expanded import freeze
        freeze(p, b)
    raw = packed(b); b["digest"] = sha(raw)
    contracts = store.root / "contracts"; contracts.mkdir(exist_ok=True)
    archive = contracts / (b["digest"] + ".json")
    if archive.exists(): require(archive.read_bytes() == raw, "已登记契约内容冲突")
    else: archive.write_bytes(raw)
    rid = "run-" + uuid.uuid4().hex[:12]; path = store.runs / rid; path.mkdir(); (path / "artifacts").mkdir()
    run = {"id": rid, "mode": "project", "project_id": project_id, "profile_digest": sha(packed(p)), "record_version": 2, "label": p["name"], "status": "queued", "decision": "inconclusive", "created_at": now(), "finished_at": None,
        "baseline": b, "suite_digest": b["suite_digest"], "target_digest": sha(packed(manifest)), "results": [], "findings": [], "artifacts": [], "commands": [], "reasons": [], "integrity": False, "active_layer": None, "layer_runs": [], "pipeline": [],
        "limits": ["仅运行已登记的现有回归用例；未完成全项目验收", "未验证运行中服务、数据库、浏览器与完整安全范围", "容器隔离执行；报告未接入独立签名，不能证明对抗恶意执行者的来源真实性"], "inputs": {}, "project_inputs": []}
    if p.get("recipe"):
        run["limits"] = ["现有测试与独立浏览器断言；完整安全、候选人流程及性能目标仍有未覆盖项", "仅合成测试数据；外部邮件、OAuth 与 GitHub 不做真实调用", "容器隔离及文件摘要不是独立执行签名"]
        if "exclusions" in p:
            run["limits"] = ["本次结论仅适用于已冻结的本地验收范围；性能与恢复时间为本机实测，不代表生产 SLO", "容器隔离及文件摘要不是独立执行签名", *[x["subject"] + "：" + x["reason"] for x in p["exclusions"]]]
    repo_path = str(root)
    run["source_context"] = {"schema_version": 1, "provenance": "captured", "captured_at": now(),
        "repository": {"id": source.repository_id(repo_path), "name": root.name, "path": repo_path, "kind": "git" if source.git(root, "rev-parse", "--show-toplevel") else "directory", "branch": source.git(root, "symbolic-ref", "-q", "--short", "HEAD"), "commit": source.git(root, "rev-parse", "--verify", "HEAD"), "remote": source.remote_label(source.git(root, "config", "--get", "remote.origin.url")), "scoped_changes": None, "untracked": None},
        "target": {"name": p["name"], "variant": "project", "kind": "node-test", "environment": "隔离容器 · 无外部网络", "url": None},
        "scope": {"kind": "files", "description": b["scope"], "files": manifest, "check_count": len(criteria)}, "snapshot": {"algorithm": "sha256", "digest": run["target_digest"]},
        "tooling": {"model": None, "executors": ["Node.js Test Runner", "JUnit XML"], "versions": {"runner_image": NODE_IMAGE}, "gate": "OPA", "opa_image": OPA}}
    if p.get("recipe"):
        run["source_context"]["scope"]["description"] = b["scope"]
        run["source_context"]["target"].update(kind="web-api-database", environment="临时容器 / 合成数据库；依赖审计访问 npm 公共库")
        run["source_context"]["tooling"]["executors"] = ["Node.js", "unittest", "Playwright", "axe-core", "npm audit", "Gitleaks", "PostgreSQL"]
        if "exclusions" in p:
            run["source_context"]["tooling"]["executors"] += ["Semgrep CE / njsscan", "Bandit", "OWASP ZAP", "k6"]
        from .expanded import recipe_files
        run["recipe_inputs"] = [{"path": name, "ref": store.artifact(run, name, raw, media_type="text/plain")} for name, raw in recipe_files().items()]
    run["inputs"]["baseline"] = store.artifact(run, "frozen-standard.json", raw, media_type="application/json")
    run["inputs"]["policy"] = store.artifact(run, "frozen-policy.rego", policy, media_type="text/plain")
    for entry in manifest:
        ref = store.artifact(run, PurePosixPath(entry["path"]).name, files[entry["path"]], media_type="text/plain")
        run["project_inputs"].append({**entry, "ref": ref})
    store.save(run)
    return run


def integrity(store, run, reader):
    try:
        b = run["baseline"]
        require(re.fullmatch(r"[a-f0-9]{64}", b["digest"]), "无效契约摘要")
        archived = (store.root / "contracts" / (b["digest"] + ".json")).read_bytes()
        require(sha(archived) == b["digest"] and {**json.loads(archived), "digest": sha(archived)} == b, "历史契约不符")
        require(reader.read(run["inputs"]["baseline"])[1] == archived, "契约快照不符")
        require(sha(reader.read(run["inputs"]["policy"])[1]) == b["policy_digest"], "策略快照不符")
        if run.get("source_artifact"):
            require(json.loads(reader.read(run["source_artifact"])[1]) == run["source_context"], "目标信息快照不符")
        rows = run["project_inputs"]
        require(len({r["path"] for r in rows}) == len(rows), "重复源文件")
        for row in rows:
            path = PurePosixPath(row["path"])
            require(not path.is_absolute() and ".." not in path.parts and str(path) == row["path"] and "\\" not in row["path"], "源文件路径越界")
            data = reader.read(row["ref"])[1]
            require(sha(data) == row["sha256"] and len(data) == row["size"], "源文件快照不符")
        manifest = [{k: r[k] for k in ("path", "sha256", "size")} for r in rows]
        require(sha(packed(manifest)) == run["target_digest"] == run["source_context"]["snapshot"]["digest"], "目标摘要不符")
        require(manifest == run["source_context"]["scope"]["files"], "范围快照不符")
        digests = {r["path"]: r["sha256"] for r in rows}
        require(all(digests.get(k) == v for k, v in b["test_digests"].items()) and digests.get(b["source"]) == b["source_digest"], "测试或标准来源不符")
        require(run["suite_digest"] == b["suite_digest"] == sha(packed(b["test_digests"])), "测试集摘要不符")
        if b.get("recipe"):
            require({r["path"]: sha(reader.read(r["ref"])[1]) for r in run["recipe_inputs"]} == b["recipe_digests"], "编排器快照不符")
        require(len({a["id"] for a in run["artifacts"]}) == len(run["artifacts"]), "证据 ID 重复")
        for a in run["artifacts"]: reader.read(a["id"])
        return True
    except (OSError, ValueError, KeyError, TypeError):
        return False


def applicability(store, run):
    try:
        p = profile(store, run["project_id"]); _, files = read_files(p)
        manifest = [{"path": name, "sha256": sha(raw), "size": len(raw)} for name, raw in sorted(files.items())]
        from .expanded import recipe_files
        recipe_matches = not run["baseline"].get("recipe") or run["baseline"]["recipe_digests"] == {k: sha(v) for k, v in recipe_files().items()}
        matches = recipe_matches and sha(packed(manifest)) == run["target_digest"] and sha(packed(p)) == run["profile_digest"]
        return {"matches": matches, "reason": "与当前项目文件及标准一致" if matches else "项目文件或标准已变化；需要创建新执行"}
    except (OSError, ValueError, KeyError, jsonschema.ValidationError):
        return {"matches": False, "reason": "当前项目或已登记标准无法核实；保留历史结果"}


def parse_junit(raw, expected_names, exit_code):
    try:
        tree = ElementTree.fromstring(raw, forbid_dtd=True)
    except (ParseError, DefusedXmlException) as exc:
        raise ValueError("JUnit XML 无效或包含禁止的实体声明") from exc
    require(tree.tag == "testsuites", "JUnit 缺少 testsuites 根节点")
    cases = list(tree.iter("testcase"))
    suites = list(tree.iter("testsuite"))
    require(all(child.tag in ("testsuite", "testcase") for parent in [tree, *suites] for child in parent), "JUnit 套件包含未知节点")
    require(sum(len(s.findall("testcase")) for s in [tree, *suites]) == len(cases), "JUnit 用例位置无效")
    require(all(c.get("file") and math.isfinite(float(c.get("time", "nan"))) and float(c.get("time")) >= 0 for c in cases), "JUnit 缺少测试文件或有效耗时")
    names = [c.get("name") for c in cases]
    require(len(names) == len(expected_names) and set(names) == set(expected_names), "JUnit 实际用例与批准清单不一致")
    require(not list(tree.iter("skipped")) and not list(tree.iter("error")), "用例跳过或执行器错误")
    failures = [c for c in cases if c.find("failure") is not None]
    require(exit_code == (1 if failures else 0), "JUnit 退出码与结果不符")
    for suite in tree.iter("testsuite"):
        direct = list(suite.findall("testcase"))
        require(int(suite.get("tests", "-1")) == len(direct), "JUnit 测试数量不符")
        require(int(suite.get("failures", "-1")) == sum(c.find("failure") is not None for c in direct), "JUnit 失败统计不符")
        require(int(suite.get("skipped", "-1")) == 0 and int(suite.get("errors", "-1")) == 0, "JUnit 存在跳过或错误")
    return {"status": "failed" if failures else "passed", "tests": len(cases), "failed": len(failures), "case_names": names,
            "files": [c.get("file") for c in cases],
            "failure_text": "\n\n".join((c.get("name", "") + "\n" + (c.find("failure").text or "")) for c in failures)}


def validate_node(reader, result):
    c = next(c for c in reader.run["baseline"]["criteria"] if c["id"] == result["criterion_id"])
    item = one([a for a in reader.run["artifacts"] if a["name"] == c["id"] + "-junit.xml" and a["id"] in result["evidence_refs"]], "缺少原始 JUnit")
    command = reader.command("node-" + c["id"])
    summary = parse_junit(reader.read(item["id"])[1], c["test_names"], command["exit_code"])
    require(set(summary["files"]) == {"/workspace/" + c["test_file"]}, "JUnit 测试文件不符")
    require(command.get("runner_image") == reader.run["baseline"].get("runner_image", NODE_IMAGE) and command.get("target_digest") == reader.run["target_digest"], "执行器镜像或目标绑定不符")
    require(command.get("report_ref") == item["id"], "命令未绑定该原始报告")
    require(command.get("test_file") == c["test_file"] and not command.get("truncated"), "测试文件不符或输出被截断")
    require(summary["status"] == result["status"], "JUnit 与检查结论不一致")
    return {"status": summary["status"], "report": summary, "primary_ref": item["id"]}


def container_command(store, run, criterion, workspace, timeout=45):
    from .engine import now
    name = "acceptance-" + run["id"] + "-" + uuid.uuid4().hex[:8]
    runner_image = run["baseline"].get("runner_image", NODE_IMAGE)
    require(re.fullmatch(r"sha256:[a-f0-9]{64}", runner_image), "执行镜像必须固定摘要")
    argv = ["docker", "run", "--rm", "--name", name, "--network", "none", "--read-only", "--cap-drop", "ALL", "--security-opt", "no-new-privileges", "--pids-limit", "64", "--memory", "256m", "--cpus", "1", "--user", "65534:65534", "--tmpfs", "/tmp:rw,noexec,nosuid,size=32m", "--mount", f"type=bind,src={workspace},dst=/workspace,readonly", "--workdir", "/workspace", "--env", "NODE_NO_WARNINGS=1", "--entrypoint", "node", runner_image, "--test", "--test-reporter=junit", criterion["test_file"]]
    started_at = now(); start = monotonic(); buffers = {"stdout": bytearray(), "stderr": bytearray()}; fault = None
    p = subprocess.Popen(argv, stdout=subprocess.PIPE, stderr=subprocess.PIPE, stdin=subprocess.DEVNULL)
    try:
        with selectors.DefaultSelector() as selector:
            selector.register(p.stdout, selectors.EVENT_READ, "stdout"); selector.register(p.stderr, selectors.EVENT_READ, "stderr")
            while selector.get_map():
                if monotonic() - start > timeout: raise TimeoutError("隔离执行超时")
                for key, _ in selector.select(timeout=0.1):
                    chunk = os.read(key.fileobj.fileno(), 65536)
                    if not chunk: selector.unregister(key.fileobj); continue
                    buffer = buffers[key.data]
                    buffer.extend(chunk)
            p.wait(timeout=max(0.1, timeout - (monotonic() - start)))
    except (TimeoutError, ValueError, subprocess.TimeoutExpired) as exc:
        fault = str(exc)
    finally:
        try:
            cleanup = subprocess.run(["docker", "rm", "-f", name], capture_output=True, timeout=10)
            if cleanup.returncode and b"No such container" not in cleanup.stderr: fault = fault or "执行容器清理失败"
        except (OSError, subprocess.TimeoutExpired):
            fault = fault or "无法确认执行容器已清理"
        finally:
            if p.poll() is None:
                p.kill(); p.wait(timeout=5)
            p.stdout.close(); p.stderr.close()
    report_ref = store.artifact(run, criterion["id"] + "-junit.xml", bytes(buffers["stdout"]), criterion["id"], "application/xml")
    log_ref = store.artifact(run, "node-" + criterion["id"] + ".log", bytes(buffers["stderr"]) + (fault or "").encode(), criterion["id"], "text/plain")
    command = {"name": "node-" + criterion["id"], "argv": argv, "started_at": started_at, "finished_at": now(), "exit_code": p.returncode, "evidence_ref": log_ref, "report_ref": report_ref, "runner_image": runner_image, "target_digest": run["target_digest"], "test_file": criterion["test_file"], "truncated": bool(fault)}
    run["commands"].append(command)
    if fault: raise RuntimeError(fault)
    return parse_junit(bytes(buffers["stdout"]), criterion["test_names"], p.returncode), report_ref, log_ref, (monotonic() - start) * 1000


def execute(store, run):
    if run["baseline"].get("recipe"):
        from .expanded import execute as expanded_execute
        return expanded_execute(store, run)
    from .engine import now
    from .validation import Reader
    try:
        run["status"] = "running"; store.save(run)
        workspace = store.path(run["id"]) / "execution" / "workspace"
        with store.stage(run, "baseline", "核对已登记标准与隔离源文件快照"):
            require(integrity(store, run, Reader(store, run)), "项目快照完整性失败")
            workspace.mkdir(parents=True)
            for row in run["project_inputs"]:
                target = workspace / row["path"]; target.parent.mkdir(parents=True, exist_ok=True)
                target.write_bytes(store.artifact_bytes(run, row["ref"])[1]); target.chmod(0o444)
            run["source_artifact"] = store.artifact(run, "source-context.json", packed(run["source_context"]), media_type="application/json")
        with store.stage(run, "cases", "按冻结测试名称核对现有回归用例") as phase:
            register_cases(store, run)
            phase["detail"] = f"{len(run['baseline']['criteria'])} 项标准 · {sum(len(c['test_names']) for c in run['baseline']['criteria'])} 个现有测试"
        with store.stage(run, "L1", "Node.js · 隔离容器执行所选回归") as phase:
            run["active_layer"] = "L1"
            for c in run["baseline"]["criteria"]:
                with checks(store, run, [c]):
                    summary, ref, log, duration = container_command(store, run, c, workspace)
                    run["results"].append({"criterion_id": c["id"], "case_id": c["case_id"], "layer": c["layer"], "attempt": 1, "status": summary["status"], "duration_ms": duration, "expected": c["expected"], "actual": summary["failure_text"] or f"{summary['tests']} 个已登记测试通过", "evidence_refs": [ref, log]})
                    store.save(run)
            phase.update(status="failed" if any(r["status"] == "failed" for r in run["results"]) else "passed", detail=f"{len(run['results'])} 项检查完成；其他层未执行")
        run["active_layer"] = None
        with store.stage(run, "findings", "按有效失败断言归纳发现") as phase:
            store.collect_findings(run); phase["detail"] = f"{len(run['findings'])} 条发现"
        with store.stage(run, "gate", "OPA · 核对标准、执行范围与有效证据") as phase:
            run["status"] = "completed"
            try: run["decision"] = store.evaluate(run)
            finally: run["status"] = "running"
            run["reasons"] = [{"allow": "所选现有回归通过；不代表全项目验收完成", "reject": "所选回归存在失败", "inconclusive": "执行或报告无法完整核实"}[run["decision"]]]
            phase.update(status="passed" if run["decision"] == "allow" else "failed" if run["decision"] == "reject" else "error", detail=run["reasons"][0])
        run["status"] = "completed"
    except Exception as exc:
        run.update(status="error", decision="inconclusive", reasons=[str(exc)[:600]])
    finally:
        run["active_layer"] = None; run["finished_at"] = now()
        store.collect_findings(run); run["integrity"] = store.check_integrity(run); store.save(run)
