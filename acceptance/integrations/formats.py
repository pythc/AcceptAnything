"""Normalize mature tool formats. These adapters do not perform vulnerability detection.

Unknown versions/statuses, malformed summaries and incomplete scans fail closed.
The complete flag describes the report, not the provenance of an imported file.
"""

from __future__ import annotations
import hashlib
import json
import math
from defusedxml import ElementTree as ET



def require(ok, message):
    if not ok:
        raise ValueError(message)


def number(value, minimum=0):
    require(not isinstance(value, bool), "布尔值不能作为指标")
    result = float(value)
    require(math.isfinite(result) and result >= minimum, "指标无效")
    return result


def fingerprint(*values):
    return hashlib.sha256(
        json.dumps(values, ensure_ascii=False, sort_keys=True).encode()
    ).hexdigest()


def base(kind):
    return dict(
        format=kind,
        complete=True,
        diagnostics=[],
        tests=[],
        findings=[],
        components=[],
        metrics={},
    )


def test(name, status, duration=None, detail="", **extra):
    require(
        isinstance(name, str)
        and name
        and status in {"passed", "failed", "error", "skipped", "unknown"},
        "无效测试结果",
    )
    return dict(
        id=fingerprint(name, extra.get("suite", ""), extra.get("parameters", [])),
        name=name,
        status=status,
        duration_ms=number(duration) if duration is not None else None,
        detail=str(detail),
        **extra,
    )


def finding(rule, message, path="", line=None, severity="medium", **extra):
    require(bool(rule) and bool(message), "发现项缺少规则或描述")
    severity = str(severity).lower()
    severity = {
        "error": "high",
        "warning": "medium",
        "warn": "medium",
        "note": "low",
        "info": "info",
        "informational": "info",
        "none": "info",
    }.get(severity, severity)
    if severity not in {"critical", "high", "medium", "low", "info", "unknown"}:
        severity = "unknown"
    if line is not None:
        require(number(line) >= 1 and int(line) == float(line), "发现位置无效")
        line = int(line)
    return dict(
        id=fingerprint(str(rule), str(path), line, extra.get("component", "")),
        rule=str(rule),
        title=str(message).splitlines()[0][:300],
        detail=str(message),
        path=str(path),
        line=line,
        severity=severity,
        validation="tool-reported",
        **extra,
    )


def json_data(raw):
    def reject_constant(value):
        raise ValueError("JSON 非有限数值：" + value)

    def unique(pairs):
        obj = {}
        for k, v in pairs:
            require(k not in obj, "JSON 重复字段：" + k)
            obj[k] = v
        return obj

    return json.loads(raw, parse_constant=reject_constant, object_pairs_hook=unique)


def xml_data(raw):
    root = ET.fromstring(raw)
    for node in root.iter():
        node.tag = node.tag.split("}")[-1]
    return root


def junit(raw):
    root = xml_data(raw)
    require(root.tag in {"testsuite", "testsuites"}, "不是 JUnit 报告")
    out = base("junit")
    suites = list(root.iter("testsuite"))
    if root.tag == "testsuites" and root.findall("testcase"):
        suites.insert(0, root)
    for suite in suites:
        cases = suite.findall("testcase")
        for row in cases:
            error = row.find("error")
            failure = row.find("failure")
            skip = row.find("skipped")
            require(
                sum(x is not None for x in (error, failure, skip)) <= 1,
                "JUnit 结果冲突",
            )
            state = (
                "error"
                if error is not None
                else "failed"
                if failure is not None
                else "skipped"
                if skip is not None
                else "passed"
            )
            detail = next(
                (
                    "\n".join([x.get("message", ""), x.text or ""]).strip()
                    for x in (error, failure, skip)
                    if x is not None
                ),
                "",
            )
            out["tests"].append(
                test(
                    row.get("name"),
                    state,
                    number(row.get("time")) * 1000 if "time" in row.attrib else None,
                    detail,
                    suite=row.get("classname", suite.get("name", "")),
                )
            )
        # Counts on nested aggregate suites include descendants, not just direct cases.
        descendants = list(suite.iter("testcase"))
        for attr, count in {
            "tests": len(descendants),
            "failures": sum(x.find("failure") is not None for x in descendants),
            "errors": sum(x.find("error") is not None for x in descendants),
            "skipped": sum(x.find("skipped") is not None for x in descendants),
        }.items():
            if attr in suite.attrib:
                require(int(suite.get(attr)) == count, "JUnit 汇总不一致：" + attr)
    require(out["tests"], "JUnit 零用例")
    if root.tag == "testsuites" and "tests" in root.attrib:
        require(int(root.get("tests")) == len(out["tests"]), "JUnit 顶层数量不符")
    return out


