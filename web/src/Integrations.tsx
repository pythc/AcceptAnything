import { useEffect, useState } from "react";
import { PriorityBadge, severity } from "./ui";
import { SpinnerGap } from "@phosphor-icons/react";
import { elapsed, seconds } from "./pipeline";
import { PlanDetails } from "./TestDesign";
import { caseForResult } from "./plannedResults";
type RecordData = Record<string, any>;
async function request(path: string, init?: RequestInit) {
  const response = await fetch("/api/integrations/" + path, init);
  if (!response.ok) throw Error(await response.text());
  return response.json();
}
const names: Record<string, string> = {
  allow: "通过",
  reject: "未通过",
  inconclusive: "无法下结论",
  queued: "等待执行",
  running: "执行中",
  completed: "已完成",
  error: "执行异常",
  cancelled: "已取消",
  passed: "通过",
  failed: "失败",
  unknown: "缺少依据",
};
function resultSummary(t: RecordData) {
  if (t.state === "running") return "正在执行，等待原始报告";
  if (t.state === "queued") return "等待执行";
  if (t.error) return t.error;
  if (!t.report) return "尚未产生报告";
  if (t.report.tests.length)
    return `${t.report.tests.length} 个测试 · ${t.report.metrics["tests.failed"]} 个失败`;
  if (t.report.components.length) return `${t.report.components.length} 个组件`;
  if (t.report.metrics["coverage.lines"] != null)
    return `行覆盖率 ${t.report.metrics["coverage.lines"]}%`;
  return `${t.report.findings.length} 项发现`;
}
export function Integrations({
  initialTab = "flow",
  onDesign,
  onOpenRun,
}: {
  initialTab?: string;
  onDesign?: (plan: RecordData) => void;
  onOpenRun?: (id: string) => void;
}) {
  const [clock, setClock] = useState(Date.now()),
    [taskId, setTaskId] = useState("");
  const [runsLoading, setRunsLoading] = useState(true),
    [profilesLoading, setProfilesLoading] = useState(true);
  const [catalog, setCatalog] = useState<RecordData | null>(null),
    [runs, setRuns] = useState<RecordData[]>([]),
    [profiles, setProfiles] = useState<RecordData[]>([]),
    [run, setRun] = useState<RecordData | null>(null),
    [id, setId] = useState(
      new URLSearchParams(location.search).get("integration") || "",
    ),
    [error, setError] = useState(""),
    [query, setQuery] = useState(""),
    [view, setView] = useState("runs"),
    [tab, setTab] = useState(initialTab),
    [profile, setProfile] = useState(""),
    [starting, setStarting] = useState(false),
    [preview, setPreview] = useState(""),
    [artifact, setArtifact] = useState("");
  const refresh = () =>
    Promise.all([
      request("catalog").then(setCatalog),
      request("runs")
        .then((r) => {
          setRuns(r);
          setId((v) => v || r[0]?.id || "");
        })
        .finally(() => setRunsLoading(false)),
      request("profiles")
        .then((p) => {
          setProfiles(p);
          setProfile((v) => v || p[0]?.id || "");
        })
        .finally(() => setProfilesLoading(false)),
    ]);
  useEffect(() => {
    refresh().catch((e) => setError(e.message));
  }, []);
  useEffect(() => {
    if (!id) return;
    let active = true;
    let timer: ReturnType<typeof setTimeout>;
    setRun(null);
    setPreview("");
    const load = async () => {
      try {
        const r = await request("runs/" + id);
        if (!active) return;
        setRun(r);
        if (["running", "queued"].includes(r.status))
          timer = setTimeout(load, 1000);
        else refresh().catch((e) => setError(e.message));
      } catch (e) {
        if (active) setError((e as Error).message);
      }
    };
    load();
    return () => {
      active = false;
      clearTimeout(timer);
    };
  }, [id]);
  useEffect(() => {
    if (onOpenRun) return;
    const p = new URLSearchParams(location.search);
    if (id) p.set("integration", id);
    p.set("tab", tab);
    history.replaceState(null, "", "?" + p);
  }, [id, tab]);
  const start = async () => {
    setStarting(true);
    setError("");
    try {
      const r = await request("runs", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ profile_id: profile }),
      });
      setId(r.id);
      if (onOpenRun) onOpenRun(r.id);
      setView("runs");
      setTab("flow");
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setStarting(false);
    }
  };
  const openEvidence = async (aid: string) => {
    setTab("evidence");
    setArtifact(aid);
    setPreview("加载中");
    try {
      const r = await fetch(`/api/integrations/runs/${id}/artifacts/${aid}`);
      if (!r.ok) throw Error(await r.text());
      const text = await r.text();
      setPreview(
        text.length > 30000
          ? text.slice(0, 30000) + "\n… 预览已截断，请下载完整证据"
          : text,
      );
    } catch (e) {
      setError((e as Error).message);
      setPreview("");
    }
  };
  const findings =
    run?.tasks.flatMap((t: RecordData) =>
      (t.report?.findings || []).map((f: RecordData) => ({ ...f, task: t })),
    ) || [];
  useEffect(() => {
    if (run?.profile_id) setProfile(run.profile_id);
  }, [run?.id]);
  const failedTests =
    run?.tasks.flatMap((t: RecordData) =>
      (t.report?.tests || [])
        .filter((x: RecordData) => x.status !== "passed")
        .map((x: RecordData) => {
          const c = caseForResult(run!, t, x);
          return {
            ...x,
            task: t,
            case: c,
            priority: c?.priority,
            trace_ref:
              c &&
              run?.artifacts.find(
                (a: RecordData) => a.name === t.id + "/" + c.id + "-trace.json",
              )?.id,
          };
        }),
    ) || [];
  const running = run?.tasks.find((t: RecordData) => t.state === "running");
  const selectedTask =
    run?.tasks.find((t: RecordData) => t.id === taskId) ||
    running ||
    run?.tasks[0];
  const taskTitle = (taskId: string) =>
    run?.onboarding_plan?.checks.find((c: RecordData) => c.id === taskId)
      ?.title || taskId;
  const time = (item: RecordData) =>
    seconds(
      item.state === "running"
        ? elapsed(item.started_at, null, clock)
        : (item.duration_ms ?? undefined),
    );
  useEffect(() => {
    if (!run || !["queued", "running"].includes(run.status)) return;
    const timer = setInterval(() => setClock(Date.now()), 250);
    return () => clearInterval(timer);
  }, [run?.id, run?.status]);
  return (
    <main className="integrations-page">
      <div className="integration-toolbar">
        <div className="integration-switch">
          <button
            className={view === "runs" ? "selected" : ""}
            onClick={() => setView("runs")}
          >
            执行记录
          </button>
          <button
            className={view === "catalog" ? "selected" : ""}
            onClick={() => setView("catalog")}
          >
            接入能力
          </button>
        </div>
        <div className="actions">
          {run?.test_plan && onDesign ? (
            <button
              className="button primary"
              onClick={() => onDesign(run.test_plan)}
            >
              重新设计方案
            </button>
          ) : (
            <>
              <select
                aria-label="验收配置"
                value={profilesLoading ? "" : profile}
                disabled={profilesLoading}
                onChange={(e) => setProfile(e.target.value)}
              >
                {profilesLoading && <option value="">正在读取验收配置</option>}
                {profiles.map((p) => (
                  <option key={p.id} value={p.id}>
                    {p.name}
                  </option>
                ))}
              </select>
              <button
                className="button primary"
                disabled={
                  !profile ||
                  profiles
                    .find((p) => p.id === profile)
                    ?.tasks.some(
                      (t: RecordData) => t.tool === "acceptance-generated",
                    ) ||
                  profilesLoading ||
                  starting ||
                  ["queued", "running"].includes(run?.status)
                }
                onClick={start}
              >
                开始验证
              </button>
            </>
          )}
        </div>
      </div>
      {error && (
        <p role="alert" className="error-banner">
          {error}
        </p>
      )}
      {view === "catalog" ? (
        <section className="integration-catalog">
          <input
            aria-label="筛选接入能力"
            placeholder="搜索执行器或报告格式"
            value={query}
            onChange={(e) => setQuery(e.target.value)}
          />
          <h2>执行器</h2>
          <table>
            <thead>
              <tr>
                <th>工具</th>
                <th>报告</th>
                <th>本机环境</th>
                <th>验证记录</th>
              </tr>
            </thead>
            <tbody>
              {catalog?.executors
                .filter((x: RecordData) => x.id.includes(query))
                .map((x: RecordData) => (
                  <tr key={x.id}>
                    <td>{x.id}</td>
                    <td>{x.format}</td>
                    <td>{x.image ? "镜像已固定" : "未安装"}</td>
                    <td>
                      {x.certification.run_id ? (
                        <button
                          className="text-button"
                          onClick={() => {
                            setId(x.certification.run_id);
                            setView("runs");
                          }}
                        >
                          {x.certification.level === "real-execution"
                            ? "真实执行已验证"
                            : x.certification.level}
                        </button>
                      ) : (
                        "尚未实测"
                      )}
                    </td>
                  </tr>
                ))}
            </tbody>
          </table>
          <h2>报告导入</h2>
          <div className="format-list">
            {catalog?.formats
              .filter((f: string) => f.includes(query))
              .map((f: string) => (
                <code key={f}>{f}</code>
              ))}
          </div>
          <p className="muted">
            外部报告保留来源标记；导入不代表本平台执行了对应扫描。
          </p>
          <h2>外部平台</h2>
          <table>
            <thead>
              <tr>
                <th>服务</th>
                <th>接入方式</th>
                <th>实际连接</th>
              </tr>
            </thead>
            <tbody>
              {catalog?.services.map((s: RecordData) => (
                <tr key={s.id}>
                  <td>{s.id}</td>
                  <td>官方 API · 环境变量凭据</td>
                  <td>
                    {s.live_verified ? (
                      <button
                        className="text-button"
                        onClick={() => {
                          setId(s.run_id);
                          setView("runs");
                        }}
                      >
                        真实 API 已验证
                      </button>
                    ) : (
                      "接口契约已测，尚无实例验证"
                    )}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
          {catalog?.services
            .filter((s: RecordData) => s.test_types?.length)
            .map((s: RecordData) => (
              <details key={s.id}>
                <summary>
                  DefectDojo 上游报告类型 · {s.test_types.length} 项
                </summary>
                <p className="muted">
                  通过平台桥转交解析。已逐项实测{" "}
                  {
                    s.test_types.filter((t: RecordData) => t.live_verified)
                      .length
                  }{" "}
                  种；其他类型保留为待认证，不计作已验证扫描器。
                </p>
                <table>
                  <thead>
                    <tr>
                      <th>报告类型</th>
                      <th>验证状态</th>
                    </tr>
                  </thead>
                  <tbody>
                    {s.test_types
                      .filter((t: RecordData) =>
                        t.name.toLowerCase().includes(query.toLowerCase()),
                      )
                      .map((t: RecordData) => (
                        <tr key={t.id}>
                          <td>{t.name}</td>
                          <td>
                            {t.live_verified
                              ? "真实导入已验证"
                              : "上游支持 · 待逐项认证"}
                          </td>
                        </tr>
                      ))}
                  </tbody>
                </table>
              </details>
            ))}
        </section>
      ) : (
        <div className="integration-layout">
          <aside
            className="integration-runs"
            aria-label="集成执行记录"
            aria-busy={runsLoading}
          >
            {runs.map((r) => (
              <button
                key={r.id}
                className={id === r.id ? "selected" : ""}
                onClick={() => {
                  if (onOpenRun) {
                    onOpenRun(r.id);
                    return;
                  }
                  setId(r.id);
                  setTab("flow");
                }}
              >
                <strong>{r.name}</strong>
                <span>
                  {["queued", "running"].includes(r.status)
                    ? names[r.status]
                    : `当时${names[r.recorded_decision || r.decision]} · ${names[r.status]}`}
                </span>
                <small>{new Date(r.created_at).toLocaleString()}</small>
              </button>
            ))}
            {!runs.length && (
              <p>{runsLoading ? "正在读取执行记录" : "还没有集成执行记录"}</p>
            )}
          </aside>
          <section className="integration-detail">
            {onOpenRun ? (
              <div className="catalogue-detail-heading">
                <h2>执行记录</h2>
                <p>选择记录后，在统一验收详情页查看流程、缺陷和证据。</p>
              </div>
            ) : run ? (
              <>
                <div className="integration-heading">
                  <div>
                    <h2>{run.name}</h2>
                    <span className={"decision " + run.decision}>
                      {["queued", "running"].includes(run.status)
                        ? names[run.status]
                        : names[run.decision]}
                    </span>
                    <span className="muted">
                      {" "}
                      {run.mode === "import"
                        ? "外部报告导入"
                        : "本机容器执行"}{" "}
                      · {run.id}
                    </span>
                  </div>
                  <a
                    className="button outline"
                    href={`/api/integrations/runs/${id}/export/markdown`}
                  >
                    导出报告
                  </a>
                </div>
                <dl className="integration-context">
                  <dt>代码仓库</dt>
                  <dd>{run.context?.repository}</dd>
                  <dt>提交 / 快照</dt>
                  <dd>
                    {run.context?.revision === "uncommitted"
                      ? "本地目录"
                      : run.context?.revision}{" "}
                    · {run.context?.snapshot_digest?.slice(0, 16)}
                  </dd>
                  <dt>验收范围</dt>
                  <dd>{run.context?.scope}</dd>
                  <dt>执行环境</dt>
                  <dd>
                    {run.context?.environment} ·{" "}
                    {run.integrity ? "证据校验通过" : "证据未确认"}
                  </dd>
                </dl>
                {run.errors?.length > 0 && (
                  <div role="alert" className="error-banner">
                    {run.errors.join("；")}
                  </div>
                )}
                <nav className="tabs" aria-label="集成验收详情">
                  {[
                    ...(run.test_plan ? [["plan", "方案与用例"]] : []),
                    ["flow", "验收流程"],
                    [
                      "findings",
                      `缺陷结论 ${findings.length + failedTests.length}`,
                    ],
                    ["evidence", `证据溯源 ${run.artifacts.length}`],
                  ].map(([key, label]) => (
                    <button
                      key={key}
                      className={tab === key ? "selected" : ""}
                      onClick={() => setTab(key)}
                    >
                      {label}
                    </button>
                  ))}
                </nav>
                {tab === "plan" && run.test_plan && (
                  <PlanDetails
                    plan={run.test_plan}
                    run={run}
                    openEvidence={openEvidence}
                  />
                )}
                {tab === "flow" && (
                  <>
                    {running && (
                      <div className="console-live-result" role="status">
                        <SpinnerGap className="spin" size={18} />
                        <strong>正在执行</strong>
                        <span>
                          {taskTitle(running.id)} · {running.tool}
                        </span>
                        <time>{time(running)}</time>
                      </div>
                    )}
                    <div className="integration-stages">
                      {run.test_plan?.stages.map((s: RecordData, i: number) => (
                        <div key={"design-" + i}>
                          <span className="status-dot completed" />
                          <strong>{s.name}</strong>
                          <span>执行前已生成</span>
                          <time>{seconds(s.duration_ms)}</time>
                          <small>{s.detail}</small>
                        </div>
                      ))}
                      {run.pipeline.map((s: RecordData, i: number) => (
                        <div key={i}>
                          <span className={"status-dot " + s.state} />
                          <strong>{taskTitle(s.name)}</strong>
                          <span>{names[s.state] || s.state}</span>
                          <time>
                            {s.state === "running" || s.duration_ms != null
                              ? time(s)
                              : "—"}
                          </time>
                          <small>
                            {s.name === "冻结输入" && s.detail.length === 64
                              ? "输入已冻结"
                              : run.tasks.some(
                                    (t: RecordData) => t.id === s.name,
                                  )
                                ? resultSummary(
                                    run.tasks.find(
                                      (t: RecordData) => t.id === s.name,
                                    ),
                                  )
                                : names[s.detail] || s.detail}
                          </small>
                        </div>
                      ))}
                    </div>
                    <h3>执行结果</h3>
                    <table className="integration-result-table">
                      <thead>
                        <tr>
                          <th>检查</th>
                          <th>状态</th>
                          <th>实际结果</th>
                          <th>耗时</th>
                          <th>证据</th>
                        </tr>
                      </thead>
                      <tbody>
                        {run.tasks.map((t: RecordData) => (
                          <tr
                            key={t.id}
                            className={
                              selectedTask?.id === t.id ? "selected" : ""
                            }
                            onClick={() => setTaskId(t.id)}
                          >
                            <td>
                              <button
                                aria-pressed={selectedTask?.id === t.id}
                                onClick={() => setTaskId(t.id)}
                              >
                                {taskTitle(t.id)}
                              </button>
                              <small className="table-secondary">
                                {t.tool}
                              </small>
                            </td>
                            <td>{names[t.state]}</td>
                            <td>{resultSummary(t)}</td>
                            <td>
                              <time>
                                {t.state === "queued" ? "—" : time(t)}
                              </time>
                            </td>
                            <td>
                              {t.report_ref && (
                                <button
                                  className="text-button"
                                  onClick={(event) => {
                                    event.stopPropagation();
                                    openEvidence(t.report_ref);
                                  }}
                                >
                                  原始报告
                                </button>
                              )}
                            </td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                    {selectedTask && (
                      <section className="integration-task-detail">
                        <h3>
                          {taskTitle(selectedTask.id)} ·{" "}
                          {names[selectedTask.state]}
                        </h3>
                        <p>{resultSummary(selectedTask)}</p>
                        <dl className="integration-context">
                          <dt>执行器 / 范围</dt>
                          <dd>
                            {selectedTask.tool} · {selectedTask.target}
                          </dd>
                          <dt>开始时间</dt>
                          <dd>
                            {selectedTask.started_at
                              ? new Date(
                                  selectedTask.started_at,
                                ).toLocaleString()
                              : "尚未开始"}
                          </dd>
                          <dt>耗时</dt>
                          <dd>
                            {selectedTask.state === "queued"
                              ? "—"
                              : time(selectedTask)}
                          </dd>
                        </dl>
                      </section>
                    )}
                    <h3>质量门禁</h3>
                    <table>
                      <thead>
                        <tr>
                          <th>规则</th>
                          <th>预期</th>
                          <th>实际</th>
                          <th>结论</th>
                        </tr>
                      </thead>
                      <tbody>
                        {run.rules.map((g: RecordData) => (
                          <tr key={g.id}>
                            <td>
                              {g.kind === "required-tests"
                                ? "用例完整性"
                                : g.id}
                            </td>
                            <td>
                              {g.kind === "required-tests" ? (
                                `必须执行 ${g.expected.values.length} 个指定用例`
                              ) : (
                                <>
                                  {g.expected.metric || g.kind}{" "}
                                  {g.expected.operator}{" "}
                                  {g.expected.values.length
                                    ? g.expected.values.join(", ")
                                    : g.expected.threshold}
                                </>
                              )}
                            </td>
                            <td>
                              {g.actual === null
                                ? "未取得"
                                : g.kind === "required-tests" &&
                                    Array.isArray(g.actual)
                                  ? g.actual.length
                                    ? `缺少 ${g.actual.length} 个用例`
                                    : "没有遗漏"
                                  : JSON.stringify(g.actual)}
                            </td>
                            <td>
                              {names[g.status]}
                              {g.reason && (
                                <small className="table-secondary">
                                  {g.reason}
                                </small>
                              )}
                            </td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                    {["queued", "running"].includes(run.status) && (
                      <button
                        className="button outline"
                        onClick={() =>
                          request("runs/" + id + "/cancel", {
                            method: "POST",
                            headers: { "Content-Type": "application/json" },
                            body: "{}",
                          }).catch((e) => setError(e.message))
                        }
                      >
                        取消本次执行
                      </button>
                    )}
                    {run.exclusions.length > 0 && (
                      <details>
                        <summary>排除范围 · {run.exclusions.length}</summary>
                        {run.exclusions.map((x: RecordData) => (
                          <p key={x.subject}>
                            {x.subject}：{x.reason}
                          </p>
                        ))}
                      </details>
                    )}
                  </>
                )}
                {tab === "findings" && (
                  <IntegrationFindings
                    findings={findings}
                    tests={failedTests}
                    openEvidence={openEvidence}
                  />
                )}
                {tab === "evidence" && (
                  <>
                    <p className="muted">
                      原始报告记录检测结果；command.json
                      记录执行命令、耗时及退出码；gate-input / result
                      记录门禁依据。
                    </p>
                    <div className="integration-evidence">
                      <div>
                        {run.artifacts.map((a: RecordData) => (
                          <button
                            className={artifact === a.id ? "selected" : ""}
                            key={a.id}
                            onClick={() => openEvidence(a.id)}
                          >
                            <strong>{a.name}</strong>
                            <small>
                              {a.size.toLocaleString()} bytes ·{" "}
                              {a.sha256.slice(0, 12)}
                            </small>
                          </button>
                        ))}
                      </div>
                      <section>
                        {artifact && (
                          <a
                            href={`/api/integrations/runs/${id}/artifacts/${artifact}`}
                            download
                          >
                            下载完整证据
                          </a>
                        )}
                        <pre>{preview || "选择一份证据查看内容"}</pre>
                      </section>
                    </div>
                    <div className="actions">
                      {["junit", "sarif", "json"].map((f) => (
                        <a
                          key={f}
                          href={`/api/integrations/runs/${id}/export/${f}`}
                        >
                          {f.toUpperCase()} 导出
                        </a>
                      ))}
                    </div>
                  </>
                )}
              </>
            ) : (
              <p>选择一条执行记录</p>
            )}
          </section>
        </div>
      )}
    </main>
  );
}

function IntegrationFindings({
  findings,
  tests,
  openEvidence,
}: {
  findings: RecordData[];
  tests: RecordData[];
  openEvidence: (id: string) => void;
}) {
  const [selected, setSelected] = useState(""),
    [query, setQuery] = useState("");
  const rows: RecordData[] = [
    ...tests.map((x: RecordData) => ({
      ...x,
      title: x.case?.title || x.name,
      detail: x.detail,
      severity: x.status,
      kind: "测试失败",
    })),
    ...findings.map((x: RecordData) => ({ ...x, kind: "工具报告 · 未复核" })),
  ];
  const filtered = rows.filter((x) =>
    (x.title + " " + x.path + " " + x.task.tool + " " + x.rule)
      .toLowerCase()
      .includes(query.toLowerCase()),
  );
  const item =
    filtered.find((x) => x.task.id + ":" + x.id === selected) || filtered[0];
  const fix = item?.fix;
  const fixText =
    typeof fix === "string"
      ? fix
      : fix?.versions?.join(", ") ||
        fix?.version ||
        fix?.message ||
        (fix ? "见原始报告" : "");
  return (
    <div className="integration-finding-split">
      <aside>
        <input
          aria-label="筛选发现记录"
          placeholder="搜索问题、规则或路径"
          value={query}
          onChange={(e) => setQuery(e.target.value)}
        />
        <p className="muted">{filtered.length} 条记录 · 保留各工具的独立结果</p>
        {filtered.map((f, i) => (
          <button
            key={f.task.id + f.id + i}
            className={f === item ? "selected" : ""}
            onClick={() => setSelected(f.task.id + ":" + f.id)}
          >
            <PriorityBadge finding={f} />
            <strong>{f.title}</strong>
            <small>
              {f.kind} · {f.task.tool}
            </small>
            <small>{f.path || f.component || f.name}</small>
          </button>
        ))}
      </aside>
      <section>
        {item ? (
          <>
            <h3>{item.title}</h3>
            <dl className="integration-context">
              <dt>优先级</dt>
              <dd>
                <PriorityBadge finding={item} />
              </dd>
              <dt>来源</dt>
              <dd>
                {item.task.tool} · {item.kind}
              </dd>
              <dt>原始级别 / 规则</dt>
              <dd>
                {severity[item.severity] ||
                  names[item.severity] ||
                  item.severity}{" "}
                · {item.rule || item.status}
              </dd>
              <dt>位置 / 组件</dt>
              <dd>
                {item.path || item.component || item.name}
                {item.line ? ":" + item.line : ""}
              </dd>
            </dl>
            <h3>检测结果</h3>
            {item.case && (
              <>
                <p>
                  验收依据：{item.case.source.title}:{item.case.source.line}
                </p>
                <blockquote>{item.case.source.quote}</blockquote>
              </>
            )}
            <p className="finding-detail">
              {item.detail || "报告未提供额外说明"}
            </p>
            {fixText && (
              <>
                <h3>修复信息</h3>
                <p>{fixText}</p>
              </>
            )}
            <button
              className="button outline"
              onClick={() => openEvidence(item.task.report_ref)}
            >
              查看原始证据
            </button>
            {item.trace_ref && (
              <button
                className="button outline"
                onClick={() => openEvidence(item.trace_ref)}
              >
                查看步骤与实际结果
              </button>
            )}
            <details>
              <summary>完整上下文</summary>
              <pre>{JSON.stringify({ ...item, task: undefined }, null, 2)}</pre>
            </details>
          </>
        ) : (
          <p>没有匹配的发现记录</p>
        )}
      </section>
    </div>
  );
}
