type Data = Record<string, any>;
export function caseForResult(run: Data, task: Data, test: Data) {
  const exact = run.test_plan?.cases.find((c: Data) => c.name === test.name);
  if (exact) return exact;
  const check = run.test_plan?.checks.find(
    (c: Data) => c.id === task.id && c.engine === "openapi",
  );
  return (
    check &&
    run.test_plan.cases.find((c: Data) => check.case_ids.includes(c.id))
  );
}
export function plannedCaseResult(run: Data | undefined, cid: string) {
  if (!run?.test_plan) return null;
  const check = run.test_plan.checks.find((c: Data) =>
    c.case_ids?.includes(cid),
  );
  const task = run.tasks.find((t: Data) => t.id === check?.id);
  if (!task) return null;
  if (task.state !== "completed")
    return { status: task.state, detail: task.error || "" };
  if (check.engine !== "openapi")
    return (
      task.report?.tests.find((x: Data) => x.name === "test_" + cid) || null
    );
  const tests = task.report?.tests || [];
  if (!tests.length) return null;
  return {
    status: tests.some((t: Data) => ["failed", "error"].includes(t.status))
      ? "failed"
      : tests.every((t: Data) => t.status === "passed")
        ? "passed"
        : "error",
    detail: tests
      .filter((t: Data) => t.status !== "passed")
      .map((t: Data) => t.name + "\n" + t.detail)
      .join("\n"),
    report_ref: task.report_ref,
  };
}
