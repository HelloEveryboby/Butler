import socket
import logging
from zeroconf import ServiceInfo, Zeroconf

logger = logging.getLogger("ButlerMDNS")

class ButlerServiceDiscovery:
    """
    Butler 局域网服务发现与注册 (mDNS)。
    实现 Master 与 Agent 之间的零配置开箱即用发现。
    """
    def __init__(self, service_type="_butler._tcp.local."):
        self.service_type = service_type
        self.zeroconf = Zeroconf()

    def register_service(self, name: str, port: int, properties: dict = None):
        """将当前节点注册到局域网"""
        local_ip = self._get_local_ip()
        info = ServiceInfo(
            self.service_type,
            f"{name}.{self.service_type}",
            addresses=[socket.inet_aton(local_ip)],
            port=port,
            properties=properties or {},
            server=f"{name}.local.",
        )
        self.zeroconf.register_service(info)
        logger.info(f"Registered Butler service: {name} at {local_ip}:{port}")
        return info

    def _get_local_ip(self):
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        try:
            # doesn't even have to be reachable
            s.connect(('10.255.255.255', 1))
            IP = s.getsockname()[0]
        except Exception:
            IP = '127.0.0.1'
        finally:
            s.close()
        return IP

    def close(self):
        self.zeroconf.close()

class ServiceListener:
    def __init__(self, on_found_callback):
        self.on_found = on_found_callback

    def remove_service(self, zeroconf, type, name):
        pass

    def add_service(self, zeroconf, type, name):
        info = zeroconf.get_service_info(type, name)
        if info:
            address = socket.inet_ntoa(info.addresses[0])
            port = info.port
            self.on_found(name, address, port, info.properties)

def browse_butler_services(callback):
    """持续监听局域网内的 Butler 服务"""
    zc = Zeroconf()
    listener = ServiceListener(callback)
    from zeroconf import ServiceBrowser
    browser = ServiceBrowser(zc, "_butler._tcp.local.", listener)
    return zc, browser
