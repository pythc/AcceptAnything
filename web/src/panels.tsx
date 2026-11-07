import { Fragment, useEffect, useRef, useState } from "react";
import {
  ArrowRight,
  ArrowUpRight,
  DownloadSimple,
  ShieldCheck,
  FileText,
  Copy,
  SpinnerGap,
  CaretRight,
  Clock,
  TerminalWindow,
  Check,
  WarningCircle,
  MagnifyingGlass,
  FolderSimple,
} from "@phosphor-icons/react";
import type { Artifact, Finding, Inspection, Run, Tab } from "./types";
import { labels, severity, StateIcon, PriorityBadge } from "./ui";
import {
  findingTitle,
  findingLocation,
  findingSummary,
  evidenceGroup,
  evidenceCommand,
} from "./presentation";
import { findingPriority } from "./priority";
import { selectEvidence, type EvidenceCategory } from "./evidence";
import { SourceDetails } from "./SourceContext";
import {
  clockTime,
  elapsed,
  pipeline,
  seconds,
  stageDuration,
  stageLabel,
} from "./pipeline";

function useClock(active: boolean) {
  const [clock, setClock] = useState(Date.now());
  useEffect(() => {
    if (!active) return;
    setClock(Date.now());
    const timer = setInterval(() => setClock(Date.now()), 100);
    return () => clearInterval(timer);
  }, [active]);
  return clock;
}

export function Flow({
  run,
  phase,
  setPhase,
  busy,
  setTab,
  showResultEvidence,
  goEvidence,
  showFinding,
}: {
  run: Run;
  phase: number;
  setPhase: (n: number) => void;
  busy: boolean;
  setTab: (t: Tab) => void;
  showResultEvidence: (id: string) => void;
  goEvidence: (id: string) => void;
  showFinding: (id: string) => void;
}) {
  const stages = pipeline(run),
    clock = useClock(busy);
  const [follow, setFollow] = useState(busy);
  const current = stages.findIndex((s) => s.status === "running");
  const trackRef = useRef<HTMLOListElement>(null),
    activeStageRef = useRef<HTMLButtonElement>(null);
  useEffect(() => {
    const track = trackRef.current,
      button = activeStageRef.current;
    if (!track || !button) return;
    const reveal = () => {
      const item = button.parentElement!;
      if (item.offsetLeft < track.scrollLeft)
        track.scrollLeft = item.offsetLeft;
      else if (
        item.offsetLeft + item.offsetWidth >
        track.scrollLeft + track.clientWidth
      )
        track.scrollLeft =
          item.offsetLeft + item.offsetWidth - track.clientWidth;
    };
    reveal();
    const observer = new ResizeObserver(reveal);
    observer.observe(track);
    return () => observer.disconnect();
  }, [phase, run.id]);
  useEffect(
    () => setFollow(["queued", "running"].includes(run.status)),
    [run.id],
  );
  useEffect(() => {
    if (busy && follow && current >= 0) setPhase(current);
    else if (!busy && follow && run.pipeline?.some((s) => s.id === "gate"))
      setPhase(stages.findIndex((s) => s.id === "gate"));
  }, [busy, follow, current, run.pipeline, setPhase]);
  const selected = stages[phase] || stages[2];
  const duration = (s: typeof selected) =>
    stageDuration(s, run.pipeline === undefined, clock);
  const criteria = run.baseline.criteria.filter(
    (c) => !selected.id.startsWith("L") || c.layer === selected.id,
  );
  const command = run.commands?.find(
    (c) =>
      (run.project_id && selected.id === "L1" && c.name.startsWith("node-")) ||
      c.name ===
        (selected.id === "L1" ? "bandit" : "playwright-" + selected.id),
  );
  const total = elapsed(run.created_at, run.finished_at, clock);
  return (
    <section className="pipeline-view">
      <div className="pipeline-heading">
        <div>
          <strong>
            {busy
              ? current >= 0
                ? `正在${stages[current].title}`
                : "等待执行"
              : run.status === "error"
                ? "执行中断"
                : "验收结束"}
          </strong>
          <span className="muted">
            {run.results.length} / {run.baseline.criteria.length} 项检查
          </span>
        </div>
        <span className="elapsed">
          <Clock size={15} />
          总历时 {seconds(total)}
        </span>
      </div>
      {!!run.baseline.exclusions?.length && (
        <details className="metadata scope-exclusions">
          <summary>
            本次不测 · {run.baseline.exclusions.length} 类环境范围
          </summary>
          <dl>
            {run.baseline.exclusions.map((item) => (
              <div key={item.subject}>
                <dt>{item.subject}</dt>
                <dd>{item.reason}</dd>
              </div>
            ))}
          </dl>
        </details>
      )}
      <ol className="pipeline-track" aria-label="验收流水线" ref={trackRef}>
        {stages.map((s, i) => (
          <li key={s.id} className={s.status}>
            <button
              className={`pipeline-stage ${phase === i ? "selected" : ""}`}
              ref={phase === i ? activeStageRef : null}
              aria-pressed={phase === i}
              onClick={() => {
                setPhase(i);
                setFollow(false);
              }}
            >
              <div className="stage-top">
                <StateIcon status={s.status} />
                <span>{stageLabel(s.status, s.id)}</span>
                <span className="stage-number">
                  {String(i + 1).padStart(2, "0")}
                </span>
              </div>
              <strong>{s.title}</strong>
              <small>{s.tool}</small>
              <span className="stage-time">
                {s.status === "queued" || s.status === "not_run"
                  ? "—"
                  : seconds(duration(s))}
              </span>
            </button>
          </li>
        ))}
      </ol>
      <div className="pipeline-detail">
        <div className="stage-heading">
          <div>
            <span className="eyebrow">
              阶段 {String(phase + 1).padStart(2, "0")}
            </span>
            <h3>{selected.title}</h3>
          </div>
          <span className={"result-text " + selected.status}>
            <StateIcon status={selected.status} />
            {stageLabel(selected.status, selected.id)} ·{" "}
            {seconds(duration(selected))}
          </span>
        </div>
        <p className="stage-work">
          {selected.id === "gate" && selected.status !== "error"
            ? selected.work
            : selected.detail}
        </p>
        <div className="stage-timing">
          <span>
            开始 <time>{clockTime(selected.started_at)}</time>
          </span>
          <span>
            结束{" "}
            <time>
              {selected.status === "running"
                ? "执行中"
                : clockTime(selected.finished_at)}
            </time>
          </span>
          {busy && !follow && (
            <button className="text-button" onClick={() => setFollow(true)}>
              跟随当前阶段 <ArrowRight />
            </button>
          )}
        </div>
        {selected.id === "baseline" || selected.id === "cases" ? (
          <>
            <div className="check-table-heading">
              <span>
                {selected.id === "baseline" ? "验收标准" : "用例与验证内容"}
              </span>
              <span>执行器</span>
            </div>
            {criteria.map((c) => (
              <div className="pipeline-check baseline-check" key={c.id}>
                <div>
                  <strong>
                    {selected.id === "cases"
                      ? run.case_plans?.[c.id]?.subject || c.case_id
                      : c.expected}
                  </strong>
                  <small>
                    {c.id} · {c.case_id}
                  </small>
                  {selected.id === "cases" && (
                    <small>
                      {run.case_plans?.[c.id]?.steps.join(" → ") || c.expected}
                    </small>
                  )}
                </div>
                <span className="muted">{c.executor}</span>
              </div>
            ))}
            <details className="metadata">
              <summary>冻结版本与来源</summary>
              <dl>
                <dt>版本</dt>
                <dd>{run.baseline.version}</dd>
                <dt>来源</dt>
                <dd>{run.baseline.source}</dd>
                <dt>标准 SHA-256</dt>
                <dd>{run.baseline.digest}</dd>
                <dt>测试集 SHA-256</dt>
                <dd>{run.suite_digest}</dd>
              </dl>
            </details>
          </>
        ) : selected.id.startsWith("L") ? (
          <>
            <div className="check-table-heading">
              <span>执行内容 / 实际结果</span>
              <span>耗时 · 状态</span>
            </div>
            {criteria.map((c) => {
              const r = run.results.find((x) => x.criterion_id === c.id),
                d = run.inspections[c.id];
              return (
                <button
                  key={c.id}
                  className="pipeline-check"
                  disabled={!r?.evidence_refs.length}
                  onClick={() => showResultEvidence(c.id)}
                >
                  <div>
                    <strong>
                      {d?.subject ||
                        run.case_plans?.[c.id]?.subject ||
                        c.expected}
                    </strong>
                    <small>
                      {r
                        ? d?.verified
                          ? d.summary
                          : r.actual
                              .split("\n")
                              .filter(Boolean)
                              .slice(0, 2)
                              .join(" ")
                        : "等待执行器报告"}
                    </small>
                    <code>{c.case_id}</code>
                  </div>
                  <div className="check-state">
                    <span
                      className={
                        "result-text " + (r?.status || selected.status)
                      }
                    >
                      <StateIcon status={r?.status || selected.status} />
                      {r
                        ? labels[r.status]
                        : selected.status === "running"
                          ? "待报告"
                          : "未执行"}
                    </span>
                    <small>
                      {r
                        ? seconds(
                            d?.verified
                              ? (d.duration_ms ?? r.duration_ms)
                              : r.duration_ms,
                          )
                        : "—"}{" "}
                      <CaretRight />
                    </small>
                  </div>
                </button>
              );
            })}
            {command && (
              <details className="execution-command">
                <summary>
                  <TerminalWindow /> 执行命令与日志{" "}
                  <span>退出码 {command.exit_code ?? "未返回"}</span>
                </summary>
                <div className="command-times">
                  {clockTime(command.started_at)} →{" "}
                  {clockTime(command.finished_at)}
                </div>
                <pre>{command.argv.join(" ")}</pre>
                {command.evidence_ref && (
                  <a
                    className="text-button"
                    href={`/api/runs/${run.id}/artifacts/${command.evidence_ref}?download=true`}
                    download
                  >
                    下载执行日志 <DownloadSimple />
                  </a>
                )}
              </details>
            )}
          </>
        ) : selected.id === "cleanup" ? (
          <p className="stage-empty">{selected.detail}</p>
        ) : selected.id === "findings" ? (
          <>
            {run.findings.map((f) => (
              <button
                className="pipeline-check"
                key={f.id}
                onClick={() => showFinding(f.id)}
              >
                <div>
                  <strong>
                    {f.id} · {f.title}
                  </strong>
                  <small>
                    {run.inspections[f.criterion_id]?.summary || f.expected}
                  </small>
                </div>
                <span className={"severity " + f.severity}>
                  {severity[f.severity]}
                </span>
              </button>
            ))}
            {!run.findings.length && (
              <p className="stage-empty">
                {busy ? "尚未归纳缺陷" : "本次没有已确认的失败检查"}
              </p>
            )}
          </>
        ) : (
          <div className="gate-overview">
            <h3 className={"result-text " + run.decision}>
              {labels[run.decision]}
            </h3>
            <div className="gate-counts">
              <span>
                <strong>
                  {run.results.filter((r) => r.status === "passed").length}
                </strong>{" "}
                项通过
              </span>
              <span>
                <strong>
                  {run.results.filter((r) => r.status === "failed").length}
                </strong>{" "}
                项失败
              </span>
              <span>
                <strong>
                  {
                    run.results.filter(
                      (r) => !["passed", "failed"].includes(r.status),
                    ).length
                  }
                </strong>{" "}
                项未完成
              </span>
            </div>
            <button className="text-button" onClick={() => goEvidence("")}>
              查看判定输入与输出 <ArrowRight />
            </button>
          </div>
        )}
      </div>
      <div className="pipeline-footnote">
        <span>
          {run.project_id
            ? `范围：${run.baseline.scope}`
            : "性能与恢复：未接入本次基线。"}
        </span>
        <button className="text-button" onClick={() => setTab("findings")}>
          查看缺陷 <ArrowRight />
        </button>
      </div>
    </section>
  );
}

