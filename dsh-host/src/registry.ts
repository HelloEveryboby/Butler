/**
 * 能力注册表：与 Go 侧 internal/registry 同语义 ——
 * 单调版本号、全量快照、增量 diff（含 tombstone 窗口）。
 */

import { Capability, RegistryDiff, RegistrySync, RiskClass } from "./protocol.js";
import { ProtoError } from "./protocol.js";

/** 保留多少个版本的删除记录用于 diff；超出即要求全量 resync。 */
const TOMBSTONE_WINDOW = 4096;

interface Entry {
  cap: Capability;
  version: number;
}

function validateCapability(c: Capability): void {
  if (!c.name) {
    throw new ProtoError("malformed_frame", "capability name is empty");
  }
  if (!c.description) {
    throw new ProtoError("malformed_frame", `capability "${c.name}" has empty description`);
  }
  if (!isRiskClass(c.risk)) {
    throw new ProtoError("malformed_frame", `capability "${c.name}" has invalid risk class "${c.risk}"`);
  }
}

function isRiskClass(r: string): r is RiskClass {
  return ["read_only", "write", "execute", "network", "unknown"].includes(r);
}

export class ToolRegistry {
  private version = 0;
  private entries = new Map<string, Entry>();
  private tombstones = new Map<string, number>();

  upsert(...caps: Capability[]): number {
    for (const c of caps) validateCapability(c);
    this.version++;
    for (const c of caps) {
      this.entries.set(c.name, { cap: c, version: this.version });
      this.tombstones.delete(c.name);
    }
    this.prune();
    return this.version;
  }

  remove(...names: string[]): number {
    this.version++;
    for (const name of names) {
      if (this.entries.delete(name)) {
        this.tombstones.set(name, this.version);
      }
    }
    this.prune();
    return this.version;
  }

  replace(caps: Capability[]): number {
    for (const c of caps) validateCapability(c);
    this.version++;
    const next = new Map<string, Entry>();
    for (const c of caps) {
      next.set(c.name, { cap: c, version: this.version });
    }
    for (const name of this.entries.keys()) {
      if (!next.has(name)) this.tombstones.set(name, this.version);
    }
    this.entries = next;
    this.prune();
    return this.version;
  }

  get(name: string): Capability | undefined {
    return this.entries.get(name)?.cap;
  }

  getVersion(): number {
    return this.version;
  }

  size(): number {
    return this.entries.size;
  }

  snapshot(): RegistrySync {
    const capabilities = [...this.entries.values()]
      .map((e) => e.cap)
      .sort((a, b) => (a.name < b.name ? -1 : a.name > b.name ? 1 : 0));
    return { version: this.version, capabilities };
  }

  /**
   * 计算 since 之后的增量变更。
   * since 超出 tombstone 窗口（或来自未来）时返回 null —— 调用方必须全量 resync。
   */
  diffSince(since: number): RegistryDiff | null {
    if (since > this.version) return null;
    const upserts: Capability[] = [];
    for (const e of this.entries.values()) {
      if (e.version > since) upserts.push(e.cap);
    }
    const removals: string[] = [];
    for (const [name, v] of this.tombstones) {
      if (v > since) removals.push(name);
    }
    upserts.sort((a, b) => (a.name < b.name ? -1 : a.name > b.name ? 1 : 0));
    removals.sort();
    return { from: since, to: this.version, upserts, removals };
  }

  private prune(): void {
    const floor = Math.max(0, this.version - TOMBSTONE_WINDOW);
    for (const [name, v] of this.tombstones) {
      if (v <= floor) this.tombstones.delete(name);
    }
  }
}
