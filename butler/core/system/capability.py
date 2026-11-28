"""``system`` 能力处理器：薄适配到 ``butler.core.system`` 下的各组实现。

每个动作都惰性导入对应实现，避免注册能力时加载 psutil / 7-Zip / 云盘适配器等重依赖。
"""

from __future__ import annotations

from typing import Any

_SECURITY_MODULES = {
    "web": "web_security_tester",
    "api": "api_security_tester",
    "llm": "llm_security_tester",
    "cloud": "cloud_security_auditor",
    "mobile": "mobile_app_tester",
    "sdlc": "sdlc_security_orchestrator",
}


def _params(payload: dict[str, Any], drop: tuple[str, ...] = ()) -> dict[str, Any]:
    """剔除与实现函数形参冲突的调度字段。"""
    blocked = {"action", *drop}
    return {key: value for key, value in payload.items() if key not in blocked}


def _sys_clean(action: str, payload: dict[str, Any]) -> dict[str, Any]:
    from butler.core.system.sys_cleaner import main as cleaner

    if action == "track":
        return cleaner.start_track(payload)
    if action == "stop_track":
        return cleaner.stop_track(payload)
    if action in ("execute_clean", "clean_track"):
        return cleaner.execute_clean(payload)
    if action == "setup_elevation":
        return cleaner.setup_elevation(payload)
    return {"error": f"未知的安装追踪动作: {action}"}


def _uninstaller(action: str, payload: dict[str, Any]) -> dict[str, Any]:
    from butler.core.system.geek_uninstaller.main import handle_request

    mapping = {
        "list": "list_software",
        "list_software": "list_software",
        "scan_leftovers": "scan_leftovers",
        "uninstall": "uninstall",
        "scan_junk": "scan_junk",
        "clean_junk": "clean_junk",
        "system_info": "system_info",
        "top_processes": "top_processes",
    }
    target = mapping.get(action)
    if target is None:
        return {"error": f"未知的软件/清理动作: {action}"}
    return handle_request(target, **_params(payload))


def _archive(action: str, payload: dict[str, Any]) -> dict[str, Any]:
    from butler.core.system import archive_manager

    archive_path = payload.get("archive_path") or payload.get("zip_path") or payload.get("path")
    if action == "archive":
        targets = payload.get("targets") or payload.get("target") or payload.get("files")
        if isinstance(targets, str):
            targets = [targets]
        if not archive_path or not targets:
            return {"error": "archive 需要 archive_path 与 targets"}
        return archive_manager.handle_request(
            "compress",
            archive_path=archive_path,
            targets=targets,
            password=payload.get("password"),
            volume_size=payload.get("volume_size"),
        )
    if action == "extract":
        if not archive_path:
            return {"error": "extract 需要 archive_path"}
        return archive_manager.handle_request(
            "extract",
            archive_path=archive_path,
            output_dir=payload.get("output_dir") or payload.get("dest_dir"),
            password=payload.get("password"),
        )
    if action == "list_archive":
        if not archive_path:
            return {"error": "list_archive 需要 archive_path"}
        return archive_manager.handle_request("list_contents", archive_path=archive_path)
    if action == "preview_archive":
        if not archive_path:
            return {"error": "preview_archive 需要 archive_path"}
        file_in_zip = payload.get("file_in_zip") or payload.get("file") or payload.get("target")
        if not file_in_zip:
            return {"error": "preview_archive 需要 file_in_zip"}
        return archive_manager.handle_request(
            "preview_file",
            archive_path=archive_path,
            file_in_zip=file_in_zip,
            password=payload.get("password"),
            max_bytes=payload.get("max_bytes"),
        )
    return {"error": f"未知的归档动作: {action}"}


def _storage(action: str, payload: dict[str, Any]) -> dict[str, Any]:
    from butler.core.system.storage_hub import hub_manager

    mapping = {
        "storage": "list_drives",
        "list_drives": "list_drives",
        "list_files": "list_files",
        "search_files": "search_all",
        "search_all": "search_all",
        "transfer": "transfer",
        "transfer_status": "check_transfer_status",
        "check_transfer_status": "check_transfer_status",
        "duplicates": "find_duplicates",
        "find_duplicates": "find_duplicates",
        "quota": "get_quota",
        "load_config": "load_config",
        "save_config": "save_config",
        "delete_file": "delete_file",
        "rename_file": "rename_file",
        "copy_file": "copy_file",
        "move_file": "move_file",
        "create_directory": "create_directory",
    }
    target = mapping.get(action)
    if target is None:
        return {"error": f"未知的云盘动作: {action}"}
    return hub_manager.handle_request(target, **_params(payload))


def _audit(payload: dict[str, Any]) -> dict[str, Any]:
    module_key = str(payload.get("module") or payload.get("system") or "web").lower()
    module_name = _SECURITY_MODULES.get(module_key)
    if module_name is None:
        return {
            "error": f"未知的安全测试模块: {module_key}",
            "available": sorted(_SECURITY_MODULES),
        }
    module = __import__(
        f"butler.core.system.security.{module_name}.main", fromlist=["handle_request"]
    )
    action = str(payload.get("op") or payload.get("test") or "test")
    kwargs = _params(payload, drop=("module", "system", "op"))
    return {"result": module.handle_request(action, **kwargs)}


def _sec_scan(payload: dict[str, Any]) -> dict[str, Any]:
    from butler.core.system.skill_sec_radar import handle_request

    target = str(payload.get("target") or "127.0.0.1")
    return {"target": target, "result": handle_request("scan", target=target)}


def handle_system(action: str, payload: dict[str, Any]) -> Any:
    if action == "clean":
        payload = {**payload, "dry_run": bool(payload.get("dry_run", True))}
        return _uninstaller("clean_junk", payload)
    if action in ("track", "stop_track", "execute_clean", "clean_track", "setup_elevation"):
        return _sys_clean(action, payload)
    if action in (
        "uninstall",
        "list",
        "list_software",
        "scan_leftovers",
        "scan_junk",
        "clean_junk",
        "system_info",
        "top_processes",
    ):
        return _uninstaller(action, payload)
    if action in ("archive", "extract", "list_archive", "preview_archive"):
        return _archive(action, payload)
    if action in (
        "storage",
        "list_drives",
        "list_files",
        "search_files",
        "search_all",
        "transfer",
        "transfer_status",
        "check_transfer_status",
        "duplicates",
        "find_duplicates",
        "quota",
        "load_config",
        "save_config",
        "delete_file",
        "rename_file",
        "copy_file",
        "move_file",
        "create_directory",
    ):
        return _storage(action, payload)
    if action == "audit":
        return _audit(payload)
    if action == "sec_scan":
        return _sec_scan(payload)
    return {"error": f"未知动作: {action}"}
