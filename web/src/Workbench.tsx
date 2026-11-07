import { executionSummary } from "./executionSummary";
import { Integrations } from "./Integrations";
import { pipeline, elapsed, seconds } from "./pipeline";
import { useCallback, useEffect, useRef, useState } from "react";
import {
  ShieldCheck,
  BookOpenText,
  ClockCounterClockwise,
  DownloadSimple,
  WarningCircle,
  ArrowCounterClockwise,
  SpinnerGap,
  PlayCircle,
  FolderSimple,
  Cube,
  DotsThree,
} from "@phosphor-icons/react";
import type { Run, RunBrief, SourceContext, Tab, View } from "./types";
import { labels, Modal } from "./ui";
import { Findings, Evidence } from "./panels";
import { ConsoleFlow as Flow } from "./ConsoleFlow";
import { SourceDetails, TargetStrip } from "./SourceContext";
import { Catalogue } from "./Catalogue";
import { LocalRepository } from "./LocalRepository";
import { TestDesign } from "./TestDesign";
type Project = {
  id: string;
  name: string;
  repository: string;
  version: string;
  check_count: number;
  test_count: number;
  scope?: string;
};
const tabs: { id: Tab; title: string }[] = [
  { id: "flow", title: "验收流程" },
  { id: "findings", title: "缺陷详情" },
  { id: "evidence", title: "证据溯源" },
];
async function request<T>(url: string, init?: RequestInit): Promise<T> {
  const controller = new AbortController();
  const abort = () => controller.abort();
  init?.signal?.addEventListener("abort", abort, { once: true });
  if (init?.signal?.aborted) controller.abort();
  const timeout = window.setTimeout(abort, 30000);
  try {
    const r = await fetch(url, { ...init, signal: controller.signal });
    if (!r.ok) throw Error((await r.text()) || `请求失败 (${r.status})`);
    return await r.json();
  } catch (error) {
    if (controller.signal.aborted && !init?.signal?.aborted)
      throw Error("读取超时，请重试。原始验收记录保留。");
    throw error;
  } finally {
    window.clearTimeout(timeout);
    init?.signal?.removeEventListener("abort", abort);
  }
}

