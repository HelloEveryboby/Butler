/**
 * @file freertos_config.c
 * @brief FreeRTOS Task Management and Task Definition for STM32 Multi-tool
 */

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
extern bool nfc_get_last_uid(uint8_t* out_uid);
extern void hw_ir_start_capture(void);
extern void hw_ir_send_pwm(uint32_t* pulses, uint16_t count);

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
    xNFCQueue = xQueueCreate(5, sizeof(uint8_t[16])); // NFC UID Queue
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
 * @brief  GUI Task - Handles LVGL and Touch Input
 */
void vGUITask( void *pvParameters ) {
    // Initial LVGL setup
    // lv_init();
    // lv_port_disp_init();
    // lv_port_indev_init();

    // UI Main Loop
    for( ;; ) {
        if( xSemaphoreTake( xGUIMutex, portMAX_DELAY ) == pdTRUE ) {
            // lv_timer_handler(); // Process LVGL timers/events
            xSemaphoreGive( xGUIMutex );
        }
        vTaskDelay( pdMS_TO_TICKS( 5 ) ); // 5ms loop for smooth UI
    }
}

/**
 * @brief  NFC Task - Handles PN532 Communication
 */
void vNFCTask( void *pvParameters ) {
    nfc_init();
    for( ;; ) {
        if (nfc_scan_tag()) {
            uint8_t uid[7];
            if (nfc_get_last_uid(uid)) {
                xQueueSend(xNFCQueue, uid, 0);
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
