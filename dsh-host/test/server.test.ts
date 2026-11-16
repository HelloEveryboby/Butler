import { test } from "node:test";
import assert from "node:assert/strict";
import * as path from "node:path";
import { fileURLToPath } from "node:url";

import { FrameDecoder, encodeFrame } from "../src/codec.js";
import { frame, Frame } from "../src/protocol.js";
import { HostServer } from "../src/server.js";

const here = path.dirname(fileURLToPath(import.meta.url));
const FIXTURE = path.join(here, "fixtures", "plugin-demo.js");

/** 构造一个可驱动的 HostServer，收集其出站帧。 */
function makeServer() {
  const decoder = new FrameDecoder();
  const out: Frame[] = [];
  const server = new HostServer(
    { pluginPaths: [FIXTURE], approvalTimeoutMs: 2000 },
    (buf) => out.push(...decoder.push(buf)),
  );
  return { server, out };
}

function takeById(out: Frame[], id: string): Frame[] {
  return out.filter((f) => f.id === id);
}

test("启动即推送 registry.sync，风险分类就位", async () => {
  const { server, out } = makeServer();
  await server.start();

  const sync = out.find((f) => f.type === "registry.sync");
  assert.ok(sync, "registry.sync not sent");
  const payload = sync!.payload as { capabilities: Array<{ name: string; risk: string; description: string }> };
  const names = payload.capabilities.map((c) => c.name).sort();
  assert.deepEqual(names, ["demo.dangerous", "demo.echo", "demo.fail", "demo.stream"]);

  const byName = new Map(payload.capabilities.map((c) => [c.name, c]));
  // 设计要点：启发式分不出来的名字一律 `unknown` —— Go 侧对 unknown 的
  // 默认策略是 ask（fail-closed）。不猜风险，是刻意的保守行为。
  assert.equal(byName.get("demo.echo")!.risk, "unknown");
  assert.equal(byName.get("demo.dangerous")!.risk, "unknown");
  assert.ok(byName.get("demo.dangerous")!.description.length > 0); // 触发率保障
  assert.ok(byName.get("demo.echo")!.description.length > 0);
  await server.shutdown();
});

test("普通工具调用：invoke → result", async () => {
  const { server, out } = makeServer();
  await server.start();
  server.feed(encodeFrame(frame("call-1", "tool.invoke", {
    tool: "demo.echo",
    args: { text: "你好" },
  })));

  await new Promise((r) => setTimeout(r, 50));
  const frames = takeById(out, "call-1");
  const result = frames.find((f) => f.type === "tool.result");
  assert.ok(result, `no result, got: ${frames.map((f) => f.type)}`);
  assert.deepEqual((result!.payload as { content: unknown }).content, { echoed: "你好" });
  assert.equal(result!.done, true);
  await server.shutdown();
});

test("流式工具调用：chunk 序列 + 终止 result", async () => {
  const { server, out } = makeServer();
  await server.start();
  server.feed(encodeFrame(frame("call-2", "tool.invoke", { tool: "demo.stream" })));

  await new Promise((r) => setTimeout(r, 50));
  const frames = takeById(out, "call-2");
  const chunks = frames.filter((f) => f.type === "tool.chunk");
  assert.equal(chunks.length, 3);
  assert.ok(chunks.every((f) => f.stream === true));
  const seqs = chunks.map((c) => (c.payload as { seq: number }).seq);
  assert.deepEqual(seqs, [0, 1, 2]);
  assert.ok(frames.some((f) => f.type === "tool.result" && f.done === true));
  await server.shutdown();
});

test("工具抛错 → isError result，不上升为协议错误", async () => {
  const { server, out } = makeServer();
  await server.start();
  server.feed(encodeFrame(frame("call-3", "tool.invoke", { tool: "demo.fail" })));

  await new Promise((r) => setTimeout(r, 50));
  const result = takeById(out, "call-3").find((f) => f.type === "tool.result");
  assert.ok(result);
  const payload = result!.payload as { isError: boolean; content: { error: string } };
  assert.equal(payload.isError, true);
  assert.match(payload.content.error, /intentional failure/);
  await server.shutdown();
});

test("未知工具 → unknown_tool 错误帧", async () => {
  const { server, out } = makeServer();
  await server.start();
  server.feed(encodeFrame(frame("call-4", "tool.invoke", { tool: "nope" })));

  await new Promise((r) => setTimeout(r, 50));
  const err = takeById(out, "call-4").find((f) => f.type === "error");
  assert.ok(err);
  assert.equal(err!.error?.code, "unknown_tool");
  await server.shutdown();
});

test("参数校验：缺 required 参数 → isError", async () => {
  const { server, out } = makeServer();
  await server.start();
  server.feed(encodeFrame(frame("call-5", "tool.invoke", { tool: "demo.echo", args: {} })));

  await new Promise((r) => setTimeout(r, 50));
  const result = takeById(out, "call-5").find((f) => f.type === "tool.result");
  assert.ok(result);
  assert.equal((result!.payload as { isError: boolean }).isError, true);
  await server.shutdown();
});

test("审批桥：approve.ask → approve.answer → 工具拿到结论", async () => {
  const { server, out } = makeServer();
  await server.start();
  server.feed(encodeFrame(frame("call-6", "tool.invoke", { tool: "demo.dangerous" })));

  await new Promise((r) => setTimeout(r, 50));
  const ask = out.find((f) => f.type === "approve.ask");
  assert.ok(ask, "approve.ask not sent");
  const req = ask!.payload as { requestId: string; tool: string };
  assert.equal(req.tool, "demo.dangerous");

  server.feed(encodeFrame(frame(req.requestId, "approve.answer", {
    requestId: req.requestId,
    allowed: true,
    reason: "operator approved",
  })));

  await new Promise((r) => setTimeout(r, 50));
  const result = takeById(out, "call-6").find((f) => f.type === "tool.result");
  assert.ok(result);
  assert.deepEqual((result!.payload as { content: { approved: boolean } }).content, { approved: true });
  await server.shutdown();
});

test("审批超时按拒绝处理（fail-closed）", async () => {
  const { server, out } = makeServer();
  await server.start();
  server.feed(encodeFrame(frame("call-7", "tool.invoke", { tool: "demo.dangerous" })));

  // 不回 approve.answer，等 approvalTimeoutMs=2000 超时
  await new Promise((r) => setTimeout(r, 2300));
  const result = takeById(out, "call-7").find((f) => f.type === "tool.result");
  assert.ok(result);
  assert.deepEqual((result!.payload as { content: { approved: boolean } }).content, { approved: false });
  await server.shutdown();
});

test("未知帧类型 → unsupported 应答（禁止静默丢弃）", async () => {
  const { server, out } = makeServer();
  await server.start();
  server.feed(encodeFrame({ v: 1, id: "x-1", type: "weird.frame" as never, ts: Date.now() }));

  await new Promise((r) => setTimeout(r, 50));
  const err = takeById(out, "x-1").find((f) => f.type === "error");
  assert.ok(err);
  assert.equal(err!.error?.code, "unsupported");
  await server.shutdown();
});
