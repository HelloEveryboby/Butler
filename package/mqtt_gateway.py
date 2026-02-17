import os
import json
import logging
import threading
import paho.mqtt.client as mqtt
from package.log_manager import LogManager

logger = LogManager.get_logger(__name__)

class MQTTGateway:
    _instance = None
    _lock = threading.Lock()

    def __new__(cls, *args, **kwargs):
        with cls._lock:
            if cls._instance is None:
                cls._instance = super(MQTTGateway, cls).__new__(cls)
                cls._instance._initialized = False
        return cls._instance

    def __init__(self, jarvis_app=None):
        if self._initialized: return
        self.jarvis = jarvis_app
        self.client = mqtt.Client(callback_api_version=mqtt.CallbackAPIVersion.VERSION2)
        self.broker = os.getenv("MQTT_BROKER", "broker.emqx.io")
        self.port = int(os.getenv("MQTT_PORT", 1883))
        self.topic_cmd = "butler/commands"
        self.topic_status = "butler/status"
        self.topic_events = "butler/events"

        self.client.on_connect = self._on_connect
        self.client.on_message = self._on_message
        self._initialized = True

    def _on_connect(self, client, userdata, flags, rc, properties):
        if rc == 0:
            logger.info(f"Connected to MQTT Broker: {self.broker}")
            self.client.subscribe([(self.topic_cmd, 0), (self.topic_events, 0)])
        else:
            logger.error(f"Failed to connect to MQTT, return code {rc}")

    def _on_message(self, client, userdata, msg):
        try:
            payload = msg.payload.decode('utf-8')
            logger.info(f"MQTT Received [{msg.topic}]: {payload}")

            if msg.topic == self.topic_cmd:
                # 硬件发来的控制指令，直接送入 Jarvis 大脑
                if self.jarvis:
                    self.jarvis.handle_user_command(payload)
            elif msg.topic == self.topic_events:
                # 硬件传感器事件等
                data = json.loads(payload)
                if self.jarvis:
                    self.jarvis.ui_print(f"硬件事件: {data}", tag='system_message')
        except Exception as e:
            logger.error(f"Error processing MQTT message: {e}")

    def publish_command(self, device_id, command, params=None):
        """向特定硬件设备发布指令。"""
        payload = json.dumps({
            "device_id": device_id,
            "command": command,
            "params": params or {}
        })
        self.client.publish(f"butler/device/{device_id}/control", payload)

    def start(self):
        def _run():
            try:
                self.client.connect(self.broker, self.port, 60)
                self.client.loop_forever()
            except Exception as e:
                logger.error(f"MQTT Loop error: {e}")

        thread = threading.Thread(target=_run, daemon=True)
        thread.start()
        logger.info("MQTT Gateway thread started.")

def run(operation=None, *args, **kwargs):
    """Butler 工具接口。"""
    gateway = MQTTGateway()
    if operation == "publish":
        device_id = kwargs.get("device_id")
        command = kwargs.get("command")
        params = kwargs.get("params", {})
        if device_id and command:
            gateway.publish_command(device_id, command, params)
            return f"Published {command} to {device_id}"
        return "Missing device_id or command"

    return "Usage: run(operation='publish', device_id='...', command='...', params={...})"
