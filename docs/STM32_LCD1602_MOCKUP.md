# LCD1602 UI Layout Mockup (Lite Version)

Since the LCD1602 is a 16x2 character display, the UI is divided into several main pages.

## 1. Home Page
```text
[1] Butler v2.0-Lite
[2] -> NFC | IR | SN
```
- Line 1: System Branding
- Line 2: Menu Guide (NFC tools, IR tools, Sensor nodes)

## 2. NFC Scanner Page
```text
[1] NFC Scanner
[2] UID: 4D 5E 6F 7G
```
- Line 1: Function name
- Line 2: Real-time scan result (or "Wait for Tag...")

## 3. IR Remote Page
```text
[1] IR Controller
[2] 1:Learn  2:Send
```
- Line 1: Function name
- Line 2: Available actions (mapped to buttons/potentiometer inputs)

## 4. Sensor Display Page
```text
[1] T: 25.4C
[2] H: 62.8%
```
- Line 1: Temperature in Celsius
- Line 2: Humidity in Percentage

---

## Comparison with Modern UI (TFT/LVGL)
| Feature | LCD1602 (Lite) | TFT (Modern) |
| :--- | :--- | :--- |
| **Color** | Monochrome | 16-bit Color (RGB565) |
| **Interaction** | Buttons/Potentiometer | Capacitive Touch (Sliding) |
| **Graphics** | ASCII characters only | Icons, Shading, Animations |
| **Styling** | Plain text | Apple Glassmorphism |
| **CPU Load** | Very Low | Moderate (LVGL overhead) |
