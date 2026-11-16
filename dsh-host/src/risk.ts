/**
 * 工具风险分类。
 *
 * 原则（与 Go 侧权限代理协同）：宁可高估，不可低估 —— 分不出来的一律
 * `unknown`，而 Go 侧对 unknown 的默认策略是 ask（fail-closed）。
 *
 * 三级来源，优先级从高到低：
 * 1. 插件显式声明（HostTool.risk / 插件 manifest）
 * 2. 配置文件里的覆盖规则（glob 匹配工具名）
 * 3. 启发式命名规则（shell.* / fs.write / net.* ...）
 */

import { RiskClass } from "./protocol.js";

export interface RiskRule {
  /** 工具名 glob，支持 `*` 通配（也跨 `.`），如 "fs.*"。 */
  tool: string;
  risk: RiskClass;
  reason?: string;
}

export interface RiskConfig {
  rules?: RiskRule[];
}

/** 命名启发式：保守归类。 */
const HEURISTICS: Array<{ pattern: RegExp; risk: RiskClass }> = [
  { pattern: /^(shell|exec|cmd|terminal|process)[.:_]/i, risk: "execute" },
  { pattern: /(delete|remove|rm|kill|destroy|format|wipe|chmod|chown|sudo)/i, risk: "write" },
  { pattern: /^(fs|file)[.:_].*(write|save|create|move|rename|upload)/i, risk: "write" },
  { pattern: /(write|save|create|append|move|rename|install|deploy)/i, risk: "write" },
  { pattern: /(fetch|http|request|download|upload|net|api|webhook|browser)/i, risk: "network" },
  { pattern: /(read|list|get|search|query|stat|open|parse|summarize|calc|compute|convert)/i, risk: "read_only" },
];

export class RiskClassifier {
  private rules: RiskRule[];

  constructor(cfg: RiskConfig = {}) {
    this.rules = [...(cfg.rules ?? [])];
  }

  /**
   * 分类一个工具：显式声明 > 配置规则 > 启发式 > `unknown`。
   */
  classify(tool: string, declared?: RiskClass): RiskClass {
    if (declared !== undefined && declared !== "unknown") {
      return declared;
    }
    for (const r of this.rules) {
      if (globMatch(r.tool, tool)) {
        return r.risk;
      }
    }
    for (const h of HEURISTICS) {
      if (h.pattern.test(tool)) {
        return h.risk;
      }
    }
    return "unknown";
  }
}

/** shell 风格 glob；`*` 跨 `.` 匹配，"fs.*" 覆盖 "fs.read" / "fs.a.b"。 */
export function globMatch(pattern: string, value: string): boolean {
  if (pattern === "*") return true;
  if (pattern === value) return true;
  // 将 glob 转正则：转义后把 * 还原为 .*
  const rx = new RegExp(
    "^" +
      pattern
        .split("*")
        .map((p) => p.replace(/[.*+?^${}()|[\]\\]/g, "\\$&"))
        .join(".*") +
      "$",
  );
  return rx.test(value);
}
