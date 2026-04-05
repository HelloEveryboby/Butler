# Butler 系统实现细节 (Implementation Details)

本文档深入探讨了 Butler 核心组件的具体技术实现、算法逻辑以及底层协议。

## 1. Butler Hybrid-Link (BHL) 通信协议

BHL 是系统实现跨语言、高性能扩展的核心协议。

### 1.1 通信模型
BHL 基于 **JSON-RPC 2.0** 协议，通过标准输入输出 (STDIN/STDOUT) 进行全双工通信：
-   **Python 端 (Client)**: 启动子进程并维持长连接。
-   **二进制端 (Server)**: 监听 STDIN 并在处理完成后将结果 JSON 序列化并打印到 STDOUT。

### 1.2 报文结构
所有请求均包含 `priority`（优先级）字段。如果子进程内部维护了任务队列，高优先级的请求将被优先处理。

**请求示例**:
```json
{
  "jsonrpc": "2.0",
  "method": "calculate_pi",
  "params": {"digits": 100},
  "id": "uuid-1234",
  "priority": 10
}
```

### 1.3 自动回退 (Fallback Mechanism)
当二进制模块缺失或由于系统环境问题无法启动时，`HybridLinkClient` 会自动重定向至 `hybrid_fallbacks.py`。该模块包含了一些核心算法的 Python 纯代码实现，确保系统在基础功能层面的“零依赖”运行。

---

## 2. 意图解析与 NLU 服务

### 2.1 基于提示工程的意图提取
`NLUService` 使用 DeepSeek 模型执行 NLU。系统不再硬编码正则表达式，而是通过 `prompts.json` 中定义的结构化 Prompt，引导模型将自然语言映射到 `program_mapping.json` 中定义的 Intent。

### 2.2 实体识别
系统不仅识别意图，还会同步提取关键实体（Entities）。例如：
-   输入：“帮我把 `report.pdf` 翻译成英文”。
-   输出：`{"intent": "translate_file", "entities": {"file_path": "report.pdf", "target_lang": "en"}}`。

---

## 3. Zvec 本地向量库与 RAG 流程

当 Redis 服务不可用时，系统会自动激活 **Zvec**。

### 3.1 核心原理
Zvec 使用 C++ 开发并封装为 Python 模块，支持完全离线的向量索引。
1.  **分块 (Chunking)**: 文档被切分为固定大小的片段（如 500 字符），并保留一定的重叠（Overlap）。
2.  **嵌入 (Embedding)**: 使用 DeepSeek 的 Embedding API 或本地模型将文本转化为 1024/1536 维向量。
3.  **索引 (Indexing)**: Zvec 在内存中构建向量索引并定期持久化到磁盘。

### 3.2 检索增强生成 (RAG)
1.  用户提问。
2.  将问题转化为向量，在 Zvec 中检索最相似的 Top-K 文档片段。
3.  将片段作为 Context 拼接至 Prompt 底部。
4.  LLM 基于 Context 生成精准回答。

---

## 4. 现代 Web UI (Modern UI) 架构

### 4.1 技术栈
-   **前端**: 纯原生 HTML5, CSS3 (CSS Variables + Glassmorphism), JS (ES6+)。
-   **后端**: 使用 Python Flask 或独立 WebSocket 端口作为 API 后端。

### 4.2 玻璃拟态与主题持久化
界面采用 Apple 风格的玻璃拟态设计（Glassmorphism）。
-   **CSS Variables**: 所有配色均通过变量控制，支持 `google` (浅色) 和 `apple` (深色) 主题的即时切换。
-   **配置同步**: 用户在 Web 端切换主题后，配置会自动回传给 `config_loader` 并持久化到 `config/system_config.json`。

---

## 5. 自治与自愈系统 (Autonomous & Self-Healing)

### 5.1 Autonomous Switchboard (AS)
AS 是一个常驻线程，负责周期性地：
-   **僵尸清理**: 终止父进程已退出的 BHL 子进程。
-   **资源熔断**: 监控 Butler 系统整体的内存占比。如果内存占用超过阈值且处于非任务状态，则主动触发垃圾回收。

### 5.2 FileSystemGuard
该组件位于 `butler/core/file_guard.py`，通过拦截系统的删除/修改指令（在 UI 层级）保护关键路径。对于 root 权限下的非法操作，系统通过 `Self-Healing` 模块中的文件校验和（Checksum）检测文件的完整性。
