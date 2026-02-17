# Butler 便携模式与本地环境管理指南

本文档详细介绍了 Butler 的“便携模式”（Portable Mode），该功能允许用户将所有 Python 第三方库甚至 Python 解释器本身都安装在项目文件夹内，实现“完全脱离系统环境”的绿色运行。

## 1. 什么是便携模式？

在标准模式下，Python 库通常安装在系统的 `site-packages` 文件夹或虚拟环境（venv）中。
**便携模式**则利用 `pip` 的 `--target` 参数，将库文件直接下载到项目根目录下的 `lib_external` 文件夹中。

### 优点：
- **零污染**：不修改系统全局 Python 环境。
- **完全便携（全量模式）**：包含 Python 运行环境，在未安装 Python 的纯净电脑上也能双击即用。
- **独立性**：避免不同项目或系统 Python 版本冲突。

---

## 2. 模式对比

| 模式 | 依赖系统 Python | 包含第三方库 | 适用场景 |
| :--- | :--- | :--- | :--- |
| **标准模式 (Standard)** | 是 | 否 (安装在全局/venv) | 常规开发使用 |
| **便携模式 (Portable)** | 是 | 是 (安装在 lib_external) | 避免库版本冲突，项目间迁移 |
| **全量便携模式 (Full Portable)** | **否** | 是 (包含 runtime 目录) | **无 Python 环境的电脑，纯绿色版** |

---

## 3. 如何开启便携模式

### 方法 A：通过安装脚本（推荐）
在首次部署项目时，运行以下脚本：
- **Windows**: 双击 `install.bat`
- **Linux/macOS**: 运行 `./install.sh`

在步骤 2（安装依赖）时，程序会提供三个选项：
1. **Standard**: 常规安装。
2. **Portable**: 仅本地化第三方库。
3. **Full Portable**: 同时下载 Python 运行环境和第三方库。

选择 `3` 即可实现真正的“解压即用”。

### 方法 B：手动命令行安装
你可以随时使用内置的 `dependency_manager` 工具进行管理：

0.  **下载便携式 Python 运行环境**：
    ```bash
    python -m package.dependency_manager setup_runtime
    ```
    *执行后将生成 `runtime` 文件夹。*

1.  **安装所有预设依赖**：
    ```bash
    # Windows (如果已下载 runtime)
    runtime\python.exe -m package.dependency_manager install_all

    # Linux/macOS (如果已下载 runtime)
    ./runtime/bin/python3 -m package.dependency_manager install_all
    ```

2.  **安装特定的第三方库**：
    ```bash
    python -m package.dependency_manager install <包名>
    ```

---

## 4. 在 Jarvis 中通过对话管理

Butler (Jarvis) 已集成依赖管理意图。你可以直接对它说：

- “**帮我安装所有本地依赖**”
- “**安装本地库 requests**”
- “**更新本地第三方库**”
- “**设置便携式运行环境**”

---

## 5. 技术实现细节

### 运行环境优先级
启动脚本（`run.bat` / `run.sh`）会优先检查项目根目录下的 `runtime` 文件夹。如果存在有效的 Python 解释器，则跳过系统变量中的 Python，使用内置环境运行。

### 路径自动加载
项目在启动时（`butler/main.py`），会自动执行以下逻辑：
1. 识别项目根目录。
2. 将项目根目录加入 `sys.path`。
3. 检查是否存在 `lib_external` 文件夹。
4. 如果存在，将其插入到 `sys.path` 的首位。

### 数据回收保护
内置的 `data_recycler`（数据回收器）已配置为保护 `lib_external` 和 `runtime` 文件夹，执行系统清理时不会误删关键文件。

---

## 6. 注意事项

- **平台兼容性**：包含 C 扩展的库（如 `numpy`, `opencv`）在下载时会针对当前操作系统和 CPU 架构进行编译。如果你在 Windows 上下载了库，将其拷贝到 Linux 上可能无法运行。
- **Python 版本**：请确保运行环境的 Python 主版本号（如 3.12）与下载库时使用的版本一致。
- **磁盘空间**：所有依赖库和运行环境都存储在项目内，会增加项目文件夹的大小。