def allure(raw):
    data = json_data(raw)
    rows = data if isinstance(data, list) else [data]
    out = base("allure")
    require(rows, "Allure 零用例")
    for row in rows:
        require(
            row.get("uuid")
            and row.get("status")
            in {"passed", "failed", "broken", "skipped", "unknown"},
            "无效 Allure result",
        )
        require(
            row.get("stage", "finished") == "finished"
            and "stop" in row
            and "start" in row,
            "Allure 未结束",
        )
        state = {"broken": "error"}.get(row["status"], row["status"])
        out["tests"].append(
            test(
                row.get("fullName") or row.get("name"),
                state,
                number(row["stop"]) - number(row["start"]),
                row.get("statusDetails", {}).get("trace")
                or row.get("statusDetails", {}).get("message", ""),
                parameters=row.get("parameters", []),
                labels=row.get("labels", []),
                attachments=row.get("attachments", []),
                history_id=row.get("historyId"),
                uuid=row["uuid"],
            )
        )
    return out


def sarif(raw):
    d = json_data(raw)
    require(
        d.get("version") == "2.1.0" and isinstance(d.get("runs"), list) and d["runs"],
        "需要 SARIF 2.1.0 runs",
    )
    out = base("sarif")
    for run in d["runs"]:
        driver = run.get("tool", {}).get("driver", {})
        require(
            driver.get("name") and isinstance(run.get("results"), list),
            "SARIF 缺少工具/结果",
        )
        rules = {r["id"]: r for r in driver.get("rules", [])}
        invocations = run.get("invocations", [])
        if not invocations:
            out["complete"] = False
            out["diagnostics"].append("SARIF 未附执行完成凭据")
        if any(x.get("executionSuccessful") is not True for x in invocations):
            out["complete"] = False
        for row in run["results"]:
            require(not row.get("suppressions"), "SARIF 含抑制项；须在门禁中显式处理")
            rule = row.get("ruleId") or str(row.get("ruleIndex", ""))
            locs = row.get("locations", []) or [{}]
            for location in locs:
                loc = location.get("physicalLocation", {})
                score = (
                    rules.get(rule, {}).get("properties", {}).get("security-severity")
                )
                level = row.get(
                    "level",
                    rules.get(rule, {})
                    .get("defaultConfiguration", {})
                    .get("level", "warning"),
                )
                if score is not None:
                    s = number(score)
                    level = (
                        "critical"
                        if s >= 9
                        else "high"
                        if s >= 7
                        else "medium"
                        if s >= 4
                        else "low"
                    )
                out["findings"].append(
                    finding(
                        rule,
                        row.get("message", {}).get("text")
                        or row.get("message", {}).get("markdown"),
                        loc.get("artifactLocation", {}).get("uri", ""),
                        loc.get("region", {}).get("startLine"),
                        level,
                        tool=driver["name"],
                        code_flows=row.get("codeFlows", []),
                        fingerprints=row.get("partialFingerprints", {}),
                    )
                )
    return out


