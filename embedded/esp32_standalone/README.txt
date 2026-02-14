ESP32 Standalone AI Terminal Setup
==================================

1. Install Arduino IDE (https://www.arduino.cc/en/software).
2. Install ESP32 Board support:
   - File -> Preferences -> Additional Boards Manager URLs:
     https://raw.githubusercontent.com/espressif/arduino-esp32/gh-pages/package_esp32_index.json
   - Tools -> Board -> Boards Manager -> Search "esp32" and install.
3. Install Libraries:
   - Tools -> Manage Libraries -> Search and install:
     * ArduinoJson (by Benoit Blanchon)
4. Open AI_Terminal.ino.
5. Replace YOUR_WIFI_SSID, YOUR_WIFI_PASSWORD, and YOUR_DEEPSEEK_API_KEY.
6. Select your board (e.g., "ESP32 Dev Module") and Upload.
7. Open Serial Monitor at 115200 baud to interact!
