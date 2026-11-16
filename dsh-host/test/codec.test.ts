import { test } from "node:test";
import assert from "node:assert/strict";

import { FrameDecoder, encodeFrame } from "../src/codec.js";
import { frame, Frame, ProtoError } from "../src/protocol.js";

test("编码-解码 round-trip", () => {
  const dec = new FrameDecoder();
  const f = frame("call-1", "tool.invoke", { tool: "doc-reader", args: { path: "r.pdf" } });
  const out = dec.push(encodeFrame(f));
  assert.equal(out.length, 1);
  assert.equal(out[0]!.id, "call-1");
  assert.equal(out[0]!.type, "tool.invoke");
  assert.equal(out[0]!.v, 1);
});

test("跨 chunk 碎片边界正确还原帧", () => {
  const dec = new FrameDecoder();
  const f1 = frame("a", "health.ping");
  const f2 = frame("b", "health.pong");
  const wire = Buffer.concat([encodeFrame(f1), encodeFrame(f2)]);

  // 逐字节喂入 —— 最极端的碎片化
  const collected: Frame[] = [];
  for (let i = 0; i < wire.length; i++) {
    collected.push(...dec.push(wire.subarray(i, i + 1)));
  }
  assert.equal(collected.length, 2);
  assert.equal(collected[0]!.id, "a");
  assert.equal(collected[1]!.id, "b");

  // 随机切分（固定种子的代表性切分点）
  const dec2 = new FrameDecoder();
  const cuts = [3, 7, 20, wire.length];
  const got: Frame[] = [];
  let prev = 0;
  for (const c of cuts) {
    got.push(...dec2.push(wire.subarray(prev, c)));
    prev = c;
  }
  assert.equal(got.length, 2);
});

test("零长帧被拒", () => {
  const dec = new FrameDecoder();
  assert.throws(
    () => dec.push(Buffer.from([0, 0, 0, 0])),
    (e: unknown) => e instanceof ProtoError && e.code === "malformed_frame",
  );
});

test("超限帧被拒", () => {
  const dec = new FrameDecoder();
  assert.throws(
    () => dec.push(Buffer.from([0xff, 0xff, 0xff, 0xff])),
    (e: unknown) => e instanceof ProtoError && e.code === "malformed_frame",
  );
});

test("非 JSON 帧体被拒", () => {
  const dec = new FrameDecoder();
  const body = Buffer.from("xxxxx");
  const wire = Buffer.concat([Buffer.from([0, 0, 0, body.length]), body]);
  assert.throws(
    () => dec.push(wire),
    (e: unknown) => e instanceof ProtoError && e.code === "malformed_frame",
  );
});

test("协议版本不符被拒", () => {
  const dec = new FrameDecoder();
  const body = Buffer.from(JSON.stringify({ v: 99, id: "x", type: "health.ping", ts: 1 }));
  const wire = Buffer.concat([Buffer.from([0, 0, 0, body.length]), body]);
  assert.throws(
    () => dec.push(wire),
    (e: unknown) => e instanceof ProtoError && e.code === "unsupported",
  );
});

test("缺 id/type 被拒", () => {
  const dec = new FrameDecoder();
  const body = Buffer.from(JSON.stringify({ v: 1, ts: 1 }));
  const wire = Buffer.concat([Buffer.from([0, 0, 0, body.length]), body]);
  assert.throws(
    () => dec.push(wire),
    (e: unknown) => e instanceof ProtoError && e.code === "malformed_frame",
  );
});

test("编码超限帧被拒", () => {
  const f = frame("x", "tool.result", { blob: "x".repeat(17 << 20) });
  assert.throws(
    () => encodeFrame(f),
    (e: unknown) => e instanceof ProtoError && e.code === "malformed_frame",
  );
});