function Values({ detail }: { detail: Inspection }) {
  return (
    <div className={"fact-comparison " + detail.status}>
      <div>
        <span>{detail.comparison_labels?.[0] || "预期"}</span>
        <strong>{detail.expected_value}</strong>
      </div>
      <div>
        <span>{detail.comparison_labels?.[1] || "实际观察"}</span>
        <strong>
          {detail.actual_value ??
            (detail.verified ? detail.summary : "证据待核实")}
        </strong>
      </div>
    </div>
  );
}

function FindingHistory({ runId }: { runId: string }) {
  const [rows, setRows] = useState<any[]>([]),
    [error, setError] = useState("");
  useEffect(() => {
    const controller = new AbortController();
    setRows([]);
    setError("");
    fetch(`/api/runs/${runId}/history`, { signal: controller.signal })
      .then(async (r) => {
        if (!r.ok) throw Error("缺陷历史暂时无法读取");
        setRows(await r.json());
      })
      .catch((e) => {
        if (e.name !== "AbortError") setError(e.message);
      });
    return () => controller.abort();
  }, [runId]);
  if (!rows.length && !error) return null;
  return (
    <details className="console-disclosure">
      <summary>DefectDojo 缺陷历史</summary>
      {error && <p role="alert">{error}</p>}
      {rows.map((row) => (
        <div key={row.key}>
          <strong>{row.task_id}</strong>
          {row.attempts.map((a: any) => (
            <p key={a.run_id}>
              <a href={`/?run=${a.run_id}&tab=findings`}>{a.run_id}</a>
              {" · "}
              {a.state === "confirmed"
                ? `${a.findings.filter((f: any) => f.active).length} 项活跃 / ${a.findings.length} 项累计`
                : "同步结果未知"}
            </p>
          ))}
          {row.test_id && (
            <a
              href={`${row.url}test/${row.test_id}`}
              target="_blank"
              rel="noreferrer"
            >
              在 DefectDojo 中复核与处置 ↗
            </a>
          )}
        </div>
      ))}
    </details>
  );
}

