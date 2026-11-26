# 12 · `package/` 能力层

> `package/` 是 Butler 的“通用能力库”，与 `butler/`（系统编排）解耦，可被技能、CLI、Agent 直接复用。
> 模块普遍采用“重依赖延迟导入 + 缺失降级”的写法，保证在精简环境中仍可启动。

## 12.1 目录与职责

```text
package/
├── algorithm/        # 算法：DP 路径优化、数学工具、排序/搜索/A*/KMeans
├── core_utils/       # 基础设施：日志、配置、依赖、配额、健康、知识库、自动交换机
├── custom_tools/     # 自定义工具占位
├── device/           # 设备：STM32/BLE/红外/USB/ADB/终端/虚拟键盘/OS 工具
├── document/         # 文档：Excel/Word/PPT/PDF/翻译/转换/摘要
├── file_system/      # 文件：整理、归档、回收、迁移、守卫
├── media/            # 媒体：音乐库/扫描/播放
├── network/          # 网络：爬虫、邮件、云盘、天气、图片搜索、Go 网络工具
├── security/         # 安全：加密、密码管理、权限边界、隔离区
├── storage_hub/      # 云存储聚合引擎 + SQLite 迁移
└── vision/           # 视觉：图像/二维码/文字识别
```

## 12.2 `algorithm/` 算法

| 文件 | 内容 |
| :--- | :--- |
| `algorithm.py` | 基础算法集合 |
| `algorithm1.py` | **基于动态规划的模块执行路径优化**：DAG 依赖解析、最低成本序列、拓扑排序与环检测 |
| `math_tool.py` | 数学工具封装 |

> 运行时另有 `butler/core/algorithms.py`：排序（内省排序/归并/堆）、二分、A*/Dijkstra/BFS/DFS、余弦相似度、RGB 边缘检测、矩阵快速幂 Fibonacci、KMeans，以及 **`LDSTResolver`（技能影子链）** 与 **`DynamicResourceManager`（DRAS 资源调度）**。二者不要混淆。

## 12.3 `core_utils/` 基础设施

| 文件 | 作用 |
| :--- | :--- |
| `log_manager.py` | `LogManager` 单例；`get_logger()`；trace-id 上下文；`log_stealth()` 隐蔽日志 |
| `config_loader.py` | 单例配置加载；YAML/JSON；`${ENV}` 替换；Pydantic 校验；`get/save` |
| `dependency_manager.py` | 便携依赖：安装到 `lib_external/`；下载便携 Python 运行时；`install_all` |
| `quota_manager.py` | 单例 `QuotaManager`：`check_quota()` / `update_usage(tokens)` / `get_usage_report()`；耗尽时全局暂停 |
| `autonomous_switch.py` | 自动交换机：跨语言进程治理、动态调度、独占模式、资源熔断（>90% 保护） |
| `health_monitor.py` | 资源审计、BHL 二进制完整性校验、磁盘追踪、自愈联动 |
| `knowledge_base_manager.py` | 基于 Zvec 的本地文档索引与语义检索 |
| `hybrid_memory_manager.py` / `hybrid_orchestrator.py` | 混合记忆/混合系统协调 |
| `program_manager.py` / `schedule_management.py` / `system_executor_tool.py` / `thread.py` / `data_analyzer.py` / `embedding_utils.py` / `dev_tools.py` | 程序管理、日程、多线程审计执行、数据分析、嵌入、开发工具 |

## 12.4 `document/` 文档

| 文件 | 作用 |
| :--- | :--- |
| `document_interpreter.py` | 结合 LLM 的文档总结与问答 |
| `excel_master_processor.py` | Excel 创建与高级公式/计算引擎 |
| `xlsx_recalc_tool.py` | XLSX 重算工具 |
| `expense_report_engine.py` | 报销单生成 |
| `office_automator.py` | Office 自动化（Word/PPT/Excel） |
| `file_converter.py` / `markdown_converter.py` / `marker_tool.py` / `hybrid_markdown_tool.py` | 多格式转 Markdown/HTML/JSON（marker-lite、markitdown） |
| `translators.py` | 统一翻译系统的兼容门面 |
| `TextEditor.py` / `cross_folder_analyzer.py` / `memory_tools*.py` / `task_manager_bridge.py` | 文本编辑、跨目录分析、记忆工具、任务桥接 |

