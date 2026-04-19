# Butler - 智能助手系统

Butler 是一个功能丰富的智能助手系统，使用 Python 开发。它集成了自然语言处理、强大的算法库、动态程序管理以及可扩展的插件系统。Butler 采用模块化架构设计，能够通过文本、语音或 API 命令执行各种复杂任务。

该项目还包含一个全面的常用算法库，并通过开发者友好的 REST API 公开它们，使其可以从任何编程语言访问。

## 功能特性

*   **对话式 AI**：使用 DeepSeek API 进行自然语言理解和响应生成。
*   **可扩展的程序管理**：动态加载和执行外部程序模块。
*   **高级算法库**：丰富、高效且文档齐全的算法库。
*   **开发者友好 API**：用于直接访问算法库的专用 REST API。
*   **交互式命令面板**：基于 Tkinter 的 GUI，用于文本交互（经典模式）。
*   **精致 Web UI**：基于 HTML/CSS/JS 的现代化玻璃拟态界面，采用“无输入框”流式交互逻辑（现代模式）。 [查看详细界面指南 »](docs/FRONTEND_MODERN_UI.md)
*   **深厚技术底蕴**：提供完整的架构设计与实现原理文档。 [查看架构设计 »](docs/ARCHITECTURE.md) | [查看实现细节 »](docs/IMPLEMENTATION_DETAILS.md)
*   **高性能独立终端**：支持 PTY 技术的独立弹窗终端，可脱离主 UI 运行。
*   **语音交互**：支持语音命令，并使用百度 AI 开放平台进行语音合成。
*   **高性能本地向量库 (Zvec)**：集成阿里云开源的 `zvec` 向量数据库，实现秒级的本地语义搜索与长短期记忆。支持**完全离线**模式，无需联网即可使用。
*   **本地知识库 (RAG)**：支持索引本地多种格式文档（PDF, Word, MD 等），并进行语义检索。
*   **多媒体中心**：支持 MP3/WAV 随机播放及 JPG 图片查看，内置格式背景由来百科。
*   **专业 Excel 专家**：集成高级 Excel 创建、编辑与财务模型准则。支持公式自动重计算与单元格错误扫描（需安装 LibreOffice）。
*   **插件系统**：使用自定义插件轻松扩展 Butler 的功能。

## 架构设计

Butler 助手建立在模块化且可扩展的架构之上，旨在实现灵活性和可伸缩性。更详尽的架构分析请参阅 [**架构设计文档 (ARCHITECTURE.md)**](docs/ARCHITECTURE.md)。

其核心是 `Jarvis` 类，它充当中央编排器，管理信息流并协调系统的各个组件。

关键架构组件包括：

*   **命令处理**：通过支持多条执行路径的高级命令处理系统处理用户输入。简单的命令可以由 `Jarvis` 类直接处理，而更复杂的查询则路由到适当的子系统。

*   **语义记忆与知识库**：系统支持多种向量存储后端。默认优先尝试 Redis；若环境不具备 Redis，则自动切换到极速的 **Zvec** 嵌入式向量数据库。通过 `knowledge_base_manager` 工具，用户可以将本地私有文档库转化为可检索的语义知识库。

*   **插件系统**：Butler 的功能可以通过动态插件系统进行扩展。`PluginManager` 负责发现、加载和执行 `plugin/` 目录中的插件。每个插件都是一个独立的模块，可以设计用于执行特定任务，例如搜索网络、管理待办事项列表或与外部 API 交互。

*   **包管理**：`package/` 目录包含助手可以调用的独立工具和实用程序。这些包是动态发现的，可以作为独立程序执行，为系统添加新功能提供了一种简单的方法。

*   **用户界面**：系统支持 **经典模式 (Tkinter)** 与 **现代模式 (Web UI)**。详细的界面功能描述与操作指南请参考：👉 **[现代界面详细指南](docs/FRONTEND_MODERN_UI.md)**。

这种模块化设计允许对每个组件进行独立开发和测试，使系统易于维护和扩展。

## 命令处理工作流

用户命令通过灵活且多层的工作流进行处理，以确保由适当的组件处理请求。

工作流如下：

1.  **输入**：用户通过 Tkinter GUI、语音输入或其他界面输入命令。

2.  **路由**：系统使用 DeepSeek API 执行自然语言理解 (NLU) 并识别用户的意图和任何关联的实体。

3.  **执行**：
    *   **意图处理**：如果匹配到意图，则调用 `Jarvis` 类中相应的处理程序。这可能涉及调用 `algorithms` 库中的函数、与插件交互或执行包。
    *   **插件执行**：如果命令旨在用于插件，`PluginManager` 将识别正确的插件并执行其 `run` 方法。
    *   **包执行**：如果命令对应于包，`Jarvis` 类将执行包的 `run()` 函数。

4.  **输出**：命令执行的结果通过 GUI 显示给用户，并在适用时使用文本转语音功能播报给用户。