function FindingReviewForm({ run, finding }: { run: Run; finding: Finding }) {
  const [state, setState] = useState("needs_review"),
    [reason, setReason] = useState(""),
    [notice, setNotice] = useState(""),
    [busy, setBusy] = useState(false);
  const [revision, setRevision] = useState(finding.review_revision || "");
  const pending = useRef<{ key: string; id: string } | null>(null);
  async function submit() {
    setBusy(true);
    setNotice("");
    const evidence = finding.evidence_refs.slice(0, 1),
      key = JSON.stringify([state, reason, revision, evidence]);
    if (pending.current?.key !== key)
      pending.current = { key, id: crypto.randomUUID() };
    try {
      const r = await fetch(
        `/api/integrations/runs/${run.id}/findings/${finding.id}/review`,
        {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({
            request_id: pending.current.id,
            expected_revision: revision,
            state,
            reason: reason.trim(),
            evidence_refs: evidence,
          }),
        },
      );
      const value = await r.json();
      if (!r.ok) throw Error(value.detail || "复核未保存");
      setRevision(value.revision);
      pending.current = null;
      setNotice(
        "复核已记录。历史门禁保持原结论，新一轮验收将冻结并应用此复核。",
      );
    } catch (e) {
      setNotice((e as Error).message);
    } finally {
      setBusy(false);
    }
  }
  return (
    <details className="metadata review-editor">
      <summary>记录证据复核</summary>
      <label>
        复核结论
        <select value={state} onChange={(e) => setState(e.target.value)}>
          {[
            ["needs_review", "待复核发现"],
            ["confirmed", "已确认缺陷"],
            ["false_positive", "工具误报"],
            ["test_issue", "用例问题"],
          ].map(([k, v]) => (
            <option value={k} key={k}>
              {v}
            </option>
          ))}
        </select>
      </label>
      <label>
        验证方法、观察结果与依据
        <textarea
          value={reason}
          onChange={(e) => setReason(e.target.value)}
          minLength={20}
          placeholder="说明实际验证了什么、原报告与源码如何支持结论（至少20字）"
        />
      </label>
      <p>绑定本发现的原始报告与冻结源码版本；不改写扫描原件。</p>
      <button
        className="button outline"
        disabled={
          busy || reason.trim().length < 20 || !finding.evidence_refs.length
        }
        onClick={submit}
      >
        {busy ? "正在保存" : "保存复核"}
      </button>
      <p role="status">{notice}</p>
    </details>
  );
}

function failedAssertionRows(raw: string) {
  try {
    const value = JSON.parse(raw);
    return Array.isArray(value?.checks)
      ? value.checks.filter((row: any) => row && typeof row === "object" && row.status === "failed" && Object.hasOwn(row, "expected") && Object.hasOwn(row, "actual"))
      : [];
  } catch { return []; }
}

