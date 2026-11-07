import { ToolCallCard } from "./components/affect/ToolCallCard";
import {
  useEffect,
  useRef,
  useState,
  type CSSProperties,
  type ReactNode,
} from "react";
import {
  ArrowUpRight,
  CheckCircle,
  XCircle,
  Circle,
  SpinnerGap,
  WarningCircle,
  FileText,
  CaretDown,
  TerminalWindow,
  ArrowLeft,
  ArrowRight,
} from "@phosphor-icons/react";
import type { Criterion, Run, Tab } from "./types";
import { labels, PriorityBadge } from "./ui";
import { focusChecks, acceptanceVerdict, acceptanceSummary } from "./focus";
import { checkProgress } from "./checkProgress";
import { isReusedStage, findingTitle, findingLocation } from "./presentation";
import { PlanDetails } from "./TestDesign";
import { CoverageGaps } from "./CoverageGaps";
import { UniversalPlanDetails } from "./UniversalPlanDetails";
import {
  pipeline,
  elapsed,
  stageDuration,
  seconds,
  clockTime,
  stageLabel,
} from "./pipeline";

type Props = {
  summary: ReactNode;
  run: Run;
  phase: number;
  setPhase: (phase: number) => void;
  busy: boolean;
  setTab: (tab: Tab) => void;
  showResultEvidence: (id: string) => void;
  goEvidence: (id: string) => void;
  showFinding: (id: string) => void;
  openArtifact: (id: string) => void;
};

export function ResultIcon({
  status,
  size = 19,
}: {
  status: string;
  size?: number;
}) {
  const Icon =
    status === "passed" || status === "allow"
      ? CheckCircle
      : status === "failed" || status === "reject"
        ? XCircle
        : status === "running"
          ? SpinnerGap
          : status === "error" || status === "blocked"
            ? WarningCircle
            : Circle;
  return (
    <Icon
      className={
        "console-status " + status + (status === "running" ? " spin" : "")
      }
      size={size}
      weight={
        size < 23 && ["passed", "failed", "allow", "reject"].includes(status)
          ? "fill"
          : "regular"
      }
      aria-hidden="true"
    />
  );
}

const shortTitles: Record<string, string> = {
  BUILD: "构建产物",
  "CLIENT-REGRESSION": "客户端回归",
  "BRIDGE-REGRESSION": "Bridge 回归",
  "PYTHON-UPLOAD": "Python 上传",
  "SECRET-SCAN": "密钥扫描",
  "DEPENDENCY-AUDIT": "依赖漏洞",
  "SAST-NODE": "JS / TS 安全",
  "SAST-PYTHON": "Python 安全",
};
function title(c: Criterion) {
  return shortTitles[c.id] || c.title;
}
function executor(c: Criterion) {
  const names: Record<string, string> = {
    build: "工作区构建",
    junit: "Node.js · JUnit",
    python: "Python unittest",
    gitleaks: "Gitleaks",
    "npm-audit": "npm audit",
    semgrep: "Semgrep CE · njsscan",
    "python-sast": "Bandit",
    playwright: "Playwright",
    zap: "OWASP ZAP",
    k6: "k6",
    "joint-restore": "PostgreSQL · 文件恢复",
    "universal-design": "文档与模型",
    "universal-prepare": "隔离容器 · 项目依赖",
    "universal-fixture": "pip · 夹具依赖缓存",
    "universal-build": "项目构建与语法检查",
    "universal-native": "项目原生测试",
    "universal-service": "本机隔离服务",
    "universal-business": "独立断言 · 协议执行器",
    "universal-cleanup": "Docker 环境回收",
  };
  return names[c.kind || ""] || names[c.executor] || c.executor;
}
function Exclusions({ run }: { run: Run }) {
  return run.baseline.exclusions?.length ? (
    <details className="console-exclusions">
      <summary>
        <CaretDown size={14} />
        排除范围 <span>{run.baseline.exclusions.length} 类</span>
      </summary>
      <dl>
        {run.baseline.exclusions.map((x) => (
          <div key={x.subject}>
            <dt>{x.subject}</dt>
            <dd>{x.reason}</dd>
          </div>
        ))}
      </dl>
    </details>
  ) : null;
}

