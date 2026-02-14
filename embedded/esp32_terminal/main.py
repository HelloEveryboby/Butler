import time
import json
import machine
try:
    from umqtt.simple import MQTTClient
except ImportError:
    print("Error: 'umqtt.simple' not found. Please install it using upip.")
    # 在文档中说明如何安装：import upip; upip.install('micropython-umqtt.simple')

# ==========================================
# MQTT 配置 - 请确保与 Butler 端一致
# ==========================================
MQTT_BROKER = "192.168.1.xxx" # 运行 Butler 的 PC 的 IP 地址
CLIENT_ID = "esp32_butler_terminal"
COMMAND_TOPIC = b"butler/commands"
STATUS_TOPIC = b"butler/status"
EVENT_TOPIC = b"butler/events"

# ==========================================
# 硬件资源初始化
# ==========================================
# 内置 LED (通常在 Pin 2)
led = machine.Pin(2, machine.Pin.OUT)

# 模拟一个外部继电器或灯光 (Pin 4)
light = machine.Pin(4, machine.Pin.OUT)

# 定义回调函数处理来自 Butler 的指令
def on_message(topic, msg):
    print("Received Command from Butler:", topic.decode(), "->", msg.decode())
    try:
        data = json.loads(msg.decode())
        action = data.get("action")

        if action == "gpio_set":
            pin_num = data.get("pin")
            value = data.get("value", 0)
            # 动态控制引脚
            target_pin = machine.Pin(pin_num, machine.Pin.OUT)
            target_pin.value(1 if value else 0)
            print(f"GPIO {pin_num} set to {value}")

        elif action == "led_toggle":
            led.value(not led.value())
            print("Status LED Toggled")

        elif action == "light_control":
            # 专门处理灯光逻辑
            state = data.get("state", "off")
            if state == "on":
                light.value(1)
            else:
                light.value(0)
            print(f"Light turned {state}")

    except Exception as e:
        print("Failed to process command:", e)

def main():
    # 创建 MQTT 客户端
    client = MQTTClient(CLIENT_ID, MQTT_BROKER)
    client.set_callback(on_message)

    # 建立连接
    print(f"Attempting to connect to MQTT Broker: {MQTT_BROKER}...")
    try:
        client.connect()
        client.subscribe(COMMAND_TOPIC)
        print("Connected and Subscribed to Butler Commands.")

        # 发送上线通知
        client.publish(EVENT_TOPIC, json.dumps({"event": "online", "device": CLIENT_ID}))
    except Exception as e:
        print("MQTT Connection failed:", e)
        time.sleep(10)
        machine.reset() # 失败后重启

    last_status_time = 0

    while True:
        try:
            # 检查是否有新消息（非阻塞）
            client.check_msg()

            # 定期同步状态（心跳）
            curr_time = time.time()
            if curr_time - last_status_time > 15:
                status_msg = {
                    "device": CLIENT_ID,
                    "led_state": led.value(),
                    "light_state": light.value(),
                    "uptime": time.ticks_ms() // 1000
                }
                client.publish(STATUS_TOPIC, json.dumps(status_msg))
                last_status_time = curr_time
                print("Heartbeat sent.")

            time.sleep(0.2)

        except Exception as e:
            print("Loop interrupted, reconnecting...", e)
            time.sleep(5)
            try:
                client.connect()
                client.subscribe(COMMAND_TOPIC)
            except:
                machine.reset()

if __name__ == "__main__":
    main()
