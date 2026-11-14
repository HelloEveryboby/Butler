"""插件市场下载器 + 安装前体检。

支持的插件来源（spec 语法）：
  doc-reader            dsh 插件市场（需要市场索引可达）
  github:owner/repo     git 仓库（--depth 1 克隆）
  npm:package-name      npm 包（registry tarball）
  ./local/path          本地目录/文件（开发调试）

安全模型（安装前体检，全部通过才落盘）：
  1. 来源白名单 —— allowlist 为空表示不限制；命中拒绝即安装失败
  2. 分类过滤   —— UI/皮肤类插件对 Butler 无意义，默认拒绝（--allow-ui 显式放行）
  3. 平台检查   —— 插件代码硬编码 bash//tmp 等，在 Windows 上给出警告
  4. 风险预判   —— 静态扫描 child_process/writeFile/fetch 等危险调用，
                  产出风险提示（最终风险分类仍由 dsh-host 运行时判定，
                  Go 侧权限代理把关执行）

安装产物布局（便携模式，删目录即卸载）：
  <plugins_dir>/<name>/
  <plugins_dir>/installed.json     安装清单（名称/来源/版本/hash/启停状态）
"""

from __future__ import annotations

import hashlib
import json
import os
import re
import shutil
import subprocess
import sys
import tarfile
import tempfile
import time
import urllib.error
import urllib.parse
import urllib.request
import zipfile
from dataclasses import dataclass, field, asdict
from pathlib import Path
from typing import Any, Iterable

DEFAULT_MARKET_BASE = "https://market.dsh-plugins.org"
MANIFEST_NAME = "installed.json"

# ---- 分类与风险启发式 ----

UI_KIND_PATTERNS = re.compile(r"\b(skin|theme|wallpaper|sidebar|ui-?kit)\b", re.I)
PROVIDER_KIND_PATTERNS = re.compile(r"\b(provider|model-?provider|llm)\b", re.I)

PLATFORM_HAZARDS = [
    (re.compile(r"/tmp/"), "硬编码 /tmp/ 路径（Windows 不可用）"),
    (re.compile(r"bash\s+-c|#!/bin/(ba)?sh"), "依赖 bash（Windows 不可用）"),
    (re.compile(r"/dev/(null|stdin|stdout)"), "依赖 Unix 设备文件（Windows 不可用）"),
]

RISK_PATTERNS = [
    (re.compile(r"child_process|\bexec(?:File|Sync)?\s*\(|spawn\s*\("), "execute", "可执行系统命令"),
    (re.compile(r"writeFile(?:Sync)?\s*\(|unlink(?:Sync)?\s*\(|rm\s+-|mkdir(?:Sync)?\s*\("), "write", "可写/删文件"),
    (re.compile(r"fetch\s*\(|https?\.request|axios|XMLHttpRequest"), "network", "可发起网络请求"),
    (re.compile(r"\bprocess\.env\b"), "read_only", "读取环境变量（注意密钥暴露面）"),
]


class MarketError(RuntimeError):
    """下载/安装失败。"""


@dataclass
class PluginInfo:
    name: str
    source: str
    version: str = "unknown"
    kind: str = "tool"            # tool | provider | ui-skin | unknown
    risk_hints: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    description: str = ""

    def summary(self) -> str:
        hints = ",".join(self.risk_hints) or "-"
        return f"{self.name} [{self.kind}] risk={hints} src={self.source} ver={self.version}"


@dataclass
class PreflightReport:
    ok: bool
    reasons: list[str] = field(default_factory=list)
    info: PluginInfo | None = None


