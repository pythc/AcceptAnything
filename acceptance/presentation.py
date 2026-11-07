"""Read-only, source-bound projections for the local fixture workbench.

Observations come from verified executor artifacts. Reproduction instructions
describe the frozen suite, not extra actions performed by this adapter.
"""
import json
import re
from pathlib import Path


CASES = {
    "SEC-SHELL": {
        "subject": "search(user_input) · Shell 调用",
        "steps": ["扫描当前版本的静态样本。", "用 Bandit B602 检查 subprocess 的 shell=True 调用。", "将命中位置、代码和规则等级保存为原始报告。"],
        "limitation": "静态检测；没有执行注入载荷，也没有证明外部调用入口可达。",
    },
    "REQ-HEALTH": {
        "subject": "GET /health",
        "steps": ["向本地夹具发送 GET /health。", "断言 HTTP 状态码为 200。"],
        "limitation": "只验证健康接口的状态码，不代表全部功能或依赖可用。",
    },
    "SEC-IDOR": {
        "subject": "Alice → Bob 的私有文档",
        "steps": ["POST /api/login，以 alice 登录并取得测试令牌。", "使用该令牌 GET /api/documents/bob-private。", "断言状态码为 403，再检查响应不含私有内容。"],
        "limitation": "若状态码断言先失败，后续正文断言不会执行；不能仅凭此报告断言具体正文已泄露。",
    },
    "SEC-SESSION": {
        "subject": "退出登录 → 重用旧令牌",
        "steps": ["以 alice 登录，确认 GET /api/me 返回 200。", "使用同一令牌 POST /api/logout。", "再次使用旧令牌 GET /api/me，断言返回 401。"],
        "limitation": "仅验证本地夹具中的会话失效行为；未测试实际身份服务。",
    },
    "REQ-IDEMPOTENCY": {
        "subject": "相同幂等键 → 两次创建订单",
        "steps": ["POST /api/orders，携带 Idempotency-Key: research-order-1。", "使用相同的键与 synthetic-item 请求体再次提交。", "确认两次响应为 201，并比较两个订单 ID 是否相同。"],
        "limitation": "这是顺序重复提交验证；未测试并发竞争或真实扣款。",
    },
    "REQ-CONTRACT": {
        "subject": "GET /api/contract · count 字段",
        "steps": ["GET /api/contract 并解析 JSON。", "读取 typeof count，断言其为 number。"],
        "limitation": "只验证 count 的 JavaScript 类型，未覆盖完整接口 Schema。",
    },
    "REQ-PERSIST": {
        "subject": "保存笔记 → 刷新页面",
        "steps": ["打开首页，在 #note 输入 independent acceptance record。", "点击 Save，并确认页面显示 Saved。", "刷新页面，断言 #saved 仍显示所保存的内容。"],
        "limitation": "断言超时为 1500 ms；这里只证明该次刷新后的页面结果，不推断其他存储环境。",
    },
    "A11Y-LABEL": {
        "subject": "首页表单 · 可访问名称",
        "steps": ["打开首页。", "使用 axe-core 执行 label 规则。", "保存完整 axe 报告，并断言 violations 为空。"],
        "limitation": "仅执行 label 规则，不代表完整无障碍审计。",
    },
}
CATALOG_SUITE_DIGEST = "4b67830b8730e15fcab3024d216da1cccf5db4b9ed0779feb2751bd03cc9e061"


def clean(value):
    return re.sub(r"\x1b\[[0-9;]*m", "", str(value or ""))


def short_path(value):
    value = str(value or "")
    index = value.find("validation/")
    return value[index:] if index >= 0 else Path(value).name


def case_plans(run):
    if run["baseline"].get("recipe"):
        return {c["id"]: {"subject": c["title"], "steps": ["核对本次冻结的源文件、标准与执行器。", c["expected"], "保存原始报告，核验实际执行清单；未覆盖项保留原因并阻止放行。"]} for c in run["baseline"]["criteria"]}
    if run.get("project_id"):
        return {c["id"]: {"subject": c["title"], "steps": ["从封存源文件启动无网络容器。", "执行 " + c["test_file"], "核对批准的测试名称、结果及原始 JUnit。"]} for c in run["baseline"]["criteria"]}
    if run.get("suite_digest") != CATALOG_SUITE_DIGEST:
        return {}
    return {c["id"]: {k: CASES[c["id"]][k] for k in ("subject", "steps")} for c in run["baseline"]["criteria"] if c["id"] in CASES}


