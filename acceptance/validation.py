"""One report validator shared by the gate, projections and exports.

Reports prove recorded tool observations, not trustworthy runner identity. No
decision is inferred from an absent field, a success exit code alone or prose.
"""
import base64
import json
from pathlib import PurePosixPath

import jsonschema


class InvalidReport(ValueError):
    pass


def require(condition, message):
    if not condition:
        raise InvalidReport(message)


def one(values, message):
    require(len(values) == 1, message)
    return values[0]


def specs(suites):
    require(isinstance(suites, list), "Playwright suites 缺失或类型错误")
    for suite in suites:
        require(isinstance(suite, dict), "Playwright suite 无效")
        rows = suite.get("specs", [])
        require(isinstance(rows, list), "Playwright specs 无效")
        yield from rows
        yield from specs(suite.get("suites", []))


BANDIT_SCHEMA = {
    "type": "object", "required": ["errors", "results", "metrics", "generated_at"],
    "properties": {
        "errors": {"type": "array"}, "generated_at": {"type": "string", "minLength": 1},
        "metrics": {"type": "object", "minProperties": 2},
        "results": {"type": "array", "items": {"type": "object", "required": ["test_id", "filename", "line_number", "issue_text"],
            "properties": {"test_id": {"const": "B602"}, "filename": {"type": "string"}, "line_number": {"type": "integer", "minimum": 1}, "issue_text": {"type": "string", "minLength": 1}}}},
    },
}


def bandit_status(report, exit_code, target):
    jsonschema.validate(report, BANDIT_SCHEMA)
    require(report["errors"] == [], "Bandit 报告存在执行错误")
    metrics = report["metrics"]
    require(set(metrics) == {target, "_totals"}, "Bandit 实际扫描文件与目标不符")
    for key in (target, "_totals"):
        row = metrics[key]
        require(isinstance(row, dict) and type(row.get("loc")) is int and row["loc"] > 0, "Bandit 未扫描有效代码")
        require(row.get("nosec") == 0 and row.get("skipped_tests") == 0, "Bandit 存在抑制或跳过检查")
    require(metrics[target]["loc"] == metrics["_totals"]["loc"], "Bandit 扫描统计不一致")
    require(all(hit["filename"] == target for hit in report["results"]), "Bandit 发现属于其他目标")
    expected = 1 if report["results"] else 0
    require(type(exit_code) is int and exit_code == expected, "Bandit 退出码与报告不一致")
    return "failed" if expected else "passed"


class Reader:
    def __init__(self, store, run):
        self.store, self.run, self.cache = store, run, {}

    def read(self, ref):
        if ref not in self.cache:
            self.cache[ref] = self.store.artifact_bytes(self.run, ref)
        return self.cache[ref]

    def named(self, name, result=None):
        candidates = [a for a in self.run["artifacts"] if a["name"] == name and (result is None or a["id"] in result["evidence_refs"])]
        item = one(candidates, "报告缺失或重复：" + name)
        return item, json.loads(self.read(item["id"])[1])

    def command(self, name):
        command = one([c for c in self.run.get("commands", []) if c["name"] == name], "执行凭据缺失或重复：" + name)
        self.read(command["evidence_ref"])
        return command


def validate_bandit(reader, result):
    artifact, report = reader.named("bandit.json", result)
    command = reader.command("bandit")
    argv = command["argv"]
    target = argv[argv.index("-t") + 2]
    require(argv[argv.index("-t") + 1] == "B602", "Bandit 规则不符")
    require(target.endswith("/validation/static-samples/" + reader.run["mode"] + ".py"), "Bandit 命令目标不符")
    status = bandit_status(report, command["exit_code"], target)
    require(status == result["status"], "Bandit 状态与结果不符")
    return {"status": status, "report": report, "primary_ref": artifact["id"]}


