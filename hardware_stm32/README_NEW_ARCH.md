# Butler STM32 混合架构自述文件

## 架构概览
本项目采用了 "Brain & Hand" 协同架构：
1. **Brain (Python)**: 运行在 PC 端，负责 AI 决策、复杂数据处理。
2. **Controller (C)**: 运行在 PC 端，提供 Neo-Embedded 交互界面，协调 Brain 与 Hardware。
3. **Physical Hand (STM32)**: 负责底层硬件控制（NFC, Storage）。

## 核心组件
- `hardware_stm32/include/butler_core.h`: 极简位操作库 (BEC)。
- `hardware_stm32/include/butler_storage_hal.h`: 通用存储抽象层。
- `hardware_stm32/src/nfc_service.c`: 补全后的 NFC 克隆逻辑。

## 如何使用
1. 在 PC 端编译 `programs/bcli` 下的控制器。
2. 将固件烧录至 STM32，确保通过串口与 PC 连接。
3. 运行控制器：`./butler-controller /dev/ttyUSB0`
