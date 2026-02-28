"""
Butler 专业级多线程系统审计与任务调度工具 (V1.2)
---------------------------------------------
核心增强：
1. [新增] 并发 Android 移动设备安全审计。
2. 并行正则表达式日志扫描。
3. 分布式节点指令下发。
4. 基于优先级的任务调度。
"""

import os
import sys
import time
import json
from typing import Dict, Any

# 确保项目根目录在导入路径中
project_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if project_root not in sys.path:
    sys.path.insert(0, project_root)

from butler.core.hybrid_link import HybridLinkClient

def on_bhl_event(event: Dict[str, Any]):
    """处理来自 BHL 模块的异步通知事件。"""
    method = event.get("method")
    params = event.get("params")
    if method == "audit_started":
        print(f"\n🔍 [审计开始] 目录: {params.get('directory')}")
    elif method == "scan_started":
        print(f"\n🔎 [日志扫描] 目录: {params.get('directory')} | 正则: {params.get('regex')}")
    else:
        print(f"\n🔔 [BHL 事件] {method}: {params}")

def run(*args, **kwargs):
    """
    系统审计工具主入口。
    """
    from butler.core.extension_manager import extension_manager

    print("\n" + "💎"*30)
    print("      Butler 专业级系统执行与调度引擎")
    print("      核心引擎: Go (并发优先级工作池)")
    print("💎"*30)

    # 1. 扫描并查找 Go 原生程序
    extension_manager.code_execution_manager.scan_and_register()
    prog_info = extension_manager.code_execution_manager.get_program("hybrid_system_executor")

    if not prog_info:
        return "❌ 错误: 未能找到 'hybrid_system_executor' 模块。"

    executable = prog_info['path']
    cwd = os.path.dirname(executable)

    try:
        with HybridLinkClient(executable, cwd=cwd) as client:
            client.register_event_callback(on_bhl_event)
            print(f"✅ 专业级 BHL 引擎已启动: {executable}\n")

            # --- 1. 获取增强状态监控 ---
            print("📊 正在获取核心负载状态...")
            stats = client.call("get_stats", {})
            if "error" not in stats:
                print(f"   [调度状态] 活跃协程: {stats['goroutines']} | 待处理队列: {stats['pq_len']}")
                print(f"   [资源信息] 内存分配: {stats['alloc_mb']} MB | 系统占用: {stats['sys_mb']} MB")

            # --- 2. 移动设备专业审计 (V1.2 新特性) ---
            print("\n📱 正在执行多设备并发安全审计 (ADB)...")
            adb_results = client.call("adb_audit", {}, timeout=10)
            if isinstance(adb_results, list):
                if not adb_results:
                    print("   ℹ️ 未检测到已连接的 Android 设备。")
                else:
                    print(f"   ✅ 发现 {len(adb_results)} 台设备，审计报告如下:")
                    for dev in adb_results:
                        root_status = "已激活 (危险)" if dev['is_rooted'] else "未激活 (安全)"
                        print(f"      - [{dev['serial']}] {dev['model']} | 安卓 {dev['android_ver']} | Root: {root_status} | 补丁: {dev['security_patch']}")
            else:
                print(f"❌ 移动审计失败: {adb_results}")

            # --- 3. 并行日志扫描 ---
            log_dir = os.path.join(project_root, "programs", "hybrid_system_executor")
            regex_pattern = "func|go"
            print(f"\n🚀 正在执行并行正则表达式扫描: {log_dir} (匹配模式: '{regex_pattern}')")
            scan_results = client.call("log_scan", {"dir": log_dir, "regex": regex_pattern}, timeout=15)

            if isinstance(scan_results, dict) and not "error" in scan_results:
                match_count = sum(len(matches) for matches in scan_results.values())
                print(f"   ✅ 扫描完成! 在 {len(scan_results)} 个文件中发现 {match_count} 处匹配。")
            else:
                print(f"❌ 日志扫描失败: {scan_results}")

            # --- 4. 任务优先级调度 ---
            print("\n⚡ 演示基于优先级的异步任务调度...")
            client.call("audit", {"dir": log_dir}, priority=10, wait=False)
            quick_stats = client.call("get_stats", {}, priority=0)
            print(f"   ✅ 高优先级任务即时返回 (当前队列长度: {quick_stats.get('pq_len')})")

            # --- 5. 节点发现与分布式控制 ---
            print("\n📡 正在执行局域网节点发现 (UDP 广播)...")
            nodes = client.call("discover_nodes", {}, timeout=3)
            if isinstance(nodes, list) and nodes:
                print(f"   🖥️ 发现 {len(nodes)} 个活跃节点:")
                for node_str in nodes:
                    print(f"      - {node_str}")
            else:
                print("   ℹ️ 未发现其他活动节点。")

    except Exception as e:
        return f"❌ 执行异常: {e}"

    return "\n✨ 专业级多端系统审计任务已圆满完成。"

if __name__ == "__main__":
    print(run())
