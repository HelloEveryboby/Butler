/*
 * ESP32 Standalone AI Terminal (Arduino / C++)
 * 核心功能：通过串口或 MQTT 与 Butler 交互，支持显示状态和播放语音。
 */

#include <WiFi.h>
#include <PubSubClient.h>

// --- 配置 ---
const char* ssid = "YOUR_WIFI";
const char* password = "YOUR_PASSWORD";
const char* mqtt_server = "broker.emqx.io";

WiFiClient espClient;
PubSubClient client(espClient);

void setup_wifi() {
  delay(10);
  Serial.begin(115200);
  Serial.println();
  Serial.print("Connecting to ");
  Serial.println(ssid);

  WiFi.begin(ssid, password);
  while (WiFi.status() != WL_CONNECTED) {
    delay(500);
    Serial.print(".");
  }
  Serial.println("\nWiFi connected");
}

void callback(char* topic, byte* payload, unsigned int length) {
  Serial.print("Message arrived [");
  Serial.print(topic);
  Serial.print("] ");
  String message = "";
  for (int i = 0; i < length; i++) {
    message += (char)payload[i];
  }
  Serial.println(message);

  // 如果收到控制指令，可以在这里处理（如控制 LED、播放声音）
}

void reconnect() {
  while (!client.connected()) {
    Serial.print("Attempting MQTT connection...");
    if (client.connect("ESP32_Jarvis_Terminal")) {
      Serial.println("connected");
      client.subscribe("butler/device/esp32_01/control");
    } else {
      Serial.print("failed, rc=");
      Serial.print(client.state());
      delay(5000);
    }
  }
}

void setup() {
  setup_wifi();
  client.setServer(mqtt_server, 1883);
  client.setCallback(callback);
}

void loop() {
  if (!client.connected()) {
    reconnect();
  }
  client.loop();

  // 示例：从串口读取用户输入的文字指令并发送给 Jarvis
  if (Serial.available()) {
    String cmd = Serial.readStringUntil('\n');
    client.publish("butler/commands", cmd.c_str());
  }
}