export function Findings({
  page,
  run,
  finding: selectedFinding,
  select,
  goEvidence,
  showStandards,
}: {
  run: Run;
  finding?: Finding;
  page?:(offset:number,state:string,query?:string)=>void;
  select: (id: string) => void;
  goEvidence: (id: string) => void;
  showStandards: () => void;
}) {
  const [reviewFilter, setReviewFilter] = useState(() =>
    selectedFinding?.review_state === "false_positive"
      ? "false_positive"
      : "active",
  );
  const [query, setQuery] = useState("");
  const [indexOpen, setIndexOpen] = useState(false);
  useEffect(()=>{
    if(!run.finding_page || query===run.finding_page.query)return;
    const timer=setTimeout(()=>page?.(0,run.finding_page!.state,query),350);
    return ()=>clearTimeout(timer);
  },[query,run.id,reviewFilter]);
  const counts = run.finding_counts;
  const matches = (f: Finding, key: string) =>
    counts
      ? key === "all" ||
        (key === "active"
          ? f.review_state !== "false_positive"
          : f.review_state === key)
      : key === "all" ||
        key === "active" ||
        (key === "reviewed" ? f.review?.non_blocking : !f.review?.non_blocking);
  const visible = run.findings.filter(
    (f) =>
      matches(f, reviewFilter) &&
      `${findingTitle(f, run)} ${f.title} ${f.id} ${findingLocation(f, run.inspections[f.id])}`
        .toLowerCase()
        .includes(query.toLowerCase()),
  );
  const finding =
    visible.find((f) => f.id === selectedFinding?.id) || visible[0];
  const detail =
    finding &&
    (run.inspections[finding.id] || run.inspections[finding.criterion_id]);
  useEffect(() => {
    if (finding && finding.id !== selectedFinding?.id) select(finding.id);
  }, [finding?.id, selectedFinding?.id]);
  useEffect(() => {
    setQuery("");
    setReviewFilter(
      selectedFinding?.review_state === "false_positive"
        ? "false_positive"
        : "active",
    );
  }, [run.id]);
  const filters = counts
    ? [
        ["active", "待处理", counts.actionable],
        ["confirmed", "已确认", counts.confirmed],
        ["needs_review", "待复核", counts.needs_review],
        ["test_issue", "用例问题", counts.test_issue],
        ["false_positive", "非缺陷", counts.false_positive],
        ["all", "全部", counts.unique],
      ]
    : [
        ["all", "全部", run.findings.length],
        [
          "pending",
          "待处理",
          run.review_summary?.pending ?? run.findings.length,
        ],
        ["reviewed", "复核不成立", run.review_summary?.non_actionable ?? 0],
      ];
  const groups = counts
    ? [
        ["confirmed", "已确认缺陷"],
        ["needs_review", "待复核发现"],
        ["test_issue", "用例问题"],
        ["false_positive", "非缺陷"],
        ["", "检查观察"],
      ]
    : [["", "检查观察"]];
  const location = finding && findingLocation(finding, detail);
  const failedAssertions = finding ? failedAssertionRows(detail?.actual_value || finding.actual) : [];
  const assertionValue = (value: unknown) => typeof value === "string" ? value : JSON.stringify(value, null, 2);
  return (
    <section className="findings-workspace">
      <div className="review-filters" aria-label="复核分类">
        {filters.map(([key, label, count]) => (
          <button
            key={key}
            aria-pressed={reviewFilter === key}
            onClick={() => {
              setReviewFilter(String(key));
              if(run.finding_page)page?.(0,String(key)==='all'?'':String(key));
              setQuery("");
              const first = run.findings.find((f) => matches(f, String(key)));
              if (first) select(first.id);
            }}
          >
            {label} <span>{count}</span>
          </button>
        ))}
      </div>
      <button
        className="mobile-index-toggle"
        aria-expanded={indexOpen}
        onClick={() => setIndexOpen(!indexOpen)}
      >
        {indexOpen ? "收起发现列表" : "选择其他发现"}
        <CaretRight size={14} />
      </button>
      <aside className={"finding-index " + (indexOpen ? "mobile-open" : "")}>
        {run.finding_page&&<nav aria-label="发现分页"><button disabled={!run.finding_page.offset} onClick={()=>page?.(Math.max(0,run.finding_page!.offset-run.finding_page!.limit),run.finding_page!.state,run.finding_page!.query)}>上一页</button><span> {run.finding_page.total?run.finding_page.offset+1:0}–{Math.min(run.finding_page.total,run.finding_page.offset+run.finding_page.limit)} / {run.finding_page.total} </span><button disabled={!run.finding_page.has_more} onClick={()=>page?.(run.finding_page!.offset+run.finding_page!.limit,run.finding_page!.state,run.finding_page!.query)}>下一页</button></nav>}
        <label className="finding-search">
          <MagnifyingGlass size={17} />
          <input
            aria-label="搜索发现"
            placeholder="搜索发现、文件或编号"
            value={query}
            onChange={(e) => setQuery(e.target.value)}
          />
        </label>
        <div className="finding-list-scroll">
          {groups.map(([category, label]) => {
            const rows = visible.filter((f) =>
              counts
                ? category
                  ? f.review_state === category
                  : ![
                      "confirmed",
                      "needs_review",
                      "test_issue",
                      "false_positive",
                    ].includes(f.review_state || "")
                : true,
            );
            if (!rows.length) return null;
            return (
              <section className="finding-group" key={category}>
                <h3>{label}</h3>
                {rows.map((f) => (
                  <button
                    key={f.id}
                    className={
                      "finding-item " + (f.id === finding?.id ? "selected" : "")
                    }
                    aria-pressed={f.id === finding?.id}
                    onClick={() => {
                      select(f.id);
                      setIndexOpen(false);
                    }}
                  >
                    <PriorityBadge finding={f} />
                    <span>
                      <strong>{findingTitle(f, run)}</strong>
                      <small title={findingLocation(f, run.inspections[f.id])}>
                        {f.id}
                        {findingLocation(f, run.inspections[f.id])
                          ? ` · ${findingLocation(f, run.inspections[f.id])}`
                          : ""}
                      </small>
                    </span>
                  </button>
                ))}
              </section>
            );
          })}
          {!visible.length && (
            <div className="empty small">
              {query ? "没有匹配的发现" : "此分类没有发现"}
            </div>
          )}
        </div>
        <div className="finding-index-footer">
          {counts && (
            <p>
              原始 {counts.raw} · 合并重复 {counts.duplicates}
            </p>
          )}
          <FindingHistory runId={run.id} />
        </div>
      </aside>
      {finding ? (
        <article className="finding-report" key={finding.id}>
          <div className="finding-eyebrow">
            <code>{finding.id}</code>
            <PriorityBadge finding={finding} />
            <span>
              {finding.review?.label ||
                (detail?.verified ? "已核对报告 · 待判定" : "证据待核实")}
            </span>
          </div>
          <header className="finding-report-heading">
            <h3>{findingTitle(finding, run)}</h3>
            <button
              className="button primary"
              onClick={() => goEvidence(finding.id)}
            >
              查看证据 <ArrowUpRight size={15} />
            </button>
          </header>
          <p className="finding-summary">{findingSummary(finding, detail)}</p>
          <div className="finding-properties">
            <span>
              来源 <strong>{detail?.method || finding.criterion_id}</strong>
            </span>
            {location && (
              <span>
                位置 <code>{location}</code>
              </span>
            )}
          </div>
          <section className="finding-observation">
            <h4>发生了什么</h4>
            <dl className="observation-values">
              {failedAssertions.length > 0 ? failedAssertions.map((row: any, index: number) => (
                <Fragment key={index}>
                  <dt>{row.step ? `步骤 ${row.step} · ` : ""}预期</dt>
                  <dd><pre>{assertionValue(row.expected)}</pre></dd>
                  <dt>实际{row.pointer ? ` · ${row.pointer}` : ""}</dt>
                  <dd><pre>{assertionValue(row.actual)}</pre></dd>
                </Fragment>
              )) : <>
              <dt>预期</dt>
              <dd>{detail?.expected_value || finding.expected}</dd>
              <dt>实际</dt>
              <dd>
                {(detail?.actual_value || finding.actual)
                  .split("\n")
                  .find(Boolean)}
              </dd>
              </>}
              <dt>影响与范围</dt>
              <dd>
                {finding.review_state === "false_positive" ||
                finding.review_state === "test_issue"
                  ? finding.review?.reason
                  : finding.review_state === "confirmed"
                    ? finding.title === "production_typescript_build"
                      ? "无法生成生产构建产物。"
                      : finding.review?.reason
                    : finding.impact}
              </dd>
            </dl>
          </section>
          {detail?.snippet ? (
            <section className="source-proof">
              <h4>定位与现场 {location && <code>{location}</code>}</h4>
              <pre>{detail.snippet}</pre>
            </section>
          ) : (
            <details className="source-proof console-disclosure" open={failedAssertions.length ? undefined : true}>
              <summary>原始诊断</summary>
              <pre>
                {(detail?.observation || finding.actual)
                  .split("\n")
                  .filter(Boolean)
                  .join("\n")}
              </pre>
            </details>
          )}
          <section className="finding-proof">
            <h4>确认依据</h4>
            {run.artifacts
              .filter((a) =>
                new Set([
                  ...finding.evidence_refs,
                  detail?.source_report,
                  detail?.primary_ref,
                ]).has(a.id),
              )
              .map((a) => (
                <button
                  className="proof-file-row"
                  key={a.id}
                  onClick={() => goEvidence(finding.id)}
                >
                  <FileText size={16} />
                  <span>{artifactTitle(a)}</span>
                  <code>{a.name}</code>
                  <ArrowUpRight size={15} />
                </button>
              ))}
            {location && (
              <p className="proof-location">
                源码位置 <code>{location}</code>
              </p>
            )}
          </section>
          <details className="metadata">
            <summary>复核记录与依据</summary>
            <p>{finding.review?.reason || "暂无独立复核记录"}</p>
            {finding.review?.rows.map((r, i) => (
              <p key={i}>
                {r.path}
                {r.line ? `:${r.line}` : ""} {r.reason}
              </p>
            ))}
            {detail && <p>{detail.limitation}</p>}
            {run.review_provenance && <p>{run.review_provenance}</p>}
          </details>
          {finding.review_state && (
            <FindingReviewForm key={finding.id} run={run} finding={finding} />
          )}
          <details className="metadata">
            <summary>复现步骤与原始观察</summary>
            <ol>
              {detail?.steps.map((step, i) => (
                <li key={i}>{step}</li>
              ))}
            </ol>
            <p>原始标题：{finding.title}</p>
            <pre>{detail?.observation || finding.actual}</pre>
          </details>
          <details className="console-disclosure">
            <summary>溯源与分级依据</summary>
            <dl className="inspector-facts">
              <dt>验收标准编号</dt>
              <dd>{finding.criterion_id}</dd>
              <dt>测试用例编号</dt>
              <dd>{finding.case_id}</dd>
              <dt>原始严重度</dt>
              <dd>{severity[finding.severity] || finding.severity}</dd>
              <dt>优先级依据</dt>
              <dd>
                {findingPriority(finding).suggested
                  ? "按原始严重度建议，待结合影响与业务范围确认"
                  : "原始记录指定；无依据时不推断"}
              </dd>
              <dt>原始命中</dt>
              <dd>{finding.occurrences?.join("、") || finding.id}</dd>
              <dt>检查来源</dt>
              <dd>
                {finding.occurrence_tasks?.join("、") || finding.criterion_id}
              </dd>
            </dl>
          </details>
          <footer className="finding-report-footer">
            <button className="text-button" onClick={showStandards}>
              查看验收标准 <ArrowUpRight size={14} />
            </button>
            <span>
              提交 {run.source.repository.commit?.slice(0, 7) || "未采集"} ·{" "}
              {seconds(finding.duration_ms)} · 第 {finding.attempt} 次执行
            </span>
          </footer>
        </article>
      ) : (
        <article className="finding-report">
          <h3>{visible.length ? labels[run.decision] : "此分类没有发现"}</h3>
          <button className="text-button" onClick={() => goEvidence("")}>
            查看本次验证证据 <ArrowRight />
          </button>
        </article>
      )}
    </section>
  );
}

