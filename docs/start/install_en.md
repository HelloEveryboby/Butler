# Butler Installation & Startup Guide (Consolidated)

> This page merges all valid content from the former `DEPLOY_GUIDE.md` / `SETUP_GUIDE.md`.
> 中文版：[install.md](./install.md)

---

## 1. One-Command Deploy (Recommended)

Fully automated and sandboxed: provisions an isolated home, bootstraps the `uv` package manager, clones the repo, creates a virtualenv, and registers a global `butler` command.

### Linux / macOS

```bash
curl -fsSL https://raw.githubusercontent.com/HelloEveryboby/Butler/main/scripts/install.sh | bash
```

Bootstrap with your DeepSeek API key (optional):

```bash
DEEPSEEK_API_KEY="sk-xxx" curl -fsSL https://raw.githubusercontent.com/HelloEveryboby/Butler/main/scripts/install.sh | bash
```

### Windows (PowerShell)

```powershell
irm https://raw.githubusercontent.com/HelloEveryboby/Butler/main/scripts/install.ps1 | iex
```

With key pre-injection (optional):

```powershell
$env:DEEPSEEK_API_KEY="sk-xxx"; iex (irm https://raw.githubusercontent.com/HelloEveryboby/Butler/main/scripts/install.ps1)
```

Once installed, open a **new terminal** and use the unified CLI:

```bash
butler doctor    # health check
butler start     # start the core runtime (REST API gateway)
butler tui       # terminal UI
```

---

## 2. Manual Deployment (Clone Mode)

### 2.1 Prerequisites

| Dependency | Requirement | Notes |
| :--- | :--- | :--- |
| Python | 3.10 / 3.11 (recommended) | 3.12+ may hit dependency wheel issues |
| PortAudio | needed to build `pyaudio` | Debian/Ubuntu: `sudo apt-get install portaudio19-dev`; macOS: `brew install portaudio` |
| Redis | optional | powers the web-crawler skill; degrades gracefully without it |

### 2.2 Install

```bash
git clone https://github.com/HelloEveryboby/Butler.git
cd Butler
```

**Option A: interactive installer (recommended)**

```bash
./bin/install.sh          # Linux/macOS: dependency mode + AI provider/key wizard
bin\install.bat           # Windows
```

**Option B: manual pip install**

```bash
python -m venv venv && source venv/bin/activate   # Windows: venv\Scripts\activate
pip install -r requirements.txt
pip install -e .
```

### 2.3 Configure

`.env` is auto-created from `.env.example` on first launch (or copy it manually).
**A single `DEEPSEEK_API_KEY` is enough** for all core AI workflows and local RAG.

See the **[full environment reference](./env-reference.md)** for other providers / voice engines / MQTT.

### 2.4 Data Files (Optional)

Startup sound: place `butler.wav` into `butler/resources/`.

### 2.5 Run

```bash
export PATH="$PWD/bin:$PATH"
butler start      # core service
butler tui        # terminal UI
butler doctor     # health check

# or via launch scripts (auto-installs deps, opens the config wizard)
./bin/run.sh              # Linux/macOS (classic)
./bin/run_modern.sh       # modern web UI
bin\run.bat               # Windows
```

---

## 3. First-Run Flow

Recommended: run **`butler init`** (3-minute setup wizard: pick a provider → enter & validate the API key → get ready-to-use example tasks).

On manual launches the system also runs an environment check + dependency installation
(`StartupWizard`), followed by the `EnhancedConfigWizard` for API key input with live validation.
Re-run configuration anytime with `butler config`.

---

## 4. Customizing Assistant Behavior (Advanced)

Personality and behavior are controlled by system prompts in `butler/prompts.json`
(`nlu_intent_extraction`, `general_response`, ...). Restart to apply changes.

---

## 5. Standalone Executable (Advanced)

```bash
pip install pyinstaller
pyinstaller --name Butler --onefile --add-data "butler/resources:butler/resources" butler.butler_app.py
```

Output lands in `dist/`. Ensure `butler/resources/butler.wav` exists first.

---

## 6. Troubleshooting

```bash
butler doctor     # one-shot diagnostics with "next step" suggestions
```

| Symptom | Fix |
| :--- | :--- |
| `pyaudio` build fails | install the PortAudio system package (see 2.1) |
| AI not responding / invalid key | `butler config` to re-configure and validate |
| Port already in use | `butler start --port <other>` |
| Missing dependencies | `python -m package.dependency_manager install_all` |
