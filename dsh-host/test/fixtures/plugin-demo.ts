/**
 * 测试插件：模拟一个真实 dsh 插件模块（Cordis 契约）。
 * 覆盖四种执行形态：普通返回 / 流式 / 抛错 / 内部审批。
 */

export const name = "demo-plugin";
export const inject = ["tools"];

interface ToolsService {
  register(spec: {
    name: string;
    description: string;
    schema?: Record<string, unknown>;
    execute: (
      args: Record<string, unknown>,
      ctx: {
        signal: AbortSignal;
        emit(topic: string, data?: unknown): void;
        askApproval(req: { tool: string; reason?: string; args?: unknown }): Promise<boolean>;
      },
    ) => unknown | AsyncIterable<unknown>;
  }): void;
}

export function apply(ctx: { tools: ToolsService }): void {
  ctx.tools.register({
    name: "demo.echo",
    description: "回显输入文本（用于连通性验证）",
    schema: {
      type: "object",
      properties: { text: { type: "string", description: "要回显的文本" } },
      required: ["text"],
    },
    execute: (args) => ({ echoed: args.text }),
  });

  ctx.tools.register({
    name: "demo.stream",
    description: "流式输出计数序列（验证 chunk 通道）",
    execute: async function* stream() {
      for (let i = 0; i < 3; i++) {
        yield { seq: i, note: `chunk-${i}` };
      }
    },
  });

  ctx.tools.register({
    name: "demo.fail",
    description: "故意抛错（验证错误传播）",
    execute: () => {
      throw new Error("intentional failure");
    },
  });

  ctx.tools.register({
    name: "demo.dangerous",
    description: "内部需要审批的操作（验证 approve.ask/answer 桥）",
    execute: async (_args, ctx) => {
      const ok = await ctx.askApproval({
        tool: "demo.dangerous",
        reason: "plugin wants to do something dangerous",
      });
      return { approved: ok };
    },
  });
}
