"""
文件关联注册器 — 将 Butler Video Player 注册为视频文件的默认打开程序。
支持 Windows / macOS / Linux 三大平台。

用法：
    from skills.video_player.register import register, unregister
    register()    # 注册
    unregister()  # 取消
"""

import os
import sys
import json
import shutil
import logging
import platform
import subprocess
from pathlib import Path

logger = logging.getLogger(__name__)

# 支持关联的视频扩展名
VIDEO_EXTENSIONS = [
    ".mp4", ".mkv", ".avi", ".mov", ".wmv", ".flv", ".webm",
    ".m4v", ".ts", ".m2ts", ".rmvb", ".rm", ".3gp", ".mpg",
    ".mpeg", ".vob", ".asf", ".ogv", ".f4v", ".mts", ".mxf",
    ".divx", ".ogm", ".wtv", ".m2v", ".m2t", ".tp", ".trp",
]

APP_NAME = "ButlerPlayer"
APP_DISPLAY_NAME = "Butler Video Player"
APP_DESCRIPTION = "Butler 本地原生视频播放器"


def get_python_exe() -> str:
    """获取当前 Python 解释器的绝对路径"""
    return sys.executable


def get_main_py_path() -> str:
    """获取 main.py 的绝对路径"""
    return str(Path(__file__).resolve().parent / "main.py")


def get_icon_path() -> str:
    """获取图标路径（如果有的话）"""
    candidates = [
        Path(__file__).resolve().parent.parent.parent / "assets" / "butler_video.ico",
        Path(__file__).resolve().parent.parent.parent / "assets" / "butler_video.png",
        Path(__file__).resolve().parent.parent.parent / "assets" / "butler_logo.ico",
        Path(__file__).resolve().parent.parent.parent / "assets" / "butler_logo.png",
    ]
    for c in candidates:
        if c.exists():
            return str(c)
    return ""


# ══════════════════════════════════════════
# Windows
# ══════════════════════════════════════════

def register_windows():
    """Windows 注册文件关联（通过注册表）"""
    try:
        import winreg
    except ImportError:
        logger.error("winreg 模块不可用，当前不是 Windows 系统")
        return False

    python_exe = get_python_exe()
    main_py = get_main_py_path()
    icon = get_icon_path()

    # 构造命令行
    # 使用 pythonw.exe 避免弹出控制台窗口
    pythonw = python_exe.replace("python.exe", "pythonw.exe")
    if not os.path.isfile(pythonw):
        pythonw = python_exe  # 回退到 python.exe

    command = f'"{pythonw}" "{main_py}" "%1"'

    try:
        # 注册文件类型
        for ext in VIDEO_EXTENSIONS:
            prog_id = f"{APP_NAME}{ext.replace('.', '').upper()}"

            # HKCU\Software\Classes\<ext>\OpenWithProgids
            try:
                key = winreg.CreateKey(
                    winreg.HKEY_CURRENT_USER,
                    f"Software\\Classes\\{ext}\\OpenWithProgids"
                )
                winreg.SetValueEx(key, prog_id, 0, winreg.REG_SZ, "")
                winreg.CloseKey(key)
            except Exception:
                pass

            # HKCU\Software\Classes\<prog_id>
            key = winreg.CreateKey(
                winreg.HKEY_CURRENT_USER,
                f"Software\\Classes\\{prog_id}"
            )
            winreg.SetValueEx(key, "", 0, winreg.REG_SZ, f"{APP_DISPLAY_NAME} ({ext})")
            winreg.CloseKey(key)

            # HKCU\Software\Classes\<prog_id>\shell\open\command
            key = winreg.CreateKey(
                winreg.HKEY_CURRENT_USER,
                f"Software\\Classes\\{prog_id}\\shell\\open\\command"
            )
            winreg.SetValueEx(key, "", 0, winreg.REG_SZ, command)
            winreg.CloseKey(key)

            # 图标
            if icon:
                key = winreg.CreateKey(
                    winreg.HKEY_CURRENT_USER,
                    f"Software\\Classes\\{prog_id}\\DefaultIcon"
                )
                winreg.SetValueEx(key, "", 0, winreg.REG_SZ, icon)
                winreg.CloseKey(key)

        # 注册到 "默认应用" 设置页
        try:
            app_reg_path = f"Software\\Classes\\Applications\\{APP_NAME}.exe\\shell\\open\\command"
            key = winreg.CreateKey(winreg.HKEY_CURRENT_USER, app_reg_path)
            winreg.SetValueEx(key, "", 0, winreg.REG_SZ, command)
            winreg.CloseKey(key)
        except Exception:
            pass

        logger.info(f"✅ Windows 文件关联注册成功（{len(VIDEO_EXTENSIONS)} 个扩展名）")
        logger.info(f"   命令: {command}")
        logger.info(f"   请在 Windows 设置 > 默认应用 中选择 {APP_DISPLAY_NAME}")
        return True

    except Exception as e:
        logger.error(f"Windows 注册失败: {e}")
        return False


