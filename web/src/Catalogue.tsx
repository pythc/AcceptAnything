import { useEffect, useState } from "react";
import {
  ArrowRight,
  FolderSimple,
  MagnifyingGlass,
  Plus,
  FileText,
  ClockCounterClockwise,
} from "@phosphor-icons/react";
import type { Repository, RunBrief, SourceContext, Tab } from "./types";
import { labels } from "./ui";
import { SourceDetails, revision } from "./SourceContext";
import { useCatalogue } from "./useCatalogue";

const recordedDecision = (r: RunBrief) => r.recorded_decision || r.decision;
const findingCount = (r: RunBrief) => r.findings_count == null ? "发现数待核对" : `${r.findings_count} 条待处理发现`;

export function Catalogue({
  kind,
  runs: initialRuns,
  target,
  selectedRepository,
  selectRepository,
  openRun,
  start,
  currentRunId,
}: {
  kind: "records" | "repositories";
  runs: RunBrief[];
  target: SourceContext | null;
  selectedRepository: string;
  selectRepository: (id: string) => void;
  openRun: (id: string, tab?: Tab) => void;
  start: () => void;
  currentRunId: string;
}) {
  const [query, setQuery] = useState(""),
    [selectedRun, setSelectedRun] = useState(currentRunId || initialRuns[0]?.id || ""),
    [repoTab, setRepoTab] = useState("overview");
  const changed = initialRuns.map(r => `${r.id}:${r.status}:${r.finished_at}`).join("|");
  const page = useCatalogue(kind, query, "", changed);
  const { runs, repositories } = page;
  const [selectedBrief, setSelectedBrief] = useState<RunBrief | null>(null);
  useEffect(() => {
    setSelectedBrief(null);
    if (kind !== "records" || !selectedRun || query) return;
    const controller = new AbortController();
    fetch(`/api/catalogue/records/${encodeURIComponent(selectedRun)}`, { signal: controller.signal })
      .then(r => r.ok ? r.json() : null)
      .then(data => { if (!controller.signal.aborted) setSelectedBrief(data); })
      .catch(() => {});
    return () => controller.abort();
  }, [selectedRun, kind, query, changed]);
  useEffect(() => setQuery(""), [kind]);
  useEffect(() => {
    if (currentRunId) setSelectedRun(currentRunId);
  }, [currentRunId]);
  const groups =
    !query && !page.loading && !page.has_more && target && !repositories.some((r) => r.id === target.repository.id)
      ? [
          {
            id: target.repository.id,
            repository: target.repository,
            run_count: 0,
            latest: null,
          },
          ...repositories,
        ]
      : repositories;
  const repo = groups.find((r) => r.id === selectedRepository) || groups[0];
  const selected = runs.find((r) => r.id === selectedRun) || (!query ? selectedBrief : null) || runs[0];
  const list =
    kind === "records"
      ? runs : groups;
  const current =
    repo?.latest?.source ||
    (repo && target?.repository.id === repo.id ? target : undefined);
  const repoPage = useCatalogue("records", "", repo?.id || "", changed, kind === "repositories" && repoTab === "runs" && !!repo);
  const repoRuns = repoPage.runs;
  return (
    <div className="catalogue">
      <aside className="catalogue-index">
        <div className="catalogue-index-title">
          <h2>{kind === "records" ? "验收记录" : "代码仓库"}</h2>
          <button className="button outline" onClick={start}>
            <Plus size={15} />
            新建验收
          </button>
        </div>
        <label className="catalogue-search">
          <MagnifyingGlass size={17} />
          <input
            aria-label={kind === "records" ? "搜索验收记录" : "搜索代码仓库"}
            placeholder={
              kind === "records" ? "搜索仓库、版本或执行 ID" : "搜索名称或目录"
            }
            value={query}
            onChange={(e) => setQuery(e.target.value)}
          />
        </label>
        <div className="catalogue-list">
          {kind === "records"
            ? (list as RunBrief[]).map((r) => (
                <button
                  key={r.id}
                  className={
                    "catalogue-row " + (selected?.id === r.id ? "selected" : "")
                  }
                  aria-pressed={selected?.id === r.id}
                  onClick={() => setSelectedRun(r.id)}
                >
                  <div>
                    <strong>
                      {r.label.startsWith(r.source.repository.name)
                        ? r.label
                        : `${r.source.repository.name} · ${r.label}`}
                    </strong>
                    <span className={"result-text " + recordedDecision(r)}>
                      {["running", "queued", "incomplete"].includes(r.status)
                        ? labels[r.status]
                        : `当时${labels[recordedDecision(r)] || recordedDecision(r)}`}
                    </span>
                  </div>
                  <small>{r.source.repository.path || "未采集目录"}</small>
                  <div className="catalogue-row-meta">
                    <code>{r.id}</code>
                    <span>
                      {findingCount(r)} ·{" "}
                      {r.created_at
                        ? new Date(r.created_at).toLocaleDateString("zh-CN")
                        : "时间无法核实"}
                    </span>
                  </div>
                </button>
              ))
            : (list as Repository[]).map((r) => (
                <button
                  key={r.id}
                  className={
                    "catalogue-row " + (repo?.id === r.id ? "selected" : "")
                  }
                  aria-pressed={repo?.id === r.id}
                  onClick={() => {
                    selectRepository(r.id);
                    setRepoTab("overview");
                  }}
                >
                  <div>
                    <strong>
                      <FolderSimple size={17} /> {r.repository.name}
                    </strong>
                    <span>{r.run_count} 次验收</span>
                  </div>
                  <small>{r.repository.path}</small>
                  <div className="catalogue-row-meta">
                    <span>最近结果</span>
                    <span
                      className={"result-text " + (r.latest ? recordedDecision(r.latest) : "")}
                    >
                      {r.latest ? `当时${labels[recordedDecision(r.latest)] || recordedDecision(r.latest)}` : "尚未验收"}
                    </span>
                  </div>
                </button>
              ))}
          {!list.length && !page.loading && !page.error && (
            <p className="catalogue-empty">
              没有匹配的{kind === "records" ? "验收记录" : "代码仓库"}
            </p>
          )}
        </div>
        <div className="catalogue-pagination">
          <span aria-live="polite">{page.loading ? "正在读取…" : `已显示 ${kind === "records" ? runs.length : repositories.length} / ${page.total}`}</span>
          {page.has_more && <button className="button outline" disabled={page.loading} onClick={() => void page.loadMore()}>加载更多</button>}
          {page.error && <><p role="alert">{page.error}</p><button className="button outline" onClick={() => void page.retry()}>重试</button></>}
          {page.index_status?.state === "error" && <p role="status">{page.index_status.message}</p>}
        </div>
      </aside>
      <section className="catalogue-detail">
        {kind === "records" && selected ? (
          selected.record_error ? (
            <>
              <h2>记录无法读取</h2>
              <p>{selected.record_error}</p>
              <code>{selected.id}</code>
            </>
          ) : (
            <>
              <div className="catalogue-detail-heading">
                <div>
                  <span className="eyebrow">验收记录</span>
                  <h2>
                    {selected.label.startsWith(selected.source.repository.name)
                      ? selected.label
                      : `${selected.source.repository.name} · ${selected.label}`}
                  </h2>
                </div>
                <button
                  className="button primary"
                  onClick={() => openRun(selected.id)}
                >
                  打开验收 <ArrowRight size={16} />
                </button>
              </div>
              <p className="catalogue-subtitle">{selected.id}</p>
              <dl className="context-fields record-overview">
                <dt>执行状态</dt>
                <dd>
                  {labels[selected.status] ||
                    (selected.status === "completed"
                      ? "已完成"
                      : selected.status)}{" "}
                  ·{" "}
                  <span className={"result-text " + recordedDecision(selected)}>
                    当时{labels[recordedDecision(selected)] || recordedDecision(selected)}
                  </span>
                </dd>
                <dt>原件核验</dt>
                <dd>打开详情时重新核验{selected.verification?.last_verified_at ? `；上次核验${selected.verification.last_valid ? "通过" : "未通过"}：${new Date(selected.verification.last_verified_at).toLocaleString("zh-CN")}` : ""}</dd>
                <dt>目录</dt>
                <dd>{selected.source.repository.path || "未采集"}</dd>
                <dt>分支 / 提交</dt>
                <dd>
                  {selected.source.repository.branch || "未采集"} ·{" "}
                  {revision(selected.source)}
                </dd>
                <dt>验收范围</dt>
                <dd>{selected.source.scope.description}</dd>
                <dt>检查 / 缺陷</dt>
                <dd>
                  {selected.check_count == null ? "检查数待核对" : `${selected.check_count} 项结果`} / {findingCount(selected)}
                </dd>
                <dt>基线</dt>
                <dd>{selected.baseline_version}</dd>
                <dt>开始时间</dt>
                <dd>
                  {new Date(selected.created_at).toLocaleString("zh-CN", {
                    hour12: false,
                  })}
                </dd>
                <dt>结束时间</dt>
                <dd>
                  {selected.finished_at
                    ? new Date(selected.finished_at).toLocaleString("zh-CN", {
                        hour12: false,
                      })
                    : "尚未结束"}
                </dd>
              </dl>
              <h3 className="catalogue-section-title">本次产物</h3>
              <div className="catalogue-artifacts">
                <button onClick={() => openRun(selected.id, "evidence")}>
                  <FileText /> {selected.artifact_count == null ? "查看证据文件" : `${selected.artifact_count} 个证据文件`}{" "}
                  <ArrowRight />
                </button>
                <a
                  href={
                    selected.report_url || `/api/runs/${selected.id}/report`
                  }
                  download
                >
                  <FileText /> Markdown 验收报告 <ArrowRight />
                </a>
              </div>
              <p className="context-note">
                {selected.source.provenance === "historical"
                  ? "此历史记录未采集 Git 元数据，打开后可核对原始结果与文件。"
                  : `本次文件快照 ${selected.source.snapshot.digest.slice(0, 16)}`}
              </p>
            </>
          )
        ) : kind === "repositories" && repo && current ? (
          <>
            <div className="catalogue-detail-heading">
              <div>
                <span className="eyebrow">代码仓库</span>
                <h2>{repo.repository.name}</h2>
              </div>
              <button className="button outline" onClick={start}>
                <Plus size={16} />
                新建验收
              </button>
            </div>
            <div className="repository-tabs">
              <button
                className={repoTab === "overview" ? "selected" : ""}
                aria-pressed={repoTab === "overview"}
                onClick={() => setRepoTab("overview")}
              >
                概览
              </button>
              <button
                className={repoTab === "runs" ? "selected" : ""}
                aria-pressed={repoTab === "runs"}
                onClick={() => setRepoTab("runs")}
              >
                验收记录 {repo.run_count}
              </button>
            </div>
            {repoTab === "overview" ? (
              <>
                <div className="repository-stats">
                  <div>
                    <span>验收次数</span>
                    <strong>{repo.run_count}</strong>
                  </div>
                  <div>
                    <span>最近待处理发现</span>
                    <strong>{repo.latest?.findings_count ?? "—"}</strong>
                  </div>
                  <div>
                    <span>
                      {repo.latest ? "最近验收源文件" : "当前目标源文件"}
                    </span>
                    <strong>{(current.scope.file_count ?? current.scope.files.length) || "未采集"}</strong>
                  </div>
                </div>
                <h3 className="repo-source-heading">
                  {repo.latest ? "最近验收快照" : "当前目录配置"}
                </h3>
                <SourceDetails source={current} current={current === target} />
                <h3 className="catalogue-section-title">最近验收</h3>
                {repo.latest ? (
                  <button
                    className="repo-recent"
                    onClick={() => openRun(repo.latest!.id)}
                  >
                    <ClockCounterClockwise />
                    <span>
                      <strong>{repo.latest.label}</strong>
                      <small>
                        {repo.latest.id} ·{" "}
                        {new Date(repo.latest.created_at).toLocaleString(
                          "zh-CN",
                        )}
                      </small>
                    </span>
                    <span className={"result-text " + recordedDecision(repo.latest)}>
                      当时{labels[recordedDecision(repo.latest)] || recordedDecision(repo.latest)}
                    </span>
                    <ArrowRight />
                  </button>
                ) : (
                  <p className="muted">尚未验收</p>
                )}
              </>
            ) : (
              <div className="repository-runs">
                {repoRuns.map((r) => (
                  <button
                    key={r.id}
                    className="repo-recent"
                    onClick={() => openRun(r.id)}
                  >
                    <ClockCounterClockwise />
                    <span>
                      <strong>
                        {r.label} · {revision(r.source)}
                      </strong>
                      <small>
                        {r.id} ·{" "}
                        {new Date(r.created_at).toLocaleString("zh-CN")}
                      </small>
                    </span>
                    <span className={"result-text " + recordedDecision(r)}>
                      当时{labels[recordedDecision(r)] || recordedDecision(r)}
                    </span>
                    <ArrowRight />
                  </button>
                ))}
                <div className="catalogue-pagination">
                  <span aria-live="polite">{repoPage.loading ? "正在读取…" : `已显示 ${repoRuns.length} / ${repoPage.total}`}</span>
                  {repoPage.has_more && <button className="button outline" disabled={repoPage.loading} onClick={() => void repoPage.loadMore()}>更多验收记录</button>}
                  {repoPage.error && <><p role="alert">{repoPage.error}</p><button className="button outline" onClick={() => void repoPage.retry()}>重试</button></>}
                </div>
              </div>
            )}
          </>
        ) : (
          <div className="empty">
            <FolderSimple size={30} />
            <p>还没有可查看的记录</p>
          </div>
        )}
      </section>
    </div>
  );
}