class PluginMarket:
    """插件安装器：下载 → 体检 → 落盘 → 记账。"""

    def __init__(
        self,
        plugins_dir: str | os.PathLike[str],
        *,
        market_base: str = "",
        allowed_sources: Iterable[str] | None = None,
        allow_ui: bool = False,
    ) -> None:
        self.plugins_dir = Path(plugins_dir)
        self.market_base = (market_base or os.environ.get("DSH_MARKET_BASE") or DEFAULT_MARKET_BASE).rstrip("/")
        self.allowed_sources = [re.compile(glob_to_regex(s)) for s in (allowed_sources or [])]
        self.allow_ui = allow_ui
        self.plugins_dir.mkdir(parents=True, exist_ok=True)

    # ---- 清单 ----

    @property
    def manifest_path(self) -> Path:
        return self.plugins_dir / MANIFEST_NAME

    def _load_manifest(self) -> dict[str, Any]:
        if self.manifest_path.exists():
            try:
                return json.loads(self.manifest_path.read_text(encoding="utf-8"))
            except json.JSONDecodeError:
                return {"plugins": {}}
        return {"plugins": {}}

    def _save_manifest(self, manifest: dict[str, Any]) -> None:
        self.manifest_path.write_text(
            json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8"
        )

    def list_installed(self) -> list[dict[str, Any]]:
        manifest = self._load_manifest()
        return list(manifest.get("plugins", {}).values())

    # ---- 搜索（市场索引；索引不可达时给出可操作的错误） ----

    def search(self, query: str, limit: int = 20) -> list[PluginInfo]:
        url = f"{self.market_base}/v1/plugins/search?q={urllib.parse.quote(query)}&limit={limit}"
        try:
            data = _http_get_json(url)
        except (urllib.error.URLError, OSError, json.JSONDecodeError) as exc:
            raise MarketError(
                f"插件市场索引不可达（{self.market_base}）：{exc}。"
                f"可改用 github:owner/repo 或 npm:package 源，或设置 DSH_MARKET_BASE 走镜像"
            ) from exc
        results = []
        for item in data if isinstance(data, list) else data.get("plugins", []):
            results.append(
                PluginInfo(
                    name=str(item.get("name", "")),
                    source=f"market:{item.get('name', '')}",
                    version=str(item.get("version", "unknown")),
                    description=str(item.get("description", "")),
                )
            )
        return results

    # ---- 安装 ----

    def install(self, spec: str) -> PluginInfo:
        """安装一个插件（spec 语法见模块文档）。返回落盘的插件信息。"""
        with tempfile.TemporaryDirectory(prefix="dsh-install-") as staging:
            staged = Path(staging) / "plugin"
            if spec.startswith("github:"):
                info = self._fetch_github(spec, staged)
            elif spec.startswith("npm:"):
                info = self._fetch_npm(spec, staged)
            elif spec.startswith("market:"):
                info = self._fetch_market(spec, staged)
            else:
                info = self._fetch_local(spec, staged)

            report = self.preflight(info, staged)
            if not report.ok:
                raise MarketError("安装前体检未通过：" + "；".join(report.reasons))

            dest = self.plugins_dir / info.name
            if dest.exists():
                shutil.rmtree(dest)
            shutil.copytree(staged, dest)

        entry = asdict(info)
        entry["installed_at"] = int(time.time())
        entry["enabled"] = True
        entry["sha256"] = _dir_hash(dest)
        manifest = self._load_manifest()
        manifest.setdefault("plugins", {})[info.name] = entry
        self._save_manifest(manifest)
        return info

    def uninstall(self, name: str) -> bool:
        manifest = self._load_manifest()
        entry = manifest.get("plugins", {}).pop(name, None)
        if entry is None:
            return False
        self._save_manifest(manifest)
        dest = self.plugins_dir / name
        if dest.exists():
            shutil.rmtree(dest)
        return True

    def set_enabled(self, name: str, enabled: bool) -> bool:
        manifest = self._load_manifest()
        entry = manifest.get("plugins", {}).get(name)
        if entry is None:
            return False
        entry["enabled"] = enabled
        self._save_manifest(manifest)
        return True

    # ---- 下载实现 ----

    def _fetch_local(self, spec: str, staged: Path) -> PluginInfo:
        src = Path(spec).expanduser().resolve()
        if not src.exists():
            raise MarketError(f"本地路径不存在：{src}")
        if src.is_dir():
            shutil.copytree(src, staged)
        else:
            staged.mkdir(parents=True)
            _extract_archive(src, staged)
        name = _plugin_name(staged) or src.stem
        return PluginInfo(name=name, source=f"local:{src}", version=_plugin_version(staged))

    def _fetch_github(self, spec: str, staged: Path) -> PluginInfo:
        repo = spec[len("github:") :].strip().strip("/")
        if not re.fullmatch(r"[\w.-]+/[\w.-]+", repo):
            raise MarketError(f"非法 github: 规格：{spec}（应为 github:owner/repo）")
        url = f"https://github.com/{repo}.git"
        with tempfile.TemporaryDirectory(prefix="dsh-git-") as tmp:
            try:
                subprocess.run(
                    ["git", "clone", "--depth", "1", "--quiet", url, tmp],
                    check=True, capture_output=True, timeout=120,
                )
            except (subprocess.CalledProcessError, subprocess.TimeoutExpired, FileNotFoundError) as exc:
                detail = getattr(exc, "stderr", b"") or b""
                raise MarketError(f"git 克隆失败 {url}：{detail.decode(errors='replace').strip()}") from exc
            shutil.copytree(tmp, staged, ignore=shutil.ignore_patterns(".git"))
        name = _plugin_name(staged) or repo.split("/")[-1]
        return PluginInfo(name=name, source=spec, version=_plugin_version(staged))

    def _fetch_npm(self, spec: str, staged: Path) -> PluginInfo:
        pkg = spec[len("npm:") :].strip()
        registry = os.environ.get("NPM_REGISTRY", "https://registry.npmjs.org").rstrip("/")
        meta = _http_get_json(f"{registry}/{urllib.parse.quote(pkg)}")
        version = meta.get("dist-tags", {}).get("latest", "")
        tarball = meta.get("versions", {}).get(version, {}).get("dist", {}).get("tarball")
        if not tarball:
            raise MarketError(f"npm 包无可用 tarball：{pkg}")
        with tempfile.TemporaryDirectory(prefix="dsh-npm-") as tmp:
            tgz = Path(tmp) / "pkg.tgz"
            _http_download(tarball, tgz)
            with tarfile.open(tgz, "r:gz") as tf:
                tf.extractall(Path(tmp) / "x", filter="data")
            pkg_root = Path(tmp) / "x" / "package"
            shutil.copytree(pkg_root if pkg_root.exists() else Path(tmp) / "x", staged)
        name = _plugin_name(staged) or pkg.replace("/", "-")
        return PluginInfo(name=name, source=spec, version=version)

    def _fetch_market(self, spec: str, staged: Path) -> PluginInfo:
        name = spec[len("market:") :].strip()
        info = next((p for p in self.search(name) if p.name == name), None)
        if info is None:
            raise MarketError(f"市场中找不到插件：{name}")
        url = f"{self.market_base}/v1/plugins/{urllib.parse.quote(name)}/download"
        with tempfile.TemporaryDirectory(prefix="dsh-market-") as tmp:
            pkg = Path(tmp) / "plugin.dshp"
            try:
                _http_download(url, pkg)
            except (urllib.error.URLError, OSError) as exc:
                raise MarketError(f"市场下载失败 {url}：{exc}") from exc
            _extract_archive(pkg, staged)
        info.version = _plugin_version(staged) or info.version
        return info

    # ---- 安装前体检 ----

    def preflight(self, info: PluginInfo, staged: Path) -> PreflightReport:
        reasons: list[str] = []

        # 1. 来源白名单
        if self.allowed_sources and not any(rx.match(info.source) for rx in self.allowed_sources):
            reasons.append(f"来源 {info.source} 不在白名单内")

        # 2. 分类过滤（读 package.json / SKILL.md 提示）
        meta_text = _read_meta_text(staged)
        if UI_KIND_PATTERNS.search(meta_text) or UI_KIND_PATTERNS.search(info.name):
            info.kind = "ui-skin"
            if not self.allow_ui:
                reasons.append("UI/皮肤类插件不适用于 Butler（如需强行安装加 --allow-ui）")
        elif PROVIDER_KIND_PATTERNS.search(meta_text):
            info.kind = "provider"
            info.warnings.append("能力 Provider 类插件：可能与 Butler 自有记忆/模型链路冲突，请确认接管方")

        # 3/4. 静态扫描：平台兼容 + 风险提示
        platform = sys.platform
        risk_found: set[str] = set()
        for path in _iter_code_files(staged):
            try:
                code = path.read_text(encoding="utf-8", errors="replace")
            except OSError:
                continue
            if platform.startswith("win"):
                for rx, msg in PLATFORM_HAZARDS:
                    if rx.search(code):
                        info.warnings.append(msg)
            for rx, risk, msg in RISK_PATTERNS:
                if rx.search(code):
                    risk_found.add(risk)
                    if msg not in info.risk_hints:
                        info.risk_hints.append(msg)
        info.risk_hints = sorted(info.risk_hints)

        return PreflightReport(ok=not reasons, reasons=reasons, info=info)