def trx(raw):
    root = xml_data(raw)
    require(root.tag == "TestRun", "不是 TRX")
    out = base("trx")
    states = {
        "Passed": "passed",
        "Failed": "failed",
        "Error": "error",
        "NotExecuted": "skipped",
        "Inconclusive": "unknown",
        "Timeout": "error",
        "Aborted": "error",
    }
    for row in root.iter("UnitTestResult"):
        require(row.get("outcome") in states, "未知 TRX outcome")
        parts = row.get("duration", "0:0:0").split(":")
        require(len(parts) == 3, "TRX duration 无效")
        duration = (
            number(parts[0]) * 3600 + number(parts[1]) * 60 + number(parts[2])
        ) * 1000
        out["tests"].append(
            test(
                row.get("testName"),
                states[row.get("outcome")],
                duration if "duration" in row.attrib else None,
                "\n".join(row.itertext()).strip(),
            )
        )
    require(out["tests"], "TRX 零用例")
    counters = root.find(".//Counters")
    require(
        counters is not None and int(counters.get("total", -1)) == len(out["tests"]),
        "TRX 汇总不符",
    )
    return out


def robot(raw):
    root = xml_data(raw)
    require(
        root.tag == "robot" and root.get("generator", "").startswith("Robot"),
        "不是 Robot Framework 输出",
    )
    out = base("robot")

    def visit(suite, prefix=""):
        name = prefix + suite.get("name", "")
        for row in suite.findall("test"):
            state = row.find("status")
            require(
                state is not None and state.get("status") in {"PASS", "FAIL", "SKIP"},
                "Robot 状态缺失",
            )
            out["tests"].append(
                test(
                    row.get("name"),
                    {"PASS": "passed", "FAIL": "failed", "SKIP": "skipped"}[
                        state.get("status")
                    ],
                    number(state.get("elapsed")) * 1000
                    if "elapsed" in state.attrib
                    else None,
                    "\n".join(state.itertext()),
                    suite=name,
                )
            )
        for child in suite.findall("suite"):
            visit(child, name + "/")

    for suite in root.findall("suite"):
        visit(suite)
    require(out["tests"], "Robot 零用例")
    return out


def coverage(raw, kind):
    out = base(kind)
    hit = total = branches = covered_branches = 0
    if kind == "lcov":
        text = raw.decode()
        require(
            "SF:" in text and text.rstrip().endswith("end_of_record"),
            "LCOV 截断或无文件",
        )
        for line in text.splitlines():
            if line.startswith("DA:"):
                parts = line[3:].split(",")
                number(parts[0])
                total += 1
                hit += number(parts[1]) > 0
            if line.startswith("BRDA:"):
                v = line.split(",")[-1]
                branches += 1
                covered_branches += v != "-" and number(v) > 0
    else:
        root = xml_data(raw)
        if kind == "cobertura":
            require(root.tag == "coverage", "不是 Cobertura")
            total = number(root.get("lines-valid"))
            hit = number(root.get("lines-covered"))
            branches = number(root.get("branches-valid", 0))
            covered_branches = number(root.get("branches-covered", 0))
        else:
            require(root.tag == "report", "不是 JaCoCo")
            counters = {x.get("type"): x for x in root.findall("counter")}
            require("LINE" in counters, "JaCoCo 缺少 LINE")
            hit = number(counters["LINE"].get("covered"))
            total = hit + number(counters["LINE"].get("missed"))
            if "BRANCH" in counters:
                covered_branches = number(counters["BRANCH"].get("covered"))
                branches = covered_branches + number(counters["BRANCH"].get("missed"))
    require(
        total > 0 and hit <= total and covered_branches <= branches,
        "覆盖率没有可测行或计数冲突",
    )
    out["metrics"] = {
        "coverage.lines": 100 * hit / total,
        "coverage.lines_total": total,
    }
    if branches:
        out["metrics"]["coverage.branches"] = 100 * covered_branches / branches
    return out


