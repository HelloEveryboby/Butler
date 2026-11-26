# 11 · 运行时服务与通信

> 本章覆盖“胶水层”：事件/消息、任务与团队、远程执行、REST/gRPC、硬件抽象、密钥、数据库迁移、配置、生命周期、扩展管理。

## 11.1 事件总线 `EventBus`

`butler/core/event_bus.py`，全局单例 `event_bus`（保留最近 100 条历史）。

| 方法 | 行为 |
| :--- | :--- |
| `subscribe(event_type, callback)` | 订阅（去重） |
| `unsubscribe(...)` | 取消订阅 |
| `emit(event_type, *args, **kwargs)` | 同步顺序调用，单回调异常被隔离 |
| `emit_async(...)` | 线程池（4 worker）异步执行 |
| `get_history()` / `clear()` | 调试 |

典型事件：`ui_output`、`voice_status`、`theme_change`、`cron:*`、`workflow_execute`、`screenshot_update`、`PROGRESS_UPDATE`、`NOTIFICATION_PUSH/CLOSE`。

## 11.2 消息总线与黑板

| 组件 | 文件 | 说明 |
| :--- | :--- | :--- |
| `MessageBus` | `butler/core/message_bus.py` | 基于文件系统的**持久化** Agent 间异步通讯；收件箱在 `data/team/inbox/`；支持 `message`/`broadcast`/`shutdown_request`/`plan_approval_*`；接收者名做路径穿越清洗 |
| `EphemeralBlackboard` | `butler/core/blackboard.py` | 带 TTL 的临时状态交换中心（ESB）；`write(key, value, ttl)` / `read` / `get_snapshot_payload(keys)`；供 LDST 影子链在技能间传递中间产物 |

## 11.3 任务与团队

| 组件 | 文件 | 说明 |
| :--- | :--- | :--- |
| `TaskManager` | `butler/core/task_manager.py` | 线程池（默认 10 worker）；`submit(func, *args, name, timeout)`；业务任务 `BusinessTask`（pending/…，支持 `blocked_by` 依赖、`claim` 认领），持久化到 SQLite |
| `TeamManager` | `butler/core/team_manager.py` | 单例；`spawn_teammate(name, role, prompt)` 启动协作队友线程；`list_teammates()`；状态保存在 `data/team` |
| `ProactiveAgent` / `FocusMode` | 见 [10](./10-kairos.md) | — |

## 11.4 远程执行节点：`RunnerServer`（Go Runner）

`butler/core/runner_server.py`：

- **传输**：WebSocket，默认 `127.0.0.1:8000`。
- **安全**：Token 强度校验（≥16 字符）+ **HMAC-SHA256 签名**（而非明文 token）+ 滑动窗口限流（1s/50 次）+ 心跳。
- **消息类型**：`register`（注册并上报环境：OS/arch/shell/权限/工具链）、`screenshot`、`sys`、`ok`、`fail`、命令下发与响应（`request_id`）。
- **能力**：`send_command(..., timeout)`、`send_command_sync()`、`broadcast_command()`、`get_all_runners_info()`、`health_check()`、`broadcast_metrics()`。
- **与 Butler 集成**：`register_event_callback(self._on_runner_event)`；`_get_runner_env_prompt_extension()` 把节点环境注入 LLM 提示，避免下发不兼容指令。
- **驱动端**：`programs/butler_runner`（Go）。

## 11.5 REST API 网关（FastAPI）

两个入口：

| 入口 | 文件 | 说明 |
| :--- | :--- | :--- |
| 桌面内嵌 API | `butler/core/api.py` | `app = FastAPI(...)`；默认 `127.0.0.1:5001`，可自签名 SSL；守护线程启动 |
| v2 运行时 API | `butler/core/runtime.py` | `ButlerRuntime._start_api_server()`；`/api/health`、`/api/task`、`/api/packages`、`/api/tasks` |

`butler/core/api.py` 的路由与安全：

| 端点 | 认证 | 说明 |
| :--- | :--- | :--- |
| `GET /healthz` | 无 | 存活探针 |
| `GET /readyz` | 无 | 就绪探针：SecretVault / NLU / Runner / 熔断器状态，返回 `ready/degraded`（NLU 项因引用未定义属性会显示为 `error`，属已知缺陷） |
| `GET /health` | 无 | 简单健康检查 |
| `POST /sensor/data` | Bearer | 转发传感 JSON 到 `SensingAPI` |
| `POST /api/features/{module}/{action}` | 视实现 | 统一功能中心：`git` / `session` / `project` / `worktree` / `computer` |

安全措施：
- `HTTPBearer` token 从 `SecretVault` 读取（`rest_api_bearer_token`）。
- CORS 白名单（`localhost/127.0.0.1:3000`）。
- 安全响应头中间件：CSP `default-src 'self'`、`X-Frame-Options: DENY`、`nosniff`、`X-XSS-Protection`。

## 11.6 gRPC 数字员工接口