# ---- 工具函数 ----

def glob_to_regex(pattern: str) -> str:
    """glob（* 跨 .）→ 正则，用于来源白名单匹配。"""
    parts = pattern.split("*")
    return "^" + ".*".join(re.escape(p) for p in parts) + "$"


def _plugin_name(staged: Path) -> str:
    pkg = staged / "package.json"
    if pkg.exists():
        try:
            name = json.loads(pkg.read_text(encoding="utf-8")).get("name")
            if name:
                return str(name).replace("/", "-")
        except json.JSONDecodeError:
            pass
    return ""


def _plugin_version(staged: Path) -> str:
    pkg = staged / "package.json"
    if pkg.exists():
        try:
            return str(json.loads(pkg.read_text(encoding="utf-8")).get("version", "unknown"))
        except json.JSONDecodeError:
            pass
    return "unknown"


def _read_meta_text(staged: Path) -> str:
    chunks = []
    for name in ("package.json", "SKILL.md", "README.md"):
        p = staged / name
        if p.exists():
            try:
                chunks.append(p.read_text(encoding="utf-8", errors="replace")[:8192])
            except OSError:
                pass
    return "\n".join(chunks)


def _iter_code_files(staged: Path) -> Iterable[Path]:
    for p in staged.rglob("*"):
        if p.is_file() and p.suffix in {".js", ".mjs", ".cjs", ".ts", ".py", ".sh"}:
            if "node_modules" in p.parts or ".git" in p.parts:
                continue
            yield p


