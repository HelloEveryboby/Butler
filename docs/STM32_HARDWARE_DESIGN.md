# STM32 Multi-Tool (Flipper-Zero Style) Hardware Design Specification

## 1. Overview
This design aims to create a handheld, portable multi-tool featuring a touch-based sliding UI (MP4 style), NFC capabilities, IR remote learning/blasting, and environmental sensing, all managed by FreeRTOS.

## 2. Component List (BOM)
| Category | Component | Description |
| :--- | :--- | :--- |
| **MCU** | STM32F411CEU6 (Black Pill) | 100MHz, 512KB Flash, 128KB RAM (Required for smooth LVGL UI) |
| **Display** | 2.8" TFT LCD (ILI9341) | 320x240 Resolution, SPI Interface |
| **Touch** | Capacitive Touch (GT911) | I2C Interface, supports multi-touch and gestures |
| **NFC** | PN532 Module | I2C/SPI/UART (I2C recommended for PCB saving) |
| **IR** | VS1838B (RX) + IR LED (TX) | 38kHz Infrared Receiver and High-power Transmitter |
| **Sensors** | DHT22 (Aosong) | High-precision Temperature and Humidity Sensor |
| **Power** | TP4056 + DW01 | Lithium Battery Charging and Protection |
| **Regulator** | AMS1117-3.3 | 5V to 3.3V Step-down for MCU and peripherals |
| **Storage** | MicroSD Slot | SPI Interface for storing NFC dumps and UI assets |
| **Battery** | 1000mAh Li-Po | 3.7V Rechargeable Battery |

## 3. PCB Layout Strategy (Handheld Form Factor)
- **Layer Stack**: 2-layer or 4-layer (4-layer recommended for better signal integrity with high-speed SPI).
- **Dimensions**: 90mm x 55mm (Standard credit card length, slightly wider for the screen).
- **Placement**:
  - **Front Side**: 2.8" TFT Screen dominates the front. No physical buttons (all touch).
  - **Back Side**:
    - STM32F4 MCU (center).
    - PN532 NFC antenna (bottom half, kept away from metal shielding).
    - MicroSD slot (edge).
    - Battery glued to the back of the PCB or sandwiched between PCB and screen.
  - **Top Edge**: IR LED (TX) and IR Receiver (RX) pointing forward.
  - **Bottom Edge**: USB-C Port for charging and programming (USART1).
  - **Side**: Power Slide Switch.

## 4. Schematic Connections (High-Level)
### A. Display (SPI1)
- SCK: PA5
- MOSI: PA7
- MISO: PA6 (not used for LCD, but used for SD)
- CS: PB0
- DC: PB1
- RST: PB2

### B. Touch (I2C1)
- SCL: PB6
- SDA: PB7
- INT: PB8
- RST: PB9

### C. NFC (I2C2)
- SCL: PB10
- SDA: PB11

### D. IR (Timers)
- IR TX: PA0 (TIM2_CH1) - PWM Carrier
- IR RX: PA1 (GPIO / TIM5_CH2) - Capture

### E. Sensor
- DHT22: PA2 (Single-bus)

## 5. Mechanical Design Idea
- 3D Printed Enclosure.
- Transparent window for IR.
- Integrated NFC antenna on the PCB back or a small external flexible antenna.
