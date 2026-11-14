/**
 * HostAdapter：隔离 dsh/Cordis 运行时的接缝。
 *
 * dsh 处于 Developer Preview，插件加载 API 会破坏性变更 —— 所有 dsh 相关
 * 代码收敛在 cordis-host.ts 一个文件里；协议层、注册表、风险分类均与运行时
 * 无关，可以在任何 HostAdapter 实现上复用（也方便测试时注入 FakeHost）。
 */

import { RiskClass, SessionEvent } from "./protocol.js";

/** 插件工具可接受的 schema：JSON Schema（推荐）或 zod 风格对象。 */
export type SchemaLike = Record<string, unknown>;

export interface ToolContext {
  /** 调用取消信号：tool.cancel / 超时 / 断连时触发。 */
  signal: AbortSignal;
  /** 发布会话事件（转发至连接器 event.push）。 */
  emit(topic: string, data?: unknown): void;
  /**
   * 插件内部操作需要人工审批时调用（对应 dsh 的权限审批管线）。
   * 超时/无应答返回 false（fail-closed）。
   */
  askApproval(req: { tool: string; reason?: string; args?: unknown }): Promise<boolean>;
}

export interface HostTool {
  name: string;
  description: string;
  schema?: SchemaLike;
  /** 显式风险声明；缺省由 RiskClassifier 启发式归类。 */
  risk?: RiskClass;
  /**
   * 执行体。返回值三种形态：
   * - 普通对象/原始值 → 单个 tool.result
   * - AsyncIterable → 逐个作为 tool.chunk 推送，迭代结束发 tool.result（汇总为空 content）
   * - 抛错 → tool.result(isError) 或 error 帧
   */
  execute(
    args: Record<string, unknown>,
    ctx: ToolContext,
  ): Promise<unknown> | AsyncIterable<unknown>;
}

export interface LoadedPlugin {
  /** 插件 id（dsh 插件模块的 name，或路径派生名）。 */
  id: string;
  version?: string;
  tools: HostTool[];
}

export interface HostAdapter {
  /** 加载全部插件，返回插件清单。幂等：可重复调用（热重载用）。 */
  load(): Promise<LoadedPlugin[]>;
  /** 优雅关闭：卸载插件、回收 Effect。 */
  shutdown(): Promise<void>;
}

/** 把 LoadedPlugin 摊平成 name→tool 表，重名即报错（先到先得 + 警告由调用方处理）。 */
export function indexTools(
  plugins: LoadedPlugin[],
): Map<string, { tool: HostTool; source: string; sourceVer?: string }> {
  const map = new Map<string, { tool: HostTool; source: string; sourceVer?: string }>();
  for (const p of plugins) {
    for (const t of p.tools) {
      if (!map.has(t.name)) {
        const entry: { tool: HostTool; source: string; sourceVer?: string } = {
          tool: t,
          source: p.id,
        };
        if (p.version !== undefined) entry.sourceVer = p.version;
        map.set(t.name, entry);
      }
    }
  }
  return map;
}