function artifactTitle(a: Artifact) {
  if (a.name === "remote-source.json") return "远程仓库与提交";
  if (a.owner_label && a.name === "gate-result.json")
    return a.owner_label + "门禁结果";
  if (a.owner_label && a.name === "gate-input.json")
    return a.owner_label + "门禁依据";
  if (a.name === "case-registration.json") return "用例登记清单";
  if (a.name === "source-context.json") return "验收目标快照";
  if (a.name === "gate-result.json") return "最终判定";
  if (a.name === "gate-input.json") return "判定依据";
  if (a.media_type === "application/xml") return "测试原始报告";
  if (a.name === "bandit.json") return "静态检测报告";
  if (a.name === "axe-result.json") return "无障碍检测报告";
  if (a.name.startsWith("playwright-") && a.name.endsWith("results.json"))
    return "执行器原始报告";
  if (a.name.endsWith("-raw.json")) return "工具原始报告";
  if (a.name.endsWith("-receipt.json")) return "检查执行记录";
  if (a.name.endsWith("-result.json")) return "用例断言报告";
  if (a.name.endsWith("trace.zip")) return "操作轨迹";
  if (a.media_type.startsWith("image/")) return "页面截图";
  if (a.name.endsWith(".log")) return "执行日志";
  if (a.name === "error-context.md") return "失败时页面上下文";
  return a.name;
}

