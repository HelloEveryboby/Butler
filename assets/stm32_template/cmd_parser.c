/**
 * Butler HCP v1 指令解析器模板 (STM32/C)
 * 硬件端实现建议：
 * 1. 串口 DMA 或 中断 接收数据。
 * 2. 校验 Header (0xAA) 和 End (0x55)。
 * 3. 校验 CheckSum。
 */
#include <stdint.h>
#include <stdbool.h>

#define HCP_HEADER 0xAA
#define HCP_END    0x55

// 指令包结构
typedef struct {
    uint8_t header;
    uint8_t type;
    uint8_t device;
    uint8_t action;
    uint8_t data[4];
    uint8_t checksum;
    uint8_t end;
} HCP_Packet_t;

// 校验和计算
uint8_t HCP_CalculateChecksum(HCP_Packet_t *packet) {
    uint8_t checksum = packet->header ^ packet->type ^ packet->device ^ packet->action;
    for (int i = 0; i < 4; i++) {
        checksum ^= packet->data[i];
    }
    return checksum;
}

// 核心解析逻辑
void HCP_ParseCommand(uint8_t *buffer, uint16_t length) {
    if (length < 10) return;

    HCP_Packet_t packet;
    packet.header = buffer[0];
    packet.type = buffer[1];
    packet.device = buffer[2];
    packet.action = buffer[3];
    for (int i = 0; i < 4; i++) {
        packet.data[i] = buffer[4 + i];
    }
    packet.checksum = buffer[8];
    packet.end = buffer[9];

    // 1. 校验头尾
    if (packet.header != HCP_HEADER || packet.end != HCP_END) return;

    // 2. 校验和
    if (packet.checksum != HCP_CalculateChecksum(&packet)) return;

    // 3. 执行分发
    switch (packet.device) {
        case 0x10: // LED
            if (packet.action == 0x01) {
                // HAL_GPIO_WritePin(LED_GPIO_Port, LED_Pin, GPIO_PIN_RESET); // 开启
            } else {
                // HAL_GPIO_WritePin(LED_GPIO_Port, LED_Pin, GPIO_PIN_SET);   // 关闭
            }
            break;
        case 0xFF: // System Lock
            if (packet.type == 0x03) {
                // 报警并锁定硬件外设
                // HAL_TIM_PWM_Start(&htim1, TIM_CHANNEL_1); // 开启蜂鸣器
            }
            break;
        default:
            break;
    }
}
