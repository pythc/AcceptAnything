import { useEffect, useState } from "react";
import { SpinnerGap, PlayCircle, FileText } from "@phosphor-icons/react";
import { Modal } from "./ui";
import { AutomaticPlanDetails } from "./AutomaticPlanDetails";
import { plannedCaseResult } from "./plannedResults";
import { modelLabel, modelVerification } from "./modelLabel";
import { CitationAdjustments } from "./CitationAdjustments";

type Data = Record<string, any>;
const dimensions: Record<string, string> = {
  normal: "正常",
  boundary: "边界",
  error: "异常",
  permission: "权限",
  state: "状态",
  persistence: "持久化",
  performance: "性能",
  recovery: "恢复",
};
async function api(path: string, body?: object) {
  const r = await fetch(
    "/api/integrations/planning/" + path,
    body
      ? {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify(body),
        }
      : undefined,
  );
  if (!r.ok) throw Error(await r.text());
  return r.json();
}

export function TestDesign({
  close,
  started,
  initial,
}: {
  close: () => void;
  started: (id: string) => void;
  initial?: Data | null;
}) {
  const [path, setPath] = useState(""),
    [documents, setDocuments] = useState<Data[]>([]),
    [files, setFiles] = useState<string[]>([]),
    [source, setSource] = useState("");
  const [spec, setSpec] = useState(""),
    [draft, setDraft] = useState<string | undefined>(),
    [plan, setPlan] = useState<Data | null>(null),
    [config, setConfig] = useState<Data | null>(null);
  const [busy, setBusy] = useState(""),
    [error, setError] = useState(""),
    [scanners, setScanners] = useState(true),
    [reviewed, setReviewed] = useState(false),
    [step, setStep] = useState("basis");
  const [scope, setScope] = useState(""),
    [mode, setMode] = useState("module"),
    [runtime, setRuntime] = useState("node"),
    [entry, setEntry] = useState("");
  useEffect(() => {
    api("status")
      .then(setConfig)
      .catch((e) => setError(e.message));
  }, []);
  useEffect(() => {
    if (!initial) return;
    const s = initial.specification;
    setPath(initial.repository);
    setDocuments(initial.documents);
    setSpec(JSON.stringify(s, null, 2));
    setScope(s.scope);
    setMode(s.environment.mode);
    setRuntime(s.environment.runtime);
    setEntry(s.environment.entrypoint || "");
    setScanners(initial.checks.some((c: Data) => !c.engine));
  }, [initial]);
  let previewSpec: Data | null = null;
  try {
    previewSpec = JSON.parse(spec);
  } catch {}
  const invalidate = () => {
    setPlan(null);
    setReviewed(false);
  };
  async function work(label: string, fn: () => Promise<void>) {
    setBusy(label);
    setError("");
    try {
      await fn();
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setBusy("");
    }
  }
  const environment = {
    mode,
    runtime,
    ...(mode === "service" ? { entrypoint: entry } : {}),
  };
  return (
    <Modal title="设计验收用例" close={close}>
      <div className="test-design-form" aria-busy={!!busy}>
        <div className="design-toolbar">
          <button
            className="text-button"
            disabled={!!busy}
            onClick={() =>
              work("读取示例", async () => {
                const example = await api("example");
                setPath(example.repository);
                setDocuments(example.documents);
                setSpec(JSON.stringify(example.specification, null, 2));
                setScope(example.specification.scope);
                setMode(example.specification.environment.mode);
                setRuntime(example.specification.environment.runtime);
                setEntry(example.specification.environment.entrypoint || "");
                setDraft(undefined);
                invalidate();
                setStep("basis");
              })
            }
          >
            载入考核项目示例
          </button>
          <label className="text-button">
            导入方案文件
            <input
              type="file"
              accept=".json"
              disabled={!!busy}
              onChange={async (e) => {
                const f = e.target.files?.[0];
                if (!f) return;
                await work("读取方案", async () => {
                  if (f.size > 600000) throw Error("方案文件超过600KB");
                  const x = JSON.parse(await f.text());
                  if (!x || typeof x !== "object" || Array.isArray(x))
                    throw Error("方案必须是 JSON 对象");
                  if (
                    x.documents &&
                    (!Array.isArray(x.documents) ||
                      x.documents.some(
                        (d: Data) =>
                          !d ||
                          typeof d.id !== "string" ||
                          typeof d.title !== "string" ||
                          typeof d.content !== "string",
                      ))
                  )
                    throw Error("依据需要编号、标题和原文");
                  setPath(
                    typeof x.repository === "string" ? x.repository : path,
                  );
                  setDocuments(x.documents || documents);
                  const s = x.specification || x;
                  setSpec(JSON.stringify(s, null, 2));
                  setScope(typeof s.scope === "string" ? s.scope : "");
                  setMode(s.environment?.mode || "module");
                  setRuntime(s.environment?.runtime || "node");
                  setEntry(s.environment?.entrypoint || "");
                  setDraft(undefined);
                  invalidate();
                });
                e.target.value = "";
              }}
            />
          </label>
        </div>
        <label className="form-label" htmlFor="design-repository">
          仓库路径
        </label>
        <div className="design-input-row">
          <input
            id="design-repository"
            value={path}
            disabled={!!busy}
            placeholder="本地仓库绝对路径"
            onChange={(e) => {
              setPath(e.target.value);
              setDocuments([]);
              setFiles([]);
              setSource("");
              setDraft(undefined);
              invalidate();
            }}
          />
          <button
            className="button outline"
            disabled={!!busy || !path.trim()}
            onClick={() =>
              work("读取仓库", async () => {
                const d = await api("sources", { repository: path });
                setFiles(d.documents);
                setSource(d.documents[0] || "");
              })
            }
          >
            读取依据
          </button>
        </div>
        <nav className="tabs" aria-label="设计步骤">
          {[
            ["basis", "验收依据"],
            ["spec", "测试方案"],
            ["preview", "生成用例"],
          ].map(([key, title]) => (
            <button
              key={key}
              className={step === key ? "selected" : ""}
              disabled={!!busy || (key === "preview" && !plan)}
              onClick={() => setStep(key)}
            >
              {title}
            </button>
          ))}
        </nav>
        {step === "basis" && (
          <>
            {!!files.length && (
              <div className="design-input-row">
                <select
                  aria-label="仓库需求文档"
                  value={source}
                  onChange={(e) => setSource(e.target.value)}
                >
                  {files.map((f) => (
                    <option key={f}>{f}</option>
                  ))}
                </select>
                <button
                  className="button outline"
                  disabled={!!busy}
                  onClick={() =>
                    work("读取文档", async () => {
                      const d = await api("sources", {
                        repository: path,
                        path: source,
                      });
                      const id = "basis" + (documents.length + 1);
                      setDocuments([...documents, { ...d, id }]);
                      setDraft(undefined);
                      invalidate();
                    })
                  }
                >
                  加入依据
                </button>
              </div>
            )}
            {documents.map((d, i) => (
              <details
                className="console-disclosure"
                key={i}
                open={documents.length === 1}
              >
                <summary>
                  {d.title} · {d.id}
                </summary>
                <label className="form-label">
                  来源原文
                  <textarea
                    aria-label={"依据原文 " + d.id}
                    value={d.content}
                    disabled={!!busy}
                    onChange={(e) => {
                      setDocuments(
                        documents.map((x, n) =>
                          n === i ? { ...x, content: e.target.value } : x,
                        ),
                      );
                      setDraft(undefined);
                      invalidate();
                    }}
                  />
                </label>
                <button
                  className="text-button"
                  disabled={!!busy}
                  onClick={() => {
                    setDocuments(documents.filter((_, n) => n !== i));
                    setDraft(undefined);
                    invalidate();
                  }}
                >
                  移除此依据
                </button>
              </details>
            ))}
            <button
              className="button outline"
              disabled={!!busy}
              onClick={() => {
                setDocuments([
                  ...documents,
                  {
                    id: "basis" + Date.now(),
                    title: "补充业务规则",
                    origin: "用户输入",
                    content: "",
                  },
                ]);
                invalidate();
              }}
            >
              添加业务规则
            </button>
            <label className="form-label" htmlFor="design-scope">
              本次验收范围
            </label>
            <textarea
              id="design-scope"
              value={scope}
              disabled={!!busy}
              placeholder="要验收哪些业务行为"
              onChange={(e) => {
                setScope(e.target.value);
                invalidate();
              }}
            />
            <div className="design-input-row">
              <select
                aria-label="运行方式"
                value={mode}
                disabled={!!busy}
                onChange={(e) => {
                  setMode(e.target.value);
                  invalidate();
                }}
              >
                <option value="module">模块函数</option>
                <option value="service">接口与页面服务</option>
              </select>
              <select
                aria-label="目标运行时"
                value={runtime}
                disabled={!!busy}
                onChange={(e) => {
                  setRuntime(e.target.value);
                  invalidate();
                }}
              >
                <option value="node">Node.js / TypeScript</option>
                <option value="python">Python</option>
              </select>
            </div>
            {mode === "service" && (
              <label className="form-label">
                服务入口
                <input
                  aria-label="服务入口"
                  value={entry}
                  placeholder="server.mjs 或 app.py；默认 PORT=19300"
                  disabled={!!busy}
                  onChange={(e) => {
                    setEntry(e.target.value);
                    invalidate();
                  }}
                />
              </label>
            )}
            <div className="design-action">
              <button
                className="button primary"
                disabled={
                  !!busy ||
                  config?.blocked ||
                  !config?.configured ||
                  !documents.length ||
                  !scope.trim()
                }
                onClick={() =>
                  work("模型正在设计方案", async () => {
                    const x = await api("draft", {
                      repository: path,
                      documents,
                      scope,
                      environment,
                    });
                    setSpec(JSON.stringify(x.specification, null, 2));
                    setDraft(x.id);
                    invalidate();
                    setStep("spec");
                  })
                }
              >
                根据依据设计方案
              </button>
              <span className="muted">
                {config?.configured
                  ? config.label || config.model
                  : "模型未配置 · 可导入或编辑结构化方案"}
              </span>
            </div>
            {(config?.blocked || config?.duplicate_confirmation_required) && (
              <div className="error-banner">
                <p>{config.blocked?'模型请求仍在执行或无法核对输入，暂不能生成。':'有历史请求终态未知；相同输入不会自动重发，其他独立方案可继续。'}</p>
                {config.pending_requests?.map((r: Data) => (
                  <p key={r.client_request_id}>
                    <code>{r.client_request_id}</code>
                  </p>
                ))}
                <button
                  className="button outline"
                  disabled={!!busy}
                  onClick={() =>
                    work("核对上次模型请求", async () =>
                      setConfig(await api("reconcile", {})),
                    )
                  }
                >
                  核对上次请求
                </button>
              </div>
            )}
            <button className="text-button" onClick={() => setStep("spec")}>
              查看 / 编辑测试方案 →
            </button>
          </>
        )}
        {step === "spec" && (
          <>
            <p className="muted">
              每条标准引用原文。数据表、组合和边界规则将展开为新的可执行用例。
            </p>
            {Array.isArray(previewSpec?.requirements) &&
              previewSpec.requirements.map((r: Data, i: number) => (
                <details className="console-disclosure" key={r?.id || i}>
                  <summary>
                    {String(r?.title || "未命名标准")} ·{" "}
                    {Array.isArray(r?.scenarios) ? r.scenarios.length : 0}{" "}
                    个场景
                  </summary>
                  <blockquote>{String(r?.quote || "")}</blockquote>
                  {Array.isArray(r?.scenarios) &&
                    r.scenarios.map((s: Data, j: number) => (
                      <p key={s?.id || j}>
                        {dimensions[s?.dimension] || "未指定角度"} ·{" "}
                        {String(s?.title || "未命名场景")} ·{" "}
                        {String(s?.engine || "")}
                      </p>
                    ))}
                  {r?.reason && <p>{String(r.reason)}</p>}
                </details>
              ))}
            <details
              className="console-disclosure"
              open={!Array.isArray(previewSpec?.requirements)}
            >
              <summary>编辑结构化方案</summary>
              <textarea
                className="design-spec-editor"
                aria-label="结构化测试方案"
                spellCheck={false}
                value={spec}
                disabled={!!busy}
                placeholder="导入方案，或由已配置的模型生成草稿"
                onChange={(e) => {
                  setSpec(e.target.value);
                  invalidate();
                }}
              />
            </details>
            <label className="local-option">
              <input
                type="checkbox"
                checked={scanners}
                disabled={!!busy}
                onChange={(e) => {
                  setScanners(e.target.checked);
                  invalidate();
                }}
              />
              同时执行适用的代码扫描
            </label>
            <button
              className="button primary"
              disabled={!!busy || !spec.trim() || !documents.length}
              onClick={() =>
                work("校验依据并生成测试", async () => {
                  const parsed = JSON.parse(spec);
                  parsed.scope = scope || parsed.scope;
                  parsed.environment = {
                    ...parsed.environment,
                    ...environment,
                  };
                  if (mode === "module") delete parsed.environment.entrypoint;
                  const p = await api("plan", {
                    repository: path,
                    documents,
                    specification: parsed,
                    include_scanners: scanners,
                    ...(draft ? { draft_id: draft } : {}),
                  });
                  setPlan(p);
                  setReviewed(false);
                  setStep("preview");
                })
              }
            >
              生成验收用例
            </button>
          </>
        )}
        {step === "preview" && plan && (
          <>
            <PlanDetails plan={plan} />
            {plan.blockers.length > 0 && (
              <div className="error-banner">
                {plan.blockers.map((x: Data) => (
                  <p key={x.id}>
                    {x.title}：{x.reason}
                  </p>
                ))}
              </div>
            )}
            <label className="local-option">
              <input
                type="checkbox"
                checked={reviewed}
                disabled={!!busy || !plan.ready}
                onChange={(e) => setReviewed(e.target.checked)}
              />
              已核对依据、预期结果和本次范围
            </label>
            <button
              className="button primary"
              disabled={!!busy || !reviewed || !plan.ready}
              onClick={() =>
                work("冻结方案并启动", async () => {
                  const r = await api("runs", {
                    plan_id: plan.id,
                    digest: plan.digest,
                  });
                  started(r.id);
                })
              }
            >
              <PlayCircle />
              按此方案执行
            </button>
          </>
        )}
        {busy && (
          <p role="status">
            <SpinnerGap className="spin" /> {busy}
          </p>
        )}
        {error && (
          <p className="error-banner" role="alert">
            {error}
          </p>
        )}
      </div>
    </Modal>
  );
}

