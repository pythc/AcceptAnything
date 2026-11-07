import type { Run } from "./types";
import { elapsed } from "./pipeline.ts";

export function checkProgress(run: Run, id: string, clock = Date.now()) {
  const result = run.results.find((r) => r.criterion_id === id);
  const recorded = run.check_runs
    ?.slice()
    .reverse()
    .find((r) => r.criterion_id === id);
  if (result)
    return {
      status: result.status,
      duration:
        (recorded?.finished_at ? recorded.duration_ms : undefined) ??
        run.inspections?.[id]?.duration_ms ??
        result.duration_ms,
      batch: false,
    };
  if (recorded)
    return {
      status:
        recorded.status === "running" &&
        !["queued", "running"].includes(run.status)
          ? "error"
          : recorded.status,
      duration:
        recorded.status === "running" && run.status === "running"
          ? elapsed(recorded.started_at, null, clock)
          : (recorded.duration_ms ?? undefined),
      batch: !!recorded.batch,
    };
  return {
    status: ["queued", "running"].includes(run.status) ? "queued" : "not_run",
    duration: undefined,
    batch: false,
  };
}