export function Workbench() {
  const params = new URLSearchParams(location.search),
    initialTab = params.get("tab") as Tab;
  const [tab, setTab] = useState<Tab>(
    tabs.some((x) => x.id === initialTab) ? initialTab : "flow",
  );
  const [view, setView] = useState<View>(
    params.has("integration")
      ? "run"
      : ["records", "repositories", "integrations"].includes(
            params.get("view") || "",
          )
        ? (params.get("view") as View)
        : "run",
  );
  const [target, setTarget] = useState<SourceContext | null>(null),
    [repositoryId, setRepositoryId] = useState(params.get("repository") || ""),
    [targetInfo, setTargetInfo] = useState(false);
  const [runs, setRuns] = useState<RunBrief[]>([]),
    [runId, setRunId] = useState(
      params.get("integration") || params.get("run") || "",
    );
  const [run, setRun] = useState<Run | null>(null),
    [findingId, setFindingId] = useState(params.get("finding") || "");
  const [findingPage, setFindingPage] = useState({
    offset: 0,
    state: "active",
    query: "",
  });
  const [artifactId, setArtifactId] = useState(params.get("artifact") || ""),
    [phase, setPhase] = useState(-1);
  const [evidenceScope, setEvidenceScope] = useState<"run" | "finding">(
    params.get("evidence") === "finding" ||
      (!params.has("evidence") && params.has("finding"))
      ? "finding"
      : "run",
  );
  const [newRun, setNewRun] = useState(false),
    [mode, setMode] = useState<"buggy" | "fixed">("fixed");
  const [projects, setProjects] = useState<Project[]>([]);
  const [projectId, setProjectId] = useState("");
  const [localRepository, setLocalRepository] = useState(false);
  const [testDesign, setTestDesign] = useState(false);
  const [designSeed, setDesignSeed] = useState<Record<string, any> | null>(
    null,
  );
  const project = projects.find((p) => p.id === projectId);
  const openNewRun = () => {
    setLocalRepository(true);
  };
  const [starting, setStarting] = useState(false),
    [error, setError] = useState(""),
    [toast, setToast] = useState("");
  const [catalogueLoading, setCatalogueLoading] = useState(true);
  const lastRun = useRef("");
  const notify = (s: string) => {
    setToast(s);
    setTimeout(() => setToast(""), 2400);
  };
  const refreshList = useCallback(async () => {
    try {
      const { runs: list } = await request<{
        runs: RunBrief[];
      }>("/api/catalogue?limit=50");
      setRuns(list);
      setRunId(
        (current) =>
          current ||
          list.find((x) => x.mode === "buggy")?.id ||
          list.find((r) => !r.id.startsWith("int-"))?.id ||
          list[0]?.id ||
          "",
      );
    } finally {
      setCatalogueLoading(false);
    }
  }, []);
  useEffect(() => {
    // A direct record link does not need to enumerate or verify all history.
    // The record/repository navigation already requests the catalogue on demand.
    if (!runId || view === "records" || view === "repositories")
      refreshList().catch((e) => setError(e.message));
    request<Project[]>("/api/projects")
      .then(setProjects)
      .catch((e) => setError(e.message));
  }, [refreshList]);
  useEffect(() => {
    let active = true;
    request<SourceContext>("/api/target?mode=" + mode)
      .then((data) => {
        if (active) setTarget(data);
      })
      .catch((e) => {
        if (active) setError(e.message);
      });
    return () => {
      active = false;
    };
  }, [mode, newRun]);
  useEffect(() => {
    if (!runId || view !== "run") return;
    const controller = new AbortController();
    let active = true,
      timer: ReturnType<typeof setTimeout>;
    const load = async () => {
      try {
        const data = await request<Run>(
          "/api/runs/" +
            runId +
            `?offset=${findingPage.offset}&state=${findingPage.state}&finding=${encodeURIComponent(findingId)}&q=${encodeURIComponent(findingPage.query)}`,
          { signal: controller.signal },
        );
        if (!active) return;
        setRun(data);
        setError("");
        if (lastRun.current !== runId) {
          const initial = !lastRun.current;
          lastRun.current = runId;
          setArtifactId((current) =>
            initial && data.artifacts.some((a) => a.id === current)
              ? current
              : "",
          );
          if (!initial) setEvidenceScope("run");
          setFindingId((current) =>
            data.findings.some((f) => f.id === current)
              ? current
              : data.findings.find((f) => f.criterion_id === "SEC-IDOR")?.id ||
                data.findings[0]?.id ||
                "",
          );
        }
        if (["queued", "running"].includes(data.status))
          timer = setTimeout(load, 1000);
      } catch (e) {
        if (active) setError((e as Error).message);
      }
    };
    load();
    return () => {
      active = false;
      clearTimeout(timer);
      controller.abort();
    };
  }, [runId, refreshList, findingPage, view]);
  useEffect(() => {
    const p = new URLSearchParams();
    if (view !== "run") p.set("view", view);
    if (repositoryId && view === "repositories")
      p.set("repository", repositoryId);
    if (runId) p.set("run", runId);
    p.set(
      "tab",
      view === "integrations"
        ? new URLSearchParams(location.search).get("tab") || tab
        : tab,
    );
    if (findingId) p.set("finding", findingId);
    p.set("evidence", evidenceScope);
    if (artifactId) p.set("artifact", artifactId);
    window.history.replaceState(null, "", "?" + p);
  }, [view, repositoryId, runId, tab, findingId, evidenceScope, artifactId]);
  const finding =
    run?.findings.find((f) => f.id === findingId) || run?.findings[0];
  const busy = starting || ["running", "queued"].includes(run?.status || "");
  const goEvidence = (id: string) => {
    setView("run");
    if (id) setFindingId(id);
    setEvidenceScope(id ? "finding" : "run");
    setArtifactId("");
    setTab("evidence");
  };
  const goResultEvidence = (criterionId: string) => {
    const result = run?.results.find((r) => r.criterion_id === criterionId);
    const observed = run?.findings.find((f) => f.criterion_id === criterionId);
    goEvidence(observed?.id || "");
    const detail = run?.inspections[criterionId];
    const preferred = [
      detail?.source_report,
      detail?.primary_ref,
      ...(result?.evidence_refs || []),
    ].find((id) => id && run?.artifacts.some((a) => a.id === id));
    setArtifactId(preferred || "");
  };
  const start = async () => {
    setStarting(true);
    setError("");
    try {
      const r = await request<{ id: string }>("/api/runs", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(projectId ? { project_id: projectId } : { mode }),
      });
      setRun(null);
      setRunId(r.id);
      setNewRun(false);
      setTab("flow");
      setView("run");
      setPhase(-1);
      await refreshList();
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setStarting(false);
    }
  };
  const openRun = (id: string, nextTab: Tab = "flow") => {
    if (id !== runId) {
      setRun(null);
      setRunId(id);
      setPhase(-1);
      setFindingId("");
      setFindingPage({ offset: 0, state: "active", query: "" });
    }
    setArtifactId("");
    setEvidenceScope("run");
    setTab(nextTab);
    setView("run");
  };
  return (
    <div className="app-shell console-v3 console-v4 focus-workbench">
      <header className="global-nav">
        <button
          className="console-brand"
          aria-label="打开验收工作台"
          onClick={() => {
            setView("run");
            setTab("flow");
          }}
        >
          <Cube size={23} />
          <span>验收工作台</span>
        </button>
        <nav aria-label="主导航">
          <button
            aria-label="验收记录"
            className={view === "run" || view === "records" ? "active" : ""}
            onClick={() => {
              setView("records");
              refreshList().catch((e) => setError(e.message));
            }}
          >
            <ClockCounterClockwise size={17} />
            验收记录
          </button>
          <button
            aria-label="代码仓库"
            className={view === "repositories" ? "active" : ""}
            onClick={() => {
              setView("repositories");
              refreshList().catch((e) => setError(e.message));
            }}
          >
            <FolderSimple size={17} />
            代码仓库
          </button>
          <button
            aria-label="接入与引擎"
            className={view === "integrations" ? "active" : ""}
            onClick={() => setView("integrations")}
          >
            <ShieldCheck size={17} />
            接入与引擎
          </button>
          <a
            aria-label="文档"
            href="https://knowledge.110-lab.cn/p/m4OHJGqujs"
            target="_blank"
            rel="noreferrer"
          >
            <BookOpenText size={17} />
            文档
          </a>
        </nav>
        <div className="local-workspace">
          <FolderSimple size={18} />
          本地工作区
        </div>
      </header>
      <div className="workspace">
        {view === "run" && (
          <>
            <div className="run-breadcrumb">
              <button onClick={() => setView("records")}>验收记录</button>
              <span>/</span>
              <button
                onClick={() => {
                  if (run) {
                    setRepositoryId(run.source.repository.id);
                    setView("repositories");
                  }
                }}
              >
                {run?.source.repository.name || "验收目标"}
              </button>
            </div>
            <div className="run-context">
              <div className="context-title">
                <div className="run-title-line">
                  <h1>
                    {run?.source.repository.name ||
                      run?.label ||
                      "正在读取验收记录"}
                  </h1>
                  {run && tab !== "flow" && (
                    <strong
                      className={
                        "decision " + (busy ? "running" : run.decision)
                      }
                    >
                      {busy
                        ? "执行中"
                        : run.status === "incomplete"
                          ? "验收未完成"
                          : labels[run.decision]}
                    </strong>
                  )}
                </div>

                {run &&
                  !busy &&
                  run.applicability &&
                  !run.applicability.matches && (
                    <p className="run-context-warning">
                      {run.applicability.reason}
                    </p>
                  )}
              </div>
              <div className="actions">
                <a
                  className={"button outline " + (!run ? "disabled" : "")}
                  href={run ? `/api/runs/${run.id}/report` : "#"}
                  download
                >
                  <DownloadSimple size={18} />
                  导出报告
                </a>
                <details className="run-action-menu">
                  <summary aria-label="更多验收操作">
                    <DotsThree size={22} />
                  </summary>
                  <div>
                    <button onClick={openNewRun} disabled={busy || !run}>
                      <ArrowCounterClockwise size={16} />
                      {busy ? "验证中" : "重新验证"}
                    </button>
                    <button onClick={() => setTargetInfo(true)} disabled={!run}>
                      <FolderSimple size={16} />
                      查看目标与范围
                    </button>
                  </div>
                </details>
              </div>
            </div>
            {run && (
              <TargetStrip
                source={run.source}
                baseline={run.baseline.version}
                details={() => setTargetInfo(true)}
                repository={() => {
                  setRepositoryId(run.source.repository.id);
                  setView("repositories");
                }}
              />
            )}
            {run?.job?.recovery_error && (
              <div className="error-banner" role="alert">
                <WarningCircle />
                <span>
                  任务中断，资源清理尚未完成：{run.job.recovery_error}
                </span>
                <a
                  href={`/api/jobs/${run.job.id}/events`}
                  target="_blank"
                  rel="noreferrer"
                >
                  恢复记录
                </a>
              </div>
            )}
            {run?.job?.state === "interrupted" && (
              <p className="run-context-warning">
                本次尝试已中断，未自动重跑。
                <a
                  href={`/api/jobs/${run.job.id}/events`}
                  target="_blank"
                  rel="noreferrer"
                >
                  查看恢复记录
                </a>
              </p>
            )}
            <nav className="tabs" role="tablist" aria-label="验收详情">
              {tabs.map((t) => (
                <button
                  key={t.id}
                  role="tab"
                  id={"tab-" + t.id}
                  aria-controls={"panel-" + t.id}
                  aria-selected={tab === t.id}
                  tabIndex={tab === t.id ? 0 : -1}
                  className={tab === t.id ? "selected" : ""}
                  onClick={() => setTab(t.id)}
                  onKeyDown={(e) => {
                    if (["ArrowRight", "ArrowLeft"].includes(e.key)) {
                      e.preventDefault();
                      const i = tabs.findIndex((x) => x.id === t.id),
                        next = tabs[(i + (e.key === "ArrowRight" ? 1 : 2)) % 3];
                      setTab(next.id);
                      document.getElementById("tab-" + next.id)?.focus();
                    }
                  }}
                >
                  {t.title}
                </button>
              ))}
            </nav>
          </>
        )}
        {error && (
          <div className="error-banner" role="alert">
            <WarningCircle />
            {error}
            <button
              onClick={() => {
                location.reload();
              }}
            >
              重试
            </button>
          </div>
        )}
        {view === "integrations" ? (
          <Integrations
            onOpenRun={openRun}
            initialTab={params.get("tab") === "plan" ? "plan" : tab}
            onDesign={(plan) => {
              setDesignSeed(plan);
              setTestDesign(true);
            }}
          />
        ) : view !== "run" ? (
          <main className="catalogue-content">
            {catalogueLoading ? (
              <div className="empty" role="status">
                <SpinnerGap className="spin" size={26} />
                <p>正在读取仓库与验收记录</p>
              </div>
            ) : (
              <Catalogue
                kind={view}
                runs={runs}
                target={target}
                selectedRepository={repositoryId}
                selectRepository={setRepositoryId}
                openRun={openRun}
                start={openNewRun}
                currentRunId={runId}
              />
            )}
          </main>
        ) : (
          <>
            <main
              id={"panel-" + tab}
              role="tabpanel"
              aria-labelledby={"tab-" + tab}
              className="content"
            >
              {!run ? (
                <div className="empty" role="status">
                  {(runId || catalogueLoading) && !error && (
                    <div className="loading-lines" aria-hidden="true">
                      <i />
                      <i />
                      <i />
                    </div>
                  )}
                  <h3>
                    {error
                      ? "验收记录暂时无法读取"
                      : runId || catalogueLoading
                        ? "正在读取执行记录"
                        : "还没有验收执行"}
                  </h3>
                  {!runId && !catalogueLoading && !error && (
                    <button className="button primary" onClick={openNewRun}>
                      开始本地验证
                    </button>
                  )}
                </div>
              ) : (
                <>
                  {tab === "flow" && (
                    <Flow
                      summary={<RunSummary run={run} busy={busy} />}
                      run={run}
                      phase={phase}
                      setPhase={setPhase}
                      busy={busy}
                      setTab={setTab}
                      showResultEvidence={goResultEvidence}
                      openArtifact={(id) => {
                        goEvidence("");
                        setArtifactId(id);
                      }}
                      goEvidence={goEvidence}
                      showFinding={(id) => {
                        setFindingId(id);
                        setTab("findings");
                      }}
                    />
                  )}
                  {tab === "findings" && (
                    <Findings
                      page={(offset, state, query = "") => {
                        setFindingId("");
                        setFindingPage({ offset, state, query });
                      }}
                      run={run}
                      finding={finding}
                      select={(id) => {
                        setFindingId(id);
                        setArtifactId("");
                      }}
                      goEvidence={goEvidence}
                      showStandards={() => {
                        setTab("flow");
                        setPhase(0);
                      }}
                    />
                  )}
                  {tab === "evidence" && (
                    <Evidence
                      run={run}
                      showFinding={(id) => {
                        setFindingId(id);
                        setTab("findings");
                      }}
                      finding={
                        evidenceScope === "finding" ? finding : undefined
                      }
                      chooseScope={goEvidence}
                      artifactId={artifactId}
                      setArtifactId={setArtifactId}
                      back={() => {
                        setTab(
                          evidenceScope === "finding" ? "findings" : "flow",
                        );
                        if (evidenceScope === "run" && run)
                          setPhase(
                            pipeline(run).findIndex((s) => s.id === "gate"),
                          );
                      }}
                      notify={notify}
                    />
                  )}
                </>
              )}
            </main>
            {run && (
              <footer className="workspace-footer">
                <button
                  className="text-button muted"
                  onClick={() => setView("records")}
                >
                  <ClockCounterClockwise size={15} />
                  {run.id}
                </button>
                <span>
                  {new Date(run.created_at).toLocaleString("zh-CN", {
                    hour12: false,
                  })}
                </span>
              </footer>
            )}
          </>
        )}
      </div>
      {toast && (
        <div className="toast" role="status">
          {toast}
        </div>
      )}
      {newRun && (
        <Modal title="开始新的验收" close={() => setNewRun(false)}>
          <button
            className="button primary local-entry"
            onClick={() => {
              setNewRun(false);
              setDesignSeed(null);
              setTestDesign(true);
            }}
          >
            设计验收用例
          </button>
          <button
            className="button outline local-entry"
            onClick={() => {
              setNewRun(false);
              setLocalRepository(true);
            }}
          >
            <FolderSimple size={17} />
            验收其他本地仓库
          </button>
          <label className="form-label" htmlFor="target-project">
            验收对象
          </label>
          <select
            id="target-project"
            value={projectId}
            onChange={(e) => setProjectId(e.target.value)}
          >
            {projects.map((p) => (
              <option key={p.id} value={p.id}>
                {p.name}
              </option>
            ))}
            <option value="">本地演示项目</option>
          </select>
          <div className="new-run-target">
            <strong>
              <FolderSimple size={16} />{" "}
              {project?.name || target?.repository.name || "读取当前目标…"}
            </strong>
            <small>{project?.repository || target?.repository.path}</small>
            <p>
              {project
                ? project.version
                : `${target?.repository.branch || "分支未采集"} · ${target?.repository.commit?.slice(0, 10) || "本地文件快照"}`}
            </p>
            <small>
              {project
                ? `${project.check_count} 项标准 · ${project.scope || "所选业务规则回归"}`
                : "本地示例的两个目标文件，8 项检查。"}
            </small>
          </div>
          {!project && (
            <>
              <label className="form-label" htmlFor="target-mode">
                待验版本
              </label>
              <select
                id="target-mode"
                value={mode}
                onChange={(e) => setMode(e.target.value as "buggy" | "fixed")}
              >
                <option value="fixed">修正版</option>
                <option value="buggy">缺陷版</option>
              </select>
            </>
          )}
          <p className="muted small-text">
            结果仅适用于本次冻结的文件与验收范围。
          </p>
          <button className="button primary" onClick={start} disabled={busy}>
            {starting ? <SpinnerGap className="spin" /> : <PlayCircle />}
            开始验证
          </button>
        </Modal>
      )}
      {localRepository && (
        <LocalRepository
          frozenDesignRun={
            run?.status === "completed" &&
            run.universal_plan &&
            !run.universal_plan.frozen_design_run &&
            Array.isArray(run.universal_plan.batches) &&
            run.universal_plan.batches.length > 0 &&
            run.universal_plan.batches.every(
              (b: any) => b.state === "completed",
            )
              ? run.id
              : ""
          }
          initialPath={run?.source.repository.path || ""}
          initialRemote={run?.source.repository.remote || ""}
          initialCommit={run?.source.repository.commit || ""}
          initialRefType={run?.source.repository.requested_kind || "branch"}
          initialReference={
            run?.source.repository.requested_ref ||
            run?.source.repository.branch ||
            ""
          }
          close={() => setLocalRepository(false)}
          started={(id) => {
            openRun(id);
            refreshList().catch((e) => setError(e.message));
            setLocalRepository(false);
          }}
        />
      )}
      {testDesign && (
        <TestDesign
          initial={designSeed}
          close={() => setTestDesign(false)}
          started={(id) => {
            openRun(id);
            setTestDesign(false);
            refreshList().catch((e) => setError(e.message));
          }}
        />
      )}
      {targetInfo && run && (
        <Modal title="本次验收目标" close={() => setTargetInfo(false)}>
          <SourceDetails source={run.source} />
          {!run.source_artifact &&
            run.artifacts.some((a) => a.name === "source-manifest.json") && (
              <a
                className="button outline"
                href={`/api/runs/${run.id}/artifacts/${run.artifacts.find((a) => a.name === "source-manifest.json")!.id}?download=true`}
                download
              >
                下载完整文件清单
              </a>
            )}
          {run.source_artifact && (
            <a
              className="button outline"
              href={`/api/runs/${run.id}/artifacts/${run.source_artifact}?download=true`}
              download
            >
              <DownloadSimple size={16} />
              下载目标快照
            </a>
          )}
        </Modal>
      )}
    </div>
  );
}

function RunSummary({ run, busy }: { run: Run; busy: boolean }) {
  const [clock, setClock] = useState(Date.now());
  useEffect(() => {
    if (!busy) return;
    const timer = setInterval(() => setClock(Date.now()), 500);
    return () => clearInterval(timer);
  }, [busy]);
  const { ended, total, passed, failed, uncertain, unfinished } =
    executionSummary(run);
  return (
    <div className="run-summary" aria-label="验收结果摘要">
      <span>
        {ended} / {total} 检查已结束
      </span>
      <span className="summary-passed">{passed} 通过</span>
      <span className="summary-failed">{failed} 未通过</span>
      {run.completion &&
        ["full", "recipe"].includes(run.completion.kind) &&
        !busy &&
        !run.completion.complete && (
          <span>{run.completion.missing.length} 个必验步骤未完成</span>
        )}
      {uncertain > 0 && <span>{uncertain} 异常或未判定</span>}
      {unfinished > 0 && <span>{unfinished} 未结束</span>}
      <span>
        总历时{" "}
        <time>{seconds(elapsed(run.created_at, run.finished_at, clock))}</time>
      </span>
    </div>
  );
}
