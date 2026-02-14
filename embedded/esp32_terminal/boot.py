import network
import time
import machine

# ==========================================
# 基础配置文件 - 请根据实际环境修改
# ==========================================
SSID = 'YOUR_WIFI_SSID'
PASSWORD = 'YOUR_WIFI_PASSWORD'

def connect_wifi():
    """连接到 WiFi 网络"""
    wlan = network.WLAN(network.STA_IF)
    wlan.active(True)
    if not wlan.isconnected():
        print('Connecting to WiFi...')
        wlan.connect(SSID, PASSWORD)

        # 等待连接，最多等待 10 秒
        retry = 10
        while not wlan.isconnected() and retry > 0:
            time.sleep(1)
            retry -= 1

    if wlan.isconnected():
        print('WiFi Connected! IP Info:', wlan.ifconfig())
    else:
        print('WiFi Connection Failed. Please check SSID/PASSWORD.')

# 启动时连接 WiFi
connect_wifi()
