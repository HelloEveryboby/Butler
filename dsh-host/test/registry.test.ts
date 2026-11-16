import { test } from "node:test";
import assert from "node:assert/strict";
import * as fs from "node:fs";
import * as path from "node:path";
import { fileURLToPath } from "node:url";

import { ToolRegistry } from "../src/registry.js";
import { Capability } from "../src/protocol.js";

function cap(name: string, source = "p"): Capability {
  return { name, description: `tool ${name}`, risk: "read_only", source };
}

test("upsert / snapshot 排序稳定", () => {
  const r = new ToolRegistry();
  r.upsert(cap("b"), cap("a"));
  const snap = r.snapshot();
  assert.deepEqual(snap.capabilities.map((c) => c.name), ["a", "b"]);
});

test("diffSince 增量语义", () => {
  const r = new ToolRegistry();
  r.upsert(cap("a"));
  const v2 = r.upsert(cap("b"));
  r.remove("a");
  r.upsert(cap("c"));

  const diff = r.diffSince(v2);
  assert.ok(diff);
  assert.deepEqual(diff.upserts?.map((c) => c.name), ["c"]);
  assert.deepEqual(diff.removals, ["a"]);
});

test("diffSince 来自未来要求 resync", () => {
  const r = new ToolRegistry();
  r.upsert(cap("a"));
  assert.equal(r.diffSince(r.getVersion() + 10), null);
});

test("replace 全量重同步", () => {
  const r = new ToolRegistry();
  r.upsert(cap("old1"), cap("old2"));
  const v = r.replace([cap("new1")]);
  assert.equal(r.size(), 1);
  const diff = r.diffSince(v - 1);
  assert.ok(diff);
  assert.ok(diff.removals?.includes("old1"));
});

test("无效能力被拒", () => {
  const r = new ToolRegistry();
  assert.throws(() => r.upsert({ name: "", description: "d", risk: "read_only", source: "p" }));
  assert.equal(r.size(), 0);
});

// ---- 跨语言契约：与 Go 侧 golden fixture 语义一致 ----

test("与 Go golden fixture 语义一致（跨语言线格式契约）", () => {
  const here = path.dirname(fileURLToPath(import.meta.url));
  const goldenPath = path.resolve(
    here,
    "../../../connector/internal/proto/testdata/golden_tool_invoke.json",
  );
  const golden = JSON.parse(fs.readFileSync(goldenPath, "utf8")) as {
    v: number;
    id: string;
    type: string;
    payload: { tool: string; args: Record<string, unknown>; risk: string; timeoutMs: number };
    ts: number;
  };

  // Go 侧编码的帧必须能被 TS 解码器语义还原（字段名/枚举值/嵌套结构一致）。
  assert.equal(golden.v, 1);
  assert.equal(golden.id, "call-42");
  assert.equal(golden.type, "tool.invoke");
  assert.equal(golden.payload.tool, "greet");
  assert.deepEqual(golden.payload.args, { name: "张三" });
  assert.equal(golden.payload.risk, "read_only");
  assert.equal(golden.payload.timeoutMs, 5000);

  // 反向：TS 编码的同内容帧，Go 侧 JSON 解析必须无未知字段（v1 冻结）。
  const allowedTop = new Set(["v", "id", "type", "stream", "done", "payload", "error", "ts"]);
  for (const key of Object.keys(golden)) {
    assert.ok(allowedTop.has(key), `golden top-level field "${key}" outside frozen v1 contract`);
  }
});
