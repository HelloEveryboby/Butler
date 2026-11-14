# @butler-dsh/host — DSH 宿主 shim（南向对端）

加载 DeepSeek Harness (dsh) 插件市场插件（Cordis 契约），通过南向协议
（4 字节大端长度前缀 + JSON 帧）对 `butler-dsh-connector` 暴露工具能力。

```
Butler (Python) ⇄ butler-dsh-connector (Go) ⇄ 本进程 (Node) ⇄ dsh 市场插件
```

## 构建与测试

```bash
npm install
npm test        # tsc 构建 + node:test 全量测试（含跨语言 golden 契约）
npm start       # node dist/bin/server.js --config host.json
```

## 配置

```json
{
  "pluginPaths": ["plugins/doc-reader", "plugins/hello-market.js"],
  "risk": { "rules": [{ "tool": "shell.*", "risk": "execute" }] },
  "approvalTimeoutMs": 30000
}
```

环境变量：`DSH_HOST_CONFIG`（配置文件路径）、`DSH_HOST_PLUGINS`（逗号分隔插件路径）。

## 插件契约（dsh/Cordis 标准形态）

```js
export const name = "my-plugin";
export const inject = ["tools"];           // 依赖声明；未知依赖加载期拒绝

export function apply(ctx) {
  ctx.tools.register({
    name: "doc.read",
    description: "读取 PDF/DOCX 并返回结构化文本",   // 质量决定模型触发率
    schema: { type: "object", properties: {...} },   // JSON Schema（或 zod 风格，自动转换）
    risk: "read_only",                               // 可选；缺省由启发式分类
    async execute(args, toolCtx) {
      // toolCtx.signal       —— 取消信号（tool.cancel/超时触发）
      // toolCtx.emit(topic, data) —— 上报 Session 事件
      // toolCtx.askApproval({...}) —— 插件内部危险操作走审批桥
      return { text: "..." };        // 普通返回 → tool.result
      // 或 async function*() { yield ... } → tool.chunk 流 + tool.result
    },
  });
}
```

## 设计要点

| 关注点 | 做法 |
|--------|------|
| **dsh API 不稳定（Developer Preview）** | 全部 dsh 适配代码收敛在 `src/cordis-host.ts` 一个文件；协议/注册表/风险分类与运行时无关 |
| **schema 兼容** | JSON Schema 直通；zod 风格对象由内置轻量转换器处理（object/string/number/boolean/array/enum/optional/describe） |
| **风险分类宁高勿低** | 显式声明 > 配置规则 > 命名启发式 > `unknown`；unknown 在 Go 侧默认 ask（fail-closed 协同） |
| **参数校验** | 轻量 type/required 校验，拒绝垃圾参数；不做完整 JSON Schema 实现（宁可不校验，不可错校验） |
| **审批桥** | 插件 `askApproval()` → `approve.ask` 帧 → 等 `approve.answer`；超时按拒绝（fail-closed） |
| **Session 语义** | `session.tool.started/finished/error` 事件只追加上报，对齐 dsh Session Log |
| **帧契约** | 与 Go 侧字节级镜像；测试含 Go golden fixture 跨语言语义校验 |

## 测试（28 项）

编解码 round-trip / 逐字节碎片重组 / 五类畸形帧拒绝 / 注册表 diff 与 tombstone /
风险分类（含 fail-closed）/ 服务端全场景（普通、流式、抛错、未知工具、参数校验、
审批闭环、审批超时拒绝、未知帧类型 unsupported）/ 跨语言 golden 契约。

## 端到端验证

工作区根目录：`python3 integration/e2e.py`
—— 真实拉起 Go 连接器 + 本 shim + 市场风格插件，12 项全链路断言
（能力注册、普通调用、流式、双层审批闭环、审计落盘、健康探测）。
