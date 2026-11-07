import test from "node:test";
import assert from "node:assert/strict";
import { checkProgress } from "../src/checkProgress.ts";

test("running elapsed comes from a recorded check, not the first missing result", () => {
  const run = {
    status: "running",
    results: [],
    check_runs: [
      {
        criterion_id: "B",
        status: "running",
        started_at: "2026-10-17T00:00:00Z",
        finished_at: null,
        batch: true,
      },
    ],
  };
  assert.equal(checkProgress(run, "A").status, "queued");
  assert.deepEqual(
    checkProgress(run, "B", Date.parse("2026-10-17T00:00:03Z")),
    { status: "running", duration: 3000, batch: true },
  );
  assert.deepEqual(run.results, []);
});
test("final results take precedence and stale running rows never imply continued execution", () => {
  const run = {
    status: "completed",
    results: [{ criterion_id: "A", status: "failed", duration_ms: 25 }],
    check_runs: [
      { criterion_id: "A", status: "running" },
      { criterion_id: "B", status: "running" },
    ],
  };
  assert.equal(checkProgress(run, "A").status, "failed");
  assert.equal(checkProgress(run, "A").duration, 25);
  assert.equal(checkProgress(run, "B").status, "error");
  assert.equal(checkProgress(run, "C").status, "not_run");
});

test("composite check uses its measured interval rather than the final read probe", () => {
  const run = {
    status: "incomplete",
    results: [{ criterion_id: "RESTORE", status: "passed", duration_ms: 290 }],
    check_runs: [
      {
        criterion_id: "RESTORE",
        status: "passed",
        finished_at: "2026-10-18T00:00:11Z",
        duration_ms: 10400,
      },
    ],
    inspections: { RESTORE: { duration_ms: 10180 } },
  };
  assert.equal(checkProgress(run, "RESTORE").duration, 10400);
  delete run.check_runs[0].finished_at;
  assert.equal(checkProgress(run, "RESTORE").duration, 10180);
  assert.equal(run.results[0].duration_ms, 290);
});
