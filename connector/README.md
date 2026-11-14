# butler-dsh-connector

Butler（Python 编排器）与 DSH 宿主（Node 插件运行时）之间的**通道连接器**——BHL 混合链路的 Node 成员。

```
┌────────────┐  北向 socket/pipe   ┌───────────────────────┐  南向 stdio    ┌─────────────────────────┐
│  Butler    │ ←── JSON-RPC/TLV ──→│  butler-dsh-connector │←── JSON-RPC ──→│  DSH 宿主 (Node)         │
│  (Python)  │                     │  (Go, 本程序)          │               │  Cordis + 市场插件       │
└────────────┘                     └───────────────────────┘               └─────────────────────────┘
```

连接器只做"通道"：**能力注册、调用路由、事件泵、权限代理、进程监管**。零业务逻辑、零外部运行时依赖（Windows named pipe 除外）。

## 构建

```bash
cd connector
go build -o bin/butler-dsh-connector ./cmd/dsh-connector
# Windows 交叉编译
GOOS=windows GOARCH=amd64 go build -o bin/butler-dsh-connector.exe ./cmd/dsh-connector
```

版本注入：

```bash
go build -ldflags "-X main.version=1.0.0" ./cmd/dsh-connector
```

## 运行

```bash
./bin/butler-dsh-connector -config connector.json
```

配置（JSON，全部字段可选，见 `internal/config`）：

```json
{
  "north": { "addr": "/run/user/1000/butler-dsh-connector.sock" },
  "south": {
    "nodeCommand": "node",
    "nodeArgs": ["lib_external/dsh-host/server.js"],
    "defaultTimeoutMs": 120000
  },
  "approval": {
    "askTimeoutMs": 30000,
    "auditLog": "logs/connector-audit.jsonl",
    "auditMaxBytes": 16777216,
    "policy": {
      "rules": [
        { "tool": "fs.*", "risk": "write", "action": "deny", "reason": "fs writes locked" },
        { "tool": "shell.*", "risk": "execute", "action": "ask" }
      ],
      "defaults": { "network": "ask" },
      "allowedSources": ["doc-reader", "ultramath"]
    }
  },
  "log": { "level": "info", "format": "text" }
}
```

环境变量覆盖：`BUTLER_DSH_NORTH_ADDR`、`BUTLER_DSH_SOUTH_CMD`、`BUTLER_DSH_LOG_LEVEL`。
子进程环境条目支持 `${VAR}` 引用——**密钥永远走环境变量，绝不写进配置文件**。

## 安全模型

| 层 | 机制 |
|----|------|
| 权限代理 | 有序规则 + 风险默认值；`read_only→allow`，其余 `ask`；**未分类风险 fail-closed** |
| 交互审批 | `ask` 判定 → `approve.ask` 帧到 Butler 控制台 → 30s（可配）超时**拒绝**；支持 `remember` 缓存 |
| 来源管控 | `allowedSources` 白名单；名单外插件工具一律 `deny` |
| 审计 | append-only JSONL（默认 `logs/connector-audit.jsonl`，16 MiB 单代轮转） |
| 传输 | Unix socket 0600 / named pipe 仅限本用户+管理员 |
| 进程 | 子进程崩溃指数退避重启（500ms→30s，±50% jitter），重启预算 5 次/2min，耗尽进入 `failed` 并 fail 所有在途调用 |

## 测试

```bash
go test ./...            # 全部单元 + 契约测试
go test ./internal/proto -update   # 协议 golden 文件更新（字节级冻结校验）
go vet ./...
```

测试覆盖要点：
- 协议编解码 round-trip、超限帧/坏帧/版本不符拒绝、**golden-file 字节稳定性**
- 注册表 diff/tombstone 语义（慢消费者强制全量 resync）
- 策略引擎：顺序规则、glob、来源白名单、未分类 fail-closed
- 南向调用多路复用：流式 chunk→result、超时→`tool.cancel`、上游错误传播、断连不可用

## 协议

见 [docs/protocol.md](docs/protocol.md)。**v1 帧格式字节级冻结**；变更需同步更新 golden 文件与协议文档。

## 目录

```
cmd/dsh-connector/     入口：装配、信号处理、优雅退出
internal/proto/        帧定义 + 编解码 + TLV 数据面
internal/registry/     能力注册表（版本化、diff、tombstone）
internal/events/       有界广播事件泵（背压计数）
internal/approval/     策略引擎 + 审批代理 + 审计日志
internal/supervisor/   子进程监管（退避重启、优雅终止）
internal/transport/    平台传输（Unix socket / Windows named pipe）
internal/north/        北向服务端（Butler 连接、调用编排、审批路由）
internal/south/        南向客户端（调用多路复用、流式、重绑定）
internal/config/       分层配置（默认<文件<环境<参数）
```
