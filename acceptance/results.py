"""Versioned, read-only result projection. Never infer a defect from an error string."""
from collections import Counter
import json
from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field

VERSION = "acceptance-result-v1"
REASONS = {
    "missing_basis": "缺少独立依据", "environment_not_ready": "环境未准备好",
    "unsupported_capability": "平台尚未支持", "tool_error": "工具执行异常",
    "model_service_error": "模型设计未完成", "case_contract_error": "用例契约问题",
    "assertion_mismatch": "业务断言不符，待复核", "cancelled": "执行已取消",
    "interrupted": "执行进程中断", "not_executed": "尚未执行",
    "missing_report": "缺少报告", "incomplete_report": "报告未完整覆盖",
    "invalid_evidence": "证据未通过本次核验", "missing_task": "冻结检查缺失",
    "invalid_identity": "检查或规则身份不一致", "missing_rule": "门禁规则缺失",
    "coverage_gap": "声明范围尚未完整验证", "decision_mismatch": "判定与冻结规则结果不一致", "unknown": "原因待复核",
}
CATEGORIES = {"basis": "missing_basis", "environment": "environment_not_ready",
              "platform": "unsupported_capability", "case": "case_contract_error"}


class Strict(BaseModel):
    model_config = ConfigDict(extra="forbid", allow_inf_nan=False)


class Reason(Strict):
    code: Literal["missing_basis", "environment_not_ready", "unsupported_capability",
                  "tool_error", "model_service_error", "case_contract_error",
                  "assertion_mismatch", "cancelled", "interrupted", "not_executed",
                  "missing_report", "incomplete_report", "invalid_evidence",
                  "missing_task", "invalid_identity", "missing_rule", "coverage_gap", "decision_mismatch", "unknown"]
    message: str
    source: str


class Observation(Strict):
    id: str
    task_id: str
    case_id: str | None = None
    report_test_id: str | None = None
    requirement_ids: list[str] = Field(default_factory=list)
    attempt_id: str
    execution: Literal["queued", "running", "completed", "error", "cancelled", "blocked", "unknown"]
    outcome: Literal["passed", "failed", "error", "skipped", "unknown"]
    coverage: Literal["verified", "not_verified"]
    reasons: list[Reason] = Field(default_factory=list)
    evidence_refs: list[str] = Field(default_factory=list)


Count = Annotated[int, Field(strict=True, ge=0)]
Decision = Literal["allow", "reject", "inconclusive"]


class Execution(Strict):
    state: Literal["queued", "running", "completed", "error", "cancelled", "interrupted", "incomplete", "unknown"]
    task_counts: dict[str, Count]
    test_counts: dict[str, Count]


class Coverage(Strict):
    state: Literal["complete", "partial"]
    scope_kind: str
    gaps: list[Reason]
    blocking_reasons: list[Reason]
    requirement_counts: dict[str, Count]


class RequirementResult(Strict):
    id: str
    title: str
    source: str | None
    quote: str | None
    disposition: Literal["required", "unresolved", "excluded"]
    case_ids: list[str]
    coverage: Literal["verified", "not_verified", "excluded"]
    reasons: list[Reason]


class Findings(Strict):
    counts: dict[str, Count]
    classification_verified: bool
    test_errors_are_defects: Literal[False] = False


class Gate(Strict):
    recorded_decision: Decision
    decision: Decision
    contract_version: Literal["acceptance-result-v1"] = VERSION
    reasons: list[Reason]


class Provenance(Strict):
    source_digest: str | None
    input_digest: str | None
    adapter_digest: str | None
    policy_digest: str | None
    evidence_refs: list[str]
    evidence_verified_now: bool
    projection_only: Literal[True] = True


class ResultContract(Strict):
    schema_version: Literal["acceptance-result-v1"] = VERSION
    run_id: str
    execution: Execution
    coverage: Coverage
    findings: Findings
    gate: Gate
    provenance: Provenance
    observations: list[Observation]
    requirements: list[RequirementResult]


def reason(code, source, message=None):
    return {"code": code, "message": message or REASONS[code], "source": str(source)}


