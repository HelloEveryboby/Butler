/**
 * 入口：node dist/bin/server.js [--config host.json]
 *
 * 配置（JSON，全部字段可选）：
 * {
 *   "pluginPaths": ["plugins/doc-reader", "plugins/greet"],
 *   "risk": { "rules": [{ "tool": "shell.*", "risk": "execute" }] },
 *   "approvalTimeoutMs": 30000
 * }
 *
 * 环境变量覆盖：DSH_HOST_CONFIG / DSH_HOST_PLUGINS（逗号分隔路径）。
 */

import * as fs from "node:fs";
import { HostServer, HostServerConfig } from "../src/server.js";

function loadConfig(): HostServerConfig {
  const args = process.argv.slice(2);
  let configPath = process.env.DSH_HOST_CONFIG ?? "";
  const idx = args.indexOf("--config");
  const argPath = idx >= 0 ? args[idx + 1] : undefined;
  if (argPath) configPath = argPath;

  let cfg: Partial<HostServerConfig> = {};
  if (configPath) {
    cfg = JSON.parse(fs.readFileSync(configPath, "utf8")) as Partial<HostServerConfig>;
  }
  const envPlugins = process.env.DSH_HOST_PLUGINS;
  const pluginPaths = cfg.pluginPaths ?? (envPlugins ? envPlugins.split(",") : []);
  if (pluginPaths.length === 0) {
    process.stderr.write("dsh-host: no pluginPaths configured (config file or DSH_HOST_PLUGINS)\n");
    process.exit(2);
  }
  return {
    pluginPaths,
    ...(cfg.risk ? { risk: cfg.risk } : {}),
    ...(cfg.approvalTimeoutMs ? { approvalTimeoutMs: cfg.approvalTimeoutMs } : {}),
  };
}

async function main(): Promise<void> {
  const cfg = loadConfig();
  const server = new HostServer(cfg, (buf) => {
    process.stdout.write(buf);
  });

  await server.start();
  process.stderr.write(`dsh-host: ready, ${cfg.pluginPaths.length} plugin path(s)\n`);

  process.stdin.on("data", (chunk: Buffer) => server.feed(chunk));
  process.stdin.on("end", () => void shutdown(0));
  process.stdin.on("error", () => void shutdown(1));

  const shutdown = async (code: number): Promise<void> => {
    await server.shutdown();
    process.exit(code);
  };
  process.on("SIGTERM", () => void shutdown(0));
  process.on("SIGINT", () => void shutdown(0));
}

main().catch((err) => {
  process.stderr.write(`dsh-host: fatal: ${err instanceof Error ? err.stack : String(err)}\n`);
  process.exit(1);
});
