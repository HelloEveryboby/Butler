/*
 * Butler STM32 Serial Sync Protocol Driver
 * Protocol: [0xAA] [Bass] [Mid] [Treble] [0xBB]
 * Baudrate: 115200
 */

#include "stm32f1xx_hal.h"

uint8_t rx_buffer[5];
uint8_t bass, mid, treble;

void HAL_UART_RxCpltCallback(UART_HandleTypeDef *huart) {
    if (rx_buffer[0] == 0xAA && rx_buffer[4] == 0xBB) {
        bass = rx_buffer[1];
        mid = rx_buffer[2];
        treble = rx_buffer[3];

        // Update PWM for LED Strips or Matrix
        __HAL_TIM_SET_COMPARE(&htim1, TIM_CHANNEL_1, bass);
        __HAL_TIM_SET_COMPARE(&htim1, TIM_CHANNEL_2, mid);
        __HAL_TIM_SET_COMPARE(&htim1, TIM_CHANNEL_3, treble);
    }

    // Restart Interrupt
    HAL_UART_Receive_IT(huart, rx_buffer, 5);
}
