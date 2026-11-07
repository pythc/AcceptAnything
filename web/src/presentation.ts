import type { Artifact, Finding, Inspection, Run } from "./types";

export function findingSummary(finding: Finding, detail?: Inspection) {
  if (
    finding.review_state === "confirmed" &&
    /TS2322/.test(finding.actual) &&
    /event\.type as string/.test(finding.review?.reason || "")
  )
    return "日志事件类型与字段定义不一致，导致 TypeScript 编译失败。";
  return (
    finding.review?.reason || detail?.summary || finding.actual.split("\n")[0]
  );
}

// Presentation only: keep the recorded finding, diagnostic and evidence unchanged.
export function findingLocation(finding: Finding, detail?: Inspection) {
  if (detail?.location) return detail.location;
  const diagnostic = finding.actual.match(
    /((?:[\w.@-]+\/)+[\w.@-]+)\((\d+),\d+\)/,
  );
  if (diagnostic) {
    const source = finding.review?.rows.find((r) =>
      r.path?.endsWith(diagnostic[1]),
    );
    return `${source?.path || diagnostic[1]}:${diagnostic[2]}`;
  }
  const location = finding.actual.match(/((?:[\w.@-]+\/)+[\w.@-]+:\d+)/);
  return location?.[1] || finding.review?.rows.find((r) => r.path)?.path || "";
}

export function findingTitle(finding: Finding, run: Run) {
  if (/[\u4e00-\u9fff]/.test(finding.title)) return finding.title;
  if (finding.title === "production_typescript_build")
    return /Logs\.tsx.*TS2322/s.test(finding.actual)
      ? "日志类型不匹配，生产构建失败"
      : "TypeScript 类型检查失败，生产构建失败";
  const rule = finding.actual.match(/(?:^|\n)(B405|B314|B101)(?:\n|$)/)?.[1];
  const ruleTitles: Record<string, string> = {
    B405: "XML 解析模块命中安全规则",
    B314: "XML 解析调用命中安全规则",
    B101: "assert 语句命中扫描规则",
  };
  if (rule) return ruleTitles[rule];
  const criterion = run.baseline.criteria.find(
    (c) => c.id === finding.criterion_id,
  );
  return criterion
    ? `${criterion.title} · ${findingLocation(finding).split(/[:/]/).filter(Boolean).slice(-2).join(":") || finding.id}`
    : finding.title;
}

export function isReusedStage(stage: { id: string; detail: string }) {
  return (
    stage.id === "design" && /复用已确认|不是本次重新调用/.test(stage.detail)
  );
}

export function evidenceGroup(artifact: Artifact, run: Run) {
  const criterion = run.baseline.criteria.find(
    (c) => c.id === artifact.criterion_id,
  );
  if (criterion) return { id: criterion.id, title: criterion.title };
  if (
    ["source-context.json", "source-manifest.json", "remote-source.json"].includes(artifact.name) ||
    artifact.name.startsWith("frozen-") ||
    [...(run.project_inputs || []), ...(run.recipe_inputs || [])].some(
      (x) => x.ref === artifact.id,
    )
  )
    return { id: "_input", title: "输入与版本" };
  return { id: "_run", title: "本次验收与门禁" };
}

export function evidenceCommand(artifact: Artifact | undefined, run: Run) {
  if (!artifact) return undefined;
  return (
    run.commands?.find((c) => c.evidence_ref === artifact.id) ||
    (artifact.criterion_id
      ? run.commands?.find((c) => c.name === artifact.criterion_id)
      : undefined)
  );
}
