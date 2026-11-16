/**
 * 南向协议线格式定义 —— 与 Go 侧 `connector/internal/proto` 严格镜像。
 *
 * 稳定性承诺：v1 帧格式字节级冻结；新增字段必须可选；未知帧类型必须以
 * `unsupported` 错误应答，禁止静默丢弃。完整规范见 connector/docs/protocol.md。
 */

export const PROTOCOL_VERSION = 1;
export const MAX_FRAME_SIZE = 16 << 20; // 16 MiB，与 Go 侧一致

export type FrameType =
  | "tool.invoke"
  | "tool.chunk"
  | "tool.result"
  | "tool.cancel"
  | "event.push"
  | "registry.sync"
  | "registry.diff"
  | "approve.ask"
  | "approve.answer"
  | "health.ping"
  | "health.pong"
  | "error";

export type RiskClass = "read_only" | "write" | "execute" | "network" | "unknown";

export const RISK_CLASSES: readonly RiskClass[] = [
  "read_only",
  "write",
  "execute",
  "network",
  "unknown",
];

/** 稳定错误码，与 Go 侧 ErrorCode 对齐。 */
export type ErrorCode =
  | "malformed_frame"
  | "unknown_tool"
  | "timeout"
  | "cancelled"
  | "denied"
  | "upstream_error"
  | "unavailable"
  | "unsupported"
  | "internal";

export interface ProtoErrorShape {
  code: ErrorCode;
  message: string;
  data?: unknown;
}

export class ProtoError extends Error {
  readonly code: ErrorCode;
  readonly data?: unknown;

  constructor(code: ErrorCode, message: string, data?: unknown) {
    super(`${code}: ${message}`);
    this.name = "ProtoError";
    this.code = code;
    this.data = data;
  }

  toShape(): ProtoErrorShape {
    const shape: ProtoErrorShape = { code: this.code, message: this.message };
    if (this.data !== undefined) shape.data = this.data;
    return shape;
  }
}

export interface Frame {
  v: number;
  id: string;
  type: FrameType;
  stream?: boolean;
  done?: boolean;
  payload?: unknown;
  error?: ProtoErrorShape;
  ts: number;
}

// ---- payload 线格式 ----

export interface ToolInvoke {
  tool: string;
  args?: Record<string, unknown>;
  risk?: RiskClass;
  timeoutMs?: number;
}

export interface ToolChunk {
  seq: number;
  data: unknown;
}

export interface ToolResult {
  tool: string;
  content?: unknown;
  isError?: boolean;
}

export interface ToolCancel {
  reason?: string;
}

export interface SessionEvent {
  topic: string;
  data?: unknown;
  ts: number;
}

export interface Capability {
  name: string;
  description: string;
  /** JSON Schema（对象形态）；zod schema 由 cordis-host 转换而来。 */
  schema?: Record<string, unknown>;
  risk: RiskClass;
  source: string;
  sourceVer?: string;
}

export interface RegistrySync {
  version: number;
  capabilities: Capability[];
}

export interface RegistryDiff {
  from: number;
  to: number;
  upserts?: Capability[];
  removals?: string[];
}

export interface ApprovalRequest {
  requestId: string;
  tool: string;
  source?: string;
  risk: RiskClass;
  args?: Record<string, unknown>;
  reason?: string;
}

export interface ApprovalDecision {
  requestId: string;
  allowed: boolean;
  reason?: string;
  remember?: boolean;
}

/** 构造一帧（ts 自动填充）。 */
export function frame(
  id: string,
  type: FrameType,
  payload?: unknown,
  extra?: { stream?: boolean; done?: boolean; error?: ProtoErrorShape },
): Frame {
  const f: Frame = { v: PROTOCOL_VERSION, id, type, ts: Date.now() };
  if (payload !== undefined) f.payload = payload;
  if (extra?.stream) f.stream = true;
  if (extra?.done) f.done = true;
  if (extra?.error) f.error = extra.error;
  return f;
}

/** 由 ProtoError 构造终止错误帧。 */
export function errorFrame(id: string, err: ProtoError): Frame {
  return frame(id, "error", undefined, { done: true, error: err.toShape() });
}

export function isTerminal(f: Frame): boolean {
  return f.type === "tool.result" || f.type === "error";
}
