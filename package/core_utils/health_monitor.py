import os
import sys
import json
import time
import subprocess
import logging
from typing import Dict, List, Any

# Try to import psutil for advanced monitoring, fallback to basic info if not available
try:
    import psutil
except ImportError:
    psutil = None

# Base path setup
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
PROGRAMS_DIR = os.path.join(PROJECT_ROOT, "programs")

class HealthMonitor:
    """
    Butler 自愈与健康监测系统 (Health Monitor & Self-Healing System)
    负责监控系统资源、验证 BHL 模块完整性并提供系统报告。
    """

    def __init__(self):
        self.logger = logging.getLogger("ButlerHealth")
        logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

        # BHL 模块映射 (源码 -> 二进制)
        self.bhl_mapping = {
            "hybrid_compute": {"lang": "C++", "source": "compute.cpp", "binary": "compute"},
            "hybrid_crypto": {"lang": "Rust", "source": "src/crypto_service.rs", "binary": "target/release/hybrid_crypto_exec"},
            "hybrid_net": {"lang": "Go", "source": "net_service.go", "binary": "hybrid_net_exec"},
            "hybrid_sysutil": {"lang": "C", "source": "sysutil.c", "binary": "sysutil"},
            "hybrid_terminal": {"lang": "Go", "source": "main.go", "binary": "terminal_service"},
            "hybrid_math": {"lang": "C++", "source": "src/math_service.cpp", "binary": "hybrid_math_exec"},
            "hybrid_vision": {"lang": "C++", "source": "src/vision_service.cpp", "binary": "hybrid_vision_exec"},
            "hybrid_doc_processor": {"lang": "C++", "source": "src/main.cpp", "binary": "processor"}
        }

    def get_file_size(self, path: str) -> int:
        """获取文件大小（字节）"""
        try:
            if os.path.exists(path):
                return os.path.getsize(path)
        except:
            pass
        return 0

    def get_directory_size(self, path: str) -> int:
        """获取目录总大小（字节）"""
        total = 0
        try:
            for dirpath, dirnames, filenames in os.walk(path):
                for f in filenames:
                    fp = os.path.join(dirpath, f)
                    if not os.path.islink(fp):
                        total += os.path.getsize(fp)
        except:
            pass
        return total

    def format_size(self, size_bytes: int) -> str:
        """格式化字节数为人类可读格式"""
        if size_bytes == 0: return "0B"
        units = ("B", "KB", "MB", "GB")
        i = 0
        while size_bytes >= 1024 and i < len(units)-1:
            size_bytes /= 1024
            i += 1
        return f"{size_bytes:.2f}{units[i]}"

    def check_bhl_status(self) -> List[Dict[str, Any]]:
        """检查 BHL 模块的二进制状态"""
        status_list = []
        for name, info in self.bhl_mapping.items():
            mod_dir = os.path.join(PROGRAMS_DIR, name)
            bin_path = os.path.join(mod_dir, info["binary"])

            exists = os.path.exists(bin_path)
            size = self.get_file_size(bin_path) if exists else 0

            status_list.append({
                "module": name,
                "language": info["lang"],
                "binary_name": info["binary"],
                "status": "Ready" if exists else "Missing (Needs Compile)",
                "size": self.format_size(size),
                "path": bin_path if exists else "N/A"
            })
        return status_list

    def get_system_resources(self) -> Dict[str, Any]:
        """获取当前系统资源占用情况"""
        res = {
            "cpu_percent": 0.0,
            "memory_used": "N/A",
            "memory_total": "N/A",
            "memory_percent": 0.0,
            "process_count": 0
        }

        if psutil:
            mem = psutil.virtual_memory()
            res["cpu_percent"] = psutil.cpu_percent(interval=0.1)
            res["memory_used"] = self.format_size(mem.used)
            res["memory_total"] = self.format_size(mem.total)
            res["memory_percent"] = mem.percent
            res["process_count"] = len(psutil.pids())

            # 统计 Butler 相关进程
            butler_mem = 0
            for proc in psutil.process_iter(['pid', 'name', 'memory_info']):
                try:
                    cmd = " ".join(proc.cmdline()).lower()
                    if "python" in cmd and ("butler" in cmd or "package" in cmd):
                        butler_mem += proc.memory_info().rss
                    elif any(m["binary"] in cmd for m in self.bhl_mapping.values()):
                        butler_mem += proc.memory_info().rss
                except:
                    continue
            res["butler_memory_usage"] = self.format_size(butler_mem)

        return res

    def generate_full_report(self):
        """生成详细的系统健康与内存占用报告"""
        print("\n" + "="*50)
        print("      Butler 系统健康与内存占用报告")
        print("="*50)

        # 1. 物理磁盘占用
        project_size = self.get_directory_size(PROJECT_ROOT)
        programs_size = self.get_directory_size(PROGRAMS_DIR)
        print(f"\n[1] 磁盘空间统计:")
        print(f"- 项目总路径: {PROJECT_ROOT}")
        print(f"- 项目总大小: {self.format_size(project_size)}")
        print(f"- 混合编程源码目录 (programs/): {self.format_size(programs_size)}")

        # 2. BHL 模块清单
        print(f"\n[2] 混合编程模块 (BHL) 状态:")
        bhl_status = self.check_bhl_status()
        print(f"{'模块名称':<20} | {'语言':<6} | {'状态':<15} | {'体积'}")
        print("-" * 60)
        for s in bhl_status:
            print(f"{s['module']:<20} | {s['language']:<6} | {s['status']:<15} | {s['size']}")

        # 3. 运行内存占用
        print(f"\n[3] 实时运行内存统计:")
        resources = self.get_system_resources()
        print(f"- 系统 CPU 使用率: {resources['cpu_percent']}%")
        print(f"- 系统内存占用: {resources['memory_used']} / {resources['memory_total']} ({resources['memory_percent']}%)")
        if "butler_memory_usage" in resources:
            print(f"- Butler 相关进程总内存占用: {resources['butler_memory_usage']}")

        print("\n" + "="*50)
        print("报告生成时间:", time.strftime("%Y-%m-%d %H:%M:%S"))
        print("="*50 + "\n")

    def run_self_healing(self):
        """自愈逻辑：检查并引导修复"""
        print("[*] 正在启动 Butler 自愈扫描...")
        missing = [s for s in self.check_bhl_status() if "Missing" in s["status"]]

        if not missing:
            print("[√] 所有核心模块状态正常，无需修复。")
        else:
            print(f"[!] 发现 {len(missing)} 个缺失的二进制模块：")
            for m in missing:
                print(f"    - {m['module']} ({m['language']})")
            print("[提示] 您可以运行各模块目录下的 build.sh 进行手动编译，或使用 Butler 自动构建工具。")

        # 资源监控熔断逻辑
        if psutil:
            mem_p = psutil.virtual_memory().percent
            if mem_p > 90:
                print(f"[危险] 系统内存占用过高 ({mem_p}%)！正在尝试触发资源保护策略...")
                # 这里可以添加清理缓存或关闭非必要模块的逻辑

def run():
    """Package 入口函数"""
    monitor = HealthMonitor()
    monitor.generate_full_report()
    monitor.run_self_healing()

if __name__ == "__main__":
    run()