export function PlanDetails({
  plan,
  run,
  openEvidence,
}: {
  plan: Data;
  run?: Data;
  openEvidence?: (id: string) => void;
}) {
  const [tab, setTab] = useState("coverage"),
    [selected, setSelected] = useState(""),
    [file, setFile] = useState("");
  if (plan.specification?.environment?.mode === "cli")
    return (
      <AutomaticPlanDetails plan={plan} run={run} openEvidence={openEvidence} />
    );
  const c = plan.cases.find((x: Data) => x.id === selected) || plan.cases[0];
  const code = file || Object.keys(plan.generated)[0];
  const result = (cid: string) => plannedCaseResult(run, cid);
  const state = (cid: string) =>
    (
      ({
        passed: "通过",
        failed: "失败",
        error: "异常",
        skipped: "跳过",
        running: "批次执行中",
        queued: "等待执行",
        cancelled: "已取消",
      }) as Record<string, string>
    )[result(cid)?.status] || (run ? "未取得结果" : "未执行");
  const evidence = (suffix: string) =>
    run?.artifacts.find((a: Data) => a.name.endsWith("/" + suffix));
  return (
    <section className="test-plan-detail">
      <div className="local-plan-heading">
        <strong>
          {
            plan.coverage.filter((x: Data) => x.disposition === "required")
              .length
          }{" "}
          项标准 · {plan.cases.length} 个生成用例
        </strong>
        <span>
          {plan.planner.kind === "model"
            ? plan.planner.connection?.verified
              ? modelLabel(plan.planner.connection)
              : "模型辅助设计"
            : "结构化规则生成"}
        </span>
      </div>
      <p>
        {plan.planner.kind === "model"
          ? plan.specification?.title || plan.name
          : plan.scope}
      </p>
      <CitationAdjustments planner={plan.planner} />
      {plan.planner.kind === "model" && (
        <details className="console-disclosure">
          <summary>原始设计请求</summary>
          <p>{plan.scope}</p>
        </details>
      )}
      <nav className="tabs" aria-label="方案详情">
        {[
          ["coverage", "标准与覆盖"],
          ["cases", "验收用例"],
          ["code", "测试代码"],
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
      {tab === "coverage" && (
        <div className="design-table-scroll">
          <table>
            <thead>
              <tr>
                <th>验收标准</th>
                <th>设计角度</th>
                <th>用例</th>
                <th>依据</th>
              </tr>
            </thead>
            <tbody>
              {plan.coverage.map((r: Data) => (
                <tr key={r.id}>
                  <td>
                    <strong>{r.title}</strong>
                    {r.disposition !== "required" && (
                      <small className="table-secondary">
                        {r.disposition === "excluded" ? "范围外" : "待确认"} ·{" "}
                        {r.reason}
                      </small>
                    )}
                  </td>
                  <td>
                    {r.dimensions
                      .map((d: string) => dimensions[d])
                      .join("、") || "—"}
                  </td>
                  <td>
                    <button
                      className="text-button"
                      disabled={!r.cases.length}
                      onClick={() => {
                        setSelected(r.cases[0]);
                        setTab("cases");
                      }}
                    >
                      {r.cases.length}
                    </button>
                  </td>
                  <td>
                    <details>
                      <summary>
                        {r.source.title}:{r.source.line}
                      </summary>
                      <blockquote>{r.source.quote}</blockquote>
                    </details>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
      {tab === "cases" && (
        <div className="design-cases">
          <aside>
            {plan.cases.map((item: Data) => (
              <button
                key={item.id}
                className={c?.id === item.id ? "selected" : ""}
                onClick={() => setSelected(item.id)}
              >
                <strong>{item.title}</strong>
                <small>
                  {item.id} · {dimensions[item.dimension]} · {state(item.id)}
                </small>
              </button>
            ))}
          </aside>
          {c && (
            <section>
              <h3>{c.title}</h3>
              <p>
                {c.priority} ·{" "}
                {(
                  {
                    module: "模块",
                    api: "接口",
                    browser: "浏览器",
                    openapi: "接口契约",
                  } as Record<string, string>
                )[c.engine] || c.engine}{" "}
                · {state(c.id)}
              </p>
              <blockquote>{c.source.quote}</blockquote>
              <p className="muted">
                {c.source.title}:{c.source.line} · {c.requirement}
              </p>
              {c.steps.map((s: Data, i: number) => (
                <div className="design-step" key={i}>
                  <strong>
                    {i + 1}.{" "}
                    {s.kind === "call"
                      ? `${s.module} → ${s.function}`
                      : s.kind === "http"
                        ? `${s.method} ${s.path}`
                        : `${s.kind} ${s.selector || s.value}`}
                  </strong>
                  {s.kind === "http" && <p>预期 HTTP {s.status}</p>}
                  {s.args && (
                    <p>
                      输入：<code>{JSON.stringify(s.args)}</code>
                    </p>
                  )}
                  {s.body != null && (
                    <p>
                      请求：<code>{JSON.stringify(s.body)}</code>
                    </p>
                  )}
                  {s.assertions?.map((a: Data, n: number) => (
                    <p key={n}>
                      预期 {a.pointer || "返回值"}{" "}
                      {(
                        {
                          equals: "等于",
                          contains: "包含",
                          schema: "符合结构",
                        } as Record<string, string>
                      )[a.operator] || a.operator}{" "}
                      <code>{JSON.stringify(a.value)}</code>
                    </p>
                  ))}
                </div>
              ))}
              {c.engine === "openapi" && (
                <p>
                  Schemathesis 根据冻结的 OpenAPI
                  生成合法、非法及边界请求。实际请求见工具报告。
                </p>
              )}
              {c.engine === "openapi" &&
                openEvidence &&
                result(c.id)?.report_ref && (
                  <button
                    className="button outline"
                    onClick={() => openEvidence(result(c.id).report_ref)}
                  >
                    查看契约验证报告
                  </button>
                )}
              {result(c.id)?.detail && <pre>{result(c.id).detail}</pre>}
              {openEvidence && evidence(c.id + "-trace.json") && (
                <button
                  className="button outline"
                  onClick={() =>
                    openEvidence(evidence(c.id + "-trace.json").id)
                  }
                >
                  查看步骤与实际结果
                </button>
              )}
            </section>
          )}
        </div>
      )}
      {tab === "code" && (
        <>
          <select
            aria-label="生成的测试文件"
            value={code || ""}
            onChange={(e) => setFile(e.target.value)}
          >
            {Object.keys(plan.generated).map((name) => (
              <option key={name}>{name}</option>
            ))}
          </select>
          <pre className="design-code">
            {plan.generated[code] || "尚未生成测试文件"}
          </pre>
          <p className="muted">
            <FileText /> 测试驱动与原始报告在证据中保留，代码未写入被测仓库。
          </p>
        </>
      )}
      {plan.planner.connection && (
        <details className="console-disclosure">
          <summary>模型调用记录</summary>
          <p>
            {plan.planner.connection.actual_model || "未记录实际型号"} ·{" "}
            {plan.planner.connection.reasoning_effort || "未记录强度"}
          </p>
          <p>
            {modelVerification(plan.planner.connection)}{" "}
            · {(plan.planner.connection.duration_ms / 1000).toFixed(1)} 秒
          </p>
          <p>
            客户端请求：
            <code>{plan.planner.connection.client_request_id || "未记录"}</code>
          </p>
          <p>
            网关请求：
            <code>{plan.planner.connection.server_request_id || "未记录"}</code>
          </p>
        </details>
      )}
      <details className="console-disclosure">
        <summary>执行检查与环境 · {plan.checks.length} 项</summary>
        <p>
          {plan.file_count} 个文件 · {plan.specification.environment.runtime} ·{" "}
          {plan.specification.environment.mode === "module"
            ? "模块函数"
            : "接口与页面服务"}
        </p>
        <p>一次性目标容器，测试驱动独立运行。</p>
        {plan.checks.map((check: Data) => (
          <p key={check.id}>
            {check.title} · {check.engine || check.tool || check.id}
          </p>
        ))}
      </details>
      {!!plan.exclusions.length && (
        <details className="console-disclosure">
          <summary>排除范围 · {plan.exclusions.length} 项</summary>
          {plan.exclusions.map((item: Data, index: number) => (
            <p key={index}>
              <strong>{item.subject}</strong>：{item.reason}
            </p>
          ))}
        </details>
      )}
    </section>
  );
}