def unregister_windows():
    """Windows 取消文件关联"""
    try:
        import winreg
    except ImportError:
        return False

    try:
        for ext in VIDEO_EXTENSIONS:
            prog_id = f"{APP_NAME}{ext.replace('.', '').upper()}"

            # 删除 OpenWithProgids 中的条目
            try:
                key = winreg.OpenKey(
                    winreg.HKEY_CURRENT_USER,
                    f"Software\\Classes\\{ext}\\OpenWithProgids",
                    0, winreg.KEY_SET_VALUE
                )
                winreg.DeleteValue(key, prog_id)
                winreg.CloseKey(key)
            except Exception:
                pass

            # 删除 ProgID
            try:
                winreg.DeleteKey(
                    winreg.HKEY_CURRENT_USER,
                    f"Software\\Classes\\{prog_id}\\shell\\open\\command"
                )
                winreg.DeleteKey(
                    winreg.HKEY_CURRENT_USER,
                    f"Software\\Classes\\{prog_id}\\shell\\open"
                )
                winreg.DeleteKey(
                    winreg.HKEY_CURRENT_USER,
                    f"Software\\Classes\\{prog_id}\\shell"
                )
                if get_icon_path():
                    try:
                        winreg.DeleteKey(
                            winreg.HKEY_CURRENT_USER,
                            f"Software\\Classes\\{prog_id}\\DefaultIcon"
                        )
                    except Exception:
                        pass
                winreg.DeleteKey(
                    winreg.HKEY_CURRENT_USER,
                    f"Software\\Classes\\{prog_id}"
                )
            except Exception:
                pass

        logger.info("✅ Windows 文件关联已取消")
        return True
    except Exception as e:
        logger.error(f"Windows 取消注册失败: {e}")
        return False


# ══════════════════════════════════════════
# macOS
# ══════════════════════════════════════════

def register_macos():
    """macOS 注册文件关联（通过 Info.plist + lsregister）"""
    main_py = get_main_py_path()
    python_exe = get_python_exe()

    # 创建 .app 包结构
    app_dir = Path.home() / "Applications" / f"{APP_NAME}.app"
    contents = app_dir / "Contents"
    macos_dir = contents / "MacOS"
    resources_dir = contents / "Resources"

    try:
        macos_dir.mkdir(parents=True, exist_ok=True)
        resources_dir.mkdir(parents=True, exist_ok=True)
    except Exception as e:
        logger.error(f"创建 .app 目录失败: {e}")
        return False

    # 创建启动脚本
    launcher = macos_dir / APP_NAME
    launcher.write_text(f"""#!/bin/bash
# Butler Video Player Launcher
export PYTHONPATH="{Path(main_py).resolve().parent.parent.parent.parent}"
"{python_exe}" "{main_py}" "$@"
""")
    launcher.chmod(0o755)

    # 构造 UTI 声明
    doc_types = []
    for ext in VIDEO_EXTENSIONS:
        doc_types.append(f"""
        <dict>
            <key>CFBundleTypeExtensions</key>
            <array><string>{ext.lstrip('.')}</string></array>
            <key>CFBundleTypeName</key>
            <string>{ext.upper().lstrip('.')} Video</string>
            <key>CFBundleTypeRole</key>
            <string>Viewer</string>
            <key>LSItemContentTypes</key>
            <array><string>public.movie</string></array>
        </dict>""")

    # 创建 Info.plist
    icon = get_icon_path()
    icon_name = Path(icon).stem if icon else ""

    plist_content = f"""<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>CFBundleName</key>
    <string>{APP_DISPLAY_NAME}</string>
    <key>CFBundleDisplayName</key>
    <string>{APP_DISPLAY_NAME}</string>
    <key>CFBundleIdentifier</key>
    <string>com.butler.player</string>
    <key>CFBundleVersion</key>
    <string>1.0.0</string>
    <key>CFBundleExecutable</key>
    <string>{APP_NAME}</string>
    <key>CFBundlePackageType</key>
    <string>APPL</string>
    <key>CFBundleDocumentTypes</key>
    <array>{''.join(doc_types)}
    </array>
    <key>NSHighResolutionCapable</key>
    <true/>
</dict>
</plist>"""

    (contents / "Info.plist").write_text(plist_content)

    # 复制图标
    if icon:
        import shutil
        dest = resources_dir / Path(icon).name
        shutil.copy2(icon, dest)

    # 注册到 Launch Services
    try:
        subprocess.run(
            ["/System/Library/Frameworks/CoreServices.framework/Frameworks/LaunchServices.framework/Support/lsregister",
             "-f", str(app_dir)],
            capture_output=True,
            timeout=10,
        )
    except Exception:
        pass

    logger.info(f"✅ macOS 文件关联注册成功")
    logger.info(f"   App 路径: {app_dir}")
    logger.info(f"   请在 系统偏好设置 > 通用 > 默认网页浏览器 旁的"
                f"   \"默认应用\" 中设置视频文件的默认打开方式")
    return True


