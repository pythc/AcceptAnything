import type { Run } from "./types";
import { checkProgress } from "./checkProgress.ts";

// Presentation only: keep the recorded verdict and every planned check intact.
export function focusChecks(run: Run, clock = Date.now()) {
  const rows = run.baseline.criteria.map((criterion) => ({
    criterion,
    ...checkProgress(run, criterion.id, clock),
  }));
  const rank: Record<string, number> = {
    failed: 0,
    error: 1,
    blocked: 2,
    running: 3,
  };
  return {
    all: rows,
    attention: rows
      .filter((row) => row.status !== "passed")
      .sort((a, b) => (rank[a.status] ?? 4) - (rank[b.status] ?? 4)),
    completed: rows.filter((row) => row.status === "passed"),
  };
}

export function acceptanceVerdict(run: Run) {
  if (["queued", "running"].includes(run.status))
    return {
      title: run.status === "queued" ? "等待验收" : "正在验收",
      label: "尚未判定",
      status: run.status,
    };
  if (run.status === "incomplete" || run.completion?.complete === false)
    return { title: "验收未完成", label: "不可放行", status: "blocked" };
  if (run.decision === "allow")
    return {
      title: "所选范围验收通过",
      label: "所选基线通过",
      status: "passed",
    };
  if (run.decision === "reject")
    return { title: "验收未通过", label: "不可放行", status: "failed" };
  return { title: "验收结论待确认", label: "无法下结论", status: "blocked" };
}

export function acceptanceSummary(run: Run) {
  if (["queued", "running"].includes(run.status))
    return "正在按冻结范围执行验证，最终结论尚未形成。";
  if (run.status === "incomplete" || run.completion?.complete === false)
    return "必验范围尚未完成，请先查看未完成项与原始证据。";
  if (run.decision === "reject")
    return "检查未满足本次验收标准，请查看需要处理的结果。";
  if (run.decision === "allow")
    return "本次冻结范围内的检查通过；结论不扩展到未覆盖的功能。";
  return "现有结果不足以形成验收结论，请查看覆盖缺口与判定依据。";
}
