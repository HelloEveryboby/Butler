/**
 * CordisHost：按 dsh（DeepSeek Harness）文档化的 Cordis 插件契约加载插件。
 *
 * 契约（见 dsh 插件开发实践）：
 *   export const name = "my-plugin"
 *   export const inject = ["tools"]        // 依赖声明，'tools' 之外暂不支持
 *   export function apply(ctx) {
 *     ctx.tools.register({ name, description, schema, execute })
 *   }
 *
 * ⚠️ dsh 是 Developer Preview，运行时 API 会破坏性变更 —— 全部 dsh 相关
 * 适配代码只允许出现在本文件。协议层/注册表/风险分类不得 import dsh。
 *
 * schema 兼容两种形态：
 *   1. JSON Schema 对象（推荐，零依赖直通）
 *   2. zod 风格对象（dsh 插件惯用 z.object({...})）→ 内置轻量转换器
 */

import * as path from "node:path";
import * as url from "node:url";
import { pathToFileURL } from "node:url";

import {
  HostAdapter,
  HostTool,
  LoadedPlugin,
  SchemaLike,
  ToolContext,
} from "./host-adapter.js";
import { ProtoError, RiskClass } from "./protocol.js";

// ---- Cordis 插件契约类型 ----

interface ToolsService {
  register(spec: {
    name: string;
    description: string;
    schema?: SchemaLike;
    risk?: RiskClass;
    execute: HostTool["execute"];
  }): void;
}

interface CordisContext {
  tools: ToolsService;
  // 后续扩展点（ctx.llm / ctx.fs / ctx.approval ...）按需在此增补；
  // 插件声明了本宿主不认识的 inject 依赖时，加载期即拒绝并给出可读错误。
}

interface CordisPluginModule {
  name?: string;
  inject?: string[];
  apply?(ctx: CordisContext): void | Promise<void>;
}

export interface CordisHostOptions {
  /** 插件入口（ESM 文件/目录路径；目录取其 package.json main 或 index.js）。 */
  pluginPaths: string[];
  /** 注入给工具执行体的回调（事件/审批），由 server 提供。 */
  onEvent: (topic: string, data: unknown) => void;
  askApproval: ToolContext["askApproval"];
  /** 调用级 signal 工厂：server 为每次调用提供 AbortSignal。 */
  signalFor: (callId: string) => AbortSignal;
}

const SUPPORTED_INJECT = new Set(["tools"]);

export class CordisHost implements HostAdapter {
  private opts: CordisHostOptions;
  private loaded: LoadedPlugin[] = [];
  private toolContexts = new Map<string, ToolContext>();

  constructor(opts: CordisHostOptions) {
    this.opts = opts;
  }

  async load(): Promise<LoadedPlugin[]> {
    const plugins: LoadedPlugin[] = [];
    for (const p of this.opts.pluginPaths) {
      plugins.push(await this.loadOne(p));
    }
    this.loaded = plugins;
    return plugins;
  }

  async shutdown(): Promise<void> {
    // Cordis 的 Effect 由插件自行回收；宿主侧清空引用即可。
    // （真实 dsh 运行时接入时，此处调用其 dispose 生命周期。）
    this.loaded = [];
    this.toolContexts.clear();
  }

  /** 为某次调用构造 ToolContext（server 在 dispatch 时调用）。 */
  contextFor(callId: string): ToolContext {
    let ctx = this.toolContexts.get(callId);
    if (!ctx) {
      const signal = this.opts.signalFor(callId);
      ctx = {
        signal,
        emit: (topic, data) => this.opts.onEvent(topic, data),
        askApproval: this.opts.askApproval,
      };
      this.toolContexts.set(callId, ctx);
    }
    return ctx;
  }

  private async loadOne(pluginPath: string): Promise<LoadedPlugin> {
    const resolved = await resolveEntry(pluginPath);
    const mod = (await import(pathToFileURL(resolved).href)) as CordisPluginModule;

    if (typeof mod.apply !== "function") {
      throw new ProtoError(
        "upstream_error",
        `plugin ${pluginPath} does not export apply(ctx) — not a Cordis/dsh plugin`,
      );
    }
    for (const dep of mod.inject ?? []) {
      if (!SUPPORTED_INJECT.has(dep)) {
        throw new ProtoError(
          "upstream_error",
          `plugin ${pluginPath} declares inject=["${dep}"] which this host does not provide (supported: tools)`,
        );
      }
    }

    const tools: HostTool[] = [];
    const ctx: CordisContext = {
      tools: {
        register: (spec) => {
          if (!spec?.name || !spec?.description) {
            throw new ProtoError(
              "upstream_error",
              `plugin ${pluginPath} registered a tool without name/description — model tool selection needs both`,
            );
          }
          const tool: HostTool = {
            name: spec.name,
            description: spec.description,
            execute: spec.execute,
          };
          if (spec.schema !== undefined) tool.schema = normalizeSchema(spec.schema);
          if (spec.risk !== undefined) tool.risk = spec.risk;
          tools.push(tool);
        },
      },
    };

    await mod.apply(ctx);

    const id = mod.name ?? path.basename(path.dirname(resolved));
    const plugin: LoadedPlugin = { id, tools };
    return plugin;
  }
}

// ---- 入口解析：文件 / 目录（package.json main / index.js） ----