> 翻译系统完整实现在 `package/document/translate_system/`（引擎、TM、术语表、双语导出），测试见 `tests/translate_system/`。

## 12.5 `device/` 设备与硬件

| 文件 | 作用 |
| :--- | :--- |
| `stm32_hw_bridge.py` | `STM32HardwareBridge`：串口发现 STM32 节点 |
| `hardware_manager.py` | 硬件管理器：统一设备生命周期 |
| `ble_connector.py` / `ir_manager.py` | BLE / 红外控制 |
| `adbsploit.py` / `high_perf_terminal.py` / `terminal.py` | ADB、高性能终端、PTY 终端 |
| `standalone_manager.py` | 独立进程/节点管理器 |
| `virtual_keyboard.py` / `os_utils.py` / `device_config_tool.py` | 虚拟键盘、OS 操作（含 `capture_screen()`）、设备配置 |

## 12.6 `file_system/` 文件

| 文件 | 作用 |
| :--- | :--- |
| `file_manager.py` / `OrganizeIT.py` | 文件管理与自动整理 |
| `archiver.py` | 压缩/解压（含流式替换 `hybrid_archive` 封装） |
| `data_recycler.py` | 临时数据回收（`/cleanup` 调用） |
| `guard.py` | `FileSystemGuard` 文件系统守卫 |
| `migration_engine.py` | `SmartMigrationEngine` 智能迁移 |

## 12.7 `network/` 网络

| 文件 | 作用 |
| :--- | :--- |
| `crawler.py` | 网页抓取（可结合 scrapy/selenium） |
| `e-mail.py` | 多邮箱账户管理；配置 `email_config.json` |
| `cloud_storage_manager.py` | 百度网盘（bypy）上传/下载/列表；接入 `storage_hub` |
| `weather.py` / `image_search_tool.py` / `network_app.py` | 天气、图片搜索、网络应用 |
| `go_net_tool.py` | Go 高性能网络工具封装（BHL） |

## 12.8 `security/` 安全

| 文件 | 作用 |
| :--- | :--- |
| `encrypt.py` | `SecureVault`、`DualLayerEncryptor`（双层加密，`Butler.__init__` 使用） |
| `crypto_core.py` | `SymmetricCrypto`（AES）与 `AsymmetricCrypto`（RSA/ECC） |
| `AccountPassword.py` | `AccountManager`：主密码保护账号密码库 |
| `asymmetric_tool.py` / `high_perf_crypto.py` | RSA/ECC 工具；高性能加密（可接 Rust `hybrid_crypto`） |
| `Limits_of_authority.py` / `authority_config.json` | 权限边界配置 |
| `quarantine.py` | 隔离区（可疑文件/内容隔离） |

## 12.9 `storage_hub/` 与 `vision/`

- `storage_hub/storage_hub.py`：`StorageHub` 云存储聚合引擎；`drivers/` 各云盘驱动；`migrations/` SQLite 迁移脚本（被 `db_migrations` 执行）。
- `vision/`：`PictureRecognition.py`、`QR-Code-Recognition.py`、`Word_reading.py`（图像识别、二维码、OCR，依赖 opencv/pytesseract，可选）。

## 12.10 使用约定

- 外部能力优先从 `package/` 复用，不要在 `butler/` 里重复造轮子。
- 重依赖（cv2、numpy、pytesseract、scrapy…）必须**延迟导入 + try/except 降级**。
- 新增能力应提供纯 Python 回退路径，或通过 BHL 接入原生实现。

## 12.11 相关章节

- 技能如何调用这些能力：[07 技能系统](./07-skills.md)
- 依赖分层：[15 依赖关系](./15-dependencies.md)
- 设备/HAL：[11 运行时服务](./11-runtime-services.md)
