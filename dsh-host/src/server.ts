/**
 * DSH 宿主 shim 主服务：stdin 读帧、stdout 写帧，驱动 HostAdapter 执行插件工具。
 *
 * 职责边界（与 Go 连接器的分工）：
 * - 本进程只做"执行侧"：加载插件、执行工具、流式输出、上报事件/审批请求
 * - 权限判定、审计、超时上限、进程监管全在 Go 连接器侧
 *
 * 事件语义对齐 dsh Session Log：tool 执行的开始/结束/错误都发布为
 * `session.*` 事件（只追加事实流），由连接器转发 Butler。
 */

import { FrameDecoder, encodeFrame } from "./codec.js";
import { CordisHost } from "./cordis-host.js";
import { indexTools, ToolContext } from "./host-adapter.js";
import {
  ApprovalDecision,
  errorFrame,
  frame,
  Frame,
  ProtoError,
  RegistrySync,
  ToolInvoke,
  ToolResult,
} from "./protocol.js";
import { RiskClassifier, RiskConfig } from "./risk.js";
import { validateArgs } from "./cordis-host.js";

export interface HostServerConfig {
  pluginPaths: string[];
  risk?: RiskConfig;
  /** 审批等待上限（毫秒），超时按拒绝处理（fail-closed）。 */
  approvalTimeoutMs?: number;
}

type Sink = (buf: Buffer) => void;

interface PendingApproval {
  resolve: (allowed: boolean) => void;
}

export class HostServer {
  private cfg: HostServerConfig;
  private write: Sink;
  private decoder = new FrameDecoder();
  private host: CordisHost;
  private classifier: RiskClassifier;
  private tools = new Map<string, ReturnType<typeof indexTools> extends Map<string, infer V> ? V : never>();
  private aborts = new Map<string, AbortController>();
  private approvals = new Map<string, PendingApproval>();
  private started = false;

  constructor(cfg: HostServerConfig, write: Sink) {
    this.cfg = cfg;
    this.write = write;
    this.classifier = new RiskClassifier(cfg.risk ?? {});
    this.host = new CordisHost({
      pluginPaths: cfg.pluginPaths,
      onEvent: (topic, data) => this.emitEvent(topic, data),
      askApproval: (req) => this.askApproval(req),
      signalFor: (callId) => {
        const ac = new AbortController();
        this.aborts.set(callId, ac);
        return ac.signal;
      },
    });
  }

  /** 启动：加载插件并推送首个 registry.sync。 */
  async start(): Promise<void> {
    const plugins = await this.host.load();
    this.tools = indexTools(plugins) as typeof this.tools;
    this.started = true;
    this.sendRegistrySync();
  }

  /** 喂入 stdin 字节。协议违例回 error 帧并继续（连接器侧负责断链决策）。 */
  feed(chunk: Buffer): void {
    let frames: Frame[];
    try {
      frames = this.decoder.push(chunk);
    } catch (err) {
      const pe = err instanceof ProtoError ? err : new ProtoError("internal", String(err));
      this.writeBuf(encodeFrame(errorFrame("unknown", pe)));
      return;
    }
    for (const f of frames) {
      void this.dispatch(f); // 每帧独立协程：慢工具不阻塞后续帧
    }
  }

  async shutdown(): Promise<void> {
    for (const ac of this.aborts.values()) ac.abort();
    for (const [, p] of this.approvals) p.resolve(false);
    await this.host.shutdown();
  }

  // ---- 帧分发 ----

  private async dispatch(f: Frame): Promise<void> {
    switch (f.type) {
      case "tool.invoke":
        await this.handleInvoke(f);
        break;
      case "tool.cancel": {
        const ac = this.aborts.get(f.id);
        ac?.abort();
        break;
      }
      case "registry.sync":
        this.sendRegistrySync(f.id);
        break;
      case "approve.answer": {
        const d = f.payload as ApprovalDecision;
        const pending = this.approvals.get(d?.requestId ?? "");
        if (pending) {
          this.approvals.delete(d.requestId);
          pending.resolve(Boolean(d.allowed));
        }
        break;
      }
      case "health.ping":
        this.send(frame(f.id, "health.pong"));
        break;
      default:
        this.send(
          errorFrame(
            f.id,
            new ProtoError("unsupported", `unsupported frame ${f.type}`),
          ),
        );
    }
  }

  // ---- 工具调用 ----

