/**
 * 模拟"dsh 插件市场"风格插件（Cordis 契约：name / inject / apply(ctx)）。
 * 用于端到端集成验证：此文件的形态 = 真实市场插件解压后的形态。
 */

export const name = "hello-market";
export const inject = ["tools"];

export function apply(ctx) {
  ctx.tools.register({
    name: "hello.greet",
    description: "向指定名字的人生成一句问候语（连通性验证工具）",
    schema: {
      type: "object",
      properties: { name: { type: "string", description: "要问候的人名" } },
      required: ["name"],
    },
    execute: (args) => ({
      greeting: `你好，${args.name}！这是来自 dsh 市场插件的问候。`,
    }),
  });

  ctx.tools.register({
    name: "hello.count",
    description: "流式计数到指定数字（验证 chunk 流式通道）",
    schema: {
      type: "object",
      properties: { to: { type: "number", description: "计数上限" } },
    },
    execute: async function* (args) {
      const to = typeof args.to === "number" ? args.to : 3;
      for (let i = 1; i <= to; i++) {
        yield { count: i };
      }
    },
  });

  ctx.tools.register({
    name: "hello.ask",
    description: "需要人工审批的示例操作（验证权限代理闭环）",
    execute: async (_args, toolCtx) => {
      const ok = await toolCtx.askApproval({
        tool: "hello.ask",
        reason: "插件请求执行一个危险操作",
      });
      return { approved: ok };
    },
  });
}
