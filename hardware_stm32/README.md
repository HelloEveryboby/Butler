# STM32 Hardware Development Node (BHL Embedded)

## [状态：硬件层面待开发 - 需物理硬件验证]
## [STATUS: HARDWARE DEVELOPMENT - PENDING PHYSICAL VERIFICATION]

本项目目录包含 Butler 系统向硬件层面延伸的核心组件。

### 目录结构
- `src/`: STM32 固件源代码 (C 语言)
  - `nfc_service.c`: NFC 读写、复制与存储逻辑实现。
  - `ir_service.c`: 红外信号学习与发射逻辑实现。
  - `main.c`: 硬件节点主循环与 BHL 协议调度。
- `include/`: 头文件
  - `buce_embedded.h`: Butler 统一计算引擎 (BUCE) 的嵌入式版本，提供 BHL 协议栈。
  - `pn532_driver.h`: NFC 驱动抽象层。

### 功能说明
1. **NFC 功能**:
   - 标签读取 (UID & 数据块)
   - 数据存储 (至 STM32 Flash 或外部存储)
   - 标签复制 (克隆 UID 至空卡)
   - 扇区写入
2. **红外功能**:
   - 信号捕捉 (红外学习模式)
   - 编码重放 (红外发射)

### 物理连接建议
- **MCU**: STM32F103C8T6 (Blue Pill) 或类似型号。
- **NFC**: PN532 模块 (I2C/UART 接口)。
- **IR**: 红外接收头 (如 VS1838B) + 红外发射二极管 (带三极管驱动)。
- **PC 通信**: 使用 USB-TTL 模块连接 STM32 的 USART1 (PA9/PA10)。
