import test from "node:test";
import assert from "node:assert/strict";
import { findingPriority } from "../src/priority.ts";

test("explicit priority takes precedence over scanner severity, including a confirmed P0", () => {
  for (const level of ["P0", "P1", "P2", "P3"]) {
    assert.deepEqual(findingPriority({ priority: level, severity: "medium" }), {
      level,
      suggested: false,
    });
  }
});

test("severity supplies suggestions rather than claiming triage or inferring P0", () => {
  for (const [severity, level] of [
    ["critical", "P1"],
    ["high", "P1"],
    ["medium", "P2"],
    ["low", "P3"],
    ["info", "P3"],
  ]) {
    const input = Object.freeze({ severity });
    assert.deepEqual(findingPriority(input), { level, suggested: true });
    assert.deepEqual(input, { severity });
  }
  assert.deepEqual(findingPriority({ severity: " MEDIUM " }), {
    level: "P2",
    suggested: true,
  });
});

test("missing or unknown grades and execution states are not invented priorities", () => {
  for (const severity of [
    undefined,
    null,
    "",
    "failed",
    "error",
    "unknown",
    "__proto__",
    "constructor",
    2,
  ]) {
    assert.deepEqual(findingPriority({ severity }), {
      level: undefined,
      suggested: false,
    });
  }
  for (const priority of ["P9", "p0", "P1 urgent", null, 1]) {
    assert.deepEqual(findingPriority({ priority, severity: "medium" }), {
      level: "P2",
      suggested: true,
    });
  }
});
