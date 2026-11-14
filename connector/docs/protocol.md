# butler-dsh-connector 协议规范 v1

> 通道连接器（Go daemon）与两端（Butler / DSH 宿主）之间的线上协议。
> 稳定性承诺：**v1 帧格式字节级冻结**；新增字段必须可选，新增帧类型必须可被旧端以 `unsupported` 错误安全拒绝。

## 1. 传输层

| 线路 | 载体 | 说明 |
|------|------|------|
| 北向（Butler ⇄ connector） | Unix socket（`$XDG_RUNTIME_DIR/butler-dsh-connector.sock`，权限 0600）/ Windows named pipe（`\\.\pipe\butler-dsh-connector`） | Butler 侧主动连接，可多连接 |
| 南向（connector ⇄ DSH 宿主） | 子进程 stdio（stdin/stdout） | 宿主崩溃由 supervisor 重启并重新绑定流 |

控制面帧 = **4 字节大端长度前缀 + UTF-8 JSON**，单帧上限 16 MiB。
数据面（音频/文档大块）= **TLV 帧**（`tag:u16 | len:u32 | value`），单值上限 256 MiB；生产部署建议独立数据通道，避免队头阻塞。

## 2. 帧通用结构

```json
{
  "v": 1,
  "id": "call-17",
  "type": "tool.invoke",
  "stream": true,
  "done": false,
  "payload": { ... },
  "error": null,
  "ts": 1763124960000
}
```

| 字段 | 说明 |
|------|------|
| `v` | 协议版本，当前 1；不匹配必须拒绝（`unsupported`） |
| `id` | 关联 ID。请求/响应/流式 chunk/终止帧共用同一 `id` |
| `type` | 帧类型（见 §3） |
| `stream` | 该帧是流式中间产物 |
| `done` | 该帧是 `id` 的终止帧之一（`tool.result`/`error`） |
| `error` | 仅 `type=error` 帧携带，结构 `{"code","message","data"}` |

**终止语义**：每个 `tool.invoke` 的 `id` 必须以恰好一个终止帧（`tool.result` 或 `error`）收尾；chunk 可以 0..N 个。

## 3. 帧类型

### 3.1 `tool.invoke`（北 → 南）
```json
{"tool": "doc-reader", "args": {"path": "r.pdf"}, "risk": "read_only", "timeoutMs": 5000}
```
- `risk` 由 connector 以注册表为准覆写，调用方传值不可信。
- `timeoutMs=0` 用连接默认超时；超时/取消时 connector 发 `tool.cancel` 并本地终止调用。

### 3.2 `tool.chunk`（南 → 北，stream=true）
```json
{"seq": 0, "data": {...}}
```
`seq` 单调递增；慢消费者丢 chunk 不破坏终止语义（结果帧仍到达）。

### 3.3 `tool.result`（南 → 北，done=true）
```json
{"tool": "doc-reader", "content": {...}, "isError": false}
```

### 3.4 `tool.cancel`（北 → 南）
```json
{"reason": "timeout"}
```

### 3.5 `registry.sync`（双向）
```json
{"version": 7, "capabilities": [
  {"name": "doc-reader", "description": "读取 PDF/DOCX 并返回结构化文本",
   "schema": {...}, "risk": "read_only", "source": "doc-reader@1.2.0", "sourceVer": "1.2.0"}
]}
```
- 宿主上线时主动推送全量；北向也可主动请求（同 type 请求-响应）。
- `description` 质量直接决定 LLM 工具选中率：用动词开头 + 明确场景。

### 3.6 `registry.diff`（南 → 北）
```json
{"from": 7, "to": 9, "upserts": [...], "removals": ["old-tool"]}
```
接收方版本不在 diff 窗口内（tombstone 过期）时必须请求全量 `registry.sync`。

### 3.7 `event.push`（南 → 北）
```json
{"topic": "session.tool.executed", "data": {...}, "ts": 1763124960000}
```
只追加事实流，映射进 Butler 事件总线；对齐 dsh Session Log 语义。

### 3.8 `approve.ask` / `approve.answer`（双向）
```json
// ask
{"requestId": "apr-...", "tool": "fs.write", "source": "evil-plugin",
 "risk": "write", "args": {...}, "reason": "policy: write requires approval"}
// answer
{"requestId": "apr-...", "allowed": true, "reason": "operator approved", "remember": true}
```
两个方向：
1. **北向调用触发的审批**：connector 策略引擎判 `ask` → 通过发起方连接广播 `approve.ask` → 等 `approve.answer`（默认 30s 超时 → **拒绝**，fail-closed）。
2. **插件内部操作触发的审批**：宿主发 `approve.ask` → connector 转发北向 → answer 按 `requestId` 路由回宿主。
`remember=true` 时 connector 缓存（source+tool）维度的结论，后续同类调用直达。

### 3.9 `health.ping` / `health.pong`（双向）
活性探针，5s 超时。

## 4. 错误码（`error.code`）

| code | 含义 |
|------|------|
| `malformed_frame` | 帧损坏/超限/版本不符 |
| `unknown_tool` | 工具未注册 |
| `timeout` | 调用超时 |
| `cancelled` | 上游取消 |
| `denied` | 权限拒绝 |
| `upstream_error` | 宿主/插件执行错误 |
| `unavailable` | 南向断连/重启中 |
| `unsupported` | 未知帧类型（必须回此码，禁止静默丢弃） |
| `internal` | 连接器内部错误 |

## 5. 时序示例（一次带审批的工具调用）

```
Butler                connector                 DSH宿主
  │ tool.invoke          │                        │
  ├─────────────────────>│ (策略: ask)            │
  │<─────────────────────┤ approve.ask            │
  │ approve.answer(true) │                        │
  ├─────────────────────>│ tool.invoke            │
  │                      ├───────────────────────>│
  │                      │ tool.chunk(seq 0..N)   │
  │<─────────────────────┤<───────────────────────┤
  │                      │ tool.result            │
  │<─────────────────────┤<───────────────────────┤
  │ tool.result (done)   │                        │
```

## 6. 兼容性规则

1. 新增帧类型：旧端遇未知 type 回 `unsupported`，新端需容忍。
2. 新增 payload 字段：必须可选且有默认语义。
3. `v` 仅在破坏性变更时递增；递增后旧连接器拒绝新宿主并给出可读错误。
4. 帧的 JSON 序列化字节稳定性由 golden-file 测试保证（Session Log 回放依赖它）。