def gate_blockers(record):
    """Structural safety guard in addition to the frozen OPA business policy."""
    errors = []
    tasks = record.get("tasks", [])
    rules = record.get("rules", [])
    ids = [t.get("id") for t in tasks]
    if not tasks:
        errors.append(reason("missing_task", "tasks"))
    if any(not isinstance(i, str) or not i for i in ids) or len(ids) != len(set(ids)):
        errors.append(reason("invalid_identity", "tasks"))
    expected = [t["id"] for t in record.get("profile", {}).get("tasks", [])]
    if expected and set(ids) != set(expected):
        errors.append(reason("missing_task", "profile.tasks"))
    config = record.get("rules_config", [])
    if not rules:
        errors.append(reason("missing_rule", "rules"))
    rule_ids = [r.get("id") for r in rules]
    if any(not isinstance(i, str) or not i for i in rule_ids) or len(rule_ids) != len(set(rule_ids)):
        errors.append(reason("invalid_identity", "rules"))
    if config:
        if {r["id"] for r in config} != set(rule_ids):
            errors.append(reason("missing_rule", "rules_config"))
        governed = {tid for r in config for tid in r["tasks"]}
        if governed != set(ids):
            errors.append(reason("missing_task", "rules_config.tasks"))
    for task in tasks:
        tid = task.get("id", "unknown")
        if task.get("state") != "completed":
            errors.append(reason("cancelled" if task.get("state") == "cancelled" else "not_executed", tid))
            continue
        report = task.get("report")
        if not report or "$payload" in report or not task.get('report_ref'):
            errors.append(reason("missing_report", tid))
        elif report.get("complete") is not True or any(t.get("status") not in {"passed", "failed"} for t in report.get("tests", [])):
            errors.append(reason("incomplete_report", tid))
    if any(r.get("status") not in {"passed", "failed"} for r in rules):
        errors.append(reason("missing_rule", "rules"))
    if record.get('decision') == 'allow' and any(r.get('status') == 'failed' for r in rules):
        errors.append(reason('decision_mismatch', 'rules'))
    obligations=record.get('universal_generation',{}).get('requirements',[])
    names=Counter(row.get('name','').split(' · ',1)[0] for task in tasks if task.get('state')=='completed' for row in task.get('report',{}).get('tests',[]) if row.get('status') in {'passed','failed'})
    seen=set()
    for req in obligations:
        rid=req.get('id')
        if not rid or rid in seen:errors.append(reason('invalid_identity','requirements'))
        seen.add(rid)
        if req.get('disposition')=='excluded':continue
        cases=[c['id'] for c in req.get('cases',[])]
        if not cases or len(cases)!=len(set(cases)) or any(names[c]!=1 for c in cases):
            errors.append(reason(CATEGORIES.get(req.get('gap_category'),'coverage_gap'),rid or 'requirements'))
    return errors


