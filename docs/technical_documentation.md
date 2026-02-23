# Butler 系统技术文档 (Technical Documentation)

## 1. 系统概述

Butler 是一个高度模块化的智能助手系统，旨在通过统一的界面（GUI、语音、命令行）调用各种专业工具。系统核心基于 Python 开发，并通过 **Butler Hybrid-Link (BHL)** 协议扩展了对 C++、Go 和 Rust 的支持，以实现性能和安全性的最大化。

## 2. 代码分类架构

所有的功能模块（Packages）均位于 `package/` 目录下，并按功能细分为以下子目录：

### 2.1 安全 (Security)
- **核心逻辑**: 实现本地数据的 AES-256 加密存储。
- **典型应用**: `AccountPassword.py` 利用主密码机制保护用户的所有账号信息。
- **使用场景**: 管理密码、敏感文件加密、操作权限控制。

### 2.2 文档处理 (Document)
- **核心逻辑**: 集成 `markitdown` 和 `marker` 库进行多格式文档转换。
- **典型应用**: `document_interpreter.py` 结合 DeepSeek API 对上传的文档进行总结和问答。
- **使用场景**: PDF 转 Markdown、Excel 数据清洗、长文档摘要。

### 2.3 核心工具 (Core Utils)
- **核心逻辑**: 提供系统运行的基础设施，如日志、依赖管理、多线程调度等。
- **典型应用**: `autonomous_switch.py` (自动交换机) 监控系统负载，自动终止冲突或过载的进程。
- **使用场景**: 环境配置、日志审计、进程治理。

### 2.4 算法 (Algorithm)
- **核心逻辑**: 提供高效的计算模型。
- **典型应用**: `algorithm.py` 提供的高性能混合排序。
- **使用场景**: 大规模数据排序、任务执行路径优化。

### 2.5 视觉识别 (Vision)
- **核心逻辑**: 集成 OpenCV 和 OCR 技术。
- **使用场景**: 图像识别、二维码扫描、文字提取。

### 2.6 网络与通讯 (Network)
- **核心逻辑**: 处理外部 API 交互、邮件发送及网络抓取。
- **使用场景**: 查天气、发邮件、网页数据抓取、云盘管理。

---

## 3. 混合链接系统 (BHL)

### 3.1 协议简介
BHL 允许 Python 逻辑透明地调用高性能的二进制模块。通信通过标准输入输出（STDIN/STDOUT）采用 JSON-RPC 2.0 格式进行。

### 3.2 模块分布
- **C++ (`hybrid_compute`)**: 负责高密集度数学运算。
- **Go (`hybrid_net`)**: 利用 Goroutine 实现高并发网络扫描。
- **Rust (`hybrid_crypto`)**: 负责对内存安全性要求极高的哈希计算。

---

## 4. 详细使用指南

### 4.1 自动交换机 (Autonomous Switch)
自动交换机是 Butler 的“系统管理员”，在后台静默运行。
- **启动**: `python -m package.core_utils.autonomous_switch`
- **功能**:
    - 自动清理重复启动的工具。
    - 当 CPU 占用超过 90% 时触发熔断保护。
    - 识别并治理 BHL 混合语言进程。

### 4.2 账号管理器 (Account Manager)
- **首次运行**: 需要设置一个主密码。请务必牢记，丢失后无法恢复数据。
- **自动登录**: 选择账号后，程序会模拟键盘输入用户名、Tab、密码并回车。

### 4.3 文档转换 (Markdown Converter)
- **命令示例**: `python -m package.document.markdown_converter <input_file>`
- **支持格式**: PDF, DOCX, XLSX, PPTX, EPUB, HTML。

---

## 5. 开发者规范

### 5.1 添加新功能
1. 在 `package/` 的相应分类下创建 `.py` 文件。
2. 必须包含一个 `run()` 函数作为入口。
3. 如果需要被意图系统识别，请在 `butler/program_mapping.json` 中添加映射。

### 5.2 注释规范
所有代码均需包含中文注释及标准的 Python Docstring，以保证系统可维护性。
