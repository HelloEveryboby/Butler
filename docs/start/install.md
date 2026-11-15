# Butler 安装与启动指南（合并版）

> 本页合并了原 `DEPLOY.md` / `SETUP_GUIDE.md` 的全部有效内容，是唯一的安装文档入口。
> English version: [install_en.md](./install_en.md)

---

## 1. 一键部署（推荐）

全自动、环境隔离：自动配置独立沙箱、引导 `uv` 极速包管理、拉取仓库、创建虚拟环境，并注册全局 `butler` 命令。

### Linux / macOS

```bash
curl -fsSL https://raw.githubusercontent.com/HelloEveryboby/Butler/main/scripts/install.sh | bash
```

部署时直接写入 DeepSeek 密钥（可选）：

```bash
DEEPSEEK_API_KEY="您的密钥" curl -fsSL https://raw.githubusercontent.com/HelloEveryboby/Butler/main/scripts/install.sh | bash
```

### Windows (PowerShell)

```powershell
irm https://raw.githubusercontent.com/HelloEveryboby/Butler/main/scripts/install.ps1 | iex
```

链式预注密钥（可选）：

```powershell
$env:DEEPSEEK_API_KEY="您的密钥"; iex (irm https://raw.githubusercontent.com/HelloEveryboby/Butler/main/scripts/install.ps1)
```

部署完成后，**新开一个终端窗口**即可使用统一命令：

```bash
butler doctor    # 系统体检
butler start     # 启动核心服务（REST API 网关）
butler tui       # 终端交互界面
```

---

## 2. 手动部署（克隆仓库模式）

### 2.1 前置条件

| 依赖 | 要求 | 说明 |
| :--- | :--- | :--- |
| Python | 3.10 / 3.11（推荐） | 3.12+ 可能遇到依赖 wheel 兼容问题 |
| PortAudio | 编译 `pyaudio` 所需 | Debian/Ubuntu: `sudo apt-get install portaudio19-dev`；macOS: `brew install portaudio` |
| Redis | 可选 | 网页爬虫功能依赖；不装则相关技能自动降级 |

### 2.2 安装

```bash
git clone https://github.com/HelloEveryboby/Butler.git
cd Butler
```

**方式 A：交互式安装脚本（推荐）**

```bash
# Linux/macOS
./bin/install.sh          # 引导选择 依赖模式 + 配置 AI 服务商与密钥
# Windows
bin\install.bat
```

**方式 B：手动 pip 安装**

```bash
python -m venv venv && source venv/bin/activate   # Windows: venv\Scripts\activate
pip install -r requirements.txt
pip install -e .          # 使 butler 命令在 shell 中可用
```

### 2.3 配置

首次启动会自动从 `.env.example` 生成 `.env`（也可手动 `cp .env.example .env`）。
**默认只需填一个 `DEEPSEEK_API_KEY`** 即可跑通核心 AI 流与本地 RAG。

其余可选项（其他 AI 服务商 / 语音引擎 / MQTT）见 **[完整环境变量参考](./env-reference.md)**。

### 2.4 数据文件（可选）

启动音效：将 `jarvis.wav` 放入 `butler/resources/` 目录。

### 2.5 启动

```bash
# 统一命令入口（将 bin/ 加入 PATH 后）
export PATH="$PWD/bin:$PATH"
butler start      # 核心服务
butler tui        # 终端 UI
butler doctor     # 体检

# 或使用启动脚本（自动装依赖、弹配置向导）
./bin/run.sh              # Linux/macOS（经典模式）
./bin/run_modern.sh       # 现代 Web UI
bin\run.bat               # Windows
```

---

## 3. 首次运行流程

第一次启动时系统会依次执行：

1. **启动向导**（`StartupWizard`）：检查环境、自动安装依赖、显示进度；
2. **配置向导**（`EnhancedConfigWizard`）：输入 API 密钥并验证有效性；
3. 进入主界面。若跳过向导，可随时运行 `butler config` 重新配置。

---

## 4. 自定义助手行为（进阶）

Butler 的行为与人格由 `butler/prompts.json` 中的系统提示词控制：

- `nlu_intent_extraction`：意图识别提示词，影响命令理解；
- `general_response`：默认对话人格，可改成更正式/更幽默。

修改后重启应用生效。

---

## 5. 构建独立可执行文件（高级）

```bash
pip install pyinstaller
pyinstaller --name Butler --onefile --add-data "butler/resources:butler/resources" butler.butler_app.py
```

产物位于 `dist/`。构建前请确认 `butler/resources/jarvis.wav` 已就绪。

---

## 6. 出问题了？

```bash
butler doctor     # 一键体检，输出带「下一步建议」
```

常见问题速查：

| 现象 | 处理 |
| :--- | :--- |
| `pyaudio` 安装失败 | 先安装 PortAudio 系统包（见 2.1） |
| AI 无响应 / Key 无效 | `butler config` 重新配置并校验密钥 |
| 端口被占用 | `butler start --port <其他端口>` |
| 依赖缺失 | `python -m package.dependency_manager install_all` |