export function ConsoleFlow({
  summary,
  run,
  phase,
  setPhase,
  busy,
  setTab,
  showResultEvidence,
  goEvidence,
  showFinding,
  openArtifact,
}: Props) {
  const stages = pipeline(run),
    overview = phase < 0,
    selected = stages[phase] ||
      stages[0] || {
        id: "baseline",
        title: "冻结依据",
        status: "not_run",
        detail: "未采集阶段记录",
        tool: "",
        work: "",
      };
  const [clock, setClock] = useState(Date.now());
  const [follow, setFollow] = useState(busy);
  const [criterionId, setCriterionId] = useState<string | null>(null);
  const [showAll, setShowAll] = useState(false);
  const autoFollowed = useRef(false);
  const detailRef = useRef<HTMLDivElement>(null);
  const pipelineRef = useRef<HTMLOListElement>(null);
  const [pipelineScroll, setPipelineScroll] = useState({
    before: false,
    after: false,
  });
  const updatePipelineScroll = () => {
    const list = pipelineRef.current;
    if (!list) return;
    const before = list.scrollLeft > 2;
    const after = list.scrollLeft + list.clientWidth < list.scrollWidth - 2;
    setPipelineScroll((current) =>
      current.before === before && current.after === after
        ? current
        : { before, after },
    );
  };
  useEffect(() => {
    const list = pipelineRef.current;
    if (!list) return;
    const observer = new ResizeObserver(updatePipelineScroll);
    observer.observe(list);
    updatePipelineScroll();
    return () => observer.disconnect();
  }, [run.id, stages.length]);
  const scrollPipeline = (direction: number) => {
    const list = pipelineRef.current;
    list?.scrollBy({
      left: direction * list.clientWidth * 0.8,
      behavior: window.matchMedia("(prefers-reduced-motion: reduce)").matches
        ? "auto"
        : "smooth",
    });
  };
  useEffect(() => {
    const list = pipelineRef.current,
      item = list?.children[phase] as HTMLElement | undefined;
    if (!list || !item) return;
    const left = item.offsetLeft - list.offsetLeft;
    if (
      left < list.scrollLeft ||
      left + item.offsetWidth > list.scrollLeft + list.clientWidth
    )
      list.scrollTo({
        left: Math.max(0, left - (list.clientWidth - item.offsetWidth) / 2),
        behavior: window.matchMedia("(prefers-reduced-motion: reduce)").matches
          ? "auto"
          : "smooth",
      });
  }, [phase, run.id]);
  const current = stages.findIndex((s) => s.status === "running");
  useEffect(() => {
    setFollow(["queued", "running"].includes(run.status));
    autoFollowed.current = false;
    setCriterionId(null);
    setShowAll(false);
  }, [run.id]);
  useEffect(() => {
    if (!busy) return;
    const timer = setInterval(() => setClock(Date.now()), 250);
    return () => clearInterval(timer);
  }, [busy]);
  useEffect(() => {
    if (busy && follow && current >= 0) {
      setPhase(current);
      autoFollowed.current = true;
    } else if (!busy && follow && autoFollowed.current) {
      setPhase(stages.findIndex((s) => s.id === "gate"));
      autoFollowed.current = false;
    }
  }, [busy, follow, current, setPhase, stages]);
  const executionStage =
    overview || run.baseline.criteria.some((c) => c.layer === selected.id);
  const grouped = focusChecks(run, clock);
  const criteria = overview
    ? (showAll ? grouped.all : grouped.attention).map((row) => row.criterion)
    : executionStage
      ? run.baseline.criteria.filter((c) => c.layer === selected.id)
      : run.baseline.criteria;
  const picked =
    criterionId === ""
      ? undefined
      : run.baseline.criteria.find((c) => c.id === criterionId) ||
        criteria.find((c) => c.id === criterionId) ||
        criteria.find(
          (c) => checkProgress(run, c.id, clock).status === "running",
        ) ||
        criteria.find((c) =>
          run.results.some(
            (r) => r.criterion_id === c.id && r.status === "failed",
          ),
        ) ||
        criteria[0];
  const result = run.results.find((r) => r.criterion_id === picked?.id);
  const pickedProgress = picked && checkProgress(run, picked.id, clock);
  const activeChecks = run.baseline.criteria.filter(
    (c) => checkProgress(run, c.id, clock).status === "running",
  );
  const currentStage = stages.find((s) => s.status === "running");
  const detail = picked && run.inspections[picked.id];
  const finding = run.findings.find((f) => f.criterion_id === picked?.id);
  const evidenceIds = new Set(result?.evidence_refs || []);
  if (detail?.primary_ref) evidenceIds.add(detail.primary_ref);
  if (detail?.source_report) evidenceIds.add(detail.source_report);
  const artifacts = run.artifacts.filter((a) => evidenceIds.has(a.id));
  const primary =
    artifacts.find((a) => a.id === detail?.source_report) ||
    artifacts.find((a) => a.id === detail?.primary_ref) ||
    artifacts[0];
  const observedLocation =
    finding && findingLocation(finding, run.inspections[finding.id] || detail);
  const locations = observedLocation
    ? [observedLocation]
    : detail?.location
      ? [detail.location]
      : (result?.actual || "")
          .split("\n")
          .filter((x) => /^\/?(?:source\/|server\/|client\/|tests\/)/.test(x))
          .map((x) => x.split(" · ")[0].replace(/^\/source\//, ""))
          .slice(0, 3);
  const duration = (s: typeof selected) =>
    stageDuration(s, run.pipeline === undefined, clock);
  const command = run.commands?.filter(
    (c) => c.name === picked?.id || c.name === detail?.method,
  );
  const inspector = picked ? (
    <div className="focus-check-detail" id={"check-detail-" + picked.id}>
      {result?.review && (
        <section className="review-conclusion">
          <strong>
            {result.review.label}
            {result.raw_status === "failed" ? " · 原始命中保留" : ""}
          </strong>
          <p>{result.review.reason}</p>
          <details>
            <summary>复核依据</summary>
            {result.review.rows.map((row, i) => (
              <p key={i}>
                {row.path}
                {row.line ? `:${row.line}` : ""} · {row.reason}
              </p>
            ))}
          </details>
        </section>
      )}

      <dl className="focus-facts">
        <dt>预期</dt>
        <dd>{picked.expected}</dd>
        <dt>实际</dt>
        <dd className="focus-observation">
          {pickedProgress?.status === "running"
            ? pickedProgress.batch
              ? "浏览器批次执行中，单项断言等待报告。"
              : "检查正在执行，尚未形成最终结论。"
            : finding?.review?.reason ||
              detail?.actual_value ||
              detail?.summary ||
              result?.actual.split("\n").find(Boolean) ||
              "尚未产生报告"}
        </dd>
      </dl>
      <div className="focus-detail-actions">
        <button
          className="button primary"
          disabled={!primary && !result?.evidence_refs.length}
          onClick={() => showResultEvidence(picked.id)}
        >
          查看原始证据
        </button>
        <button
          className="text-button"
          onClick={() => {
            const index = stages.findIndex((s) =>
              ["requirements", "baseline", "design"].includes(s.id),
            );
            if (index >= 0) {
              setPhase(index);
              setFollow(false);
              setCriterionId(null);
            }
          }}
        >
          查看独立标准
        </button>
        {finding && (
          <button
            className="text-button"
            onClick={() => showFinding(finding.id)}
          >
            查看缺陷详情 <ArrowUpRight size={14} />
          </button>
        )}
      </div>
      <details className="focus-technical">
        <summary>执行详情与溯源</summary>
        <dl className="inspector-facts">
          <dt>执行器</dt>
          <dd>{detail?.method || executor(picked)}</dd>
          <dt>标准编号</dt>
          <dd>
            <code>{picked.id}</code>
          </dd>
          <dt>用例编号</dt>
          <dd>
            <code>{picked.case_id}</code>
          </dd>
          {locations.length > 0 && (
            <>
              <dt>位置</dt>
              <dd>
                {locations.map((x) => (
                  <code key={x}>{x}</code>
                ))}
              </dd>
            </>
          )}
          {result?.actual && (
            <>
              <dt>完整结果</dt>
              <dd className="full-observation">{result.actual}</dd>
            </>
          )}
        </dl>
        <details className="inspector-proof">
          <summary>证据信息与校验</summary>
          <dl className="inspector-facts">
            <dt>原始报告</dt>
            <dd>
              {primary ? (
                <button
                  className="text-button"
                  onClick={() => showResultEvidence(picked.id)}
                >
                  <FileText size={14} />
                  {primary.name}
                </button>
              ) : pickedProgress?.status === "running" ? (
                "报告生成中"
              ) : (
                "未采集"
              )}
            </dd>
            <dt>来源</dt>
            <dd>{detail?.method || executor(picked)}</dd>
            <dt>校验</dt>
            <dd
              className={
                run.integrity && detail?.verified ? "verified-note" : "muted"
              }
            >
              <ResultIcon
                status={
                  run.integrity && detail?.verified ? "passed" : "blocked"
                }
              />
              {run.integrity && detail?.verified
                ? "已核对原始报告"
                : pickedProgress?.status === "running"
                  ? "等待检查结束"
                  : "证据未确认"}
            </dd>
          </dl>
        </details>
        {finding && (
          <button
            className="text-button inspector-finding"
            onClick={() => showFinding(finding.id)}
          >
            <PriorityBadge finding={finding} />
            查看缺陷 {finding.id} <ArrowUpRight size={14} />
          </button>
        )}
        {!!command?.length && (
          <div className="focus-tool-calls" aria-label="执行命令">
            {command.map((c, i) => {
              const start = Date.parse(c.started_at);
              const end = c.finished_at ? Date.parse(c.finished_at) : NaN;
              const running = !c.finished_at && run.status === "running" && pickedProgress?.status === "running";
              const status = running ? "running" : !c.finished_at || c.exit_code === null
                ? "unknown" : c.exit_code === 0 ? "success" : "error";
              return (
                <ToolCallCard
                  key={run.id + "/" + picked.id + "/" + i}
                  name={detail?.method || executor(picked)}
                  summary="执行命令"
                  icon={<TerminalWindow size={17} />}
                  status={status}
                  statusLabel={status === "unknown" ? "状态未确认" : running ? "执行中" : "退出码 " + c.exit_code}
                  args={{ argv: c.argv }}
                  result={c.finished_at ? { exit_code: c.exit_code, evidence_ref: c.evidence_ref ?? null } : undefined}
                  error={status === "error" ? "命令返回退出码 " + c.exit_code + "。请核对原始报告中的扫描命中或执行错误。" : undefined}
                  startedAt={running && Number.isFinite(start) ? start : undefined}
                  duration={Number.isFinite(start) && Number.isFinite(end) && end >= start ? end - start : undefined}
                  openOnError={false}
                  maxCodeHeight={180}
                />
              );
            })}
          </div>
        )}

        <Exclusions run={run} />
      </details>
    </div>
  ) : null;
  const renderChecks = (items: Criterion[]) => (
    <div className="focus-check-list">
      {items.map((c) => {
        const progress = checkProgress(run, c.id, clock);
        const result = run.results.find((r) => r.criterion_id === c.id);
        const expanded = picked?.id === c.id;
        return (
          <section
            className={"focus-check" + (expanded ? " expanded" : "")}
            key={c.id}
          >
            <button
              className="focus-check-trigger"
              aria-expanded={expanded}
              aria-controls={"check-detail-" + c.id}
              onClick={() => setCriterionId(expanded ? "" : c.id)}
            >
              <ResultIcon status={progress.status} size={20} />
              <span className="focus-check-label">
                {title(c)}
                {result?.review && <small>{result.review.label}</small>}
              </span>
              <span className={"focus-check-state " + progress.status}>
                {labels[progress.status] || progress.status}
              </span>
              <time>
                {progress.duration !== undefined
                  ? seconds(progress.duration)
                  : "—"}
              </time>
              <CaretDown size={16} className="focus-check-caret" />
            </button>
            {expanded && inspector}
          </section>
        );
      })}
    </div>
  );
  const verdict = acceptanceVerdict(run);
  return (
    <section className="console-flow">
      <header className="focus-verdict">
        <ResultIcon status={verdict.status} size={23} />
        <div>
          <h2>{verdict.title}</h2>
          <p>{acceptanceSummary(run)}</p>
        </div>
        <span className={"focus-gate-label " + verdict.status}>
          {verdict.label}
        </span>
      </header>
      <ol
        ref={pipelineRef}
        className="console-pipeline"
        id="acceptance-pipeline"
        aria-label="验收流水线"
        onScroll={updatePipelineScroll}
        tabIndex={0}
        style={{ "--stage-count": stages.length } as CSSProperties}
      >
        {stages.map((s, i) => (
          <li
            key={s.id}
            className={s.status + (i === phase ? " selected" : "")}
          >
            <button
              aria-pressed={i === phase}
              aria-label={`${s.title} · ${stageLabel(s.status, s.id)} · ${isReusedStage(s) ? "已复用" : seconds(duration(s))}`}
              onClick={() => {
                setPhase(i);
                setFollow(false);
                setCriterionId(null);
                requestAnimationFrame(() => {
                  if (window.matchMedia("(max-width: 700px)").matches) {
                    detailRef.current?.scrollIntoView({
                      block: "start",
                      behavior: window.matchMedia(
                        "(prefers-reduced-motion: reduce)",
                      ).matches
                        ? "auto"
                        : "smooth",
                    });
                  }
                });
              }}
            >
              <ResultIcon status={s.status} size={18} />
              <strong>{s.title}</strong>
              <time>
                <span>{stageLabel(s.status, s.id)}</span>
                {" · "}
                {isReusedStage(s)
                  ? "已复用"
                  : s.status === "queued" || s.status === "not_run"
                    ? "—"
                    : seconds(duration(s))}
              </time>
            </button>
          </li>
        ))}
      </ol>
      {(pipelineScroll.before || pipelineScroll.after) && (
        <nav className="pipeline-scroll-controls" aria-label="流水线滚动">
          <span>共 {stages.length} 个阶段</span>
          <button
            aria-label="查看前面的验收阶段"
            aria-controls="acceptance-pipeline"
            disabled={!pipelineScroll.before}
            onClick={() => scrollPipeline(-1)}
          >
            <ArrowLeft size={16} />
          </button>
          <button
            aria-label="查看后面的验收阶段"
            aria-controls="acceptance-pipeline"
            disabled={!pipelineScroll.after}
            onClick={() => scrollPipeline(1)}
          >
            <ArrowRight size={16} />
          </button>
        </nav>
      )}
      {busy && (
        <div className="console-live-result" role="status" aria-live="polite">
          <SpinnerGap className="spin" size={18} />
          <strong>正在执行</strong>
          <span>
            {(activeChecks.length > 1
              ? `浏览器验证批次 · ${activeChecks.length} 项检查`
              : activeChecks.map(title).join("、")) ||
              currentStage?.title ||
              "等待执行器启动"}
          </span>
          <time aria-live="off">
            {seconds(
              activeChecks.length
                ? checkProgress(run, activeChecks[0].id, clock).duration
                : currentStage
                  ? duration(currentStage)
                  : undefined,
            )}
          </time>
          {run.current_activity &&
            !run.current_activity.finished_at &&
            !activeChecks.some((c) => c.id === run.current_activity?.name) && (
              <small>{run.current_activity.name}</small>
            )}
        </div>
      )}
      {busy && !follow && (
        <button
          className="text-button follow-stage"
          onClick={() => setFollow(true)}
        >
          跟随当前阶段
        </button>
      )}
      {!overview && (
        <button
          className="text-button focus-back"
          onClick={() => {
            setPhase(-1);
            setFollow(false);
            setCriterionId(null);
          }}
        >
          <ArrowLeft size={14} /> 返回验收概览
        </button>
      )}
      {executionStage ? (
        <div className="console-stage-workspace focus-stage" ref={detailRef}>
          <section
            className="console-results"
            aria-label={overview ? "验收检查" : selected.title + "结果"}
          >
            <header className="console-section-heading">
              <h2>
                {overview
                  ? showAll
                    ? "全部检查"
                    : grouped.attention.length
                      ? "需要处理"
                      : "检查结果"
                  : selected.title}
              </h2>
              <button
                className="text-button"
                onClick={() => {
                  setShowAll(overview ? !showAll : true);
                  setPhase(-1);
                  setFollow(false);
                  setCriterionId(null);
                }}
              >
                {overview && showAll ? "只看需要处理" : "查看全部检查"}{" "}
                <ArrowUpRight size={14} />
              </button>
            </header>
            {run.universal_plan &&
              !overview &&
              [
                "discovery",
                "design",
                "fixture",
                "service",
                "business",
              ].includes(selected.id) && (
                <details className="focus-plan">
                  <summary>查看本阶段方案与用例</summary>
                  <UniversalPlanDetails
                    plan={run.universal_plan}
                    run={run}
                    focus={selected.id === "fixture" ? "fixture" : undefined}
                  />
                </details>
              )}
            {renderChecks(criteria)}
            {!criteria.length && (
              <p className="focus-no-attention">
                {overview
                  ? "没有需要处理的检查；最终结论以本次验收范围和门禁为准。"
                  : "本阶段没有登记检查项。"}
              </p>
            )}
            {overview && !showAll && grouped.completed.length > 0 && (
              <details className="focus-completed">
                <summary>
                  已完成的检查 <span>{grouped.completed.length} 项通过</span>
                </summary>
                {renderChecks(grouped.completed.map((row) => row.criterion))}
              </details>
            )}
          </section>
        </div>
      ) : (
        <div
          className="console-stage-workspace auxiliary-stage"
          ref={detailRef}
        >
          <section className="console-results">
            <header className="console-section-heading">
              <h2>{selected.title}</h2>
              <span className={"console-result-state " + selected.status}>
                {stageLabel(selected.status, selected.id)}
              </span>
              <time>{seconds(duration(selected))}</time>
            </header>
            {selected.id === "design" || selected.id === "requirements" ? (
              <div className="console-stage-description">
                <p>{selected.detail}</p>
                {run.universal_plan && (
                  <UniversalPlanDetails plan={run.universal_plan} run={run} />
                )}
                {selected.id === "design" && run.workflow?.model_batches && (
                  <table className="console-standards">
                    <thead>
                      <tr>
                        <th>验收标准</th>
                        <th>设计状态</th>
                        <th>耗时</th>
                        <th>证据</th>
                      </tr>
                    </thead>
                    <tbody>
                      {run.workflow.model_batches.map((b) => (
                        <tr key={b.id}>
                          <td>{b.title}</td>
                          <td>
                            {(
                              {
                                passed: "草稿已生成",
                                running: "执行中",
                                queued: "等待",
                                blocked: "未完成",
                              } as Record<string, string>
                            )[b.status] || b.status}
                          </td>
                          <td>
                            {seconds(
                              b.connection?.duration_ms ??
                                elapsed(b.started_at, b.finished_at, clock),
                            )}
                          </td>
                          <td>
                            {b.input_ref && (
                              <button
                                className="text-button"
                                onClick={() => openArtifact(b.input_ref!)}
                              >
                                设计输入
                              </button>
                            )}
                            {b.ref && (
                              <button
                                className="text-button"
                                onClick={() => openArtifact(b.ref!)}
                              >
                                模型原件
                              </button>
                            )}
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                )}
                {run.test_plans?.length
                  ? run.test_plans.map((p, i) => (
                      <details key={i} open={i === 0}>
                        <summary>
                          {p.plan.planner?.kind === "model"
                            ? "模型设计方案"
                            : "结构化规则方案"}
                        </summary>
                        <PlanDetails
                          plan={p.plan}
                          run={p.execution}
                          openEvidence={openArtifact}
                        />
                      </details>
                    ))
                  : run.test_plan && (
                      <PlanDetails
                        plan={run.test_plan}
                        run={run.native_integration}
                        openEvidence={openArtifact}
                      />
                    )}
              </div>
            ) : selected.id === "baseline" || selected.id === "cases" ? (
              <div className="console-table-scroll">
                {run.test_plan && !run.test_plans && (
                  <PlanDetails
                    plan={run.test_plan}
                    run={run.native_integration}
                    openEvidence={openArtifact}
                  />
                )}
                <p className="console-stage-description">
                  {selected.id === "baseline"
                    ? "核对冻结的代码、验收标准及编排版本，并准备隔离执行环境。"
                    : run.case_registration_ref
                      ? "校验并登记已有用例，不在此阶段生成新测试；主要是本地校验与清单写入，因此通常很快。"
                      : "读取已有用例并登记执行范围，不在此阶段设计新测试；此旧记录未采集单独的用例清单校验产物。"}
                </p>
                {selected.id === "cases" && run.case_registration_ref && (
                  <button
                    className="text-button console-registration"
                    onClick={() => openArtifact(run.case_registration_ref!)}
                  >
                    查看用例登记清单 <ArrowUpRight size={14} />
                  </button>
                )}
                <table className="console-standards">
                  <thead>
                    <tr>
                      <th>
                        {selected.id === "baseline" ? "验收标准" : "验证用例"}
                      </th>
                      <th>执行器</th>
                    </tr>
                  </thead>
                  <tbody>
                    {criteria.map((c) => (
                      <tr key={c.id}>
                        <td>
                          <strong>
                            {selected.id === "baseline"
                              ? c.expected
                              : run.case_plans?.[c.id]?.subject || title(c)}
                          </strong>
                          <details className="console-trace-ids">
                            <summary>溯源编号</summary>
                            <dl>
                              <dt>验收标准编号</dt>
                              <dd>
                                <code>{c.id}</code>
                              </dd>
                              <dt>测试用例编号</dt>
                              <dd>
                                <code>{c.case_id}</code>
                              </dd>
                            </dl>
                          </details>
                          {selected.id === "cases" && (
                            <p>
                              {run.case_plans?.[c.id]?.steps.join(" → ") ||
                                c.expected}
                            </p>
                          )}
                        </td>
                        <td>{c.executor}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            ) : selected.id === "findings" || selected.id === "review" ? (
              <div className="console-finding-rows">
                {run.findings
                  .filter((f) => f.review_state !== "false_positive")
                  .map((f) => (
                    <button key={f.id} onClick={() => showFinding(f.id)}>
                      <span className="console-finding-label">
                        <PriorityBadge finding={f} />
                        <span>{findingTitle(f, run)}</span>
                        <code>{f.id}</code>
                        {run.baseline.recipe && (
                          <small className="muted">
                            {f.review?.label || "待复核"}
                          </small>
                        )}
                      </span>
                      <ArrowUpRight size={16} />
                    </button>
                  ))}
                {!run.findings.length && (
                  <p>{busy ? "尚未归纳缺陷" : "本次没有失败检查"}</p>
                )}
              </div>
            ) : selected.id === "gate" ? (
              <div className="console-gate">
                <ResultIcon status={run.decision} size={28} />
                <h3>{labels[run.decision]}</h3>
                <p>{run.reasons[0] || "等待门禁结果"}</p>
                <button
                  className="button outline"
                  onClick={() => goEvidence("")}
                >
                  查看判定输入与输出 <ArrowUpRight size={15} />
                </button>
              </div>
            ) : (
              <p className="console-stage-note">{selected.detail}</p>
            )}
          </section>
          <aside className="console-inspector">
            <h3>阶段记录</h3>
            <dl className="inspector-facts">
              <dt>执行内容</dt>
              <dd>{selected.detail}</dd>
              <dt>开始</dt>
              <dd>
                <time>{clockTime(selected.started_at)}</time>
              </dd>
              <dt>结束</dt>
              <dd>
                <time>
                  {selected.status === "running"
                    ? "执行中"
                    : clockTime(selected.finished_at)}
                </time>
              </dd>
              <dt>基线</dt>
              <dd>{run.baseline.version}</dd>
            </dl>
            <details className="console-disclosure">
              <summary>冻结版本与来源</summary>
              <dl className="inspector-facts">
                <dt>标准来源</dt>
                <dd>{run.baseline.source}</dd>
                <dt>标准摘要</dt>
                <dd>
                  <code>{run.baseline.digest}</code>
                </dd>
                <dt>测试集摘要</dt>
                <dd>
                  <code>{run.suite_digest}</code>
                </dd>
              </dl>
            </details>
            <Exclusions run={run} />
          </aside>
        </div>
      )}
      <div className="focus-run-context">
        {run.reasons.length > 0 && (
          <details className="focus-execution-summary">
            <summary>判定依据</summary>
            {run.reasons.map((reason, i) => (
              <p key={i}>{reason}</p>
            ))}
          </details>
        )}

        <details className="focus-execution-summary">
          <summary>执行统计与耗时</summary>
          {summary}
        </details>
        {run.completion && (
          <details className="completion-details">
            <summary>
              {busy
                ? "流程执行中"
                : run.completion.complete
                  ? "所选流程已执行"
                  : "验收范围与未完成项"}
            </summary>
            <p>
              {run.completion.kind === "scoped"
                ? "所选范围检查，非完整验收。"
                : run.completion.kind === "recipe"
                  ? "本地配方验收；结论仅适用于冻结范围。"
                  : "按声明范围执行；覆盖缺口单独判定。"}
            </p>
            {run.completion.gaps?.length ? (
              <CoverageGaps issues={run.completion.gaps} />
            ) : (
              [...run.completion.missing, ...(run.completion.errors || [])].map(
                (s, i) => <p key={i}>{s}</p>,
              )
            )}
          </details>
        )}
      </div>
      <footer className="console-flow-footer">
        <details>
          <summary>验收范围</summary>
          <p>{run.baseline.scope}</p>
        </details>
        <button className="text-button" onClick={() => setTab("findings")}>
          查看缺陷 <ArrowUpRight size={13} />
        </button>
      </footer>
    </section>
  );
}