def sbom(raw, kind):
    d = json_data(raw)
    out = base(kind)
    if kind == "cyclonedx":
        require(
            d.get("bomFormat") == "CycloneDX"
            and d.get("specVersion") in {"1.4", "1.5", "1.6", "1.7"}
            and isinstance(d.get("components", []), list),
            "CycloneDX 版本/组件无效",
        )
        for c in d.get("components", []):
            require(c.get("name") and c.get("type"), "SBOM 组件无身份")
            out["components"].append(
                dict(
                    name=c["name"],
                    version=c.get("version"),
                    purl=c.get("purl"),
                    licenses=[
                        x.get("expression")
                        or x.get("license", {}).get("id")
                        or x.get("license", {}).get("name", "UNKNOWN")
                        for x in c.get("licenses", [])
                    ],
                )
            )
    else:
        require(
            d.get("spdxVersion") in {"SPDX-2.2", "SPDX-2.3"}
            and isinstance(d.get("packages"), list),
            "需要 SPDX 2.2/2.3 JSON",
        )
        for c in d["packages"]:
            require(c.get("name") and c.get("SPDXID"), "SPDX 包无身份")
            out["components"].append(
                dict(
                    name=c["name"],
                    version=c.get("versionInfo"),
                    purl=next(
                        (
                            x.get("referenceLocator")
                            for x in c.get("externalRefs", [])
                            if x.get("referenceType") == "purl"
                        ),
                        None,
                    ),
                    licenses=[c.get("licenseConcluded", "NOASSERTION")],
                )
            )
    out["metrics"]["sbom.components"] = len(out["components"])
    out["metrics"]["sbom.unknown_license"] = sum(
        not c["licenses"]
        or any(x in {"UNKNOWN", "NOASSERTION", "NONE"} for x in c["licenses"])
        for c in out["components"]
    )
    require(out["components"], "SBOM 零组件；不能证明软件物料覆盖")
    return out


