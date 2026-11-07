import { useState } from "react";
import { modelLabel } from "./modelLabel";
import { CitationAdjustments } from "./CitationAdjustments";
type Data = Record<string, any>;
const labels: Record<string, string> = {
  normal: "正常",
  boundary: "边界",
  error: "异常",
  state: "状态",
};
export function AutomaticPlanDetails({
  plan,
  run,
  openEvidence,
}: {
  plan: Data;
  run?: Data;
  openEvidence?: (id: string) => void;
}) {
  const [selected, setSelected] = useState("");
  const requirements = plan.specification.requirements;
  const cases = requirements.flatMap((q: Data) =>
    q.scenarios.map((s: Data) => ({ ...s, requirement: q })),
  );
  const current = cases.find((s: Data) => s.id === selected) || cases[0];
  const tasks = run?.tasks || run?.native_integration?.tasks || [];
  const task = tasks.find((t: Data) => t.tool === "auto-go-business");
  const result = (id: string) =>
    task?.report?.tests.find((t: Data) => t.name.startsWith(id + " · "));
  const state = (id: string) =>
    ({ passed: "通过", failed: "失败", error: "异常" })[
      result(id)?.status as string
    ] || (task?.state === "running" ? "执行中" : "未执行");
  const evidence = run?.artifacts?.find(
    (a: Data) => a.name === "auto-business/cases.json",
  );
  return (
    <section className="test-plan-detail">
      <div className="local-plan-heading">
        <strong>
          {requirements.length} 项标准 · {cases.length} 个中文用例
        </strong>
        <span>{modelLabel(plan.planner?.connection)}</span>
      </div>
      <p>{plan.specification.scope}</p>
      <CitationAdjustments planner={plan.planner} />
      <div className="design-cases">
        <aside>
          {cases.map((s: Data) => (
            <button
              key={s.id}
              className={s.id === current?.id ? "selected" : ""}
              onClick={() => setSelected(s.id)}
            >
              <strong>{s.title}</strong>
              <small>
                {labels[s.dimension]} · {state(s.id)}
              </small>
            </button>
          ))}
        </aside>
        {current && (
          <section>
            <h3>{current.title}</h3>
            <p>{current.rationale}</p>
            <blockquote>{current.requirement.quote}</blockquote>
            <p className="muted">
              依据：{current.requirement.source} · {current.requirement.title}
            </p>
            <div className="design-step">
              <strong>输入</strong>
              <pre>
                {JSON.stringify(
                  { argv: current.argv, stdin: current.stdin },
                  null,
                  2,
                )}
              </pre>
            </div>
            <div className="design-step">
              <strong>独立预期</strong>
              <pre>
                {JSON.stringify(
                  {
                    stdout: current.stdout,
                    stderr_contains: current.stderr_contains,
                    exit_code: current.exit_code,
                    comparison: current.comparison,
                  },
                  null,
                  2,
                )}
              </pre>
            </div>
            <p>实际结果：{state(current.id)}</p>
            {result(current.id)?.detail && (
              <pre>{result(current.id).detail}</pre>
            )}
            {evidence && openEvidence && (
              <button
                className="button outline"
                onClick={() => openEvidence(evidence.id)}
              >
                查看全部输入、输出与结果
              </button>
            )}
          </section>
        )}
      </div>
      {requirements
        .filter((q: Data) => q.disposition !== "required")
        .map((q: Data) => (
          <p key={q.id}>
            {q.disposition === "unresolved" ? "待确认" : "范围外"}：{q.title} ·{" "}
            {q.reason}
          </p>
        ))}
      <details className="console-disclosure">
        <summary>独立依据原文</summary>
        {plan.documents.map((d: Data) => (
          <section key={d.id}>
            <strong>{d.title}</strong>
            <small>{d.origin}</small>
            <pre>{d.content}</pre>
          </section>
        ))}
      </details>
    </section>
  );
}