`butler/core/agent_node.py` + `docs/butler_agent.proto` + 生成的 `butler_agent_pb2*.py`：

- `ButlerAgentServicer.ExecuteTask`：接收 `skill_id/action/payload_json`，调用 `SkillManager.execute()`。
- `GetSystemStatus`：返回 CPU/内存/hostname（来自 `dras_manager.get_system_stats()`）。
- 提供跨进程/跨机器的“远程执行技能”能力。

## 11.7 硬件抽象层（HAL）与显示

| 模块 | 文件 | 说明 |
| :--- | :--- | :--- |
| HAL 抽象 | `butler/core/hal/base.py`、`butler/hal/base.py` | `AbstractHAL`、`BaseSensor`、`BaseAudio`、`BaseDisplay` 接口 |
| 系统资源传感器 | `butler/core/hal/sensors.py` | `SystemResourceSensor.read()` 采集 CPU/内存/磁盘/电量 |
| 硬件驱动 | `butler/hal/drivers/pc`、`package/device/*` | STM32 桥、BLE、红外、USB 屏、虚拟键盘、ADB 等 |
| USB 屏 | `butler/usb_screen.py` | 40×8 字符屏输出；`ui_print` 同步显示 |
| 显示协议 | `butler/core/display_protocol.py` | `SocketDisplayServer`（TCP `9000`），供 ESP32 等通过 Wi-Fi 拉取渲染指令 |
| 传感 API | `butler/core/sensing_api.py` | 解析标准传感器 JSON 并触发事件 |

无硬件时全部降级为“纯软件管家模式”，不抛阻断错误。

## 11.8 密钥库 `SecretVault`（零信任）

`butler/core/secret_vault.py`：

- 存储：`data/system_data/secrets.db`（SQLite）。
- 加密：**PBKDF2** 派生主密钥 + **AES-256-GCM**；可选系统 **Keyring**。
- 主密码来源：`BUTLER_MASTER_PASSWORD` 环境变量或已初始化的密钥库。
- 常见密钥：`rest_api_bearer_token`、`runner_token`、第三方 API Key。
- `bootstrap.get_secure_runner_token()` / `get_secure_api_token()`：优先 Vault → 环境变量 → 生成临时 token（并 `warning` 提示持久化）。

## 11.9 数据库迁移

`butler/core/db_migrations.py` 的 `DatabaseMigrationRunner`：

- 默认数据库：`data/system_data/long_memory.db`。
- 迁移目录：`package/storage_hub/migrations/`。
- `run_all_migrations()` 在 `ButlerRuntime.init()` 与 CLI 启动前自动执行，避免“冷启动表不存在”。
- 相关：`PackageRegistry`（`packages` 表）、`TaskManager`（`tasks` 表）、`busy` 中 `tasks` 表缺失时自动补建。

## 11.10 配置与生命周期

| 组件 | 文件 | 说明 |
| :--- | :--- | :--- |
| `ConfigLoader` | `package/core_utils/config_loader.py` | 单例；YAML 优先、JSON 兜底；`${VAR:-default}` 环境变量替换；Pydantic `ButlerConfig` 校验；`get("a.b.c")` 点路径 |
| `ConfigManager` | `butler/core/config_manager.py` | 可写的运行时配置（`get/set(persist)/save_yaml/reload/validate_required_keys`） |
| `SystemLifecycle` | `butler/core/lifecycle.py` | 状态机 `INIT→STARTING→RUNNING→STOPPING→SHUTDOWN` |
| `ExtensionManager` | `butler/core/extension_manager.py` | 统一扫描插件/包/外部程序 |
| `PackageLoader/Registry/Manifest` | `butler/package_runtime/*` | 安装式包管理（`butler/data/installed_packages/`，`packages` 表） |
| `plugin_bundle.py` | `butler/core/plugin_bundle.py` | dsh / Claude Code 插件包声明式兼容层 |

## 11.11 其它基础设施

| 模块 | 作用 |
| :--- | :--- |
| `butler/core/security` + `butler/security/audit.py` | `SecurityAuditor.log_action_permission()` 写 `data/security_audit.log` |
| `butler/core/errors.py` | 统一错误码 `BTL-xxxx` + `format_error()` |
| `butler/core/git_tools.py` | 内置 Git 能力（status/diff/commit/push/PR/branch/worktree） |
| `butler/core/session_modes.py` / `project_manager.py` | 会话模式与多项目管理 |
| `butler/core/capability_reporter.py` | 启动时扫描能力可用性，显式报告 `full/partial/absent` |
| `butler/core/ipc_tlv.py` | TLV 进程间通信 |
| `butler/core/alias_store.py` / `naming_policy.py` | 中文显示名 ↔ 英文/拼音真实名映射 |

## 11.12 相关章节

- 架构中的位置：[02 整体架构](./02-architecture.md)
- 配置与 CLI：[14 配置与 CLI](./14-config-cli.md)
- 部署端口：[16 运行、部署与测试](./16-deployment-testing.md)
