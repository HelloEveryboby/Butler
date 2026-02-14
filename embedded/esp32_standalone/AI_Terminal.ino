/*
 * Butler Standalone AI Terminal (ESP32)
 * 这是一个独立的单片机方案，直接调用 DeepSeek API，无需 PC 中转。
 *
 * 依赖库:
 * - ArduinoJson (用于解析 API 返回的 JSON)
 * - HTTPClient (内置)
 * - WiFiClientSecure (内置)
 */

#include <WiFi.h>
#include <HTTPClient.h>
#include <WiFiClientSecure.h>
#include <ArduinoJson.h>

// ==========================================
// 基础配置
// ==========================================
const char* ssid = "YOUR_WIFI_SSID";
const char* password = "YOUR_WIFI_PASSWORD";
const char* apiKey = "YOUR_DEEPSEEK_API_KEY";

const char* apiUrl = "https://api.deepseek.com/chat/completions";

// 硬件引脚
const int LED_PIN = 2;

// ==========================================
// 系统提示词：定义单片机的身份和能力
// ==========================================
const char* systemPrompt =
  "你是一个运行在单片机上的智能助手。你的输出必须简洁。"
  "如果你想控制硬件，请在回复中包含以下指令标签："
  "[LED_ON] - 开启灯光"
  "[LED_OFF] - 关闭灯光"
  "例如：好的，这就为您开灯 [LED_ON]";

void setup() {
  Serial.begin(115200);
  pinMode(LED_PIN, OUTPUT);
  digitalWrite(LED_PIN, LOW);

  // 连接 WiFi
  WiFi.begin(ssid, password);
  Serial.print("Connecting to WiFi");
  while (WiFi.status() != WL_CONNECTED) {
    delay(500);
    Serial.print(".");
  }
  Serial.println("\nWiFi Connected!");
}

/**
 * 调用 DeepSeek API
 */
String callDeepSeek(String userQuery) {
  if (WiFi.status() != WL_CONNECTED) return "WiFi Disconnected";

  WiFiClientSecure client;
  client.setInsecure(); // 为了简化，不校验根证书（生产环境建议校验）

  HTTPClient http;
  http.begin(client, apiUrl);
  http.addHeader("Content-Type", "application/json");
  http.addHeader("Authorization", String("Bearer ") + apiKey);

  // 构建 JSON 请求体
  StaticJsonDocument<512> doc;
  doc["model"] = "deepseek-chat";
  JsonArray messages = doc.createNestedArray("messages");

  JsonObject systemMsg = messages.createNestedObject();
  systemMsg["role"] = "system";
  systemMsg["content"] = systemPrompt;

  JsonObject userMsg = messages.createNestedObject();
  userMsg["role"] = "user";
  userMsg["content"] = userQuery;

  String requestBody;
  serializeJson(doc, requestBody);

  Serial.println("Sending request to DeepSeek...");
  int httpResponseCode = http.POST(requestBody);

  String result = "";
  if (httpResponseCode > 0) {
    String response = http.getString();
    StaticJsonDocument<2048> resDoc;
    deserializeJson(resDoc, response);
    result = resDoc["choices"][0]["message"]["content"].as<String>();
  } else {
    result = "Error: " + String(httpResponseCode);
  }

  http.end();
  return result;
}

/**
 * 硬件指令解析器
 */
void executeHardwareCommands(String aiResponse) {
  if (aiResponse.indexOf("[LED_ON]") != -1) {
    digitalWrite(LED_PIN, HIGH);
    Serial.println(">>> Hardware: LED turned ON");
  }
  if (aiResponse.indexOf("[LED_OFF]") != -1) {
    digitalWrite(LED_PIN, LOW);
    Serial.println(">>> Hardware: LED turned OFF");
  }
}

void loop() {
  // 模拟从串口接收用户输入
  if (Serial.available() > 0) {
    String query = Serial.readStringUntil('\n');
    query.trim();

    if (query.length() > 0) {
      Serial.println("User: " + query);
      String response = callDeepSeek(query);
      Serial.println("AI: " + response);

      // 解析并执行硬件指令
      executeHardwareCommands(response);
    }
  }
  delay(100);
}
