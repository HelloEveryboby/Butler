/**
 * @file app_main.c
 * @brief Main Entry Point for STM32 FreeRTOS Multi-tool
 */

#include "FreeRTOS.h"
#include "task.h"
#include "freertos_config_app.h"
#include "buce_embedded.h"

// Global Sensor Data (Shared with GUI Task)
float g_current_temp = 25.0f;
float g_current_hum = 50.0f;
char g_nfc_last_uid[16] = "None";

// External Task Handlers
extern void os_init(void);
extern void ui_init(void);

/**
 * @brief  System Hardware Initialization (ST HAL)
 */
void System_Init(void) {
    // HAL_Init();
    // SystemClock_Config();
    // MX_GPIO_Init();
    // MX_I2C1_Init(); // For Touch & PN532
    // MX_SPI1_Init(); // For LCD
    // MX_TIM2_Init(); // For IR PWM
    // MX_TIM5_Init(); // For IR Capture
}

/**
 * @brief  Main program entry point
 */
int main(void) {
    // 1. Basic Hardware Setup
    System_Init();

    // 2. Initialize UI Components (LVGL)
    // Note: Memory allocation for LVGL should happen before scheduler or inside GUI task
    ui_init();

    // 3. Launch FreeRTOS Task Scheduler
    // This will create GUI, NFC, IR, and Sensor tasks
    os_init();

    // We should never reach here
    while (1);
}

/**
 * @brief FreeRTOS Hook: Stack Overflow
 */
void vApplicationStackOverflowHook(TaskHandle_t xTask, char *pcTaskName) {
    // Handle error
    while(1);
}

/**
 * @brief FreeRTOS Hook: Malloc Failed
 */
void vApplicationMallocFailedHook(void) {
    // Handle error
    while(1);
}
