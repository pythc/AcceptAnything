"""Execution history and native web/security reports, retaining retry evidence."""

from .formats import base, test, finding, json_data, require, number


def playwright(raw):
    d = json_data(raw)
    require(
        isinstance(d.get("errors"), list) and isinstance(d.get("suites"), list),
        "Playwright 报告字段缺失",
    )
    out = base("playwright")
    out["complete"] = not d["errors"]
    flaky = retried = 0

    def walk(suites):
        for suite in suites:
            yield from suite.get("specs", [])
            yield from walk(suite.get("suites", []))

    for spec in walk(d["suites"]):
        for case in spec["tests"]:
            results = case["results"]
            require(results, "Playwright 用例未执行")
            require(
                [x.get("retry") for x in results] == list(range(len(results))),
                "重试记录缺失/顺序不符",
            )
            status = results[-1]["status"]
            require(
                status in {"passed", "failed", "timedOut", "skipped", "interrupted"},
                "Playwright 未知状态",
            )
            previous_failure = any(x["status"] != "passed" for x in results[:-1])
            is_flaky = status == "passed" and previous_failure
            flaky += is_flaky
            retried += len(results) > 1
            out["tests"].append(
                test(
                    spec["title"],
                    {"timedOut": "error", "interrupted": "error"}.get(status, status),
                    sum(number(x["duration"]) for x in results),
                    "\n".join(
                        e.get("message", "")
                        for r in results
                        for e in r.get("errors", [])
                    ),
                    suite=spec.get("file", "") + " / " + case.get("projectName", ""),
                    attempts=results,
                    flaky=is_flaky,
                    environment=case.get("projectName"),
                    expected_status=case.get("expectedStatus"),
                )
            )
    require(out["tests"], "Playwright 零用例")
    stats = d.get("stats", {})
    require(
        all(k in stats for k in ("expected", "unexpected", "flaky", "skipped")),
        "Playwright 汇总缺失",
    )
    require(
        sum(stats[k] for k in ("expected", "unexpected", "flaky", "skipped"))
        == len(out["tests"]),
        "Playwright 汇总不符",
    )
    require(stats["flaky"] == flaky, "Playwright flaky 数量不符")
    out["metrics"].update(
        {
            "tests.flaky": flaky,
            "tests.retried": retried,
            "tests.max_duration_ms": max(t["duration_ms"] for t in out["tests"]),
        }
    )
    return out


def zap(raw):
    d = json_data(raw)
    require(
        d.get("@version") and isinstance(d.get("site"), list) and d["site"],
        "ZAP 报告无扫描站点",
    )
    out = base("zap")
    for site in d["site"]:
        require(
            site.get("@name") and isinstance(site.get("alerts"), list),
            "ZAP 站点格式错误",
        )
        for x in site["alerts"]:
            severity = {"0": "info", "1": "low", "2": "medium", "3": "high"}.get(
                str(x["riskcode"])
            )
            require(severity is not None and x.get("instances"), "ZAP 风险或证据缺失")
            for location in x["instances"]:
                out["findings"].append(
                    finding(
                        str(x["pluginid"]),
                        x.get("name") or x["alert"],
                        location["uri"],
                        severity=severity,
                        method=location.get("method"),
                        parameter=location.get("param"),
                        evidence=location.get("evidence"),
                        cwe=x.get("cweid"),
                        solution=x.get("solution"),
                        description=x.get("desc"),
                    )
                )
    return out
