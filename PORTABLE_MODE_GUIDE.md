# Butler 便携模式与本地依赖管理指南

本文档详细介绍了 Butler 的“便携模式”（Portable Mode），该功能允许用户将所有 Python 第三方库安装在项目文件夹内，实现“绿色版”运行，无需安装全局依赖。

## 1. 什么是便携模式？

在标准模式下，Python 库通常安装在系统的 `site-packages` 文件夹或虚拟环境（venv）中。
**便携模式**则利用 `pip` 的 `--target` 参数，将库文件直接下载到项目根目录下的 `lib_external` 文件夹中。

### 优点：
- **零污染**：不修改系统全局 Python 环境。
- **便携性**：配置完成后，整个项目文件夹（包括依赖库）可以拷贝到其他相同操作系统和架构的电脑上直接运行。
- **独立性**：避免不同项目之间的版本冲突。

---

## 2. 如何开启便携模式

### 方法 A：通过安装脚本（推荐）
在首次部署项目时，运行以下脚本：
- **Windows**: 双击 `install.bat`
- **Linux/macOS**: 运行 `./install.sh`

在步骤 2（安装依赖）时，程序会询问：
`Do you want to install dependencies to a local folder (Portable Mode)? (y/n)`
输入 `y` 即可自动开始本地化安装。

### 方法 B：手动命令行安装
你可以随时使用内置的 `dependency_manager` 工具进行管理：

1.  **安装所有预设依赖**（基于 `requirements.txt`）：
    ```bash
    python -m package.dependency_manager install_all
    ```

2.  **安装特定的第三方库**：
    ```bash
    python -m package.dependency_manager install <包名>
    ```
    *例如：`python -m package.dependency_manager install requests`*

---

## 3. 在 Jarvis 中通过对话管理

Butler (Jarvis) 已集成依赖管理意图。你可以直接对它说：

- “**帮我安装所有本地依赖**”
- “**安装本地库 requests**”
- “**更新本地第三方库**”

Jarvis 会在后台调用 `dependency_manager` 并实时反馈进度。

---

## 4. 技术实现细节

### 路径自动加载
项目在启动时（`butler/main.py`），会自动执行以下逻辑：
1. 识别项目根目录。
2. 将项目根目录加入 `sys.path`。
3. 检查是否存在 `lib_external` 文件夹。
4. 如果存在，将其插入到 `sys.path` 的首位。

这意味着 `lib_external` 中的库将具有**最高优先级**。如果本地和系统同时存在某个库，程序将优先使用本地版本。

### 数据回收保护
内置的 `data_recycler`（数据回收器）已配置为保护 `lib_external` 文件夹，执行系统清理时不会误删已下载的库文件。

---

## 5. 注意事项

- **平台兼容性**：包含 C 扩展的库（如 `numpy`, `opencv`）在下载时会针对当前操作系统和 CPU 架构进行编译。如果你在 Windows 上下载了库，将其拷贝到 Linux 上可能无法运行。
- **Python 版本**：请确保运行环境的 Python 主版本号（如 3.12）与下载库时使用的版本一致。
- **磁盘空间**：所有依赖库都存储在项目内，会增加项目文件夹的大小（通常在 200MB - 1GB 之间，取决于安装的库数量）。
