import type { PipelineStage, Run } from "./types";

export const stageDefinitions = [
  {
    id: "baseline",
    title: "基线校验",
    tool: "冻结输入",
    work: "核对标准、测试集、目标与策略的摘要",
  },
  {
    id: "cases",
    title: "用例登记",
    tool: "已登记用例",
    work: "核对已有检查的编号、标准、执行器与层级，保存用例清单",
  },
  {
    id: "L1",
    title: "代码检查",
    tool: "L1 · Bandit",
    work: "扫描静态样本中的 Shell 调用风险",
  },
  {
    id: "L2",
    title: "接口验证",
    tool: "L2 · Playwright",
    work: "验证健康接口、权限、会话、幂等与字段类型",
  },
  {
    id: "L3",
    title: "页面验证",
    tool: "L3 · Playwright / axe",
    work: "验证保存后刷新与表单可访问名称",
  },
  {
    id: "L4",
    title: "性能与恢复",
    tool: "L4 · PostgreSQL",
    work: "核对大文件传输、备份恢复及未覆盖的性能要求",
  },
  {
    id: "cleanup",
    title: "环境清理",
    tool: "Docker",
    work: "回收本次临时容器与网络",
  },
  {
    id: "findings",
    title: "缺陷归纳",
    tool: "结果与证据",
    work: "把失败检查关联到标准、用例与原始证据",
  },
  {
    id: "gate",
    title: "验收判定",
    tool: "OPA",
    work: "核对必验项和证据完整性，输出最终结论",
  },
];

export function pipeline(run: Run) {
  if (run.display_stages) return run.display_stages.map(s=>s.id==='review'&&run.finding_counts?{...s,detail:`已确认缺陷 ${run.finding_counts.confirmed} · 待复核 ${run.finding_counts.needs_review} · 工具误报 ${run.finding_counts.false_positive} · 用例问题 ${run.finding_counts.test_issue}；合并重复 ${run.finding_counts.duplicates} 条`}:s);
  const terminal = ["completed", "error"].includes(run.status);
  return stageDefinitions
    .filter(
      (s) =>
        (s.id !== "cleanup" || run.baseline.recipe) &&
        (s.id !== "L4" ||
          run.baseline.recipe ||
          run.baseline.criteria.some((c) => c.layer === "L4")),
    )
    .map((original) => {
      const definition =
        run.project_id && !run.baseline.recipe && original.id === "L1"
          ? {
              ...original,
              title: "业务回归",
              tool: "L1 · Node.js",
              work: "在隔离容器运行已登记测试，核对原始 JUnit 与测试清单",
            }
          : run.baseline.recipe && original.id.startsWith("L")
            ? {
                ...original,
                tool: (
                  {
                    L1: "构建 / Node / unittest / 安全扫描",
                    L2: "Node / PostgreSQL",
                    L3: run.baseline.exclusions
                      ? "Playwright / axe / ZAP"
                      : "Playwright / axe",
                    L4: run.baseline.exclusions
                      ? "k6 / 备份恢复"
                      : "pg_dump / pg_restore",
                  } as Record<string, string>
                )[original.id],
                work:
                  run.pipeline?.find((s) => s.id === original.id)?.detail ||
                  original.work,
              }
            : original;
      const excluded =
        original.id.startsWith("L") &&
        !run.baseline.criteria.some((c) => c.layer === original.id);
      let record: PipelineStage | undefined = run.pipeline?.find(
        (s) => s.id === definition.id,
      );
      if (!record && run.pipeline === undefined) {
        // Historical records contain actual layer timestamps, but no phase timers.
        const layer = run.layers.find((l) => l.id === definition.id);
        const timing = run.layer_runs?.find((l) => l.layer === definition.id);
        if (layer && timing)
          record = {
            id: definition.id,
            status: layer.status,
            ...timing,
            detail: `${layer.count} 项结果 · ${layer.failed} 项失败`,
          };
        else if (["baseline", "cases"].includes(definition.id))
          record = {
            id: definition.id,
            status: "recorded",
            detail: "已绑定冻结输入；历史记录未单独采集该阶段时间",
          };
        else if (definition.id === "findings" && terminal)
          record = {
            id: definition.id,
            status: "recorded",
            detail: `记录 ${run.findings.length} 条缺陷；未单独采集归纳时间`,
          };
        else if (
          definition.id === "gate" &&
          run.artifacts.some((a) => a.name === "gate-result.json")
        )
          record = {
            id: definition.id,
            status:
              run.decision === "allow"
                ? "passed"
                : run.decision === "reject"
                  ? "failed"
                  : "error",
            detail: run.reasons[0] || "查看原始门禁结果",
          };
      }
      return {
        ...definition,
        status: terminal || excluded ? "not_run" : "queued",
        detail: excluded
          ? "不在本次验收范围"
          : terminal
            ? "此阶段没有执行记录"
            : definition.work,
        ...record,
      };
    });
}

export function seconds(ms?: number) {
  if (ms === undefined || !Number.isFinite(ms)) return "未记录";
  if (ms > 0 && ms < 10) return "<0.01 s";
  return (ms / 1000).toFixed(ms < 1000 ? 2 : 1) + " s";
}
export function elapsed(
  start?: string,
  end?: string | null,
  clock = Date.now(),
) {
  if (!start) return undefined;
  const value = (end ? Date.parse(end) : clock) - Date.parse(start);
  return Number.isFinite(value) ? Math.max(0, value) : undefined;
}
export function stageDuration(
  stage: PipelineStage,
  legacy: boolean,
  clock = Date.now(),
) {
  if (stage.status === "running" && stage.started_at)
    return elapsed(stage.started_at, null, clock);
  if (stage.duration_ms !== undefined) return stage.duration_ms;
  if (stage.status === "running") return elapsed(stage.started_at, null, clock);
  if (legacy && stage.finished_at)
    return elapsed(stage.started_at, stage.finished_at);
  return undefined;
}
export function clockTime(value?: string | null) {
  return value
    ? new Date(value).toLocaleTimeString("zh-CN", {
        hour: "2-digit",
        minute: "2-digit",
        second: "2-digit",
        hour12: false,
        fractionalSecondDigits: 3,
      })
    : "未记录";
}
export function stageLabel(status: string, id?: string) {
  if (status === "recorded") return "已记录";
  if (status === "failed") return id === "gate" ? "未通过" : "检查失败";
  if (status === "passed") return id === "gate" ? "通过" : "成功";
  return (
    {
      running: "执行中",
      queued: "等待中",
      error: "执行异常",
      blocked: "未完成",
      not_run: "未执行",
    }[status] || status
  );
}
