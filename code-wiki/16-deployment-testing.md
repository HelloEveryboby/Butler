# 16 · 运行、部署与测试

## 16.1 环境要求

| 项 | 要求 |
| :--- | :--- |
| Python | ≥ 3.10（推荐 3.10 / 3.11；Docker 用 3.12-slim） |
| 操作系统 | Windows / Linux / macOS |
| LLM | 至少一个 API Key，或本地 Ollama（OpenAI 兼容） |
| 可选工具链 | gcc/g++/go/cargo（BHL）、ffmpeg、LibreOffice/pandoc（文档转换） |
| 端口 | `5001` REST API、`8000` Runner WebSocket、`9000` 显示协议、`3000` 前端开发 |

## 16.2 一键安装（推荐）

**Linux / macOS：**

```bash
curl -fsSL https://raw.githubusercontent.com/HelloEveryboby/Butler/main/scripts/install.sh | bash
# 可预注入密钥：
DEEPSEEK_API_KEY="sk-xxx" curl -fsSL https://raw.githubusercontent.com/HelloEveryboby/Butler/main/scripts/install.sh | bash
```

**Windows（PowerShell）：**

```powershell
irm https://raw.githubusercontent.com/HelloEveryboby/Butler/main/scripts/install.ps1 | iex
$env:DEEPSEEK_API_KEY="sk-xxx"; iex (irm https://raw.githubusercontent.com/HelloEveryboby/Butler/main/scripts/install.ps1)
```

`scripts/install.sh` 会：检查 git/python3 → 在 `BUTLER_HOME`（默认 `~/.local/share/butler`）创建沙箱 → 用 `uv` 建虚拟环境并高速安装 → 注册 `~/.local/bin/butler` 到 PATH。

### 便携模式（完全隔离）

```bash
bin/install.sh
# 依赖装进项目内 lib_external/，不污染系统环境；删文件夹即卸载
```

实现：`package/core_utils/dependency_manager.py`（`setup_runtime` 下载便携 Python，`install_all` 安装到 `lib_external`），`butler_app.py` 启动时 `site.addsitedir(lib_external)`。

## 16.3 手动启动

```bash
git clone https://github.com/HelloEveryboby/Butler.git
cd Butler
python -m pip install -e .        # 或 pip install -r requirements.txt

python -m butler                  # 默认 TUI
# 或
./bin/run.sh                      # Linux/macOS 经典 UI
bin\run.bat                       # Windows
./bin/run_modern.sh               # 现代 Web UI（需 pywebview）
```

统一命令（把 `bin/` 加入 PATH）：

```bash
export PATH="$PWD/bin:$PATH"
butler init      # 首次配置向导
butler doctor    # 体检
butler start     # 启动 REST 服务
butler tui       # 终端界面
```

首次启动会自动从 `.env.example` 生成 `.env`，只需填入一个 `DEEPSEEK_API_KEY` 即可跑通核心 AI 流与本地 RAG。

## 16.4 各运行模式启动命令

| 模式 | 命令 | 说明 |
| :--- | :--- | :--- |
| TUI | `butler` / `butler tui` | 需要交互式 TTY |
| 经典 GUI | `butler gui` | Tkinter |
| 现代 Web UI | `butler web` | pywebview |
| 无头 | `butler headless` | 后台 + API |
| REST API | `butler start` / `butler api --port 5001` | FastAPI |
| 数字员工 | `butler agent run <role> "<task>"` | 真实工具循环 |
| BHL | `butler hybrid status/build/call` | 跨语言模块 |
| 诊断 | `butler doctor` | 体检 |

## 16.5 Docker 部署

`Dockerfile` 为**多阶段构建**：编译期安装 gcc/g++/python3-dev 与 OpenCV 运行库，最终镜像基于 `python:3.12-slim`，以非 root 用户 `butler` 运行。

```bash
docker build -t butler:latest .
docker run --rm -p 5001:5001 -p 8000:8000 -p 3000:3000 \
  --env-file .env -v "$PWD/data:/app/data" -v "$PWD/config:/app/config" \
  butler:latest
```