def _dir_hash(root: Path) -> str:
    h = hashlib.sha256()
    for p in sorted(root.rglob("*")):
        if p.is_file():
            h.update(str(p.relative_to(root)).encode())
            h.update(p.read_bytes())
    return h.hexdigest()


def _extract_archive(archive: Path, dest: Path) -> None:
    dest.mkdir(parents=True, exist_ok=True)
    name = archive.name.lower()
    if name.endswith((".tgz", ".tar.gz", ".tar")):
        with tarfile.open(archive, "r:*") as tf:
            tf.extractall(dest, filter="data")
    elif name.endswith(".zip") or name.endswith(".dshp"):
        # .dshp 按 zip 尝试；失败再按 tar
        try:
            with zipfile.ZipFile(archive) as zf:
                zf.extractall(dest)
        except zipfile.BadZipFile:
            with tarfile.open(archive, "r:*") as tf:
                tf.extractall(dest, filter="data")
    else:
        # 普通单文件（如单文件插件 .js）：直接拷入
        shutil.copy(archive, dest / archive.name)


def _http_get_json(url: str) -> Any:
    req = urllib.request.Request(url, headers={"User-Agent": "butler-dsh/0.1"})
    with urllib.request.urlopen(req, timeout=15) as resp:
        return json.loads(resp.read().decode("utf-8"))


def _http_download(url: str, out: Path) -> None:
    req = urllib.request.Request(url, headers={"User-Agent": "butler-dsh/0.1"})
    with urllib.request.urlopen(req, timeout=60) as resp, open(out, "wb") as f:
        shutil.copyfileobj(resp, f)