def validate_playwright(reader, result):
    cid, layer = result["criterion_id"], result["layer"]
    raw_artifact, raw = reader.named("playwright-" + layer + "-results.json")
    require(isinstance(raw, dict) and raw.get("errors") == [], "Playwright 报告错误或缺失 errors")
    expected_ids = {c["id"] for c in reader.run["baseline"]["criteria"] if c["layer"] == layer and c["executor"] == "playwright"}
    rows = list(specs(raw.get("suites")))
    ids = [row["title"].split(":", 1)[0] for row in rows]
    require(len(ids) == len(expected_ids) and set(ids) == expected_ids, "Playwright 实际用例范围缺失、重复或超出计划")
    observations = {}
    for row in rows:
        test = one(row["tests"], "一个用例只能对应一次配置执行")
        require(test.get("expectedStatus") == "passed", "用例被标为预期失败或跳过")
        observed = one(test["results"], "存在重试或缺失首次执行")
        state = observed.get("status")
        require(state in ("passed", "failed") and observed.get("retry") == 0, "用例未正常完成或发生重试")
        require(test.get("status") == ("expected" if state == "passed" else "unexpected"), "Playwright 用例终态不一致")
        require(isinstance(observed.get("duration"), (int, float)) and observed["duration"] >= 0 and bool(observed.get("startTime")), "Playwright 执行时间缺失")
        errors = observed.get("errors")
        require(isinstance(errors, list) and (bool(errors) == (state == "failed")), "Playwright 错误与状态不符")
        if state == "failed":
            require(bool(observed.get("error", {}).get("message")), "失败用例缺少错误证据")
        observations[row["title"].split(":", 1)[0]] = (row, observed)
    counts = raw.get("stats", {})
    passed = sum(observation[1]["status"] == "passed" for observation in observations.values())
    failed = len(observations) - passed
    require(all(counts.get(k) == v for k, v in {"expected": passed, "unexpected": failed, "skipped": 0, "flaky": 0}.items()), "Playwright 汇总统计不符")
    command = reader.command("playwright-" + layer)
    require(command.get("exit_code") == (1 if failed else 0), "Playwright 退出码与报告不符")
    if reader.run["baseline"].get("recipe"):
        require(command.get("target_digest")==reader.run["target_digest"] and command.get("baseline_digest")==reader.run["baseline"]["digest"] and not command.get("truncated"), "浏览器命令与冻结输入不符")
    row, observed = observations[cid]
    artifact, report = reader.named(cid + "-result.json", result)
    require(report.get("source_report") == raw_artifact["id"] and report.get("result") == observed and report.get("title") == row["title"], "派生结果与原始 Playwright 报告不一致")
    require(report.get("status") == observed["status"] == result["status"] and result.get("attempt") == 1, "执行状态或 attempt 不一致")
    for attachment in observed.get("attachments", []):
        name = PurePosixPath(attachment["path"]).name if attachment.get("path") else attachment["name"] + ".json"
        item = one([a for a in reader.run["artifacts"] if a["id"] in result["evidence_refs"] and a["name"] == name], "执行附件缺失或重复：" + name)
        data = reader.read(item["id"])[1]
        if "body" in attachment:
            require(data == base64.b64decode(attachment["body"], validate=True), "内联附件与原始报告不一致")
    if cid == "A11Y-LABEL":
        _, axe = reader.named("axe-result.json", result)
        require(axe.get("testEngine", {}).get("name") == "axe-core", "axe 执行器身份缺失")
        for key in ("violations", "passes", "inapplicable", "incomplete"):
            require(isinstance(axe.get(key), list), "axe 结果字段缺失：" + key)
        require(axe["incomplete"] == [], "axe 存在无法自动判断的结果")
        checks = axe["violations"] + axe["passes"] + axe["inapplicable"]
        require(len(checks) == 1 and checks[0].get("id") == "label", "axe 未完整执行指定规则")
        require(bool(axe["violations"]) == (observed["status"] == "failed"), "axe 与断言结果不一致")
    if cid == "BROWSER-A11Y":
        _, axe=reader.named("axe-result.json",result)
        require(axe.get("testEngine",{}).get("name")=="axe-core", "缺少 axe 执行器")
        rules=axe["violations"]+axe["passes"]+axe["inapplicable"]+axe["incomplete"]
        require(len(rules)==3 and {x["id"] for x in rules}=={"label","button-name","link-name"}, "axe 规则范围不符")
        require(bool(axe["violations"] or axe["incomplete"])==(observed["status"]=="failed"), "axe 结论不符")
    return {"status": observed["status"], "report": report, "primary_ref": artifact["id"], "source_report": raw_artifact["id"]}


def validate_results(store, run, reader=None):
    reader = reader or Reader(store, run)
    checks, errors = {}, []
    criteria = {c["id"]: c for c in run["baseline"]["criteria"]}
    for cid, criterion in criteria.items():
        candidates = [r for r in run["results"] if r.get("criterion_id") == cid]
        if not candidates and run["status"] in ("queued", "running"):
            continue
        try:
            result = one(candidates, "结果缺失或重复")
            require(all(result.get(k) == criterion[k] for k in ("case_id", "layer", "expected")), "标准、用例或预期不匹配")
            require(result["status"] in (("passed", "failed", "blocked") if criterion["executor"] == "assessment-check" else ("passed", "failed")), "没有有效通过/失败结果")
            require(result.get("attempt") == 1, "不支持未审阅的重试结果")
            for ref in result["evidence_refs"]:
                item, _ = reader.read(ref)
                require(item["criterion_id"] in (None, cid), "引用了其他检查的证据")
            from .projects import validate_node
            from .expanded import validate_check
            validator = {"assessment-check": validate_check, "bandit": validate_bandit, "playwright": validate_playwright, "node-junit": validate_node}.get(criterion["executor"])
            require(validator is not None, "未注册结果适配器")
            checks[cid] = {"valid": True, **validator(reader, result)}
        except (OSError, ValueError, KeyError, TypeError, AttributeError, IndexError, RecursionError, jsonschema.ValidationError) as exc:
            message = str(exc).splitlines()[0][:240]
            checks[cid] = {"valid": False, "status": "error", "reason": message}
            errors.append(cid + "：" + message)
    extra = [r.get("criterion_id") for r in run["results"] if r.get("criterion_id") not in criteria]
    if extra:
        errors.append("包含计划外的检查结果")
    return {"valid": not errors and len(checks) == len(criteria), "checks": checks, "errors": errors}