  private async handleInvoke(f: Frame): Promise<void> {
    const inv = (f.payload ?? {}) as ToolInvoke;
    const entry = this.tools.get(inv.tool);
    if (!entry) {
      this.send(
        errorFrame(
          f.id,
          new ProtoError("unknown_tool", `tool ${inv.tool} is not registered`),
        ),
      );
      return;
    }

    // 参数结构校验（轻量：type/required）。
    const args = (inv.args ?? {}) as Record<string, unknown>;
    const argErrors = validateArgs(entry.tool.schema, args);
    if (argErrors.length > 0) {
      this.sendResult(f.id, {
        tool: inv.tool,
        content: { errors: argErrors },
        isError: true,
      });
      return;
    }

    const ctx = this.host.contextFor(f.id);
    this.emitEvent("session.tool.started", { callId: f.id, tool: inv.tool });

    try {
      const out = entry.tool.execute(args, ctx);
      if (isAsyncIterable(out)) {
        let seq = 0;
        for await (const chunk of out) {
          if (ctx.signal.aborted) {
            throw new ProtoError("cancelled", "call cancelled");
          }
          this.send({
            ...frame(f.id, "tool.chunk", { seq: seq++, data: chunk }, { stream: true }),
          });
        }
        this.sendResult(f.id, { tool: inv.tool, content: { streamed: seq } });
      } else {
        const content = await out;
        this.sendResult(f.id, { tool: inv.tool, content: content ?? null });
      }
      this.emitEvent("session.tool.finished", { callId: f.id, tool: inv.tool });
    } catch (err) {
      if (err instanceof ProtoError && err.code === "cancelled") {
        this.send(errorFrame(f.id, err));
      } else {
        this.sendResult(f.id, {
          tool: inv.tool,
          content: { error: err instanceof Error ? err.message : String(err) },
          isError: true,
        });
      }
      this.emitEvent("session.tool.error", {
        callId: f.id,
        tool: inv.tool,
        error: err instanceof Error ? err.message : String(err),
      });
    } finally {
      this.aborts.delete(f.id);
      void ctx;
    }
  }

  // ---- 审批桥（插件内部操作 → approve.ask → 等 approve.answer） ----

  private askApproval(req: {
    tool: string;
    reason?: string;
    args?: unknown;
  }): Promise<boolean> {
    const requestId = `shim-apr-${Date.now()}-${Math.random().toString(36).slice(2, 8)}`;
    return new Promise<boolean>((resolve) => {
      const timeoutMs = this.cfg.approvalTimeoutMs ?? 30_000;
      const timer = setTimeout(() => {
        this.approvals.delete(requestId);
        resolve(false); // fail-closed
      }, timeoutMs);
      this.approvals.set(requestId, {
        resolve: (allowed) => {
          clearTimeout(timer);
          resolve(allowed);
        },
      });
      this.send(
        frame(requestId, "approve.ask", {
          requestId,
          tool: req.tool,
          risk: "unknown",
          reason: req.reason ?? "plugin requested approval",
          ...(req.args !== undefined ? { args: req.args } : {}),
        }),
      );
    });
  }

  // ---- 事件 / 注册表 ----

  private emitEvent(topic: string, data: unknown): void {
    this.send(frame(`evt-${Date.now()}`, "event.push", { topic, data, ts: Date.now() }));
  }

  private sendRegistrySync(replyTo?: string): void {
    const snap = snapshotOf(this.tools, this.classifier);
    this.send(frame(replyTo ?? `sync-${Date.now()}`, "registry.sync", snap));
  }

  private sendResult(id: string, result: ToolResult): void {
    this.send(frame(id, "tool.result", result, { done: true }));
  }

  private send(f: Frame): void {
    this.writeBuf(encodeFrame(f));
  }

  private writeBuf(buf: Buffer): void {
    try {
      this.write(buf);
    } catch {
      // stdout 写失败：连接器侧已断开，静默（进程即将退出）。
    }
  }
}

// ---- 工具函数 ----

function snapshotOf(
  tools: Map<string, { tool: { name: string; description: string; schema?: Record<string, unknown>; risk?: string }; source: string; sourceVer?: string }>,
  classifier: RiskClassifier,
): RegistrySync {
  const capabilities = [...tools.entries()].map(([name, e]) => {
    const risk = classifier.classify(name, e.tool.risk as never);
    const cap: RegistrySync["capabilities"][number] = {
      name: e.tool.name,
      description: e.tool.description,
      risk,
      source: e.source,
    };
    if (e.tool.schema !== undefined) cap.schema = e.tool.schema;
    if (e.sourceVer !== undefined) cap.sourceVer = e.sourceVer;
    return cap;
  });
  capabilities.sort((a, b) => (a.name < b.name ? -1 : a.name > b.name ? 1 : 0));
  return { version: Date.now(), capabilities }; // 版本号由 Go 侧注册表接管
}

function isAsyncIterable(v: unknown): v is AsyncIterable<unknown> {
  return typeof (v as AsyncIterable<unknown>)[Symbol.asyncIterator] === "function";
}
