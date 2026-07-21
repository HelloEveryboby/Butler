# ==============================================================================
# Butler Windows PowerShell 自动化一键部署引擎 (install.ps1)
# ==============================================================================
# 设计特点:
#   1. 完全静默 & 非交互，完美支持 irm | iex 一行流
#   2. 自包含沙箱设计，默认 $env:LOCALAPPDATA\Butler 根目录
#   3. 使用极速包管理器 uv 自动引导、创建虚拟环境并进行超高速依赖安装
#   4. 自动注册并封装 %LOCALAPPDATA%\Butler\bin\butler.cmd 快捷外壳
#   5. 智能自更新 User 级别的 PATH 环境变量
# ==============================================================================

$ErrorActionPreference = "Stop"

# 统一彩色日志
function Write-LogInfo {
    Write-Host "[INFO] $args" -ForegroundColor Green
}
function Write-LogWarn {
    Write-Host "[WARN] $args" -ForegroundColor Yellow
}
function Write-LogError {
    Write-Host "[ERROR] $args" -ForegroundColor Red
}
function Write-LogStep {
    Write-Host "`n=== $args ===" -ForegroundColor Cyan
}

# 1. 路径规划
$ButlerHome = if ($env:BUTLER_HOME) { $env:BUTLER_HOME } else { Join-Path $env:LOCALAPPDATA "Butler" }
$ButlerBin = if ($env:BUTLER_BIN) { $env:BUTLER_BIN } else { Join-Path $ButlerHome "bin" }
$AppDir = Join-Path $ButlerHome "app"
$UvExe = Join-Path $ButlerBin "uv.exe"

Write-LogStep "阶段 1: 平台与沙箱路径初始化"
Write-LogInfo "目标安装目录 (BUTLER_HOME): $ButlerHome"
Write-LogInfo "目标可执行命令目录 (BUTLER_BIN): $ButlerBin"

if (!(Test-Path $ButlerHome)) { New-Item -ItemType Directory -Path $ButlerHome -Force | Out-Null }
if (!(Test-Path $ButlerBin)) { New-Item -ItemType Directory -Path $ButlerBin -Force | Out-Null }

# 2. 前置依赖自检
Write-LogStep "阶段 2: 系统基础工具链自检 (Git)"

$hasGit = Get-Command git -ErrorAction SilentlyContinue
if (!$hasGit) {
    Write-LogError "系统未检测到 'git' 命令行工具。"
    Write-LogWarn "请先下载并安装 Git For Windows (https://git-scm.com/download/win)，或运行: winget install Git.Git"
    exit 1
} else {
    $gitVer = &(git --version)
    Write-LogInfo "Git 校验通过: $gitVer"
}

# 3. 超高速包管理器 uv 引导
Write-LogStep "阶段 3: 引导极速 Python 包管理器 (uv)"
if (!(Test-Path $UvExe)) {
    Write-LogInfo "未检测到本地私有 'uv' 引擎，正在静默下载并部署..."

    # 启用安全网络连接
    [Net.ServicePointManager]::SecurityProtocol = [Net.SecurityProtocolType]::Tls12 -bor [Net.SecurityProtocolType]::Tls13

    $uvInstallScript = Join-Path $env:TEMP "install_uv.ps1"
    try {
        (New-Object System.Net.WebClient).DownloadFile("https://astral.sh/uv/install.ps1", $uvInstallScript)

        # 隔离安装至 Butler 内部 bin 目录
        $env:UV_INSTALL_DIR = $ButlerBin
        powershell -ExecutionPolicy Bypass -File $uvInstallScript < $null
        Write-LogInfo "uv 部署成功。"
    } catch {
        Write-LogWarn "通过官方下载 uv 发生异常，尝试使用 python/pip 作为备用手段..."
        $hasPython = Get-Command python -ErrorAction SilentlyContinue
        if ($hasPython) {
            pip install --user uv | Out-Null
            $globalUv = Get-Command uv -ErrorAction SilentlyContinue
            if ($globalUv) {
                Copy-Item $globalUv.Source $UvExe -Force
                Write-LogInfo "uv 备用方案部署成功。"
            }
        }
    }
} else {
    Write-LogInfo "本地私有 'uv' 已存在，跳过引导。"
}

$useUv = $true
if (!(Test-Path $UvExe)) {
    Write-LogWarn "未能成功引导独立 'uv' 引擎，将退化为系统原生 pip/venv 机制运行。"
    $useUv = $false
}

# 4. 代码库下载与安全更新
Write-LogStep "阶段 4: 克隆/同步 Butler 核心代码仓库"
$RepoUrl = "https://github.com/HelloEveryboby/Butler.git"

if (Test-Path (Join-Path $AppDir ".git")) {
    Write-LogInfo "检测到已存在的 Butler 目录，正在安全拉取最新变更..."
    Set-Location $AppDir
    git stash -u | Out-Null
    try {
        git pull origin main
        Write-LogInfo "Butler 代码更新成功。"
    } catch {
        Write-LogWarn "Git 同步遇到波折，保留当前本地版本继续执行安装。"
    }
} else {
    Write-LogInfo "正在静默克隆 Butler 主仓库到沙箱空间..."
    try {
        git clone --depth=1 $RepoUrl $AppDir
        Write-LogInfo "Butler 仓库克隆完成。"
    } catch {
        Write-LogError "克隆 Butler 仓库失败，请检查网络连接。"
        exit 1
    }
}