def inspections(store, run, validation=None, reader=None):
    """Never rewrite a sealed historical record or derive facts from file names."""
    projected = {}
    if validation is None:
        from acceptance.validation import Reader, validate_results
        reader = Reader(store, run)
        validation = validate_results(store, run, reader)
    if run["baseline"].get("recipe"):
        for result in run["results"]:
            cid=result["criterion_id"]
            c=next(c for c in run["baseline"]["criteria"] if c["id"]==cid)
            check=validation["checks"].get(cid,{})
            valid=check.get("valid",False)
            report=check.get("report",{})
            observed=report.get("summary") or ("浏览器断言通过" if result["status"]=="passed" else clean(report.get("result",{}).get("error",{}).get("message")))
            if valid and c["kind"] in ("junit", "python", "semgrep", "python-sast", "zap"):
                observed=report.get("summary",observed).split("\n",1)[0]
            if valid and result["status"] != "blocked" and c["kind"] == "gitleaks":
                observed=f"{report['failed']} 处密钥规则命中，尚待确认用途。"
            if valid and result["status"] != "blocked" and c["kind"] == "npm-audit":
                observed=f"{report['failed']} 个依赖告警；是否可利用仍需复核调用路径。"
            projected[cid]={**case_plans(run)[cid], "criterion_id":cid,"status":result["status"],"method":{"junit":"Node.js · JUnit", "python":"Python unittest", "build":"工作区构建", "gitleaks":"Gitleaks", "npm-audit":"npm audit", "restore":"PostgreSQL · pg_dump / pg_restore", "playwright":"Playwright", "gap":"未覆盖范围", "semgrep":"Semgrep CE · njsscan", "python-sast":"Bandit", "zap":"OWASP ZAP", "k6":"k6", "joint-restore":"pg_dump / pg_restore · 文件摘要 · HTTP 读取"}[c["kind"]],"verified":valid,
                "summary":observed if valid else "原始结果无法核实", "observation":(report.get("actual") or clean(result["actual"])) if valid else check.get("reason","执行未完成"),
                "expected_value":c["expected"],"actual_value":observed if valid else None,"evidence_refs":result["evidence_refs"],"primary_ref":check.get("primary_ref"),"source_report":check.get("source_report"),"limitation":c["limitation"]}
            # Composite checks must not display only the final hash/read probe's
            # duration. Keep the original command timing unchanged in evidence.
            if valid and result["status"] != "blocked" and c["kind"] == "joint-restore":
                raw=json.loads(reader.read(check["primary_ref"])[1])
                projected[cid]["duration_ms"]=raw["recovery_seconds"]*1000
            if valid and result["status"] != "blocked" and c["kind"] == "build":
                projected[cid]["duration_ms"]=sum(cmd["duration_ms"] for cmd in run["commands"] if cmd["name"] in ("compile",cid))
            if valid and result["status"] != "blocked" and c["kind"] == "zap":
                raw=json.loads(reader.read(check["primary_ref"])[1])
                rules=[x["Plugin"] for x in raw["active_progress"][1]["HostProcess"]]
                sent=sum(int(x[5])>0 for x in rules)
                projected[cid]["summary"]=f"{len(raw['urls'])} 个地址、{raw['messages']} 次 HTTP 请求，{report['failed']} 类安全告警"
                projected[cid]["observation"]+=f"\n\n扫描范围：公开入口，未登录。{len(rules)} 条主动规则调度结束，其中 {sent} 条产生请求，{len(rules)-sent} 条未产生请求；不能据此认定已覆盖全部攻击类型。"
                if raw.get("diagnostics"):
                    projected[cid]["observation"]+="\n\n工具诊断（保留原文，不作为产品漏洞）：\n"+"\n".join(raw["diagnostics"])
        return projected
    if run.get("project_id"):
        for result in run["results"]:
            cid = result["criterion_id"]
            check = validation["checks"].get(cid, {})
            c = next((c for c in run["baseline"]["criteria"] if c["id"] == cid), None)
            if c is None:
                continue
            report = check.get("report", {})
            projected[cid] = {**case_plans(run)[cid], "criterion_id": cid, "status": result["status"], "method": "Node.js Test Runner · JUnit 核验", "verified": check.get("valid", False),
                "summary": (f"{report['tests']} 个已登记测试，{report['failed']} 个失败。" if check.get("valid") else "原始执行报告无法核实。"),
                "observation": report.get("failure_text") or ("\n".join(report.get("case_names", [])) if check.get("valid") else check.get("reason", "执行未完成")),
                "expected_value": c["expected"], "actual_value": (str(report["failed"]) + " 个失败") if check.get("valid") else None, "evidence_refs": result["evidence_refs"], "primary_ref": check.get("primary_ref"), "location": c["test_file"],
                "limitation": "仅验证现有回归测试中的断言；未证明完整业务流程、服务端权限或实际部署通过。"}
        return projected
    if run.get("suite_digest") != CATALOG_SUITE_DIGEST:
        return projected
    for result in run["results"]:
        cid = result["criterion_id"]
        case = CASES.get(cid)
        if not case:
            continue
        detail = {**case, "criterion_id": cid, "status": result["status"], "method": "Bandit B602 · 静态检测" if cid == "SEC-SHELL" else "Playwright · 运行验证",
                  "summary": "原始结果待核实", "observation": "尚未读取到有效执行报告。", "verified": False,
                  "evidence_refs": result["evidence_refs"], "expected_value": result["expected"], "actual_value": None}
        try:
            checked = validation["checks"].get(cid, {})
            if not checked.get("valid"):
                raise ValueError(checked.get("reason", "结果未核实"))
            name = "bandit.json" if cid == "SEC-SHELL" else cid + "-result.json"
            artifact = next((a for a in run["artifacts"] if a["id"] in result["evidence_refs"] and a["name"] == name), None)
            if not artifact:
                projected[cid] = detail
                continue
            _, data = reader.read(artifact["id"])
            report = json.loads(data)
            detail["primary_ref"] = artifact["id"]
            if cid == "SEC-SHELL":
                if report.get("errors") or not isinstance(report.get("results"), list):
                    raise ValueError("不完整的 Bandit 报告")
                hits = [x for x in report["results"] if x.get("test_id") == "B602"]
                if (result["status"] == "failed" and not hits) or (result["status"] == "passed" and hits):
                    raise ValueError("检测状态与报告不一致")
                detail.update(verified=True, expected_value="B602 命中 0 处", actual_value=f"B602 命中 {len(hits)} 处")
                if hits:
                    hit = hits[0]
                    detail.update(summary="静态样本把拼接后的命令交给 Shell 执行。",
                                  observation=f"Bandit B602 命中 {len(hits)} 处 shell=True 调用；首处位于第 {hit['line_number']} 行。",
                                  location=f"{short_path(hit['filename'])}:{hit['line_number']}", snippet=hit.get("code", ""),
                                  rule=f"B602 · CWE-{hit.get('issue_cwe', {}).get('id', '未记录')} · {hit.get('issue_severity', '未记录')}")
                else:
                    detail.update(summary="静态样本未命中 B602 规则。", observation="Bandit 报告无 B602 发现，且未报告扫描错误。")
            else:
                observed = report.get("result")
                if not isinstance(observed, dict) or report.get("status") != result["status"]:
                    raise ValueError("断言状态与报告不一致")
                detail.update(verified=True, duration_ms=observed.get("duration"), started_at=observed.get("startTime"))
                error = observed.get("error", {})
                message = clean(error.get("message"))
                values = re.search(r"Expected:\s*([^\n]+)\nReceived:\s*([^\n]+)", message)
                if values:
                    detail.update(expected_value=values[1].strip(), actual_value=values[2].strip())
                location = error.get("location", {})
                if location.get("file") and location.get("line"):
                    detail["location"] = f"{short_path(location['file'])}:{location['line']}"
                if error.get("snippet"):
                    detail["snippet"] = clean(error["snippet"])
                detail["source_report"] = report.get("source_report")
                if result["status"] == "passed":
                    detail.update(summary="该用例的断言全部通过。", observation="Playwright 原始报告记录 passed；本次仅执行一次，未重试。")
                elif result["status"] == "failed":
                    actual = detail["actual_value"]
                    summaries = {
                        "SEC-IDOR": f"Alice 读取 Bob 私有文档时，接口返回 {actual}，未按预期拒绝。",
                        "SEC-SESSION": f"退出登录后，旧令牌访问个人信息仍返回 {actual}。",
                        "REQ-IDEMPOTENCY": "同一幂等键的两次提交返回不同的订单 ID。",
                        "REQ-CONTRACT": f"count 的实际类型为 {actual}，与接口约定不符。",
                        "REQ-PERSIST": "页面提示保存成功，但刷新后显示内容为空。" if actual == '\"\"' else f"页面提示保存成功，但刷新后 #saved 的内容为 {actual}。",
                        "A11Y-LABEL": "axe 的 label 规则检测到表单控件缺少可访问名称。",
                    }
                    # Only use a value-based narrative when the assertion recorded it.
                    final_lines = {"SEC-IDOR": 20, "SEC-SESSION": 27, "REQ-IDEMPOTENCY": 35, "REQ-CONTRACT": 38, "REQ-PERSIST": 14}
                    at_expected_assertion = location.get("line") == final_lines.get(cid) and short_path(location.get("file")) == "validation/tests/acceptance.spec.mjs"
                    if at_expected_assertion:
                        detail["comparison_labels"] = {
                            "SEC-IDOR": ["预期状态码", "实际状态码"], "SEC-SESSION": ["退出后预期状态码", "旧令牌实际状态码"],
                            "REQ-IDEMPOTENCY": ["首次提交的订单 ID", "重复提交的订单 ID"], "REQ-CONTRACT": ["约定字段类型", "实际字段类型"],
                            "REQ-PERSIST": ["保存的内容", "刷新后显示的内容"],
                        }.get(cid, ["预期", "实际观察"])
                    detail["summary"] = summaries.get(cid, "本次用例断言失败。") if actual is not None and at_expected_assertion else "本次用例断言失败，具体观察见报告。"
                    detail["observation"] = message or "原始报告未记录断言信息。"
                else:
                    detail.update(summary="未取得可判定的检查结果。", observation=message or "执行器没有产生有效通过或失败结果。")
                if cid == "A11Y-LABEL":
                    axe = next((a for a in run["artifacts"] if a["id"] in result["evidence_refs"] and a["name"] == "axe-result.json"), None)
                    if axe:
                        _, raw = reader.read(axe["id"])
                        violations = json.loads(raw).get("violations")
                        if not isinstance(violations, list) or any(v.get("id") != "label" for v in violations):
                            raise ValueError("不是本次 label 规则的完整 axe 报告")
                        if (result["status"] == "failed" and not violations) or (result["status"] == "passed" and violations):
                            raise ValueError("axe 报告与断言状态不一致")
                        nodes = [n for v in violations if v.get("id") == "label" for n in v.get("nodes", [])]
                        detail.update(actual_value=f"{len(nodes)} 个控件缺少名称", expected_value="0 个违规控件")
                        if nodes:
                            detail.update(summary=f"首页有 {len(nodes)} 个表单控件未通过 label 规则。", snippet="\n".join(n.get("html", "") for n in nodes), location="页面元素 " + ", ".join(str(t) for n in nodes for t in n.get("target", [])))
                        detail["axe_ref"] = axe["id"]
        except (OSError, ValueError, KeyError, TypeError, AttributeError, IndexError):
            detail.update(verified=False, actual_value=None, expected_value=result["expected"], summary="证据读取或校验失败，不能据此确认发生经过。", observation="请核对原始文件与本次执行记录。")
            for field in ("location", "snippet", "rule"):
                detail.pop(field, None)
        projected[cid] = detail
    return projected
