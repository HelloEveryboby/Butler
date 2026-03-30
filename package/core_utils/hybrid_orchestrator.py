"""
Butler 混合系统协调器 (Enhanced V2.0)
------------------------------------
此工具展示了 Butler 多语言协作（BHL）的核心能力：
1. C++ 处理高性能数学计算 (质因数分解与斐波那契数列)。
2. Go 处理高并发网络任务 (URL 可用性检测与端口扫描)。
3. Rust 处理内存安全的极速加密 (SHA256 哈希计算)。
4. Python 负责整体业务逻辑编排、异常处理与事件回调。
"""

import os
import sys
import traceback
from typing import Dict, Any

# 确保项目根目录在导入路径中
project_root = os.path.dirname(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
)
if project_root not in sys.path:
    sys.path.insert(0, project_root)

from butler.core.hybrid_link import HybridLinkClient


def on_bhl_event(event: Dict[str, Any]):
    """
    BHL 异步事件回调函数。
    当 Go 或其他模块产生异步通知时（如端口扫描发现），此函数将被触发。
    """
    method = event.get("method")
    params = event.get("params")
    print(f"\n🔔 [异步事件] 方法: {method}, 数据: {params}")


def run(*args, **kwargs):
    """
    混合系统编排器的主入口函数。
    """
    # 延迟导入以避免某些环境下的预加载问题
    from butler.core.extension_manager import extension_manager

    print("\n" + "=" * 60)
    print("      Butler 混合链接系统 (Hybrid-Link V2.0)")
    print("      支持语言: Python + C++ + Go + Rust")
    print("=" * 60)

    # 1. 扫描并注册所有已编译的二进制程序
    extension_manager.code_execution_manager.scan_and_register()

    # 获取各语言模块的信息
    compute_info = extension_manager.code_execution_manager.get_program(
        "hybrid_compute"
    )
    net_info = extension_manager.code_execution_manager.get_program("hybrid_net")
    crypto_info = extension_manager.code_execution_manager.get_program("hybrid_crypto")
    sysutil_info = extension_manager.code_execution_manager.get_program(
        "hybrid_sysutil"
    )
    math_info = extension_manager.code_execution_manager.get_program("hybrid_math")
    vision_info = extension_manager.code_execution_manager.get_program("hybrid_vision")

    # 检查模块可用性，若不可用将自动回退到 Python 原生实现
    missing = []
    if not compute_info:
        missing.append("C++ (hybrid_compute)")
    if not net_info:
        missing.append("Go (hybrid_net)")
    if not crypto_info:
        missing.append("Rust (hybrid_crypto)")
    if not sysutil_info:
        missing.append("C (hybrid_sysutil)")
    if not math_info:
        missing.append("C++ (hybrid_math)")
    if not vision_info:
        missing.append("C++ (hybrid_vision)")

    if missing:
        print(f"⚠️ [警告] 部分 BHL 模块缺失: ({', '.join(missing)})。")
        print("   系统将自动切换至 Python 备用方案执行任务。")

    results = []

    # 使用上下文管理器确保进程生命周期自动关闭
    try:
        # 定义辅助函数获取路径和工作目录
        get_path = lambda info: info["path"] if info else "MISSING"
        get_cwd = lambda info: os.path.dirname(info["path"]) if info else None

        with (
            HybridLinkClient(
                get_path(compute_info), cwd=get_cwd(compute_info)
            ) as compute_client,
            HybridLinkClient(get_path(net_info), cwd=get_cwd(net_info)) as net_client,
            HybridLinkClient(
                get_path(crypto_info), cwd=get_cwd(crypto_info)
            ) as crypto_client,
            HybridLinkClient(
                get_path(sysutil_info), cwd=get_cwd(sysutil_info)
            ) as sysutil_client,
            HybridLinkClient(
                get_path(math_info), cwd=get_cwd(math_info)
            ) as math_client,
            HybridLinkClient(
                get_path(vision_info), cwd=get_cwd(vision_info)
            ) as vision_client,
        ):
            # 注册 Go 模块的异步事件回调
            net_client.register_event_callback(on_bhl_event)

            print("✅ 跨语言环境初始化完成。\n")

            # --- 0. C 任务：高性能系统工具 ---
            print("🔹 [Python -> C] 正在获取系统资源状态...")
            sys_info = sysutil_client.call("get_system_info", {})
            if "error" in sys_info:
                results.append(f"❌ C 系统工具错误: {sys_info['error']['message']}")
            else:
                results.append(
                    f"✅ C 结果: 运行时间 {sys_info['uptime']}s, 负载 {sys_info['load_1m']}, 剩余内存 {sys_info['free_mb']}MB"
                )

            print("🔹 [Python -> C] 正在扫描 Butler 相关进程...")
            proc_info = sysutil_client.call("list_processes", {})
            if "error" in proc_info:
                results.append(f"❌ C 进程扫描错误: {proc_info['error']['message']}")
            else:
                p_count = len(proc_info.get("processes", []))
                results.append(f"✅ C 结果: 发现 {p_count} 个 Butler 相关进程")

            # --- 0.1 C++ 任务：高级数学与视觉 ---
            print("🔹 [Python -> C++] 正在进行统计分析任务...")
            stats_res = math_client.call("get_stats", {})
            if "error" in stats_res:
                results.append(f"❌ C++ 数学错误: {stats_res['error']['message']}")
            else:
                results.append(
                    f"✅ C++ 结果: 数据均值 {stats_res['mean']}, 中位数 {stats_res['median']}"
                )

            print("🔹 [Python -> C++] 正在执行边缘检测算法...")
            vision_res = vision_client.call("process_test", {})
            if "error" in vision_res:
                results.append(f"❌ C++ 视觉错误: {vision_res['error']['message']}")
            else:
                results.append(f"✅ C++ 结果: {vision_res['status']}")

            # --- 1. Rust 任务：高速哈希计算 ---
            secret_msg = "Butler 是最优秀的智能助手系统！"
            print(f"🔹 [Python -> Rust] 正在计算消息摘要: '{secret_msg}'")
            rust_result = crypto_client.call("hash_sha256", {"text": secret_msg})
            if "error" in rust_result:
                results.append(f"❌ Rust 错误: {rust_result['error']['message']}")
            else:
                results.append(f"✅ Rust 结果: SHA256 为 {rust_result['hash'][:32]}...")

            # --- 2. C++ 任务：重型数学运算 ---
            n_fib = 40
            print(f"🔹 [Python -> C++] 正在计算斐波那契数列(n={n_fib})...")
            math_result = compute_client.call("fibonacci", {"n": n_fib})
            if "error" in math_result:
                results.append(f"❌ C++ 错误: {math_result['error']['message']}")
            else:
                results.append(
                    f"✅ C++ 结果: Fibonacci({n_fib}) = {math_result['value']}"
                )

            # --- 3. Go 任务：高并发网络扫描 (支持事件驱动) ---
            target_host = "127.0.0.1"
            print(f"🔹 [Python -> Go] 正在并发扫描主机 {target_host} 的端口...")
            # 扫描 20-1024 端口
            net_result = net_client.call(
                "scan_ports",
                {"host": target_host, "start": 20, "end": 1024},
                timeout=15,
            )
            if "error" in net_result:
                results.append(f"❌ Go 错误: {net_result['error']['message']}")
            else:
                open_ports = net_result.get("open_ports", [])
                results.append(
                    f"✅ Go 结果: 在 {target_host} 上发现 {len(open_ports)} 个开放端口: {open_ports}"
                )

    except Exception as e:
        return f"系统协调异常: {e}\n{traceback.format_exc()}"

    summary = "\n".join(results)
    return f"\n--- 混合系统执行报告 ---\n{summary}\n"


if __name__ == "__main__":
    # 独立运行进行测试
    print(run())
