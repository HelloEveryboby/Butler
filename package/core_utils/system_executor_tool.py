"""
Butler 高性能多线程系统执行与审计工具
------------------------------------
此工具利用 Go 核心实现多线程文件审计与跨设备发现。
"""

import os
import sys
import time
from typing import Dict, Any

# 确保项目根目录在导入路径中
project_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if project_root not in sys.path:
    sys.path.insert(0, project_root)

from butler.core.hybrid_link import HybridLinkClient

def on_audit_event(event: Dict[str, Any]):
    method = event.get("method")
    params = event.get("params")
    if method == "audit_started":
        print(f"\n🔍 [审计开始] 目录: {params.get('directory')}")
    else:
        print(f"\n🔔 [BHL 事件] {method}: {params}")

def run(*args, **kwargs):
    from butler.core.extension_manager import extension_manager

    print("\n" + "⚡"*30)
    print("      Hybrid Multi-Node Executor & Audit Tool")
    print("      Language: Python (Master) + Go (Worker)")
    print("⚡"*30)

    # 1. 扫描并查找 Go 二进制程序
    extension_manager.code_execution_manager.scan_and_register()
    prog_info = extension_manager.code_execution_manager.get_program("hybrid_system_executor")

    if not prog_info:
        return "❌ 错误: 未能找到 'hybrid_system_executor' 模块。请确保已在 programs/ 下编译。"

    executable = prog_info['path']
    cwd = os.path.dirname(executable)

    try:
        with HybridLinkClient(executable, cwd=cwd) as client:
            client.register_event_callback(on_audit_event)
            print(f"✅ BHL 引擎已启动: {executable}\n")

            # --- 功能展示 1: 获取运行状态 ---
            print("📊 正在获取 Go 核心状态...")
            stats = client.call("get_stats", {})
            if "error" in stats:
                print(f"❌ 获取状态失败: {stats['error']}")
            else:
                print(f"   [核心信息] 系统: {stats['os']} | 架构: {stats['arch']}")
                print(f"   [并发信息] 工作线程数: {stats['workers']} | 活跃协程: {stats['goroutines']}")
                print(f"   [资源信息] 内存分配: {stats['alloc_mb']} MB | 系统占用: {stats['sys_mb']} MB")

            # --- 功能展示 2: 节点发现 ---
            print("\n📡 正在执行局域网节点发现 (UDP 广播)...")
            nodes = client.call("discover_nodes", {}, timeout=5)
            if isinstance(nodes, list):
                if not nodes:
                    print("   ℹ️ 未发现其他活动节点。")
                for node in nodes:
                    print(f"   🖥️ 发现节点: {node}")
            else:
                print(f"❌ 节点发现失败: {nodes}")

            # --- 功能展示 3: 多线程文件审计 ---
            # 默认审计当前程序的源码目录
            audit_path = os.path.join(project_root, "programs", "hybrid_system_executor")
            print(f"\n🛡️ 正在进行多线程文件完整性审计: {audit_path}")
            audit_results = client.call("audit", {"dir": audit_path}, timeout=30)

            if isinstance(audit_results, list):
                print(f"   ✅ 审计完成! 处理文件数: {len(audit_results)}")
                # 只显示前 5 个结果
                for res in audit_results[:5]:
                    status = "OK" if "hash" in res else "ERR"
                    filename = os.path.basename(res['path'])
                    print(f"   [{status}] {filename} -> {res.get('hash', res.get('error'))[:16]}...")
                if len(audit_results) > 5:
                    print(f"   ... 以及其他 {len(audit_results)-5} 个文件。")
            else:
                print(f"❌ 审计任务失败: {audit_results}")

    except Exception as e:
        return f"❌ 执行过程中发生异常: {e}"

    return "\n✨ 系统审计与任务执行已圆满完成。"

if __name__ == "__main__":
    print(run())