`docker-compose.yml` 提供 `butler` 服务，并在 `ollama` profile 下可启动本地模型：

```bash
docker compose up -d
docker compose --profile ollama up -d   # 可选：本地 Ollama
```

容器入口：

```dockerfile
CMD ["python", "-m", "butler.butler_app", "--headless"]
```

端口：`5001` API、`8000` Runner、`3000` 前端；挂载 `data/`、`config/`、`logs/` 持久化。

## 16.6 打包为可执行文件

`build.py`（PyInstaller）：

```bash
python build.py            # 默认 TUI 版本
python build.py --mode gui # GUI 版本
python build.py --mode all # 全部
python build.py --clean    # 清理
```

产物在 `dist/`，构建规格在 `build_specs/`。`scripts/build_release.sh` 用于发布构建。

## 16.7 测试

| 位置 | 内容 |
| :--- | :--- |
| `tests/unit/` | 单元测试：容器、事件总线、Agent 运行时、技能、BHL、意图弹性、配置、自愈、沙箱等 |
| `tests/integration/` | 集成测试（如 Agent Runtime e2e） |
| `tests/translate_system/` | 翻译系统（引擎、TM、术语、导出） |
| `tests/test_smoke.py` | 冒烟测试 |
| `verification/` | 前端/能力验证脚本与截图 |

pytest 配置（`pyproject.toml`）：

```toml
[tool.pytest.ini_options]
minversion = "7.0"
testpaths = ["tests", "verification"]
addopts = "-ra --tb=short"
filterwarnings = ["error::DeprecationWarning"]
```

运行：

```bash
PYTHONPATH=. pytest tests/unit/ -v --tb=short
python -m pytest tests/unit/test_agent_native_loop.py \
  tests/unit/test_agent_runtime_context.py \
  tests/unit/test_agent_runtime_tools.py \
  tests/integration/test_agent_runtime_e2e.py -q
```

> 共约 42 个 `test_*.py`。部分用例依赖可选包（如 pypdf），CI 会额外安装。

## 16.8 代码质量与 CI

`.github/workflows/ci.yml` 三个 Job：

| Job | 内容 |
| :--- | :--- |
| `lint` | `ruff check butler/ tests/`、`ruff format --check`、`mypy` 指定核心模块 |
| `test` | `pip install .` + `pytest tests/unit/ -v --cov=butler` |
| `docker` | `docker build -t butler:latest .` |

Ruff 配置：`line-length=100`、`target-version=py310`、启用 E/W/F/I/B/C4/UP/SIM/TID，忽略 E501。
Mypy：`strict=true`（当前仅对少数核心模块执行，存量代码未全量严格化）。

## 16.9 常见问题（FAQ）

| 现象 | 排查 |
| :--- | :--- |
| 启动报 `BTL-1002` 缺依赖 | `python -m package.dependency_manager install_all` 或 `pip install -r requirements.txt` |
| TUI 无法显示 | 需真实交互式终端（有 TTY），或改用 `butler gui/web` |
| LLM 调用失败 | `butler doctor`、`butler config check`，确认 `AI_PROVIDER` 与对应 Key |
| Agent 提示没有产出 | 检查 API Key / 网络；`agent.runtime` 是否开启 |
| BHL 模块未构建 | `butler hybrid status`，确认 gcc/go/cargo；`butler hybrid build <module> --force` |
| 记忆不生效 | 确认 `data/system_data/long_memory.db` 可写；查看降级日志 |
| 端口占用 | `5001/8000/9000` 冲突时改 `--port` 或配置 `runner_server.port` |
| 容器无法访问宿主 Ollama | 取消 `docker-compose.yml` 中 `extra_hosts` 注释，或 `--network host` |

## 16.10 相关章节

- 配置项细节：[14 配置与 CLI](./14-config-cli.md)
- 依赖分层：[15 依赖关系](./15-dependencies.md)
- 入口模式：[03 入口与运行模式](./03-entrypoints.md)
