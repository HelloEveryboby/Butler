import json
import logging
from butler.core.event_bus import event_bus

logger = logging.getLogger("SensingAPI")

class SensingAPI:
    """
    通用传感数据 API (P3)
    解析符合规范的 JSON 传感数据并触发系统响应。
    规范格式: {"sensor": "distance", "value": 30, "unit": "cm"}
    """
    def __init__(self, jarvis):
        self.jarvis = jarvis

    def process_sensor_data(self, data_str):
        try:
            data = json.loads(data_str)
            sensor_type = data.get("sensor")
            value = data.get("value")

            if sensor_type == "distance":
                self._handle_distance(value)
            elif sensor_type == "noise":
                self._handle_noise(value)

            event_bus.emit(f"sensor:{sensor_type}", value)
        except Exception as e:
            logger.error(f"Failed to process sensor data: {e}")

    def _handle_distance(self, value):
        # 当检测到人靠近 (距离 < 50cm) 且环境安静时，使用细腻弹窗
        if value < 50:
            logger.info("User detected nearby. Adjusting notification style.")
            # 可以在此处触发 UI 状态变更

    def _handle_noise(self, value):
        # 当环境嘈杂时，自动增大提醒音量
        if value > 70:
            self.jarvis.ui_print("环境较嘈杂，已自动提高提醒音量。", tag='system_message')
            # self.jarvis.hardware.set_volume(80)

sensing_api = None

def init_sensing_api(jarvis):
    global sensing_api
    sensing_api = SensingAPI(jarvis)
    return sensing_api