export function Evidence({
  run,
  finding,
  artifactId,
  setArtifactId,
  back,
  notify,
  chooseScope,
  showFinding,
}: {
  run: Run;
  finding?: Finding;
  artifactId: string;
  setArtifactId: (id: string) => void;
  back: () => void;
  notify: (s: string) => void;
  chooseScope: (id: string) => void;
  showFinding: (id: string) => void;
}) {
  const [category, setCategory] = useState<EvidenceCategory>("all");
  const [fileQuery, setFileQuery] = useState("");
  const [filesOpen, setFilesOpen] = useState(false);
  const findingDetail =
    finding &&
    (run.inspections[finding.id] || run.inspections[finding.criterion_id]);
  const refs = new Set(finding?.evidence_refs || []);
  if (findingDetail?.source_report) refs.add(findingDetail.source_report);
  const evidence = selectEvidence(
    run,
    finding ? "all" : category,
    fileQuery,
    artifactId,
    finding ? refs : undefined,
  );
  const artifact =
    evidence.find((a) => a.id === artifactId) ||
    evidence.find((a) => a.id === findingDetail?.primary_ref) ||
    evidence.find((a) => a.name === "gate-result.json") ||
    evidence[0];
  const cid = artifact?.criterion_id || finding?.criterion_id;
  const criterion = run.baseline.criteria.find((c) => c.id === cid);
  const result = run.results.find((r) => r.criterion_id === cid);
  const linkedFinding =
    finding ||
    run.findings.find(
      (f) => f.criterion_id === cid && f.review_state === "confirmed",
    ) ||
    run.findings.find((f) => f.criterion_id === cid);
  const detail =
    (finding && artifact?.criterion_id === finding.criterion_id
      ? findingDetail
      : undefined) || (cid ? run.inspections[cid] : undefined);
  const command = evidenceCommand(artifact, run);
  const isInput = artifact && evidenceGroup(artifact, run).id === "_input";
  const groups = Array.from(
    new Set(evidence.map((a) => evidenceGroup(a, run).id)),
  );
  const selectedFileRef = useRef<HTMLButtonElement>(null);

  const summary = linkedFinding
    ? findingTitle(linkedFinding, run)
    : criterion?.title || artifact?.name || "本次验收";
  return (
    <section className="evidence-workspace">
      <button
        className="mobile-index-toggle"
        aria-expanded={filesOpen}
        onClick={() => setFilesOpen(!filesOpen)}
      >
        {filesOpen ? "收起证据目录" : "选择步骤或文件"}
        <CaretRight size={14} />
      </button>
      <aside className={"file-list " + (filesOpen ? "mobile-open" : "")}>
        <h3>{finding ? `${finding.id} · 关联证据` : "本次验收"}</h3>
        <select
          className="evidence-scope"
          aria-label="证据范围"
          value={finding?.id || "run"}
          onChange={(e) =>
            chooseScope(e.target.value === "run" ? "" : e.target.value)
          }
        >
          <option value="run">本次验收 · 全部证据</option>
          {run.findings.map((f) => (
            <option key={f.id} value={f.id}>
              {f.id} · {findingTitle(f, run)}
            </option>
          ))}
        </select>
        <label className="finding-search">
          <MagnifyingGlass size={16} />
          <input
            aria-label="搜索证据文件"
            placeholder="搜索步骤或文件"
            value={fileQuery}
            onChange={(e) => setFileQuery(e.target.value)}
          />
        </label>
        {!finding && (
          <select
            aria-label="文件类别"
            value={category}
            onChange={(e) => setCategory(e.target.value as EvidenceCategory)}
          >
            <option value="all">全部文件</option>
            <option value="reports">检查报告</option>
            <option value="logs">执行日志</option>
            <option value="sources">源文件与基线</option>
          </select>
        )}
        <div className="file-list-scroll">
          {groups.map((id) => {
            const files = evidence.filter(
              (a) => evidenceGroup(a, run).id === id,
            );
            const group = evidenceGroup(files[0], run);
            return (
              <details
                className="evidence-group"
                key={id}
                open={files.some((a) => a.id === artifact?.id) || !!fileQuery}
              >
                <summary>
                  <FolderSimple size={16} />
                  {group.title}
                  <small>{files.length}</small>
                </summary>
                {files.map((a) => (
                  <button
                    key={a.id}
                    ref={a.id === artifact?.id ? selectedFileRef : null}
                    className={
                      "file-row " + (a.id === artifact?.id ? "selected" : "")
                    }
                    aria-pressed={a.id === artifact?.id}
                    onClick={() => {
                      setArtifactId(a.id);
                      setFilesOpen(false);
                    }}
                  >
                    <FileText size={16} />
                    <span>
                      <strong>{artifactTitle(a)}</strong>
                      <small>{a.name}</small>
                    </span>
                  </button>
                ))}
              </details>
            );
          })}
          {!evidence.length && <p className="empty small">没有匹配的文件</p>}
        </div>
      </aside>
      <article className="evidence-reader">
        <span className="eyebrow">
          {criterion?.title || (isInput ? "输入与版本" : "本次验收与门禁")} /{" "}
          {artifact ? artifactTitle(artifact) : "证据"}
        </span>
        <header className="evidence-page-heading">
          <h3>{summary}</h3>
          <a className="button outline" href={`/api/runs/${run.id}/result-contract`} download={`${run.id}-result-contract.json`}>核验结果 JSON</a>
        {artifact && <a className="button primary" href={`/api/runs/${run.id}/artifacts/${artifact.id}?download=true`} download><DownloadSimple size={15}/>下载原件</a>}
          <button
            className="text-button"
            onClick={linkedFinding ? () => showFinding(linkedFinding.id) : back}
          >
            {linkedFinding ? `查看缺陷 ${linkedFinding.id}` : "返回流程"}
            <ArrowUpRight size={14} />
          </button>
        </header>
        {linkedFinding && (
          <p className="evidence-linked">
            关联发现{" "}
            <button onClick={() => showFinding(linkedFinding.id)}>
              {linkedFinding.id}
            </button>{" "}
            · {linkedFinding.review?.label || "待复核"}
          </p>
        )}
        <div className="evidence-provenance">
          <span>
            源码{" "}
            <code>
              {run.source.repository.commit?.slice(0, 7) ||
                run.source.snapshot.digest.slice(0, 12)}
            </code>
          </span>
          <ArrowRight size={14} />
          <span>{criterion?.title || (isInput ? "来源冻结" : "门禁判定")}</span>
          <ArrowRight size={14} />
          <span>{artifact?.name || "待生成原件"}</span>
          {linkedFinding && (
            <>
              <ArrowRight size={14} />
              <button onClick={() => showFinding(linkedFinding.id)}>
                {linkedFinding.id}
              </button>
            </>
          )}
        </div>
        {command && (
          <details className="execution-info" open>
            <summary>执行信息</summary>
            <dl className="inspector-facts">
              <dt>执行命令</dt>
              <dd>
                <code>
                  {command.argv.includes("-c")
                    ? command.argv[command.argv.indexOf("-c") + 1]
                    : command.argv.slice(-6).join(" ")}
                </code>
              </dd>
              <dt>退出码</dt>
              <dd>{command.exit_code ?? "未记录"}</dd>
              <dt>执行耗时</dt>
              <dd>
                {seconds(elapsed(command.started_at, command.finished_at))}
              </dd>
              <dt>完整命令</dt>
              <dd>
                <details>
                  <summary>展开原始参数</summary>
                  <pre>{command.argv.join(" ")}</pre>
                </details>
              </dd>
            </dl>
          </details>
        )}
        <ArtifactPreview
          run={run}
          artifact={artifact}
          detail={detail}
          notify={notify}
          openFile={setArtifactId}
        />
        {detail && (
          <details className="evidence-explanation">
            <summary>预期、执行步骤与验证边界</summary>
            <p>{detail.expected_value}</p>
            <ol>
              {detail.steps.map((s, i) => (
                <li key={i}>{s}</li>
              ))}
            </ol>
            <p>{detail.limitation}</p>
            <p>
              标准 {cid} · 用例 {result?.case_id || criterion?.case_id}
            </p>
          </details>
        )}
      </article>
    </section>
  );
}

function artifactMeaning(a: Artifact) {
  if (a.name === "remote-source.json") return "拉取时固定的远程地址、选择的分支或提交、实际 SHA 和源码快照；不随远端后续更新而改变。";
  if (a.owner_label && ["gate-result.json", "gate-input.json"].includes(a.name))
    return (
      a.owner_label +
      "子任务的门禁记录，仅代表这个环节；完整验收结论以父任务的最终判定为准。"
    );
  if (a.name === "source-context.json")
    return "本次执行创建时封存的仓库、版本、验收范围与文件摘要；查看历史时不重新读取 Git。";
  if (a.name === "gate-result.json")
    return "OPA 实际返回的验收判定。判定使用的检查结果在“判定依据”中。";
  if (a.name === "gate-input.json")
    return "提交给 OPA 的完整输入：必验标准、执行结果和证据完整性。";
  if (a.name.endsWith("-junit.xml"))
    return "Node.js 原始测试报告，记录测试名称、耗时和失败断言；仅证明所选测试的执行结果。";
  if (a.name === "bandit.json")
    return "Bandit 记录的规则命中、代码位置和原始代码；证明静态风险命中。";
  if (a.name === "axe-result.json")
    return "axe 记录的违规规则和具体页面元素；用于确认哪个控件缺少名称。";
  if (a.name.endsWith("trace.zip"))
    return "Playwright 采集的操作与网络轨迹。可直接打开本地 Trace Viewer 检查请求、截图和页面变化。";
  if (a.media_type.startsWith("image/"))
    return "本次浏览器执行采集的页面现场；通过或失败以关联断言为准。";
  if (a.name.endsWith(".log"))
    return "执行器的标准输出与错误输出；用于判断执行过程，检查结论以原始报告为准。";
  if (a.name.endsWith("-result.json"))
    return "从原始执行报告提取的单次用例结果，包含断言、耗时与失败位置。";
  if (a.name.startsWith("playwright-"))
    return "Playwright 输出的原始报告，保留所有用例、单次执行结果与附件记录。";
  return "本次执行采集的原始文件；可下载核对。";
}

