# Butler 单片机 (MCU) 接入指南

本指南介绍如何将单片机（如 ESP32）接入 Butler 系统，实现语音控制硬件的功能。

## 1. 架构方案

我们采用 **“脑-体” (Brain-Body) 架构**：
*   **大脑 (Brain)**：运行在 PC、树莓派或服务器上的 Butler 系统，负责语音识别、自然语言处理 (LLM) 和高级逻辑。
*   **身体 (Body)**：单片机终端（终端节点），负责连接物理世界的传感器和执行器。
*   **通信层**：通过 **MQTT 协议** 进行异步通信，具有低延迟、低功耗的特点。

## 2. 硬件准备

*   **核心板**：推荐使用 **ESP32** (具有内置 WiFi 和蓝牙，主频高，支持 MicroPython)。
*   **执行器**：
    *   板载 LED (Pin 2) 用于状态指示。
    *   继电器模块或外部 LED (Pin 4) 模拟灯光控制。
*   **环境**：
    *   运行 Butler 的电脑。
    *   一个 **MQTT Broker** (推荐使用开源的 [Mosquitto](https://mosquitto.org/))。

## 3. 软件配置

### 3.1 启动 MQTT Broker
单片机与 Butler 需要通过 MQTT 服务中转。在 Ubuntu/Debian 上安装：
```bash
sudo apt-get update
sudo apt-get install mosquitto mosquitto-clients
sudo systemctl enable mosquitto
sudo systemctl start mosquitto
```
*Windows 用户可以下载 Mosquitto 的安装包运行，或者使用在线的公共 Broker 进行测试。*

### 3.2 Butler 系统设置
1.  **安装依赖**：
    ```bash
    pip install paho-mqtt
    ```
2.  **环境变量**：
    在根目录的 `.env` 文件中添加：
    ```dotenv
    MQTT_BROKER=192.168.x.x  # 你的 PC 局域网 IP
    MQTT_PORT=1883
    ```

### 3.3 单片机固件部署
1.  **安装 MicroPython**：为你的 ESP32 烧录 MicroPython 固件（可使用 Thonny 或 esptool）。
2.  **上传代码**：
    *   将 `embedded/esp32_terminal/boot.py` 上传至 ESP32，并修改其中的 `SSID` 和 `PASSWORD` 为你的 WiFi 信息。
    *   将 `embedded/esp32_terminal/main.py` 上传至 ESP32，修改 `MQTT_BROKER` 为你 PC 的 IP 地址。
3.  **安装 MQTT 库**：在 ESP32 的终端运行：
    ```python
    import upip
    upip.install('micropython-umqtt.simple')
    ```

## 4. 交互指令

成功连接后，你可以通过 Butler 与单片机交互：

| 用户指令 (中文) | 对应意图 | 执行动作 |
| :--- | :--- | :--- |
| “打开灯” / “开灯” | `iot_control` | 向 `butler/commands` 发送 `{"action": "light_control", "state": "on"}` |
| “把灯关掉” | `iot_control` | 向 `butler/commands` 发送 `{"action": "light_control", "state": "off"}` |
| “单片机状态” | `get_mcu_status` | 获取并播报单片机上报的心跳数据 (Uptime, LED 状态等) |

## 5. 进阶扩展

*   **传感器上报**：你可以修改单片机的 `main.py`，在循环中读取温湿度传感器（如 DHT11）数据，并发布到 `butler/status` 主题。
*   **实时音视频**：对于 ESP32-S3 等高性能芯片，可以探索通过 I2S 协议将音频流实时推送到 Butler 进行识别，实现真正的远程无线拾音。