def security(raw, kind):
    d = json_data(raw)
    out = base(kind)
    if kind == "semgrep":
        require(
            isinstance(d.get("results"), list)
            and d.get("errors") == []
            and d.get("paths", {}).get("scanned"),
            "Semgrep 有错误或未扫描文件",
        )
        for x in d["results"]:
            out["findings"].append(
                finding(
                    x["check_id"],
                    x["extra"]["message"],
                    x["path"],
                    x["start"]["line"],
                    x["extra"]["severity"],
                )
            )
        out["metrics"]["scan.files"] = len(d["paths"]["scanned"])
    elif kind == "bandit":
        require(
            d.get("errors") == []
            and isinstance(d.get("results"), list)
            and number(d.get("metrics", {}).get("_totals", {}).get("loc", 0)) > 0,
            "Bandit 错误/零扫描",
        )
        for x in d["results"]:
            out["findings"].append(
                finding(
                    x["test_id"],
                    x["issue_text"],
                    x["filename"],
                    x["line_number"],
                    x["issue_severity"],
                    cwe=x.get("issue_cwe"),
                )
            )
    elif kind == "gitleaks":
        require(isinstance(d, list), "Gitleaks 不是列表")
        for x in d:
            require(x.get("Secret") == "REDACTED", "Gitleaks 必须使用 --redact=100")
            out["findings"].append(
                finding(
                    x["RuleID"], x["Description"], x["File"], x["StartLine"], "high"
                )
            )
    elif kind == "trivy":
        require(
            d.get("SchemaVersion") == 2
            and d.get("ArtifactName")
            and isinstance(d.get("Results", []), list),
            "Trivy SchemaVersion 2 required",
        )
        require(d.get("Results"), "Trivy 未报告扫描对象")
        for result in d["Results"]:
            for x in result.get("Vulnerabilities", []) or []:
                out["findings"].append(
                    finding(
                        x["VulnerabilityID"],
                        x.get("Title") or x["VulnerabilityID"],
                        result.get("Target", ""),
                        severity=x["Severity"],
                        component=x["PkgName"] + "@" + x["InstalledVersion"],
                        fix=x.get("FixedVersion"),
                    )
                )
            for x in result.get("Misconfigurations", []) or []:
                out["findings"].append(
                    finding(
                        x["ID"],
                        x["Message"],
                        result.get("Target", ""),
                        x.get("CauseMetadata", {}).get("StartLine") or None,
                        x["Severity"],
                    )
                )
            for x in result.get("Secrets", []) or []:
                out["findings"].append(
                    finding(
                        x["RuleID"],
                        x["Title"],
                        result.get("Target", ""),
                        x.get("StartLine"),
                        x["Severity"],
                    )
                )
    elif kind == "grype":
        require(
            isinstance(d.get("matches"), list)
            and d.get("descriptor", {}).get("name") == "grype"
            and d.get("source"),
            "Grype 报告缺失",
        )
        for x in d["matches"]:
            v = x["vulnerability"]
            c = x["artifact"]
            out["findings"].append(
                finding(
                    v["id"],
                    v.get("description") or v["id"],
                    severity=v["severity"],
                    component=c["name"] + "@" + c["version"],
                    fix=v.get("fix"),
                    locations=c.get("locations", []),
                )
            )
    elif kind == "npm-audit":
        require(
            d.get("auditReportVersion") == 2
            and isinstance(d.get("vulnerabilities"), dict)
            and d.get("metadata", {}).get("dependencies", {}).get("total", 0) > 0
            and not d.get("error"),
            "npm audit 不完整",
        )
        for name, x in d["vulnerabilities"].items():
            for v in x.get("via", []):
                if isinstance(v, dict):
                    out["findings"].append(
                        finding(
                            str(v["source"]),
                            v["title"],
                            severity=v["severity"],
                            component=name,
                            url=v.get("url"),
                            fix=x.get("fixAvailable"),
                        )
                    )
        # Transitive aliases remain in the original artifact; do not invent a CVE for them.
    elif kind == "pip-audit":
        require(
            isinstance(d, dict)
            and isinstance(d.get("dependencies"), list)
            and d["dependencies"],
            "pip-audit 零依赖",
        )
        for dep in d["dependencies"]:
            require(not dep.get("skip_reason"), "pip-audit 存在跳过的依赖")
            for x in dep["vulns"]:
                out["findings"].append(
                    finding(
                        x["id"],
                        x.get("description") or x["id"],
                        severity="unknown",
                        component=dep["name"] + "@" + dep["version"],
                        fix=x.get("fix_versions", []),
                    )
                )
    elif kind == "defectdojo":
        require(
            isinstance(d.get("findings"), list), "DefectDojo Generic Findings 格式错误"
        )
        for x in d["findings"]:
            out["findings"].append(
                finding(
                    x.get("vuln_id_from_tool")
                    or x.get("unique_id_from_tool")
                    or str(x.get("cwe", "finding")),
                    x["title"] + "\n" + x.get("description", ""),
                    x.get("file_path", ""),
                    x.get("line"),
                    x["severity"],
                    cwe=x.get("cwe"),
                    mitigation=x.get("mitigation"),
                )
            )
    else:
        raise ValueError("未知安全报告格式")
    return out


