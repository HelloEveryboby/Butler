# ESP32 语音终端固件 (MicroPython)
# 作用：连接 Wi-Fi，采集麦克风音频并通过 MQTT 发送到 Jarvis

import network
import time
from umqtt.simple import MQTTClient
from machine import I2S, Pin

# --- 配置区 ---
WIFI_SSID = "您的_WIFI_名称"
WIFI_PASS = "您的_WIFI_密码"
MQTT_BROKER = "您的_电脑_IP" # 或者使用 broker.emqx.io
DEVICE_ID = "esp32_voice_01"

# I2S 麦克风引脚配置 (以 INMP441 为例)
SCK_PIN = 14
WS_PIN = 15
SD_PIN = 32

def connect_wifi():
    wlan = network.WLAN(network.STA_IF)
    wlan.active(True)
    if not wlan.isconnected():
        print('Connecting to WiFi...')
        wlan.connect(WIFI_SSID, WIFI_PASS)
        while not wlan.isconnected():
            pass
    print('WiFi Connected:', wlan.ifconfig())

def main():
    connect_wifi()

    client = MQTTClient(DEVICE_ID, MQTT_BROKER)
    client.connect()
    print("MQTT Connected")

    # 初始化 I2S 麦克风
    audio_in = I2S(0,
                   sck=Pin(SCK_PIN), ws=Pin(WS_PIN), sd=Pin(SD_PIN),
                   mode=I2S.RX, bits=16, format=I2S.MONO,
                   rate=16000, ibuf=32000)

    print("Listening...")

    # 简单的能量检测或持续流发送
    # 这里演示发送指令文本（假设板载了简单的语音识别，或仅作为中转）
    # 实际的高级版本会通过 WebSocket 发送原始音频流
    while True:
        # 示例：按下板载按钮发送一次测试指令
        # if button.value() == 0:
        #     client.publish("butler/commands", "打开电灯")
        #     time.sleep(1)

        # 接收来自 Jarvis 的指令
        client.check_msg()
        time.sleep(0.1)

if __name__ == "__main__":
    main()