async function resolveEntry(p: string): Promise<string> {
  const fs = await import("node:fs/promises");
  const abs = path.resolve(p);
  let st;
  try {
    st = await fs.stat(abs);
  } catch {
    throw new ProtoError("upstream_error", `plugin path not found: ${p}`);
  }
  if (st.isFile()) return abs;
  // 目录：package.json 的 main/exports，否则 index.js
  const pkgPath = path.join(abs, "package.json");
  try {
    const pkg = JSON.parse(await fs.readFile(pkgPath, "utf8")) as {
      main?: string;
      module?: string;
    };
    const entry = pkg.module ?? pkg.main;
    if (entry) return path.resolve(abs, entry);
  } catch {
    /* 无 package.json，走 index.js */
  }
  for (const candidate of ["index.js", "index.mjs", "index.cjs"]) {
    const c = path.join(abs, candidate);
    try {
      await fs.access(c);
      return c;
    } catch {
      /* 继续 */
    }
  }
  throw new ProtoError("upstream_error", `cannot resolve plugin entry in ${p}`);
}

// ---- schema 规范化：JSON Schema 直通；zod 风格对象转换 ----

interface ZodLike {
  _def?: {
    typeName?: string;
    description?: string;
    shape?: () => Record<string, ZodLike>;
    innerType?: ZodLike;
    type?: ZodLike;
    values?: readonly (string | number)[];
  };
  description?: string;
  isOptional?: () => boolean;
}

/**
 * 把插件的 schema 统一成 JSON Schema 对象。
 * - 已是 JSON Schema（有 type/properties/oneOf 等关键字）→ 原样直通
 * - zod 风格（带 _def.typeName）→ 递归转换（object/string/number/boolean/
 *   array/enum/optional/nullable/describe 覆盖 dsh 插件的常见用法）
 * - 无法识别 → 丢弃 schema（宁可不校验，不可错校验），依赖模型自描述
 */
export function normalizeSchema(schema: SchemaLike): SchemaLike {
  if (looksLikeJsonSchema(schema)) return schema;
  const converted = convertZodLike(schema as ZodLike);
  return converted ?? {};
}

function looksLikeJsonSchema(s: SchemaLike): boolean {
  return (
    "type" in s ||
    "properties" in s ||
    "oneOf" in s ||
    "anyOf" in s ||
    "$schema" in s
  );
}

function convertZodLike(z: ZodLike): SchemaLike | undefined {
  const def = z?._def;
  if (!def?.typeName) return undefined;

  let out: Record<string, unknown>;
  switch (def.typeName) {
    case "ZodObject": {
      const shape = typeof def.shape === "function" ? def.shape() : {};
      const properties: Record<string, unknown> = {};
      const required: string[] = [];
      for (const [key, val] of Object.entries(shape)) {
        const converted = convertZodLike(val);
        if (converted === undefined) continue;
        properties[key] = stripDescription(converted, val);
        if (!val?.isOptional?.()) required.push(key);
      }
      out = { type: "object", properties };
      if (required.length > 0) out.required = required;
      break;
    }
    case "ZodString":
      out = { type: "string" };
      break;
    case "ZodNumber":
      out = { type: "number" };
      break;
    case "ZodBoolean":
      out = { type: "boolean" };
      break;
    case "ZodArray":
      out = {
        type: "array",
        ...(def.type ? { items: convertZodLike(def.type) ?? {} } : {}),
      };
      break;
    case "ZodEnum":
      out = { type: "string", enum: [...(def.values ?? [])] };
      break;
    case "ZodOptional":
    case "ZodNullable":
      return def.innerType ? convertZodLike(def.innerType) : undefined;
    default:
      return undefined; // 未覆盖的 zod 类型：放弃转换
  }

  const desc = z.description ?? def.description;
  if (desc) out.description = desc;
  return out;
}

function stripDescription(converted: Record<string, unknown>, _z: ZodLike): Record<string, unknown> {
  return converted; // description 保留（模型选工具/填参数都需要它）
}

// ---- 极简 JSON Schema 结构校验（够拒绝垃圾参数，不做完整规范实现） ----

export function validateArgs(
  schema: SchemaLike | undefined,
  args: Record<string, unknown>,
): string[] {
  if (!schema || Object.keys(schema).length === 0) return [];
  const errors: string[] = [];
  if (schema.type === "object") {
    const props = (schema.properties ?? {}) as Record<string, SchemaLike>;
    const required = (schema.required ?? []) as string[];
    for (const key of required) {
      if (args[key] === undefined) errors.push(`missing required argument "${key}"`);
    }
    for (const [key, val] of Object.entries(args)) {
      const sub = props[key];
      if (!sub) continue; // 未声明的参数交给插件处理
      const t = sub.type;
      if (typeof t === "string" && !typeMatches(t, args[key])) {
        errors.push(`argument "${key}" must be ${t}`);
      }
    }
  }
  return errors;
}

function typeMatches(t: string, v: unknown): boolean {
  switch (t) {
    case "string":
      return typeof v === "string";
    case "number":
      return typeof v === "number";
    case "boolean":
      return typeof v === "boolean";
    case "array":
      return Array.isArray(v);
    case "object":
      return typeof v === "object" && v !== null && !Array.isArray(v);
    default:
      return true;
  }
}

// 供 server 获得稳定的相对引用（tree-shaking 友好占位）
export const cordisHostVersion = "0.1.0";
export type { CordisPluginModule };
export const moduleDir = path.dirname(url.fileURLToPath(import.meta.url));