def unregister_macos():
    """macOS 取消文件关联"""
    app_dir = Path.home() / "Applications" / f"{APP_NAME}.app"
    if app_dir.exists():
        shutil.rmtree(app_dir)
        logger.info(f"✅ macOS 已删除 {app_dir}")
    return True


# ══════════════════════════════════════════
# Linux
# ══════════════════════════════════════════

def register_linux():
    """Linux 注册文件关联（通过 .desktop 文件 + xdg-mime）"""
    main_py = get_main_py_path()
    python_exe = get_python_exe()
    icon = get_icon_path()

    # ~/.local/share/applications/
    apps_dir = Path.home() / ".local" / "share" / "applications"
    apps_dir.mkdir(parents=True, exist_ok=True)

    # 构造 MIME 类型列表
    mime_types = []
    ext_to_mime = {
        ".mp4": "video/mp4",
        ".mkv": "video/x-matroska",
        ".avi": "video/x-msvideo",
        ".mov": "video/quicktime",
        ".wmv": "video/x-ms-wmv",
        ".flv": "video/x-flv",
        ".webm": "video/webm",
        ".m4v": "video/x-m4v",
        ".ts": "video/mp2t",
        ".mpg": "video/mpeg",
        ".mpeg": "video/mpeg",
        ".3gp": "video/3gpp",
        ".ogv": "video/ogg",
    }
    for ext in VIDEO_EXTENSIONS:
        mime = ext_to_mime.get(ext, f"video/x-{ext.lstrip('.')}")
        mime_types.append(mime)

    # 创建 .desktop 文件
    desktop_content = f"""[Desktop Entry]
Name={APP_DISPLAY_NAME}
Comment={APP_DESCRIPTION}
Exec={python_exe} "{main_py}" %f
Icon={icon if icon else 'video-x-generic'}
Terminal=false
Type=Application
Categories=AudioVideo;Video;Player;
MimeType={';'.join(mime_types)};
StartupNotify=true
"""

    desktop_file = apps_dir / f"{APP_NAME}.desktop"
    desktop_file.write_text(desktop_content)
    desktop_file.chmod(0o755)

    # 注册 MIME 类型
    try:
        subprocess.run(
            ["xdg-mime", "default", f"{APP_NAME}.desktop"]
            + mime_types,
            capture_output=True,
            timeout=10,
        )
    except Exception:
        pass

    # 更新桌面数据库
    try:
        subprocess.run(
            ["update-desktop-database", str(apps_dir)],
            capture_output=True,
            timeout=10,
        )
    except Exception:
        pass

    logger.info(f"✅ Linux 文件关联注册成功")
    logger.info(f"   .desktop 文件: {desktop_file}")
    logger.info(f"   右键视频文件 > 打开方式 > 选择 {APP_DISPLAY_NAME}")
    return True


def unregister_linux():
    """Linux 取消文件关联"""
    desktop_file = Path.home() / ".local" / "share" / "applications" / f"{APP_NAME}.desktop"
    if desktop_file.exists():
        desktop_file.unlink()
        logger.info(f"✅ Linux 已删除 {desktop_file}")

        # 更新桌面数据库
        try:
            apps_dir = Path.home() / ".local" / "share" / "applications"
            subprocess.run(
                ["update-desktop-database", str(apps_dir)],
                capture_output=True,
                timeout=10,
            )
        except Exception:
            pass

    return True


# ══════════════════════════════════════════
# 统一入口
# ══════════════════════════════════════════

def register():
    """注册文件关联（自动检测平台）"""
    system = platform.system()
    logger.info(f"正在注册文件关联... (平台: {system})")

    if system == "Windows":
        return register_windows()
    elif system == "Darwin":
        return register_macos()
    elif system == "Linux":
        return register_linux()
    else:
        logger.error(f"不支持的平台: {system}")
        return False


def unregister():
    """取消文件关联（自动检测平台）"""
    system = platform.system()
    logger.info(f"正在取消文件关联... (平台: {system})")

    if system == "Windows":
        return unregister_windows()
    elif system == "Darwin":
        return unregister_macos()
    elif system == "Linux":
        return unregister_linux()
    else:
        logger.error(f"不支持的平台: {system}")
        return False