## 项目结构

项目分为几个关键目录，每个目录都有特定的角色：

*   `butler/`：Butler 助手的核心。此目录包含主应用程序逻辑，包括编排整个系统的 `Jarvis` 类。它还包含基于 Tkinter 的 GUI (`CommandPanel.py`)、对话式 AI 集成以及算法库的 REST API。

*   `package/`：Butler 助手可以调用的独立模块和工具的集合。此目录中的每个 `.py` 文件都被视为一个单独的包，并且必须包含一个 `run()` 函数才能执行。这使得使用新的、独立的工具轻松扩展 Butler 的功能成为可能。

*   `plugin/`：用于创建和管理插件以扩展 Butler 核心功能的框架。插件比包集成得更深，并由 `PluginManager` 管理。它们必须继承自 `AbstractPlugin`，并可用于添加复杂功能，如网络搜索、长期记忆或与外部服务交互。

*   `logs/`：包含应用程序的日志文件，对于调试和监视系统行为非常有用。

## 快速入门

### 安装

1.  **克隆仓库：**
    ```bash
    git clone https://github.com/PAYDAY3/Butler.git
    cd Butler
    ```

2.  **创建虚拟环境（推荐）：**
    ```bash
    python -m venv venv
    source venv/bin/activate  # 在 Windows 上，使用 `venv\Scripts\activate`
    ```

3.  **安装依赖：**
    ```bash
    pip install -r requirements.txt
    ```

4.  **配置 API 密钥：**
    通过复制 `.env.example` 文件在根目录下创建一个 `.env` 文件。然后，添加你的 API 密钥：
    ```
    DEEPSEEK_API_KEY="你的_deepseek_api_密钥"
    BAIDU_APP_ID="你的_baidu_app_id"
    BAIDU_API_KEY="你的_baidu_api_key"
    BAIDU_SECRET_KEY="你的_baidu_secret_key"
    ```

## 便携模式与本地依赖管理

Butler 支持将第三方库直接下载到项目文件夹中 (`lib_external`)，从而实现“绿色便携化”。这对于无法安装全局 Python 环境或希望保持项目独立性的用户非常有用。详细说明请参考 [便携模式使用指南](PORTABLE_MODE_GUIDE.md)。

### 使用方法

1.  **安装时选择**：运行 `install.sh` 或 `install.bat` 时，选择“便携模式” (Portable Mode)，系统会自动将所有依赖安装到 `lib_external` 文件夹。
2.  **手动安装**：
    *   安装所有依赖：`python -m package.dependency_manager install_all`
    *   安装特定包：`python -m package.dependency_manager install <包名>`
3.  **自动加载**：程序启动时会自动检测 `lib_external` 文件夹并将其加入 `sys.path`，无需额外配置即可直接使用其中的库。

## 使用方法

### 快速启动（推荐）

安装依赖并配置 API 密钥后，你可以轻松启动应用程序：

*   **Windows 用户：** 只需双击 `run.bat` 文件。
*   **macOS 或 Linux 用户：** 从终端使用 `./run.sh` 运行 `run.sh` 脚本，或者在文件管理器中双击它（你可能需要先使用 `chmod +x run.sh` 授予其执行权限）。

这些脚本将打开带有图形用户界面的主应用程序。

### 手动启动

如果你愿意，仍然可以从命令行手动运行应用程序。

#### Butler 助手

启动带有 GUI 的 Butler 助手（经典模式）：

```bash
python -m butler.butler_app
```

启动精致 Web UI（现代模式）：

```bash
./run_modern.sh  # 或 python -m butler.butler_app --modern
```

启动独立高性能终端：

```bash
python -m package.device.high_perf_terminal
```

你可以通过在输入框中输入命令或使用语音命令与助手交互。

### 算法 API

启动算法库的 REST API 服务器：

```bash
python -m butler.api
```

服务器将在 `http://localhost:5001` 上运行。然后，你可以向可用的端点（例如 `/api/sort`, `/api/search`）发起请求。

## 包 (Packages)

`package/` 目录包含 Butler 助手可以执行的工具和实用程序。此目录中的每个模块都应该有一个 `run()` 函数，作为执行的入口点。

要添加新包，只需在 `package/` 目录中创建一个新的 Python 文件，并在其中实现 `run()` 函数。Butler 将自动发现并能够执行它。

## 插件 (Plugins)

`plugin/` 目录包含扩展 Butler 助手功能的插件。每个插件都应该继承自 `plugin.abstract_plugin.AbstractPlugin` 并实现所需的方法。

`PluginManager` 将自动加载放置在此目录中的任何有效插件。

## 贡献

我们欢迎任何形式的贡献！请随时提交 Pull Request。贡献时，请确保你的代码符合项目的风格，并在适当的地方更新文档。

## 开源协议

本项目采用 MIT 协议。有关详细信息，请参阅 `LICENSE` 文件。
