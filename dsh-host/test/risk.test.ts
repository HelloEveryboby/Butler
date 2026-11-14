import { test } from "node:test";
import assert from "node:assert/strict";

import { RiskClassifier, globMatch } from "../src/risk.js";

test("显式声明优先于一切", () => {
  const c = new RiskClassifier({ rules: [{ tool: "shell.*", risk: "read_only" }] });
  assert.equal(c.classify("shell.exec", "execute"), "execute");
});

test("配置规则优先于启发式", () => {
  const c = new RiskClassifier({ rules: [{ tool: "fs.export", risk: "read_only" }] });
  assert.equal(c.classify("fs.export"), "read_only");
  assert.equal(c.classify("fs.write"), "write"); // 启发式接管
});

test("启发式分类", () => {
  const c = new RiskClassifier();
  assert.equal(c.classify("shell.exec"), "execute");
  assert.equal(c.classify("fs.write"), "write");
  assert.equal(c.classify("plugin.delete_files"), "write");
  assert.equal(c.classify("web.fetch"), "network");
  assert.equal(c.classify("doc-reader.parse"), "read_only");
});

test("分不出来归 unknown（交给 Go 侧 fail-closed）", () => {
  const c = new RiskClassifier();
  assert.equal(c.classify("mystery-tool"), "unknown");
  assert.equal(c.classify("anything", "unknown"), "unknown");
});

test("glob 匹配", () => {
  assert.ok(globMatch("fs.*", "fs.read"));
  assert.ok(globMatch("fs.*", "fs.a.b"));
  assert.ok(!globMatch("fs.*", "net.read"));
  assert.ok(globMatch("*", "anything"));
  assert.ok(globMatch("exact", "exact"));
});
