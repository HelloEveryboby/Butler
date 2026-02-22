# Butler 混合链接 (BHL) 协议规范

## 1. 概述
Butler 混合链接 (BHL) 协议旨在实现 Butler 的 Python 核心与使用其他语言（C++、Go、Rust 等）编写的专用模块之间的轻量级跨语言通信。该协议针对 PC 环境进行了优化，并考虑了未来向微控制器 (MCU) 的移植。

## 2. 传输层
- **PC**: 标准输入 (Stdin) 和标准输出 (Stdout) 管道。
- **MCU**: UART 串口或 MQTT 主题。
- **帧格式**: 每个 JSON 消息必须位于单行（行分隔的 JSON）。

## 3. 消息格式
BHL 遵循简化的 JSON-RPC 2.0 结构。

### 3.1 请求 (Python -> 模块)
```json
{
  "jsonrpc": "2.0",
  "method": "function_name",
  "params": {
    "key": "value"
  },
  "id": "unique_id"
}
```

### 3.2 响应 (模块 -> Python)
```json
{
  "jsonrpc": "2.0",
  "result": {
    "data": "..."
  },
  "id": "unique_id"
}
```

### 3.3 异步事件 (模块 -> Python)
当模块需要主动推送通知（如扫描进度或状态更新）时使用，不包含 `id` 字段。
```json
{
  "jsonrpc": "2.0",
  "method": "event_name",
  "params": {
    "key": "value"
  }
}
```

### 3.4 错误
```json
{
  "jsonrpc": "2.0",
  "error": {
    "code": -32000,
    "message": "错误描述"
  },
  "id": "unique_id"
}
```

## 4. 生命周期
1. **发现**: Butler 扫描 `manifest.json` 以识别兼容 BHL 的程序。
2. **启动**: Butler 启动外部程序并建立管道连接。
3. **执行**: Butler 发送请求；程序处理请求并返回响应或推送事件。
4. **关闭**: Butler 发送 `exit` 方法或直接终止进程。

## 5. 设计原则 (扬长避短)
- **Python**: 任务编排、AI 集成、字符串处理及回退逻辑。
- **C++**: 高性能数学运算、硬件级控制。
- **Go**: 高并发网络处理、高吞吐量数据流。
- **Rust**: 内存安全的快速计算、加密基元。

## 6. 当前实现功能

### 6.1 Python (核心与回退)
- **角色**: 中央协调器 (`HybridLinkClient`) 与回退方案提供者。
- **回退功能**: 为所有 BHL 方法提供纯 Python 实现，确保在缺少外部语言环境时系统仍能运行。
- **关键机制**:
  - `dispatch_fallback`: 将请求路由至本地 Python 实现。
  - 事件分发: 处理来自模块的异步通知。

### 6.2 C++ (性能模块)
- **角色**: 处理计算密集型任务。
- **已实现方法**:
  - `factorize`: 针对大整数的高速质因数分解。
  - `fibonacci`: 针对大斐波那契数优化的迭代计算。

### 6.3 Go (并发模块)
- **角色**: 高并发网络任务与实时监控。
- **已实现方法**:
  - `check_network`: 对多个 URL 进行并发 HTTP 状态检查。
  - `scan_ports`: 高速并行 TCP 端口扫描。
- **推送事件**:
  - `scan_started`: 网络扫描开始时的异步通知。

### 6.4 Rust (安全模块)
- **角色**: 内存安全、高性能的加密处理。
- **已实现方法**:
  - `hash_sha256`: 使用工业级库进行极速 SHA256 哈希计算。

## 7. Hybrid-or-Python 回退机制
为了在不同环境下保持系统稳定性，Butler 实施了“混合或 Python”策略：
1. **检测**: `CodeExecutionManager` 检测所需编译器 (`g++`, `go`, `cargo`) 或预编译二进制文件是否可用。
2. **平滑降级**: 如果混合模块无法编译或启动，`HybridLinkClient` 会自动将 BHL 调用重定向到 `butler/core/hybrid_fallbacks.py` 中的对应 Python 实现。
3. **透明化**: 无论任务是由高性能原生模块还是 Python 回退方案执行，上层编排逻辑（如 `hybrid_orchestrator.py`）均保持一致，无需特殊处理。
