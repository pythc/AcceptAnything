import { useState } from "react";
import {
  FolderSimple,
  SpinnerGap,
  PlayCircle,
  GitBranch,
} from "@phosphor-icons/react";
import { Modal } from "./ui";
import { AutomaticPlanDetails } from "./AutomaticPlanDetails";
import { CitationAdjustments } from "./CitationAdjustments";
import { UniversalPlanDetails } from "./UniversalPlanDetails";
import {
  basisSelection,
  recommendedBasis,
  readableApiError,
  defaultBasisLimits,
  type BasisLimits,
  type BasisCandidate,
} from "./basisSelection";
type Plan = {
  id: string;
  kind?: string;
  digest: string;
  repository: string;
  scope: string;
  file_count: number;
  check_count: number;
  ready: boolean;
  stages: { id: string; title: string }[];
  blockers: string[];
  documents: string[];
  exclusions: { subject: string; reason: string }[];
  detection?: {
    stacks: { name: string; manifest: string }[];
    adapter: string | null;
    entrypoints: string[];
    document_candidates: BasisCandidate[];
    basis_limits?: BasisLimits;
  };
  specification?: Record<string, any>;
  planner?: Record<string, any>;
  universal?: Record<string,any>;
  remote_source?: {
    url: string;
    branch: string | null;
    commit: string;
    requested_kind: string;
    requested_ref: string;
    duration_ms: number;
  };
};
type RemoteRefs = {
  default_branch: string;
  branches: { name: string; commit: string }[];
  truncated: boolean;
};
async function post<T>(path: string, body: object): Promise<T> {
  const r = await fetch("/api/acceptance/" + path, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
  if (!r.ok) throw Error(readableApiError(await r.text()));
  return r.json();
}
export function LocalRepository({
  close,
  started,
  initialPath = "",
  initialRemote = "",
  initialCommit = "",
  initialRefType = "branch",
  initialReference = "",
  frozenDesignRun = "",
}: {
  close: () => void;
  started: (id: string) => void;
  initialPath?: string;
  initialRemote?: string;
  initialCommit?: string;
  initialRefType?: "branch" | "commit";
  initialReference?: string;
  frozenDesignRun?: string;
}) {
  const [useFrozen,setUseFrozen]=useState(false);
  const [path, setPath] = useState(initialPath),
    [source, setSource] = useState(initialRemote ? "remote" : "local"),
    [url, setUrl] = useState(initialRemote),
    [refType, setRefType] = useState<string>(initialRefType),
    [ref, setRef] = useState(initialReference),
    [references, setReferences] = useState<RemoteRefs | null>(null),
    [configuration, setConfiguration] = useState(""),
    [plan, setPlan] = useState<Plan | null>(null),
    [busy, setBusy] = useState(false),
    [error, setError] = useState("");
  const [documents, setDocuments] = useState<string[]>([]),
    [requirements, setRequirements] = useState(""),
    [scope, setScope] = useState(""),
    [reviewed, setReviewed] = useState(false);
  const limits = plan?.detection?.basis_limits || defaultBasisLimits;
  const candidates = plan?.detection?.document_candidates || [];
  const selection = basisSelection(candidates, documents, requirements, limits);
  function invalidate() {
    setPlan(null);
    setDocuments([]);
    setRequirements("");
    setScope("");
    setReviewed(false);
    setError("");
  }
  async function work(fn: () => Promise<void>) {
    setBusy(true);
    setError("");
    try {
      await fn();
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setBusy(false);
    }
  }
  return (
    <Modal title="新建验收" close={close}>
      <div className="local-repository-form">
        <div
          className="repository-source-switch"
          role="group"
          aria-label="仓库来源"
        >
          <button
            type="button"
            disabled={busy}
            aria-pressed={!useFrozen && source === "local"}
            onClick={() => {
              setUseFrozen(false);
              setSource("local");
              invalidate();
              setError("");
            }}
          >
            本地路径
          </button>
          <button
            type="button"
            disabled={busy}
            aria-pressed={!useFrozen && source === "remote"}
            onClick={() => {
              setUseFrozen(false);
              setSource("remote");
              invalidate();
              setError("");
            }}
          >
            远程仓库
          </button>
          {frozenDesignRun&&<button type="button" disabled={busy} aria-pressed={useFrozen} onClick={()=>{setUseFrozen(true);invalidate();setError("");}}>沿用冻结设计</button>}
        </div>
        {useFrozen ? <p>沿用记录 <code>{frozenDesignRun}</code> 的独立标准和模型原件，重新校验并执行全部检查。源码发生变化时会拒绝复用。</p> : source === "local" ? (
          <>
            <label className="form-label" htmlFor="local-repository-path">
              <FolderSimple size={16} />
              本地仓库
            </label>
            <input
              id="local-repository-path"
              placeholder="/Users/alex/projects/my-project"
              value={path}
              disabled={busy}
              onChange={(e) => {
                setPath(e.target.value);
                invalidate();
              }}
            />
          </>
        ) : (
          <>
            <label className="form-label" htmlFor="remote-repository-url">
              <GitBranch size={16} />
              GitHub / GitLab 仓库
            </label>
            <div className="remote-url-row">
              <input
                id="remote-repository-url"
                placeholder="https://github.com/owner/repository"
                value={url}
                disabled={busy}
                onChange={(e) => {
                  setUrl(e.target.value);
                  setReferences(null);
                  setRef("");
                  invalidate();
                  setError("");
                }}
              />
              <button
                className="button"
                disabled={busy || !url.trim()}
                onClick={() =>
                  work(async () => {
                    const r = await post<RemoteRefs>("remote/refs", {
                      url: url.trim(),
                    });
                    setReferences(r);
                    setRef(r.default_branch);
                    setRefType("branch");
                    invalidate();
                  })
                }
              >
                读取分支
              </button>
            </div>
            <div className="remote-ref-row">
              <label className="form-label" htmlFor="remote-ref-type">
                版本类型
                <select
                  id="remote-ref-type"
                  disabled={busy}
                  value={refType}
                  onChange={(e) => {
                    setRefType(e.target.value);
                    setRef(
                      e.target.value === "branch"
                        ? references?.default_branch || ""
                        : initialCommit,
                    );
                    invalidate();
                  }}
                >
                  <option value="branch">分支</option>
                  <option value="commit">提交 SHA</option>
                </select>
              </label>
              <label className="form-label" htmlFor="remote-ref">
                {refType === "branch" ? "分支名称" : "完整提交 SHA"}
                <input
                  id="remote-ref"
                  list={refType === "branch" ? "remote-branches" : undefined}
                  value={ref}
                  disabled={busy}
                  placeholder={
                    refType === "branch" ? "留空使用默认分支" : "40位提交 SHA"
                  }
                  onChange={(e) => {
                    setRef(e.target.value);
                    invalidate();
                  }}
                />
              </label>
            </div>
            <datalist id="remote-branches">
              {references?.branches.map((b) => (
                <option key={b.name} value={b.name} />
              ))}
            </datalist>
            {references && (
              <p className="muted small-text">
                默认分支 {references.default_branch} · 已读取{" "}
                {references.branches.length} 个分支
                {references.truncated
                  ? "（列表已截取，仍可输入完整分支名）"
                  : ""}
              </p>
            )}
          </>
        )}
        {!useFrozen&&<>
        <label className="form-label" htmlFor="project-configuration">
          项目配置（可选）
        </label>
        <input
          id="project-configuration"
          placeholder="外部配置文件路径；默认读取仓库内 acceptance.project.json"
          value={configuration}
          disabled={busy}
          onChange={(e) => {
            setConfiguration(e.target.value);
            invalidate();
          }}
        />
        <p className="muted small-text">
          {source === "remote"
            ? "拉取到独立工作区，确认后固定提交执行。私有仓库使用服务端配置的凭据。"
            : "源码只读。使用临时容器、合成数据和独立测试数据库。"}
        </p>
        </>}
        {!plan ? (
          <button
            className="button primary"
            disabled={
              busy ||
              (!useFrozen && !(source === "local" ? path.trim() : url.trim())) ||
              (!useFrozen && source === "remote" &&
                refType === "commit" &&
                !/^[a-fA-F0-9]{40}$/.test(ref.trim()))
            }
            onClick={() =>
              work(async () =>
                setPlan(
                  await post<Plan>("plan", useFrozen ? {frozen_design_run:frozenDesignRun} : {
                    ...(source === "local"
                      ? { repository: path.trim() }
                      : {
                          remote_url: url.trim(),
                          ref_type: refType,
                          ref: ref.trim(),
                        }),
                    ...(configuration.trim()
                      ? { configuration: configuration.trim() }
                      : {}),
                  }),
                ),
              )
            }
          >
            {busy ? <SpinnerGap className="spin" /> : <FolderSimple />}
            检查验收准备情况
          </button>
        ) : (
          <>
            {plan.kind==='universal'&&<UniversalPlanDetails plan={plan}/>}
            {plan.remote_source && (
              <div className="remote-resolved" role="status">
                <strong>已固定远程版本</strong>
                <span>{plan.remote_source.url}</span>
                <span>
                  {plan.remote_source.branch || "指定提交"} ·{" "}
                  <code>{plan.remote_source.commit}</code>
                </span>
                <small>
                  拉取 {(plan.remote_source.duration_ms / 1000).toFixed(1)} 秒 ·
                  执行时不重新追踪分支
                </small>
              </div>
            )}
            {plan.detection && (
              <section className="console-disclosure">
                <strong>技术栈识别</strong>
                <details className="console-disclosure">
                  <summary>
                    {[
                      ...new Set(plan.detection.stacks.map((s) => s.name)),
                    ].join(" · ")}{" "}
                    · {plan.detection.stacks.length} 份清单
                  </summary>
                  {plan.detection.stacks.map((s, i) => (
                    <p key={i}>
                      {s.name} <code>{s.manifest}</code>
                    </p>
                  ))}
                </details>
                {plan.detection.entrypoints.length > 0 && (
                  <p>命令行入口：{plan.detection.entrypoints.join("、")}</p>
                )}
                {plan.id.startsWith("intake-") && (
                  <>
                    <p className="muted small-text">
                      每次最多选择 {limits.max_documents} 份独立依据，合计最多{" "}
                      {limits.max_total_characters.toLocaleString()}{" "}
                      字符（含补充需求）。每份读取前{" "}
                      {limits.per_document_characters.toLocaleString()}{" "}
                      字符，原文件摘要会冻结。未选文档不计入本次覆盖。
                    </p>
                    <div
                      className="basis-selection-summary"
                      role="status"
                      aria-live="polite"
                    >
                      <span>
                        已选 {selection.count} / {limits.max_documents} 份 ·{" "}
                        {selection.total.toLocaleString()} /{" "}
                        {limits.max_total_characters.toLocaleString()} 字符
                      </span>
                      <button
                        type="button"
                        className="text-button"
                        disabled={busy || !candidates.length}
                        onClick={() => {
                          setDocuments(
                            recommendedBasis(candidates, requirements, limits),
                          );
                          setError("");
                        }}
                      >
                        按目录选择
                      </button>
                      <button
                        type="button"
                        className="text-button"
                        disabled={busy || !documents.length}
                        onClick={() => setDocuments([])}
                      >
                        清空选择
                      </button>
                    </div>
                    {selection.count >= limits.max_documents && (
                      <p className="muted small-text">
                        已达文档数量上限；取消一份后可选择其他文档。
                      </p>
                    )}
                    <div
                      className="basis-document-list"
                      role="group"
                      aria-label="独立依据文档"
                    >
                      {candidates.map((d) => (
                        <label className="local-option" key={d.path}>
                          <input
                            type="checkbox"
                            disabled={busy || selection.disabled(d)}
                            checked={documents.includes(d.path)}
                            onChange={(e) =>
                              setDocuments(
                                e.target.checked
                                  ? [...documents, d.path]
                                  : documents.filter((x) => x !== d.path),
                              )
                            }
                          />
                          <span>
                            {d.path}
                            <small className="muted">
                              {(
                                d.excerpt_characters ??
                                Math.min(d.size, limits.per_document_characters)
                              ).toLocaleString()}{" "}
                              字符
                              {d.excerpt_characters === undefined
                                ? "（估算）"
                                : ""}
                            </small>
                          </span>
                        </label>
                      ))}
                    </div>
                    <label
                      className="form-label"
                      htmlFor="automatic-requirements"
                    >
                      补充独立需求（可选）
                    </label>
                    <textarea
                      id="automatic-requirements"
                      disabled={busy}
                      value={requirements}
                      onChange={(e) => setRequirements(e.target.value)}
                      placeholder="预期行为、输入输出、权限或错误规则；缺少依据的内容不会猜测"
                      rows={4}
                    />
                    <label className="form-label" htmlFor="automatic-scope">
                      本次验收范围（可选）
                    </label>
                    <input
                      id="automatic-scope"
                      disabled={busy}
                      value={scope}
                      maxLength={2000}
                      onChange={(e) => setScope(e.target.value)}
                      placeholder="默认按文档与已支持的执行方式确定范围"
                    />
                    <button
                      className="button primary"
                      disabled={
                        busy ||
                        !plan.detection.adapter ||
                        !selection.canGenerate
                      }
                      onClick={() =>
                        work(async () => {
                          if (!selection.canGenerate)
                            throw Error(selection.error);
                          const p = await post<Plan>("automatic/design", {
                            intake_id: plan.id,
                            documents,
                            requirements_text: requirements,
                            scope,
                          });
                          setPlan(p);
                          setReviewed(false);
                        })
                      }
                    >
                      {busy ? <SpinnerGap className="spin" /> : null}
                      模型设计中文用例
                    </button>
                    {selection.error &&
                      (documents.length > 0 || requirements.length > 0) && (
                        <p role="alert" className="error-banner">
                          {selection.error}
                        </p>
                      )}
                    {busy && (
                      <p role="status">
                        正在生成方案，请等待实际模型返回；不会自动重试或降级模型。
                      </p>
                    )}
                  </>
                )}
              </section>
            )}
            <div className="local-plan-heading">
              <strong>
                {plan.kind === 'universal' ? '通用验收计划' : plan.kind === "configured"
                  ? "项目验收计划"
                  : plan.detection
                    ? "自动验收计划"
                    : "完整验收计划"}
              </strong>
              <span>
                {plan.file_count} 个文件 · {plan.check_count} 项检查
                {plan.specification && (
                  <> · {plan.specification.requirements.reduce(
                    (n: number, q: any) => n + q.scenarios.length, 0,
                  )} 条模型用例</>
                )}
              </span>
            </div>
            <ol className="workflow-plan-stages">
              {plan.stages.map((s) => (
                <li key={s.id}>{s.title}</li>
              ))}
            </ol>
            <p className="muted small-text">
              {plan.kind === 'universal' ? '开始通用验收' : plan.kind === "configured" || plan.detection
                ? plan.scope
                : "模型设计、新生成用例、扫描、业务、浏览器、性能与恢复均参与完整性核对。缺少必验步骤时，本次验收显示未完成。"}
            </p>
            <details className="console-disclosure">
              <summary>依据与排除范围</summary>
              {plan.documents.map((d: any) => (
                <p key={typeof d === "string" ? d : d.id}>
                  {typeof d === "string" ? d : d.title}
                </p>
              ))}
              {plan.exclusions.map((x, i) => (
                <p key={i}>
                  {x.subject}：{x.reason}
                </p>
              ))}
            </details>
            {plan.blockers.length > 0 && (
              <details className="error-banner local-plan-blockers" role="alert">
                <summary>{plan.blockers.length} 项待确认，暂不能开始验收</summary>
                {plan.blockers.map((x) => (
                  <p key={x}>{x}</p>
                ))}
              </details>
            )}
            {plan.specification?.environment.mode === "module" && (
              <CitationAdjustments planner={plan.planner} />
            )}
            {plan.specification?.environment.mode === "cli" && (
              <AutomaticPlanDetails plan={plan} />
            )}
            {plan.specification?.environment.mode === "module" && (
              <details className="console-disclosure">
                <summary>模型生成的标准与用例</summary>
                {plan.specification.requirements.map((q: any) => (
                  <section key={q.id}>
                    <strong>{q.title}</strong>
                    <blockquote>{q.quote}</blockquote>
                    {q.reason && <p>{q.reason}</p>}
                    {q.scenarios.map((s: any) => (
                      <details key={s.id}>
                        <summary>{s.title}</summary>
                        <pre>{JSON.stringify(s.steps, null, 2)}</pre>
                      </details>
                    ))}
                  </section>
                ))}
              </details>
            )}
            {plan.specification && (
              <label className="local-option">
                <input
                  type="checkbox"
                  checked={reviewed}
                  disabled={busy}
                  onChange={(e) => setReviewed(e.target.checked)}
                />
                已核对独立依据、生成用例及本次范围
              </label>
            )}
            <button
              className="button primary"
              disabled={
                busy || !plan.ready || (!!plan.specification && !reviewed)
              }
              onClick={() =>
                work(async () => {
                  const r = await post<{ id: string }>("runs", {
                    plan_id: plan.id,
                    digest: plan.digest,
                  });
                  started(r.id);
                })
              }
            >
              {busy ? <SpinnerGap className="spin" /> : <PlayCircle />}
              {plan.kind === "configured" || plan.detection
                ? "按配置范围开始验收"
                : "按完整流程开始验收"}
            </button>
          </>
        )}
        {error && (
          <p role="alert" className="error-banner">
            {error}
          </p>
        )}
      </div>
    </Modal>
  );
}
