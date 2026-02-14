import os
import json
import logging
import threading
import paho.mqtt.client as mqtt
from typing import Dict, Any, Optional

logger = logging.getLogger(__name__)

class MQTTGateway:
    """
    MQTT 网关，用于与单片机（MCU）通信。
    采用单例模式以维持持久连接。
    """
    _instance = None
    _lock = threading.Lock()

    def __new__(cls):
        with cls._lock:
            if cls._instance is None:
                cls._instance = super(MQTTGateway, cls).__new__(cls)
                cls._instance._initialized = False
        return cls._instance

    def __init__(self):
        if self._initialized:
            return

        self.broker = os.getenv("MQTT_BROKER", "localhost")
        self.port = int(os.getenv("MQTT_PORT", 1883))
        self.client_id = os.getenv("MQTT_CLIENT_ID", "butler_brain")
        self.username = os.getenv("MQTT_USER")
        self.password = os.getenv("MQTT_PASS")

        # 使用 paho-mqtt v2.x API
        self.client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2, client_id=self.client_id)
        if self.username and self.password:
            self.client.username_pw_set(self.username, self.password)

        self.client.on_connect = self._on_connect
        self.client.on_message = self._on_message

        self.connected = False
        self.status_data = {}
        self._initialized = True

    def _on_connect(self, client, userdata, flags, rc, properties=None):
        if rc == 0:
            self.connected = True
            logger.info("Successfully connected to MQTT Broker!")
            self.client.subscribe("butler/status")
            self.client.subscribe("butler/events")
        else:
            logger.error(f"Failed to connect to MQTT, return code {rc}")

    def _on_message(self, client, userdata, msg):
        try:
            payload = json.loads(msg.payload.decode())
            if msg.topic == "butler/status":
                self.status_data.update(payload)
                logger.debug(f"Updated MCU status: {payload}")
            elif msg.topic == "butler/events":
                logger.info(f"Received event from MCU: {payload}")
                # 此处未来可以触发 Jarvis 的事件处理逻辑
        except Exception as e:
            logger.error(f"Error parsing MQTT message: {e}")

    def start(self):
        """启动 MQTT 客户端循环（如果尚未启动）"""
        if not self.connected:
            try:
                self.client.connect(self.broker, self.port, 60)
                self.client.loop_start()
                # 等待连接成功
                import time
                timeout = 5
                while not self.connected and timeout > 0:
                    time.sleep(0.1)
                    timeout -= 0.1
            except Exception as e:
                logger.error(f"MQTT Connection error: {e}")
                return False
        return True

    def stop(self):
        """停止 MQTT 客户端"""
        self.client.loop_stop()
        self.client.disconnect()
        self.connected = False

    def publish_command(self, action: str, **kwargs):
        """发布指令到单片机"""
        if not self.start():
            return {"success": False, "error": "Could not connect to MQTT broker"}

        payload = {"action": action}
        payload.update(kwargs)

        topic = "butler/commands"
        result = self.client.publish(topic, json.dumps(payload))
        success = (result.rc == mqtt.MQTT_ERR_SUCCESS)

        if success:
            logger.info(f"Published to {topic}: {payload}")
        else:
            logger.error(f"Failed to publish to {topic}, rc={result.rc}")

        return {"success": success, "msg_id": result.mid}

    def get_status(self):
        """获取最近一次收到的 MCU 状态"""
        return self.status_data

def run(command=None, *args, **kwargs):
    """
    Butler 工具入口。

    用法:
    run("publish", "gpio_set", "pin=2", "value=1")
    run("status")
    """
    gateway = MQTTGateway()

    if not command:
        return "MQTT 网关可用命令: publish (发布指令), status (查询状态)"

    try:
        if command == "publish":
            if not args:
                return "缺少 action 参数。用法: publish <action> [key=value ...]"

            action = args[0]
            extra_kwargs = {}
            for arg in args[1:]:
                if '=' in arg:
                    k, v = arg.split('=', 1)
                    try:
                        # 尝试转换为数字
                        if v.lower() in ('true', 'false'):
                            v = (v.lower() == 'true')
                        elif '.' in v:
                            v = float(v)
                        else:
                            v = int(v)
                    except ValueError:
                        pass
                    extra_kwargs[k] = v

            return gateway.publish_command(action, **extra_kwargs)

        elif command == "status":
            return gateway.get_status()

    except Exception as e:
        logger.error(f"MQTT Gateway tool error: {e}")
        return {"error": str(e)}

    return f"未知命令: {command}"