# 5. 构建隔离虚拟环境 & 高速安装依赖
Write-LogStep "阶段 5: 构建独立虚拟环境与极速依赖编译"
Set-Location $AppDir

$venvDir = Join-Path $AppDir ".venv"
$venvPython = Join-Path $venvDir "Scripts\python.exe"

if ($useUv) {
    Write-LogInfo "正在使用 uv 初始化轻量级独立虚拟环境 (.venv)..."
    & $UvExe venv --quiet --python 3.10

    Write-LogInfo "正在使用 uv 极速安装 Butler 的生产级依赖库..."
    & $UvExe pip install --quiet -r requirements.txt
    & $UvExe pip install --quiet -e .
} else {
    $hasPython = Get-Command python -ErrorAction SilentlyContinue
    if (!$hasPython) {
        Write-LogError "系统缺乏 Python 环境且未能引导独立 uv 引擎，无法继续安装依赖。"
        exit 1
    }
    Write-LogInfo "正在使用系统原生 venv 初始化环境..."
    python -m venv $venvDir
    Write-LogInfo "正在安装依赖（这可能需要较长时间，请耐心等待）..."
    & $venvPython -m pip install --quiet --upgrade pip
    & $venvPython -m pip install --quiet -r requirements.txt
    & $venvPython -m pip install --quiet -e .
}

Write-LogInfo "独立虚拟环境构建完成。"

# 6. 配置文件初始化与链式环境变量注入
Write-LogStep "阶段 6: 引导自动化环境配置文件 (.env) 模板注入"
$envFile = Join-Path $AppDir ".env"
$envExampleFile = Join-Path $AppDir ".env.example"

if (!(Test-Path $envFile)) {
    Write-LogInfo "未检测到 .env 配置文件，正在以 .env.example 为模板克隆创建..."
    Copy-Item $envExampleFile $envFile -Force

    # 检测外界是否通过命令行链式注入了 DEEPSEEK_API_KEY
    if ($env:DEEPSEEK_API_KEY) {
        Write-LogInfo "捕获到链式声明的 DEEPSEEK_API_KEY，正在自动完成无感写入..."
        $content = Get-Content $envFile -Raw
        $content = $content -replace "DEEPSEEK_API_KEY=.*", "DEEPSEEK_API_KEY=`"$($env:DEEPSEEK_API_KEY)`""
        [System.IO.File]::WriteAllText($envFile, $content)
    }
} else {
    Write-LogInfo ".env 配置文件已存在，跳过初始化，保留您的本地设置。"
}

# 7. 全系统 CLI 指令封装与 PATH 注入
Write-LogStep "阶段 7: 全局 CLI 指令封装与用户 PATH 变量注册"

$LauncherPath = Join-Path $ButlerBin "butler.cmd"
Write-LogInfo "正在将快速启动入口封装至: $LauncherPath"

$LauncherContent = @"
@echo off
setlocal
set PATH=$venvDir\Scripts;%PATH%
"$venvPython" "$AppDir\butler_cli.py" %*
endlocal
"@

[System.IO.File]::WriteAllText($LauncherPath, $LauncherContent)

# 自动将 $ButlerBin 加入当前 User 级别的 PATH 环境变量
$userPath = [Environment]::GetEnvironmentVariable("Path", "User")
if ($userPath -split ';' -notcontains $ButlerBin) {
    Write-LogInfo "正在将 $ButlerBin 追加写入当前用户的 PATH 环境变量中..."
    $newUserPath = $userPath + ";" + $ButlerBin
    [Environment]::SetEnvironmentVariable("Path", $newUserPath, "User")
    Write-LogInfo "PATH 写入完成。重启终端即可生效。"
} else {
    Write-LogInfo "您的用户 PATH 中已包含该路径，跳过写入。"
}

# 8. 顺利完结与指引提示
Write-LogStep "🎉 Butler 部署顺利完成！"
Write-Host "恭喜！Butler 操作系统级数字员工已在您的系统沙箱成功安家。`n" -ForegroundColor Green

Write-Host "您可以执行以下命令进行体验（若指令未生效，请新开一个终端窗口）："
Write-Host "  1. butler doctor       (全面体检自检)" -ForegroundColor Yellow
Write-Host "  2. butler start        (启动核心网关)" -ForegroundColor Yellow
Write-Host "  3. butler agent run demo-agent `"你的任务需求`"`n" -ForegroundColor Yellow

if (!(Test-Path $envFile) -or !((Get-Content $envFile -Raw) -match "sk-")) {
    Write-LogWarn "💡 提示: 检测到您尚未配置有效的 DeepSeek API 密钥。"
    Write-Host "   请编辑 $envFile 文件填充 DEEPSEEK_API_KEY=`"您的密钥`"，方可享受完整 AI 协同体验！`n" -ForegroundColor Cyan
}
# ==============================================================================