def diagnostics(raw, kind):
    d = json_data(raw)
    out = base(kind)
    if kind == "eslint":
        require(isinstance(d, list) and d, "ESLint 没有扫描文件")
        for f in d:
            require(
                f.get("fatalErrorCount", 0) == 0
                and isinstance(f.get("messages"), list),
                "ESLint 解析错误",
            )
            for x in f["messages"]:
                out["findings"].append(
                    finding(
                        x.get("ruleId") or "parse",
                        x["message"],
                        f["filePath"],
                        x.get("line"),
                        "medium" if x["severity"] == 2 else "low",
                    )
                )
        out["metrics"]["scan.files"] = len(d)
    elif kind == "ruff":
        require(isinstance(d, list), "Ruff 格式错误")
        for x in d:
            out["findings"].append(
                finding(
                    x["code"],
                    x["message"],
                    x["filename"],
                    x["location"]["row"],
                    "medium",
                    fix=x.get("fix"),
                )
            )
    elif kind in {"hadolint", "shellcheck", "spectral"}:
        if kind == "shellcheck":
            d = d["comments"]
        require(isinstance(d, list), "诊断结果不是列表")
        for x in d:
            path = x.get("file") or x.get("source", "")
            line = x.get("line")
            if kind == "spectral":
                line = x["range"]["start"]["line"] + 1
            out["findings"].append(
                finding(
                    str(x["code"]),
                    x["message"],
                    path,
                    line,
                    str(x.get("level", "medium")),
                )
            )
    elif kind == "checkov":
        groups = d if isinstance(d, list) else [d]
        require(
            groups
            and any(
                x.get("summary", {}).get("passed", 0)
                + x.get("summary", {}).get("failed", 0)
                > 0
                for x in groups
            ),
            "Checkov 零检查",
        )
        for group in groups:
            require(
                group.get("summary", {}).get("parsing_errors", 0) == 0
                and group.get("summary", {}).get("skipped", 0) == 0,
                "Checkov 解析错误/跳过",
            )
            for x in group.get("results", {}).get("failed_checks", []):
                out["findings"].append(
                    finding(
                        x["check_id"],
                        x["check_name"],
                        x["file_path"],
                        (x.get("file_line_range") or [None])[0],
                        x.get("severity") or "unknown",
                        resource=x.get("resource"),
                    )
                )
    else:
        raise ValueError("未知诊断格式")
    return out


def performance(raw, kind):
    d = json_data(raw)
    out = base(kind)
    if kind == "k6":
        require(
            isinstance(d.get("metrics"), dict)
            and d["metrics"].get("iterations", {}).get("values", {}).get("count", 0)
            > 0,
            "k6 零迭代或非 handleSummary 输出",
        )
        for name, metric in d["metrics"].items():
            for key, value in metric.get("values", {}).items():
                out["metrics"]["k6." + name + "." + key] = number(value)
            for name_, threshold in metric.get("thresholds", {}).items():
                require(isinstance(threshold.get("ok"), bool), "k6 threshold 状态缺失")
                out["tests"].append(
                    test(name + " " + name_, "passed" if threshold["ok"] else "failed")
                )
    elif kind == "axe":
        require(
            d.get("testEngine", {}).get("name") == "axe-core"
            and all(
                isinstance(d.get(k), list)
                for k in ("violations", "passes", "incomplete", "inapplicable")
            ),
            "axe 报告不完整",
        )
        out["complete"] = not d["incomplete"]
        require(d["violations"] or d["passes"], "axe 没有适用规则")
        for x in d["violations"]:
            out["findings"].append(
                finding(
                    x["id"],
                    x["help"],
                    d.get("url", ""),
                    severity={
                        "critical": "critical",
                        "serious": "high",
                        "moderate": "medium",
                        "minor": "low",
                    }.get(x.get("impact"), "unknown"),
                    nodes=x["nodes"],
                    tags=x.get("tags", []),
                )
            )
    elif kind == "lighthouse":
        require(
            d.get("lighthouseVersion")
            and not d.get("runtimeError")
            and d.get("categories"),
            "Lighthouse 执行未完成",
        )
        for key, c in d["categories"].items():
            out["metrics"]["lighthouse." + key] = 100 * number(c["score"])
        for key, a in d.get("audits", {}).items():
            if a.get("score") == 0:
                out["findings"].append(
                    finding(
                        key,
                        a["title"],
                        d.get("finalDisplayedUrl", d.get("finalUrl", "")),
                        severity="medium",
                        description=a.get("description"),
                    )
                )
    elif kind == "newman":
        run = d.get("run", {})
        require(
            run.get("executions") and isinstance(run.get("failures"), list),
            "Newman 未执行请求",
        )
        for execution in run["executions"]:
            name = execution.get("item", {}).get("name", "request")
            for assertion in execution.get("assertions", []):
                state = (
                    "skipped"
                    if assertion.get("skipped")
                    else "failed"
                    if assertion.get("error")
                    else "passed"
                )
                out["tests"].append(
                    test(
                        name + " / " + assertion["assertion"],
                        state,
                        detail=json.dumps(assertion.get("error", {})),
                    )
                )
        require(out["tests"], "Newman 没有断言")
        if run["failures"] and not any(t["status"] == "failed" for t in out["tests"]):
            out["complete"] = False
    return out