function ArtifactPreview({
  run,
  artifact,
  detail,
  notify,
  openFile,
}: {
  run: Run;
  artifact?: Artifact;
  detail?: Inspection;
  notify: (s: string) => void;
  openFile: (id: string) => void;
}) {
  const [content, setContent] = useState<{ url: string; text: string } | null>(
      null,
    ),
    [error, setError] = useState(""),
    [loading, setLoading] = useState(false),
    [raw, setRaw] = useState(false);
  const [part,setPart]=useState(0);
  const pageBytes=256*1024;
  const chunked=!!artifact && artifact.size>pageBytes;
  const url = artifact ? `/api/runs/${run.id}/artifacts/${artifact.id}` : "";
  useEffect(()=>setPart(0),[url]);
  useEffect(() => {
    setContent(null);
    setError("");
    setRaw(false);
    setLoading(false);
    if (
      !artifact ||
      (!artifact.media_type.startsWith("text/") &&
        !["application/json", "application/xml"].includes(artifact.media_type))
    )
      return;
    const controller = new AbortController();
    setLoading(true);
    fetch(url, { signal: controller.signal,headers:chunked?{Range:`bytes=${part*pageBytes}-${Math.min(artifact!.size-1,(part+1)*pageBytes-1)}`} : undefined })
      .then(async (r) => {
        if (!r.ok) throw Error(await r.text());
        return r.text();
      })
      .then((text) => {
        if (!controller.signal.aborted) setContent({ url, text });
      })
      .catch((e) => {
        if (e.name !== "AbortError") setError(e.message);
      })
      .finally(() => {
        if (!controller.signal.aborted) setLoading(false);
      });
    return () => controller.abort();
  }, [url, artifact?.media_type,part]);
  if (!artifact)
    return (
      <div className="empty">
        <FileText size={30} />
        <p>尚无可读取的证据文件</p>
      </div>
    );
  const text = content?.url === url ? content.text : "",
    ready = content?.url === url;
  let value: any = null;
  try {
    if (ready && !chunked && artifact.media_type === "application/json")
      value = JSON.parse(text);
  } catch {
    /* unfamiliar content stays raw */
  }
  const gate =
    artifact.name === "gate-result.json"
      ? value?.result?.[0]?.expressions?.[0]?.value
      : undefined;
  const gateInput =
    artifact.name === "gate-input.json" &&
    Array.isArray(value?.results) &&
    Array.isArray(value?.required)
      ? value
      : null;
  const bandit =
    artifact.name === "bandit.json" && Array.isArray(value?.results)
      ? value
      : null;
  const axe =
    artifact.name === "axe-result.json" && Array.isArray(value?.violations)
      ? value
      : null;
  const assertion =
    artifact.criterion_id &&
    artifact.name.endsWith("-result.json") &&
    typeof value?.title === "string" &&
    value?.result &&
    typeof value.result === "object"
      ? value
      : null;
  const sourceSnapshot =
    artifact.name === "source-context.json" &&
    value?.schema_version === 1 &&
    value?.repository &&
    value?.snapshot &&
    Array.isArray(value?.scope?.files) &&
    value?.tooling
      ? value
      : null;
  let xmlTests: {
    name: string;
    status: string;
    message: string;
    duration: string;
  }[] = [];
  if (
    ready && !chunked &&
    artifact.media_type === "application/xml" &&
    text.length <= 2_000_000
  ) {
    const doc = new DOMParser().parseFromString(text, "application/xml");
    if (!doc.querySelector("parsererror"))
      xmlTests = Array.from(doc.querySelectorAll("testcase")).map((node) => ({
        name: node.getAttribute("name") || "未命名用例",
        status: node.querySelector("failure,error")
          ? "failed"
          : node.querySelector("skipped")
            ? "not_run"
            : "passed",
        message:
          node.querySelector("failure,error")?.textContent ||
          node.querySelector("failure,error")?.getAttribute("message") ||
          "",
        duration: node.getAttribute("time") || "",
      }));
  }
  const junit = xmlTests.length > 0;
  const hasExplanation =
    junit ||
    gate !== undefined ||
    gateInput ||
    bandit ||
    axe ||
    assertion ||
    sourceSnapshot;
  return (
    <>
      <div className="artifact-viewer">
        <div className="artifact-header">
          <div>
            <strong>{artifactTitle(artifact)}</strong>
            <small>{artifact.name}</small>
          </div>
          <div className="artifact-actions">
            {ready && (
              <button
                className="text-button muted"
                aria-label="复制原始证据"
                onClick={async () => {
                  try {
                    await navigator.clipboard.writeText(text);
                    notify(chunked?"已复制当前字节片段":"已复制原始证据");
                  } catch {
                    notify("复制不可用，请下载原始证据");
                  }
                }}
              >
                <Copy size={17} />
                复制
              </button>
            )}
            <a
              className="text-button muted"
              href={url + "?download=true"}
              download
            >
              <DownloadSimple size={17} />
              下载
            </a>
          </div>
        </div>
        <p className="artifact-file-meta">
          {artifact.size.toLocaleString()} B ·{" "}
          {run.integrity ? "登记文件摘要相符" : "完整性未确认"}
        </p>
        {chunked&&<nav aria-label="证据片段分页"><button disabled={!part} onClick={()=>setPart(part-1)}>上一片段</button><span> 字节 {part*pageBytes+1}–{Math.min(artifact.size,(part+1)*pageBytes)} / {artifact.size} · 可逐段查看，下载保留完整原件 </span><button disabled={(part+1)*pageBytes>=artifact.size} onClick={()=>setPart(part+1)}>下一片段</button></nav>}
        <details className="artifact-meaning">
          <summary>文件说明</summary>
          <p>{artifactMeaning(artifact)}</p>
        </details>
        {hasExplanation && (
          <div className="reader-tabs">
            <button
              className={!raw ? "selected" : ""}
              onClick={() => setRaw(false)}
              aria-pressed={!raw}
            >
              证据解读
            </button>
            <button
              className={raw ? "selected" : ""}
              onClick={() => setRaw(true)}
              aria-pressed={raw}
            >
              原始文件
            </button>
          </div>
        )}
        {loading ||
        (!ready &&
          (artifact.media_type.startsWith("text/") ||
            ["application/json", "application/xml"].includes(
              artifact.media_type,
            )) &&
          !error) ? (
          <div className="empty small">
            <SpinnerGap className="spin" />
            读取并校验证据…
          </div>
        ) : error ? (
          <div className="error-banner" role="alert">
            {error}
          </div>
        ) : artifact.media_type.startsWith("image/") ? (
          <img
            className="evidence-image"
            src={url}
            alt={"本次执行采集的页面现场 · " + artifact.name}
          />
        ) : raw ? (
          <pre className="code-view">{text || "此文件没有文本输出。"}</pre>
        ) : junit ? (
          <div className="readable-evidence">
            <span className="eyebrow">原始测试报告 · {xmlTests.length} 项</span>
            {xmlTests.map((t, i) => (
              <section className="junit-test" key={i}>
                <div>
                  <strong>{t.name}</strong>
                  <span className={"result-text " + t.status}>
                    {labels[t.status] || t.status}
                    {t.duration ? ` · ${t.duration} s` : ""}
                  </span>
                </div>
                {t.message && (
                  <pre className="code-view">
                    {t.message.split("\n").filter(Boolean).join("\n")}
                  </pre>
                )}
              </section>
            ))}
          </div>
        ) : sourceSnapshot ? (
          <div className="readable-evidence">
            <SourceDetails source={sourceSnapshot} />
          </div>
        ) : gate !== undefined ? (
          <div className="readable-evidence">
            <span className="eyebrow">原始 OPA 返回值</span>
            <h3
              className={
                "result-text " + (gate === run.decision ? gate : "error")
              }
            >
              {labels[gate] || String(gate)} <code>{String(gate)}</code>
            </h3>
            {gate !== run.decision && (
              <p className="result-text error">
                原始门禁输出与当前可用结论不同，请检查完整性或记录有效性。
              </p>
            )}
            <p>输入中的检查结果和完整性决定本次判定。</p>
            <button
              className="text-button"
              onClick={() => {
                const a = run.artifacts.find(
                  (a) => a.name === "gate-input.json",
                );
                if (a) openFile(a.id);
              }}
            >
              查看判定依据 <ArrowRight />
            </button>
          </div>
        ) : gateInput ? (
          <div className="readable-evidence">
            <div className="input-flags">
              <span>
                执行完成{" "}
                <strong>{gateInput.complete === true ? "是" : "否"}</strong>
              </span>
              <span>
                输入完整性{" "}
                <strong>
                  {gateInput.integrity === true ? "相符" : "不符"}
                </strong>
              </span>
              <span>
                必验项 <strong>{gateInput.required.length}</strong>
              </span>
            </div>
            {gateInput.results.map((r: any, i: number) => (
              <div className="input-result" key={i}>
                <code>{r.criterion_id}</code>
                <span className={"result-text " + r.status}>
                  {labels[r.status] || r.status}
                </span>
              </div>
            ))}
          </div>
        ) : bandit ? (
          <div className="readable-evidence">
            <p>
              扫描错误 {bandit.errors?.length ?? "未记录"} 条 · 规则命中{" "}
              {bandit.results.length} 处
            </p>
            {bandit.results.map((hit: any, i: number) => (
              <div className="scan-hit" key={i}>
                <strong>
                  {hit.test_id} · {hit.test_name}
                </strong>
                <small>
                  {String(hit.filename).split("validation/").pop()}:
                  {hit.line_number} · 风险 {hit.issue_severity} · 置信{" "}
                  {hit.issue_confidence}
                </small>
                <pre>{hit.code}</pre>
                <p>{hit.issue_text}</p>
              </div>
            ))}
            {!bandit.results.length && (
              <p className="verified-note">未命中 B602 规则。</p>
            )}
          </div>
        ) : axe ? (
          <div className="readable-evidence">
            <strong>{axe.violations.length} 条违规规则</strong>
            {axe.violations.map((v: any) => (
              <div className="scan-hit" key={v.id}>
                <p>
                  {v.id} · {v.help}
                </p>
                {v.nodes?.map((n: any, i: number) => (
                  <div key={i}>
                    <pre>{n.html}</pre>
                    <p className="muted small-text">{n.failureSummary}</p>
                  </div>
                ))}
              </div>
            ))}
          </div>
        ) : assertion ? (
          <div className="readable-evidence">
            <div className="assertion-heading">
              <strong>{detail?.subject || assertion.title}</strong>
              <span className={"result-text " + assertion.status}>
                {labels[assertion.status] || assertion.status}
              </span>
            </div>
            {detail && <Values detail={detail} />}
            <p>
              {detail?.summary ||
                assertion.result.error?.message?.replace(
                  /\x1b\[[0-9;]*m/g,
                  "",
                ) ||
                "断言通过"}
            </p>
            {detail?.location && <small>断言位置 · {detail.location}</small>}
            {assertion.source_report &&
              run.artifacts.some((a) => a.id === assertion.source_report) && (
                <button
                  className="text-button"
                  onClick={() => openFile(assertion.source_report)}
                >
                  查看执行器原始报告 <ArrowRight />
                </button>
              )}
          </div>
        ) : ready ? (
          <pre className="code-view">
            {text || "此执行器没有标准输出或错误输出。检查结果请查看检测报告。"}
          </pre>
        ) : (
          <div className="trace-instructions">
            <TerminalWindow size={25} />
            <strong>
              {artifact.name.endsWith("trace.zip")
                ? "查看操作轨迹"
                : "原始文件"}
            </strong>
            <p>{artifact.name}</p>
            {artifact.name.endsWith("trace.zip") && (
              <a
                className="button primary"
                target="_blank"
                rel="noreferrer"
                href={
                  "/trace-viewer/index.html?trace=" +
                  encodeURIComponent(window.location.origin + url)
                }
              >
                打开操作轨迹
              </a>
            )}
            <a
              className="button outline"
              href={url + "?download=true"}
              download
            >
              <DownloadSimple />
              {artifact.name.endsWith("trace.zip")
                ? "下载轨迹"
                : "下载原始文件"}
            </a>
          </div>
        )}
      </div>
      <details className="metadata">
        <summary>
          来源与文件校验{" "}
          <span>{run.integrity ? "摘要相符" : "未完成或未通过"}</span>
        </summary>
        <dl>
          <dt>本次执行</dt>
          <dd>
            {run.id} · {run.label}
          </dd>
          <dt>证据 ID</dt>
          <dd>{artifact.id}</dd>
          <dt>SHA-256</dt>
          <dd>{artifact.sha256}</dd>
          <dt>文件大小</dt>
          <dd>{artifact.size.toLocaleString()} bytes</dd>
          <dt>采集时间</dt>
          <dd>
            {new Date(artifact.collected_at).toLocaleString("zh-CN", {
              hour12: false,
            })}
          </dd>
          <dt>校验边界</dt>
          <dd>校验文件与本机登记摘要是否相符，尚无可信采集签名。</dd>
        </dl>
      </details>
    </>
  );
}
