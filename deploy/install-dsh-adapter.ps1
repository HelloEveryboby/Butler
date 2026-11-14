# butler-dsh-adapter 安装脚本（Windows）：从 GitHub Releases 拉取预编译产物到 lib_external/。
#
# 用法（PowerShell）：
#   iex (irm https://raw.githubusercontent.com/HelloEveryboby/Butler/main/deploy/install-dsh-adapter.ps1)
#   或本地: .\deploy\install-dsh-adapter.ps1 -Version v0.1.0 -Prefix .\lib_external
#
# 参数：
#   -Version   版本 tag（默认 latest）
#   -Prefix    安装根目录（默认 .\lib_external）
#   -Repo      仓库（默认 HelloEveryboby/Butler）
#   -BaseUrl   自定义下载基址（镜像/测试用；亦可用 BUTLER_DSH_BASE_URL 环境变量）

param(
    [string]$Version = "latest",
    [string]$Prefix = ".\lib_external",
    [string]$Repo = $(if ($env:BUTLER_DSH_REPO) { $env:BUTLER_DSH_REPO } else { "HelloEveryboby/Butler" }),
    [string]$BaseUrl = $(if ($env:BUTLER_DSH_BASE_URL) { $env:BUTLER_DSH_BASE_URL } else { "" }),
    [switch]$SkipNodeCheck
)

$ErrorActionPreference = "Stop"

function Log($msg)  { Write-Host "[dsh-adapter] $msg" }
function Die($msg)  { Write-Error "[dsh-adapter] 错误: $msg"; exit 1 }

# ---- Node.js 检查（shim 运行必需） ----
if (-not $SkipNodeCheck) {
    $node = Get-Command node -ErrorAction SilentlyContinue
    if (-not $node) { Die "未找到 Node.js。DSH 宿主 shim 需要 Node.js >= 20，请先安装（https://nodejs.org）" }
    $major = [int]((node -e "console.log(process.versions.node.split('.')[0])").Trim())
    if ($major -lt 20) { Die "Node.js 版本过低，需要 >= 20（当前 $(node --version)）" }
    Log "Node.js $(node --version) OK"
}

# ---- 平台（Release 产物 windows-amd64） ----
$plat = "windows-amd64"
if ($env:PROCESSOR_ARCHITECTURE -ne "AMD64") {
    Log "警告: 非 x64 架构（$($env:PROCESSOR_ARCHITECTURE)），仍尝试 windows-amd64 产物"
}

# ---- 解析版本 ----
if ($Version -eq "latest") {
    try {
        $rel = Invoke-RestMethod "https://api.github.com/repos/$Repo/releases/latest"
        $Version = $rel.tag_name
    } catch {
        Die "无法解析最新 Release，请显式指定 -Version（镜像/离线场景）"
    }
    Log "最新版本: $Version"
}

if (-not $BaseUrl) {
    $BaseUrl = "https://github.com/$Repo/releases/download/$Version"
}

$connPkg = "butler-dsh-connector_${Version}_${plat}.zip"
$hostPkg = "butler-dsh-host_${Version}.tar.gz"
$tmp = Join-Path ([System.IO.Path]::GetTempPath()) "dsh-adapter-$(Get-Random)"
New-Item -ItemType Directory -Path $tmp | Out-Null

function Download($url, $out) {
    Log "下载 $url"
    try {
        Invoke-WebRequest -Uri $url -OutFile $out -UseBasicParsing -MaximumRetryCount 3 -RetryIntervalSec 2
    } catch {
        Die "下载失败: $url（网络问题可设 BUTLER_DSH_BASE_URL 走镜像）"
    }
}

function Verify-SHA256($file, $sumsFile) {
    $name = Split-Path $file -Leaf
    $line = Get-Content $sumsFile | Where-Object { $_ -match [regex]::Escape($name) }
    if (-not $line) { Die "SHA256SUMS 中找不到 $name" }
    $expected = ($line -split '\s+')[0]
    $actual = (Get-FileHash -Algorithm SHA256 $file).Hash.ToLower()
    if ($actual -ne $expected.ToLower()) { Die "校验和不匹配: $name" }
    Log "$name 校验通过"
}

try {
    Download "$BaseUrl/SHA256SUMS" (Join-Path $tmp "SHA256SUMS")
    Download "$BaseUrl/$connPkg"   (Join-Path $tmp $connPkg)
    Download "$BaseUrl/$hostPkg"   (Join-Path $tmp $hostPkg)

    Verify-SHA256 (Join-Path $tmp $connPkg) (Join-Path $tmp "SHA256SUMS")
    Verify-SHA256 (Join-Path $tmp $hostPkg) (Join-Path $tmp "SHA256SUMS")

    # 连接器：zip 解压
    $connDir = Join-Path $Prefix "dsh-connector"
    New-Item -ItemType Directory -Force -Path $connDir | Out-Null
    Expand-Archive -Path (Join-Path $tmp $connPkg) -DestinationPath $connDir -Force

    # shim：tar.gz（Windows 10+ 自带 tar）
    $hostDir = Join-Path $Prefix "dsh-host"
    New-Item -ItemType Directory -Force -Path $hostDir | Out-Null
    tar -xzf (Join-Path $tmp $hostPkg) -C $hostDir

    Set-Content -Path (Join-Path $connDir "VERSION") -Value $Version
    Log "安装完成 -> $connDir  $hostDir"

    Write-Host ""
    Write-Host "[dsh-adapter] 安装完成。下一步："
    Write-Host "  1. 运行连接器: $connDir\butler-dsh-connector.exe -config <connector.json>"
    Write-Host "  2. 卸载 = 删除目录: Remove-Item -Recurse $Prefix\dsh-connector, $Prefix\dsh-host"
} finally {
    Remove-Item -Recurse -Force $tmp -ErrorAction SilentlyContinue
}
