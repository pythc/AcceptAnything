"""Explicit policy operands; OPA is the final authority for release decisions."""

from pathlib import Path
import json
import subprocess
from .formats import require
from .models import Rule


def evaluate(rules, tasks, baseline=None):
    by_id = {t["id"]: t for t in tasks}
    results = []
    for data in rules:
        rule = Rule.model_validate(data)
        item = dict(
            id=rule.id,
            kind=rule.kind,
            tasks=rule.tasks,
            status="unknown",
            expected=rule.model_dump(),
            actual=None,
            reason="",
        )
        try:
            selected = [by_id[x] for x in rule.tasks]
            require(
                all(
                    t.get("state") == "completed"
                    and t.get("report", {}).get("complete") is True
                    for t in selected
                ),
                "任务未完整执行",
            )
            reports = [t["report"] for t in selected]
            if rule.kind in {"metric", "delta"}:
                require(
                    all(rule.metric in r["metrics"] for r in reports),
                    "缺少指标 " + str(rule.metric),
                )
                reduce = {"sum": sum, "min": min, "max": max}[rule.reduction]
                actual = reduce([r["metrics"][rule.metric] for r in reports])
                if rule.kind == "delta":
                    require(
                        baseline is not None
                        and baseline.get("integrity") is True
                        and baseline.get("decision") in {"allow", "reject"},
                        "缺少完整可比基线",
                    )
                    previous = {t["id"]: t for t in baseline["tasks"]}
                    require(
                        all(
                            x in previous
                            and rule.metric in previous[x]["report"]["metrics"]
                            for x in rule.tasks
                        ),
                        "基线任务或指标不完整",
                    )
                    actual -= reduce(
                        [
                            previous[x]["report"]["metrics"][rule.metric]
                            for x in rule.tasks
                        ]
                    )
                ok = {
                    "le": lambda: actual <= rule.threshold,
                    "ge": lambda: actual >= rule.threshold,
                    "eq": lambda: actual == rule.threshold,
                }[rule.operator]()
            elif rule.kind == "new-findings":
                require(
                    baseline is not None
                    and baseline.get("integrity") is True
                    and baseline.get("decision") in {"allow", "reject"},
                    "缺少完整可比基线",
                )
                previous = {t["id"]: t for t in baseline["tasks"]}
                require(set(rule.tasks) <= set(previous), "基线缺少任务")
                before = {
                    (x, f["id"])
                    for x in rule.tasks
                    for f in previous[x]["report"]["findings"]
                }
                after = {
                    (t["id"], f["id"])
                    for t in selected
                    for f in t["report"]["findings"]
                    if not rule.values or f["severity"] in rule.values
                }
                actual = len(after - before)
                ok = actual <= rule.threshold
            elif rule.kind == "licenses":
                components = [c for r in reports for c in r["components"]]
                require(components, "缺少 SBOM 组件")
                import re

                actual = sorted(
                    {
                        license_
                        for c in components
                        for license_ in (c["licenses"] or ["UNKNOWN"])
                        if any(x in rule.values for x in re.split(r"[ ()]+", license_))
                        or license_ in {"NOASSERTION", "UNKNOWN", "NONE"}
                    }
                )
                ok = not actual
            elif rule.kind == "required-tests":
                rows = [t for r in reports for t in r["tests"]]
                matches = {
                    v: [t for t in rows if t["id"] == v or t["name"] == v]
                    for v in rule.values
                }
                require(all(matches.values()), "必测用例缺失")
                require(
                    all(len(v) == 1 for v in matches.values()),
                    "用例名称不唯一；请用稳定用例 ID 指定",
                )
                actual = [
                    v
                    for v, matches_ in matches.items()
                    if matches_[0]["status"] != "passed"
                ]
                ok = not actual
            else:
                actual = sorted({t["environment"] for t in selected})
                ok = set(rule.values) <= set(actual)
            item.update(
                actual=actual,
                status="passed" if ok else "failed",
                reason="" if ok else "未满足冻结门禁条件",
            )
        except (ValueError, KeyError) as exc:
            item["reason"] = str(exc)
        results.append(item)
    return results


def opa_decide(payload, directory, image):
    directory = Path(directory).resolve()
    # OPA consumes deterministic aggregate operands, not duplicated raw reports.
    # Original reports/review retain their separate verified evidence identities.
    projected={**payload,'tasks':[{'id':t['id'],'state':t['state'],'report':{'complete':t.get('report',{}).get('complete',False),'metrics':t.get('report',{}).get('metrics',{})},'source_report_ref':t.get('report_ref')} for t in payload['tasks']]}
    if 'finding_review' in projected:
        projected['finding_review']={k:payload['finding_review'][k] for k in ['version','summary','snapshot_digest','policy_sha256'] if k in payload['finding_review']}
    (directory / "gate-input.json").write_text(json.dumps(projected, ensure_ascii=False, allow_nan=False))
    policy = Path(__file__).with_name("gates.rego").read_bytes()
    (directory / "policy.rego").write_bytes(policy)
    args = [
        "docker",
        "run",
        "--rm",
        "--network",
        "none",
        "--cap-drop",
        "ALL",
        "--security-opt",
        "no-new-privileges",
        "--memory",
        "256m",
        "--cpus",
        "1",
        "--mount",
        f"type=bind,src={directory},dst=/input,readonly",
        image,
        "eval",
        "--format=json",
        "--data",
        "/input/policy.rego",
        "--input",
        "/input/gate-input.json",
        "data.integrations.decision",
    ]
    result = subprocess.run(args, capture_output=True, timeout=30)
    (directory / "gate-result.json").write_bytes(result.stdout)
    require(
        result.returncode == 0,
        "OPA 执行失败：" + result.stderr.decode(errors="replace")[:200],
    )
    d = json.loads(result.stdout)
    values = d.get("result", [])
    require(
        len(values) == 1 and len(values[0]["expressions"]) == 1, "OPA 未产生唯一判定"
    )
    decision = values[0]["expressions"][0]["value"]
    require(decision in {"allow", "reject", "inconclusive"}, "OPA 判定无效")
    return decision
