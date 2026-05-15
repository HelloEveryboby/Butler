import os
from butler.core.hybrid_link import HybridLinkClient

def handle_request(action, **kwargs):
    entities = kwargs.get("entities", {})
    cmd = action or entities.get("action")

    project_root = os.getcwd()

    if "系统状态" in cmd or cmd == "status":
        exe_path = os.path.join(project_root, "programs/hybrid_sysutil/sysutil")
        if not os.path.exists(exe_path): return "模块未就绪。"
        client = HybridLinkClient(exe_path)
        info = client.call("get_system_info", {})
        summary = f"系统负载: {info.get('load_1m')}, 可用内存: {info.get('free_mb')} MB"
        client.stop()
        return summary

    elif "安全扫描" in cmd or cmd == "scan":
        target = entities.get("target") or "127.0.0.1"
        exe_path = os.path.join(project_root, "programs/hybrid_net/net_tool")
        if not os.path.exists(exe_path): return "模块未就绪。"
        client = HybridLinkClient(exe_path)
        res = client.call("scan_ports", {"host": target, "ports": "80,443,3306"})
        client.stop()
        return f"扫描完成。开放端口: {res.get('open_ports')}"

    elif "校验文件" in cmd or cmd == "verify":
        path = entities.get("path")
        if not path: return "提供路径。"
        exe_path = os.path.join(project_root, "programs/hybrid_crypto/crypto_tool")
        if not os.path.exists(exe_path): return "模块未就绪。"
        client = HybridLinkClient(exe_path)
        res = client.call("hash_file", {"path": os.path.abspath(path)})
        client.stop()
        return f"SHA256: {res.get('hash')}"

    return "系统安全盾就绪。"
