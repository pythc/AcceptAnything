import test from "node:test";
import assert from "node:assert/strict";
import {
  findingLocation,
  findingTitle,
  isReusedStage,
  evidenceCommand,
  evidenceGroup,
} from "../src/presentation.ts";

test("compiler locations are derived from diagnostics and bound source paths, never invented", () => {
  const f = {
    actual: "src/pages/Logs.tsx(73,9): error TS2322",
    review: {
      rows: [{ path: "web/package.json" }, { path: "web/src/pages/Logs.tsx" }],
    },
  };
  assert.equal(findingLocation(f), "web/src/pages/Logs.tsx:73");
  assert.equal(findingLocation({ actual: "No source recorded" }), "");
  assert.equal(
    findingLocation(f, { location: "recorded.ts:12" }),
    "recorded.ts:12",
  );
});

test("translated build titles require the matching diagnostic; original data stays unchanged", () => {
  const f = Object.freeze({
    title: "production_typescript_build",
    actual: "src/pages/Logs.tsx(73,9): error TS2322",
  });
  assert.equal(
    findingTitle(f, { baseline: { criteria: [] } }),
    "日志类型不匹配，生产构建失败",
  );
  assert.equal(
    findingTitle(
      { ...f, actual: "other.ts(1,1): error TS1005" },
      { baseline: { criteria: [] } },
    ),
    "TypeScript 类型检查失败，生产构建失败",
  );
  assert.equal(f.title, "production_typescript_build");
});

test("only explicit reuse evidence hides a historical model duration", () => {
  assert.equal(
    isReusedStage({
      id: "design",
      detail: "复用已确认模型方案；不是本次重新调用",
    }),
    true,
  );
  assert.equal(
    isReusedStage({ id: "design", detail: "模型正在设计用例" }),
    false,
  );
  assert.equal(
    isReusedStage({ id: "L2", detail: "复用已确认接口数据" }),
    false,
  );
});

test("artifact command binding uses exact criterion IDs and direct evidence references", () => {
  const commands = [
    { name: "build-old", argv: ["old"] },
    { name: "build", argv: ["real"] },
    { name: "other", evidence_ref: "direct", argv: ["direct"] },
  ];
  assert.equal(
    evidenceCommand({ id: "report", criterion_id: "build" }, { commands }),
    commands[1],
  );
  assert.equal(
    evidenceCommand({ id: "direct", criterion_id: "build" }, { commands }),
    commands[2],
  );
  assert.equal(
    evidenceCommand({ id: "unknown", criterion_id: "missing" }, { commands }),
    undefined,
  );
});

test("evidence groups preserve criterion context and distinguish frozen input from gate output", () => {
  const run = {
    baseline: { criteria: [{ id: "api", title: "接口用例" }] },
    recipe_inputs: [{ ref: "source" }],
  };
  assert.deepEqual(evidenceGroup({ id: "report", criterion_id: "api" }, run), {
    id: "api",
    title: "接口用例",
  });
  assert.equal(
    evidenceGroup({ id: "source", name: "requirements.md" }, run).id,
    "_input",
  );
  assert.equal(evidenceGroup({ id: "remote", name: "remote-source.json" }, run).id, "_input");
  assert.equal(
    evidenceGroup({ id: "gate", name: "gate-result.json" }, run).id,
    "_run",
  );
});
