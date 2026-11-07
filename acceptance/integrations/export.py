"""CI consumes real gate status (0/1/2); exports never turn inconclusive into green."""

from xml.etree.ElementTree import Element, SubElement, tostring
import json


def junit(run):
    rows = run.get("rules", [])
    suite = Element(
        "testsuite",
        name=run["name"],
        tests=str(max(1, len(rows))),
        failures=str(sum(x["status"] == "failed" for x in rows)),
        errors=str(sum(x["status"] == "unknown" for x in rows) if rows else 1),
    )
    for rule in rows or [
        {"id": "execution", "status": "unknown", "reason": "未产生门禁结果"}
    ]:
        c = SubElement(suite, "testcase", name=rule["id"], classname="acceptance.gate")
        if rule["status"] != "passed":
            SubElement(
                c,
                "failure" if rule["status"] == "failed" else "error",
                message=rule.get("reason", ""),
            ).text = json.dumps(rule, ensure_ascii=False)
    if (
        run["decision"] == "inconclusive"
        and rows
        and not any(x["status"] == "unknown" for x in rows)
    ):
        c = SubElement(suite, "testcase", name="evidence-integrity")
        SubElement(c, "error", message="证据/执行完整性未确认")
        suite.set("tests", str(len(rows) + 1))
        suite.set("errors", str(int(suite.get("errors")) + 1))
    return tostring(suite, encoding="utf-8", xml_declaration=True)


def sarif(run):
    results = []
    for task in run["tasks"]:
        for f in task.get("report", {}).get("findings", []):
            row = {
                "ruleId": task["tool"] + "/" + f["rule"],
                "level": "error"
                if f["severity"] in {"critical", "high"}
                else "warning",
                "message": {"text": f["detail"]},
                "partialFingerprints": {"acceptance/v1": f["id"]},
                "properties": {
                    "task": task["id"],
                    "severity": f["severity"],
                    "validation": f["validation"],
                },
            }
            if f["path"]:
                loc = {"artifactLocation": {"uri": f["path"]}}
                if f.get("line"):
                    loc["region"] = {"startLine": f["line"]}
                row["locations"] = [{"physicalLocation": loc}]
            results.append(row)
    return json.dumps(
        {
            "version": "2.1.0",
            "$schema": "https://json.schemastore.org/sarif-2.1.0.json",
            "runs": [
                {
                    "tool": {
                        "driver": {
                            "name": "Acceptance Integrations",
                            "version": "0.9.0",
                        }
                    },
                    "invocations": [
                        {
                            "executionSuccessful": run["status"] == "completed"
                            and run["decision"] != "inconclusive"
                        }
                    ],
                    "results": results,
                }
            ],
        },
        ensure_ascii=False,
        indent=2,
    ).encode()


def markdown(run):
    s = [
        f"# {run['name']}",
        f"结论：{run['decision']}",
        f"执行：{run['id']}",
        f"来源：{run['mode']}",
    ]
    context = run.get("context") or {}
    s += [
        f"{k}：{context.get(k, '未采集')}"
        for k in ("repository", "revision", "snapshot_digest", "environment", "scope")
    ]
    s += ["## 检查结果"]
    for t in run["tasks"]:
        s += [
            f"- {t['id']} · {t['state']} · {t.get('duration_ms', '未采集')} ms · {t.get('error', '')}"
        ]
    s += ["## 门禁"]
    for r in run["rules"]:
        s += [f"- {r['id']} · {r['status']} · 实际 {r['actual']} · {r['reason']}"]
    s += ["## 发现项"]
    for t in run["tasks"]:
        for f in t.get("report", {}).get("findings", []):
            s += [
                f"### {f['title']}",
                f"{t['id']} · {f['severity']} · {f['path']}:{f.get('line') or ''}",
                f["detail"],
                f"证据：{t.get('report_ref')} · 定位标识 {f['id']}",
            ]
    s += ["## 原始证据"]
    for a in run["artifacts"]:
        s += [f"- {a['name']} · {a['id']} · SHA-256 {a['sha256']}"]
    s += ["## 排除范围"] + [
        f"- {x['subject']}：{x['reason']}" for x in run["exclusions"]
    ]
    return ("\n\n".join(s) + "\n").encode()