FORMATS = {
    "junit": junit,
    "allure": allure,
    "sarif": sarif,
    "trx": trx,
    "robot": robot,
    **{k: (lambda raw, k=k: coverage(raw, k)) for k in ("lcov", "cobertura", "jacoco")},
    **{k: (lambda raw, k=k: sbom(raw, k)) for k in ("cyclonedx", "spdx")},
    **{
        k: (lambda raw, k=k: security(raw, k))
        for k in (
            "semgrep",
            "bandit",
            "gitleaks",
            "trivy",
            "grype",
            "npm-audit",
            "pip-audit",
            "defectdojo",
        )
    },
    **{
        k: (lambda raw, k=k: diagnostics(raw, k))
        for k in ("eslint", "ruff", "hadolint", "shellcheck", "spectral", "checkov")
    },
    **{
        k: (lambda raw, k=k: performance(raw, k))
        for k in ("k6", "axe", "lighthouse", "newman")
    },
}


def parse(kind, raw):
    require(kind in FORMATS, "未注册报告格式")
    require(0 < len(raw), "报告为空")
    try:
        out = FORMATS[kind](raw)
    except (KeyError, TypeError, AttributeError, OverflowError) as exc:
        raise ValueError("报告结构不完整：" + str(exc)) from exc
    ids = [t["id"] for t in out["tests"]]
    require(len(ids) == len(set(ids)), "重复测试身份；重试须独立作为 attempt 导入")
    for f in out["findings"]:
        f["observation_id"] = fingerprint(f)
    out["metrics"].update(
        {
            "tests.total": len(out["tests"]),
            **{
                "tests." + s: sum(t["status"] == s for t in out["tests"])
                for s in ("passed", "failed", "error", "skipped", "unknown")
            },
            "findings.total": len(out["findings"]),
            **{
                "findings." + s: sum(f["severity"] == s for f in out["findings"])
                for s in ("critical", "high", "medium", "low", "info", "unknown")
            },
        }
    )
    if out["tests"]:
        out["metrics"]["tests.success_rate"] = (
            100 * out["metrics"]["tests.passed"] / len(out["tests"])
        )
        if all(t["duration_ms"] is not None for t in out["tests"]):
            out["metrics"]["tests.duration_ms"] = sum(
                t["duration_ms"] for t in out["tests"]
            )
    if any(t["status"] in {"error", "unknown", "skipped"} for t in out["tests"]):
        out["complete"] = False
    return out


# Late binding avoids importing HTTP clients in each low-level format adapter.
def _service(raw, kind):
    from .services import parse_service

    return parse_service(raw, kind)


FORMATS.update(
    {
        k: (lambda raw, k=k: _service(raw, k))
        for k in ("defectdojo-api", "reportportal", "sonarqube")
    }
)


def _extended(raw, kind):
    from . import extended_formats

    return getattr(extended_formats, kind)(raw)


FORMATS.update({k: (lambda raw, k=k: _extended(raw, k)) for k in ("playwright", "zap")})
