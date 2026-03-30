import os
from typing import List, Dict, Any
from .plugin_interface import AbstractPlugin, PluginResult


class SystemShieldPlugin(AbstractPlugin):
    def __init__(self):
        super().__init__()
        self.name = "SystemShieldPlugin"
        self.chinese_name = "系统安全盾插件"
        self.description = "集成 Rust, Go 和 C 的混合开发插件，提供高性能的系统安全监测、文件校验和状态分析。"
        self.parameters = {
            "action": "执行的操作 (status, scan, verify_file)",
            "path": "文件路径 (用于 verify_file)",
            "target": "扫描目标 (用于 scan)",
        }

    def valid(self) -> bool:
        return True

    def init(self, logger):
        self.logger = logger
        self.logger.info(f"{self.chinese_name} 初始化完成")

    def get_name(self) -> str:
        return self.name

    def get_chinese_name(self) -> str:
        return self.chinese_name

    def get_description(self) -> str:
        return self.description

    def get_parameters(self) -> Dict[str, str]:
        return self.parameters

    def on_startup(self):
        self.logger.info(f"{self.chinese_name} 已启动")

    def on_shutdown(self):
        super().on_shutdown()
        self.logger.info(f"{self.chinese_name} 已关闭")

    def get_commands(self) -> List[str]:
        return ["系统状态", "安全扫描", "校验文件"]

    def run(self, command: str, args: dict) -> PluginResult:
        action = args.get("action")

        # 1. 系统状态获取 (使用 C 模块: hybrid_sysutil)
        if "系统状态" in command or action == "status":
            return self._get_system_status()

        # 2. 安全扫描 (使用 Go 模块: hybrid_net)
        elif "安全扫描" in command or action == "scan":
            target = args.get("target", "127.0.0.1")
            return self._run_security_scan(target)

        # 3. 文件校验 (使用 Rust 模块: hybrid_crypto)
        elif "校验文件" in command or action == "verify_file":
            path = args.get("path")
            if not path:
                return PluginResult.new(
                    result=None, success=False, error_message="缺少 'path' 参数"
                )
            return self._verify_file_integrity(path)

        return PluginResult.new(
            result=None, success=False, error_message=f"不支持的命令: {command}"
        )

    def _get_system_status(self) -> PluginResult:
        client = self.get_hybrid_client("hybrid_sysutil")
        if not client:
            return PluginResult.new(
                result=None,
                success=False,
                error_message="无法加载 C 语言高性能系统工具模块",
            )

        info = client.call("get_system_info", {})
        processes = client.call("list_processes", {})

        result = {
            "system_info": info,
            "butler_processes": processes.get("processes") if processes else [],
        }

        summary = f"系统负载: {info.get('load_1m')}, 可用内存: {info.get('free_mb')} MB, 运行时间: {info.get('uptime')} 秒"
        return PluginResult.new(result=summary, additional_data=result)

    def _run_security_scan(self, target: str) -> PluginResult:
        client = self.get_hybrid_client("hybrid_net")
        if not client:
            return PluginResult.new(
                result=None,
                success=False,
                error_message="无法加载 Go 语言高并发网络模块",
            )

        self.logger.info(f"正在对 {target} 进行安全端口扫描...")
        # 扫描常用危险端口
        ports = "21,22,23,25,53,80,110,135,139,443,445,1433,3306,3389,8080"
        scan_result = client.call("scan_ports", {"host": target, "ports": ports})

        if not scan_result:
            return PluginResult.new(
                result=None, success=False, error_message="扫描失败"
            )

        open_ports = scan_result.get("open_ports", [])
        result_text = f"对 {target} 的扫描完成。开放端口: {', '.join(map(str, open_ports)) if open_ports else '无'}"
        return PluginResult.new(result=result_text, additional_data=scan_result)

    def _verify_file_integrity(self, path: str) -> PluginResult:
        if not os.path.exists(path):
            return PluginResult.new(
                result=None, success=False, error_message=f"文件不存在: {path}"
            )

        client = self.get_hybrid_client("hybrid_crypto")
        if not client:
            return PluginResult.new(
                result=None,
                success=False,
                error_message="无法加载 Rust 语言高性能加密模块",
            )

        self.logger.info(f"正在使用 Rust 计算文件哈希: {path}")
        hash_result = client.call("hash_file", {"path": os.path.abspath(path)})

        if hash_result and "hash" in hash_result:
            file_hash = hash_result["hash"]
            return PluginResult.new(
                result=f"文件 SHA256 校验值: {file_hash}",
                additional_data={"path": path, "hash": file_hash},
            )
        else:
            return PluginResult.new(
                result=None, success=False, error_message="哈希计算失败"
            )

    def status(self) -> Any:
        return f"{self.chinese_name} 运行中，已连接模块: {list(self._hybrid_clients.keys())}"
