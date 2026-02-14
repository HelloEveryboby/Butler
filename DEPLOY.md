# Butler (Jarvis) 部署指南

本指南提供了从源代码设置和运行 Butler（原名 Jarvis）语音助手应用程序的说明。该项目有多个复杂的依赖项，请务必仔细按照步骤操作。

## 1. 前置条件

在开始之前，请确保您的系统满足以下要求。

### 系统级依赖
您必须在系统中安装以下软件：

1.  **Python**：3.8 或更高版本。
2.  **PortAudio**：这是编译 `pyaudio` 库所必需的。
    -   在 Debian/Ubuntu 上：`sudo apt-get update && sudo apt-get install portaudio19-dev`
    -   在其他系统上，请使用系统的包管理器安装 PortAudio 开发包。
3.  **Redis**：网页爬虫功能依赖于 Redis 服务器。
    -   安装 Redis 并确保其在默认端口 `localhost:6379` 上运行。
    -   在 Debian/Ubuntu 上：`sudo apt-get install redis-server`

### 手动 Python 依赖

目前不再需要手动安装 Python 依赖。

## 2. 安装步骤

1.  **克隆仓库**
    ```bash
    git clone <仓库地址>
    cd <仓库名称>
    ```

2.  **安装其他 Python 依赖**
    从 `requirements.txt` 文件安装所有其他必需的 Python 库：
    ```bash
    pip install -r requirements.txt
    ```

4.  **安装 Butler 应用程序**
    以可编辑模式安装应用程序本身。这将使 `butler` 命令在您的 shell 中可用。
    ```bash
    pip install .
    ```

## 3. 配置

应用程序的核心服务需要 API 密钥。

1.  **创建 `.env` 文件**：将示例模板复制到名为 `.env` 的新文件中。
    ```bash
    cp .env.example .env
    ```

2.  **编辑 `.env` 文件**：在文本编辑器中打开 `.env` 文件并填写您的私钥：
    ```dotenv
    # 用于 NLP 处理的 DeepSeek API 密钥
    DEEPSEEK_API_KEY=在此填写您的_DEEPSEEK_API_KEY

    # 用于语音转文本的 Azure 认知语音服务
    AZURE_SPEECH_KEY=在此填写您的_AZURE_SPEECH_KEY
    AZURE_SERVICE_REGION=chinaeast2
    ```

## 4. 数据文件

应用程序需要将自定义数据文件放置在 `butler/` 包目录中。

1.  **启动声音**：将您想要的启动音效文件放在 `butler/resources/` 目录中。应用程序会查找 `butler/resources/jarvis.wav`。

## 5. 运行应用程序

完成上述所有步骤后，您只需在终端输入以下命令即可运行应用程序：
```bash
butler
```
应用程序将启动，您可以通过 GUI 与其交互。

## 6. 构建独立可执行文件（高级）

可以使用 `PyInstaller` 构建独立的可执行文件。本指南已为此准备好了项目结构。基本命令是：
```bash
pyinstaller --name Butler --onefile --add-data "butler/resources:butler/resources" butler/main.py
```
**注意**：在运行此命令之前，必须确保所需的数据文件（如第 4 节所述）已就绪。可执行文件将在 `dist` 目录中生成。
