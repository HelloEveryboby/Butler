"""
Butler Go 高性能网络工具集
---------------------------
利用 Go 语言的高并发优势，提供压测、并发下载和批量探测功能。
遵循 BHL V2.0 协议进行混编交互。
"""

import os
import sys
import argparse
from typing import Dict, Any

# 确保项目根目录在导入路径中
project_root = os.path.dirname(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
)
if project_root not in sys.path:
    sys.path.insert(0, project_root)

from butler.core.hybrid_link import HybridLinkClient
from butler.core.extension_manager import extension_manager


def on_event(event: Dict[str, Any]):
    """处理来自 Go 模块的异步事件"""
    method = event.get("method")
    params = event.get("params")
    if method == "benchmark_started":
        print(
            f"🚀 压测开始: {params.get('url')} (并发: {params.get('concurrency')}, 总数: {params.get('count')})"
        )
    elif method == "download_started":
        print(
            f"📥 下载开始: 文件大小 {params.get('size')} 字节, 分片数 {params.get('chunks')}"
        )
    elif method == "download_progress":
        print(f"  - 分片 {params.get('chunk')} 下载完成")
    elif method == "scan_started":
        print(f"🔍 端口扫描开始: {params.get('host')} 范围 {params.get('range')}")


def run(*args, **kwargs):
    """
    Butler 扩展入口点
    """
    parser = argparse.ArgumentParser(description="Go 高性能网络工具")
    parser.add_argument(
        "--mode",
        choices=["benchmark", "download", "ping", "scan"],
        default="ping",
        help="运行模式",
    )
    parser.add_argument("--url", help="目标 URL")
    parser.add_argument("--path", default="downloaded_file.tmp", help="下载保存路径")
    parser.add_argument("--count", type=int, default=100, help="请求总数 (压测)")
    parser.add_argument("--concurrency", type=int, default=10, help="并发数")
    parser.add_argument("--hosts", nargs="+", help="批量 Ping 的主机列表")
    parser.add_argument("--host", default="127.0.0.1", help="端口扫描目标")

    # 支持从 args 或 sys.argv 传递参数
    if args:
        parsed_args = parser.parse_args(args)
    elif len(sys.argv) > 1:
        parsed_args = parser.parse_args(sys.argv[1:])
    else:
        # 默认示例行为
        print(
            "💡 提示: 可以通过参数调用此工具。示例: --mode benchmark --url http://example.com"
        )
        parsed_args = parser.parse_args(
            ["--mode", "ping", "--hosts", "google.com", "baidu.com", "github.com"]
        )

    # 查找 Go 二进制
    extension_manager.code_execution_manager.scan_and_register()
    prog_info = extension_manager.code_execution_manager.get_program("hybrid_net")

    if not prog_info:
        print("❌ 错误: 未找到 hybrid_net Go 二进制文件。")
        return

    exe_path = prog_info["path"]
    cwd = os.path.dirname(exe_path)

    with HybridLinkClient(exe_path, cwd=cwd) as client:
        client.register_event_callback(on_event)

        if parsed_args.mode == "benchmark":
            if not parsed_args.url:
                print("❌ 错误: 压测模式需要 --url 参数")
                return
            result = client.call(
                "benchmark",
                {
                    "url": parsed_args.url,
                    "count": parsed_args.count,
                    "concurrency": parsed_args.concurrency,
                },
                timeout=60,
            )

            if result and "error" in result:
                print(f"❌ 压测失败: {result['error'].get('message')}")
                return

            print("\n📊 压测结果报告:")
            print(f"  成功请求: {result.get('success')}/{result.get('total_requests')}")
            print(f"  平均延迟: {result.get('avg_ms')}ms")
            print(f"  最小延迟: {result.get('min_ms')}ms")
            print(f"  最大延迟: {result.get('max_ms')}ms")
            print(f"  P95 延迟: {result.get('p95_ms')}ms")

        elif parsed_args.mode == "download":
            if not parsed_args.url:
                print("❌ 错误: 下载模式需要 --url 参数")
                return
            result = client.call(
                "concurrent_download",
                {
                    "url": parsed_args.url,
                    "path": parsed_args.path,
                    "concurrency": parsed_args.concurrency,
                },
                timeout=300,
            )

            if result and "error" in result:
                print(f"❌ 下载失败: {result['error'].get('message')}")
                return

            print(f"\n✅ 下载完成! 文件保存在: {result.get('path')}")

        elif parsed_args.mode == "ping":
            hosts = parsed_args.hosts or ["127.0.0.1", "localhost"]
            print(f"📡 正在探测主机存活状态: {hosts}")
            results = client.call("batch_ping", {"hosts": hosts})
            print("\n📶 探测结果:")
            for r in results:
                status = "🟢 在线" if r.get("alive") else "🔴 离线"
                latency = f" ({r.get('latency_ms')}ms)" if r.get("alive") else ""
                print(f"  - {r.get('host')}: {status}{latency}")

        elif parsed_args.mode == "scan":
            result = client.call(
                "scan_ports",
                {"host": parsed_args.host, "start": 1, "end": 1024},
                timeout=30,
            )
            print(f"\n🛡️ 扫描结果 ({parsed_args.host}):")
            print(f"  开放端口: {result.get('open_ports')}")


if __name__ == "__main__":
    run()
