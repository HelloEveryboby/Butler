/**
 * @file freertos_config.c
 * @brief FreeRTOS Task Management and Task Definition for STM32 Multi-tool
 */

#include <stdio.h>
#include <string.h>
#include "FreeRTOS.h"
#include "task.h"
#include "queue.h"
#include "semphr.h"

// Task Priority Definitions
#define PRIORITY_GUI_TASK        ( tskIDLE_PRIORITY + 3 )
#define PRIORITY_NFC_TASK        ( tskIDLE_PRIORITY + 2 )
#define PRIORITY_IR_TASK         ( tskIDLE_PRIORITY + 2 )
#define PRIORITY_SENSOR_TASK     ( tskIDLE_PRIORITY + 1 )

// Task Stack Sizes
#define STACK_SIZE_GUI           ( 2048 / sizeof( StackType_t ) )
#define STACK_SIZE_NFC           ( 512 / sizeof( StackType_t ) )
#define STACK_SIZE_IR            ( 512 / sizeof( StackType_t ) )
#define STACK_SIZE_SENSOR        ( 256 / sizeof( StackType_t ) )

// Queues and Semaphores
QueueHandle_t xNFCQueue;
QueueHandle_t xIRQueue;
SemaphoreHandle_t xGUIMutex;

// External Service Prototypes (from nfc_service.c, ir_service.c)
extern bool nfc_init(void);
extern bool nfc_scan_tag(void);
extern bool nfc_get_last_uid(uint8_t* out_uid, uint8_t max_len, uint8_t* actual_len);
extern void hw_ir_start_capture(void);
extern void hw_ir_send_pwm(uint32_t* pulses, uint16_t count);

// UI Mode Configuration (0: Modern/LVGL, 1: Lite/LCD1602)
#define UI_MODE_LITE 1

// Shared Global Variables
extern float g_current_temp;
extern float g_current_hum;
extern char g_nfc_last_uid[16];

// Task Function Prototypes
void vGUITask( void *pvParameters );
void vNFCTask( void *pvParameters );
void vIRTask( void *pvParameters );
void vSensorTask( void *pvParameters );

/**
 * @brief  System OS Startup
 */
void os_init(void) {
    // 1. Create Synchronization Objects
    xNFCQueue = xQueueCreate(5, 11); // 10 bytes UID + 1 byte length
    xIRQueue = xQueueCreate(5, sizeof(uint32_t));    // IR Code Queue
    xGUIMutex = xSemaphoreCreateMutex();

    // 2. Create Tasks
    xTaskCreate( vGUITask, "GUI", STACK_SIZE_GUI, NULL, PRIORITY_GUI_TASK, NULL );
    xTaskCreate( vNFCTask, "NFC", STACK_SIZE_NFC, NULL, PRIORITY_NFC_TASK, NULL );
    xTaskCreate( vIRTask, "IR", STACK_SIZE_IR, NULL, PRIORITY_IR_TASK, NULL );
    xTaskCreate( vSensorTask, "SENSOR", STACK_SIZE_SENSOR, NULL, PRIORITY_SENSOR_TASK, NULL );

    // 3. Start Scheduler
    vTaskStartScheduler();
}

/**
 * @brief  GUI Task - Handles LVGL or LCD1602 Rendering
 */
extern void ui_init(void);
extern void ui_lcd1602_render(void);
extern void ui_update_data(float temp, float hum, const char* nfc_uid);
extern void lv_timer_handler(void);

void vGUITask( void *pvParameters ) {
    #if (UI_MODE_LITE == 1)
        // Lite UI Mode (LCD1602)
        ui_lcd1602_render();
    #else
        // Modern UI Mode (LVGL)
        ui_init();
    #endif

    for( ;; ) {
        // Consumer: Check for NFC data
        struct { uint8_t data[10]; uint8_t len; } nfc_msg;
        if (xQueueReceive(xNFCQueue, &nfc_msg, 0) == pdTRUE) {
            char hex_uid[31] = {0};
            for(int i=0; i<nfc_msg.len; i++) sprintf(hex_uid + strlen(hex_uid), "%02X ", nfc_msg.data[i]);
            strncpy(g_nfc_last_uid, hex_uid, 15);
        }

        if( xSemaphoreTake( xGUIMutex, portMAX_DELAY ) == pdTRUE ) {
            #if (UI_MODE_LITE == 1)
                ui_lcd1602_render();
                vTaskDelay( pdMS_TO_TICKS( 200 ) );
            #else
                ui_update_data(g_current_temp, g_current_hum, g_nfc_last_uid);
                lv_timer_handler(); // Active Modern UI Handler
                vTaskDelay( pdMS_TO_TICKS( 5 ) );
            #endif
            xSemaphoreGive( xGUIMutex );
        }
    }
}

/**
 * @brief  NFC Task - Handles PN532 Communication
 */
void vNFCTask( void *pvParameters ) {
    nfc_init();
    for( ;; ) {
        if (nfc_scan_tag()) {
            uint8_t uid[10]; // PN532 can handle up to 10-byte UIDs (e.g., ISO14443B)
            uint8_t actual_len = 0;
            if (nfc_get_last_uid(uid, 10, &actual_len)) {
                // Wrap in a structure for the queue to preserve length
                struct { uint8_t data[10]; uint8_t len; } msg;
                memcpy(msg.data, uid, actual_len);
                msg.len = actual_len;
                xQueueSend(xNFCQueue, &msg, 0);
            }
        }
        vTaskDelay( pdMS_TO_TICKS( 200 ) ); // 200ms polling rate
    }
}

/**
 * @brief  IR Task - Handles Infrared RX/TX
 */
void vIRTask( void *pvParameters ) {
    hw_ir_start_capture();
    for( ;; ) {
        // Signal capture is interrupt driven in real hardware
        // This task would process captured signals from a buffer
        vTaskDelay( pdMS_TO_TICKS( 50 ) );
    }
}

/**
 * @brief  Sensor Task - Handles DHT22 Polling
 */
void vSensorTask( void *pvParameters ) {
    for( ;; ) {
        // float temp, hum;
        // DHT22_Read(&temp, &hum);
        // Update Global Sensor Variables or send via Queue
        vTaskDelay( pdMS_TO_TICKS( 2000 ) ); // 2s interval for DHT
    }
}