def project(record, *, verified, coverage=None, review=None):
    """Current projection, with recorded verdict retained. Does not mutate input."""
    rid = record["id"]
    errors = gate_blockers(record)
    if not verified:
        errors.append(reason("invalid_evidence", rid))
    coverage = coverage if coverage is not None else record.get("recipe_completion")
    gaps = []
    if coverage and not coverage.get("complete"):
        for gap in coverage.get("gaps", []):
            code = CATEGORIES.get(gap.get("category"), "model_service_error" if gap.get("kind") == "generation" else "coverage_gap")
            gaps.append(reason(code, gap.get("case") or gap.get("source") or rid, gap.get("reason")))
        if not gaps:
            gaps.append(reason("coverage_gap", rid))
        errors.extend(gaps)
    # No changing an old reject into a pass, even if today's classifier differs.
    recorded = record.get("decision", "inconclusive")
    effective = "inconclusive" if errors or record.get("status") != "completed" else recorded
    requirements = {}
    for req in record.get("universal_generation", {}).get("requirements", []):
        for case in req.get("cases", []):
            requirements.setdefault(case["id"], []).append(str(req.get("id", "unknown")))
    observations = []
    totals = Counter()
    for task in record.get("tasks", []):
        tid = task.get("id") or "unknown"
        state = task.get("state", "unknown")
        if state not in {"queued", "running", "completed", "error", "cancelled", "blocked"}:
            state = "unknown"
        report = task.get("report", {})
        rows = report.get("tests", [])
        totals.update(t.get("status", "unknown") for t in rows)
        entries = rows or [{"id": None, "status": "unknown"}]
        for i, row in enumerate(entries):
            case = row.get("name", "").split(" · ", 1)[0]
            outcome = row.get("status", "unknown")
            if outcome not in {"passed", "failed", "error", "skipped"}:
                outcome = "unknown"
            why = []
            code = None
            if state in {"queued", "running"}: code = "not_executed"
            elif state == "cancelled": code = "cancelled"
            elif state in {"error", "blocked", "unknown"}:
                code = task.get("failure", {}).get("code", "tool_error")
                if code not in REASONS: code = "unknown"
            elif outcome == "failed": code = "assertion_mismatch"
            elif outcome in {"error", "skipped"}:
                code = "incomplete_report"
                # Only an explicit structured category is admissible; never
                # classify by matching words in assertion/error prose.
                try: detail = json.loads(row.get('detail') or '{}')
                except (ValueError,TypeError): detail = {}
                if isinstance(detail,dict): code = CATEGORIES.get(detail.get('gap_category'),code)
            elif not report: code = "missing_report"
            elif report.get("complete") is not True: code = "incomplete_report"
            if code: why.append(reason(code, tid))
            valid = verified and state == "completed" and (outcome in {"passed", "failed"} if rows else report.get("complete") is True)
            observations.append(dict(id=f"{tid}/{row.get('id') or i}", task_id=tid, case_id=case if case in requirements else row.get("id"), report_test_id=row.get('id'),
                requirement_ids=requirements.get(case, []), attempt_id=f"{rid}/{tid}/{task.get('attempt', 1)}",
                execution=state, outcome=outcome, coverage="verified" if valid else "not_verified",
                reasons=why, evidence_refs=list(dict.fromkeys(task.get("artifacts", []) + ([task["report_ref"]] if task.get("report_ref") else [])))))
    review = review if review is not None else record.get("finding_review", {})
    summary = review.get("summary", {}) if verified else {}
    checks = Counter(t.get("state", "unknown") for t in record.get("tasks", []))
    obligations=[]
    by_case={}
    for observation in observations:
        if observation['requirement_ids']: by_case.setdefault(observation['case_id'],[]).append(observation)
    for req in record.get('universal_generation',{}).get('requirements',[]):
        cases=[c['id'] for c in req.get('cases',[])]
        disposition=req.get('disposition','required')
        valid=bool(cases) and all(len(by_case.get(c,[]))==1 and by_case[c][0]['coverage']=='verified' for c in cases)
        status='excluded' if disposition=='excluded' else 'verified' if disposition=='required' and valid else 'not_verified'
        why=[]
        if status=='not_verified':
            why=[reason(CATEGORIES.get(req.get('gap_category'),'coverage_gap'),req['id'],req.get('reason') or None)]
            errors.extend(why)
        obligations.append(dict(id=req['id'],title=req.get('title',req['id']),source=req.get('source'),quote=req.get('quote'),
            disposition=disposition,case_ids=cases,coverage=status,reasons=why))
    effective = 'inconclusive' if errors or record.get('status')!='completed' else effective
    policy=next((a for a in record.get('artifacts',[]) if a['name']=='policy.rego'),None)
    return ResultContract.model_validate(dict(
        schema_version=VERSION, run_id=rid,
        execution={"state": record.get("status", "unknown"), "task_counts": dict(checks), "test_counts": dict(totals)},
        coverage={"state": "complete" if not errors and record.get('status')=='completed' else "partial", "scope_kind": (coverage or {}).get("kind", "scoped"), "gaps": gaps, "blocking_reasons": errors,
            'requirement_counts':{'total':len(obligations),'verified':sum(r['coverage']=='verified' for r in obligations),'excluded':sum(r['coverage']=='excluded' for r in obligations),'not_verified':sum(r['coverage']=='not_verified' for r in obligations)}},
        findings={"counts": summary, "classification_verified": bool(verified and summary), "test_errors_are_defects": False},
        gate={"recorded_decision": recorded, "decision": effective, "contract_version": VERSION, "reasons": errors},
        provenance={"source_digest": (record.get("context") or {}).get("snapshot_digest"), "input_digest": record.get("scope_digest"), "adapter_digest": record.get("adapter_digest"),
            'policy_digest':policy['sha256'] if policy else None,'evidence_refs':[a['id'] for a in record.get('artifacts',[])],"evidence_verified_now": bool(verified), "projection_only": True},
        observations=observations,requirements=obligations)).model_dump()


def native_project(view):
    """Adapter for historical native/workflow views, with no invented evidence."""
    rows = {r['criterion_id']: r for r in view.get('results', [])}
    tasks, rules = [], []
    for criterion in view.get('baseline', {}).get('criteria', []):
        if criterion.get('required') is False: continue
        cid = criterion['id']; row = rows.get(cid)
        status = row.get('status', 'unknown') if row else 'unknown'
        valid = status in {'passed','failed'} and bool(row.get('evidence_refs')) if row else False
        refs=row.get('evidence_refs',[]) if row else []
        tasks.append(dict(id=cid,state='completed' if row else 'queued',artifacts=refs,report_ref=refs[0] if refs else None,
            report={'complete':valid,'tests':[{'id':row.get('case_id',cid),'status':status}] if row else []}))
        rules.append({'id':cid,'status':status if valid else 'unknown'})
    record = dict(id=view['id'],status=view['status'],decision=view['decision'],tasks=tasks,rules=rules,
        context={'snapshot_digest':view.get('target_digest')},scope_digest=view.get('suite_digest'))
    scope = view.get('completion')
    # A legacy scoped record does not claim full-product coverage.
    if scope and scope.get('kind')=='scoped': scope=None
    result = project(record,verified=view.get('integrity') is True,coverage=scope)
    result['gate']['recorded_decision'] = view.get('recorded_decision',view['decision'])
    return result
