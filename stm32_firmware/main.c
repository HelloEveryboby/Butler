/**
 * @file main.c
 * @brief Main firmware for STM32 to act as an IoT device controlled by Butler.
 * @author Jules (AI Assistant)
 * @date 2023-10-27
 *
 * @description
 * This firmware enables an STM32 microcontroller to connect to a Wi-Fi network
 * and an MQTT broker using an external ESP8266 module. It subscribes to a specific
 * MQTT topic to receive commands from the Butler system and controls a local LED
 * based on the received messages.
 *
 * The communication with the ESP8266 is done via UART using AT commands.
 *
 * HARDWARE SETUP:
 * 1. STM32 Nucleo Board (e.g., NUCLEO-F446RE, but adaptable to others)
 * 2. ESP8266 Wi-Fi Module (e.g., ESP-01)
 * 3. An LED connected to a GPIO pin.
 *
 * WIRING:
 * - STM32 TX (e.g., PA2) -> ESP8266 RX
 * - STM32 RX (e.g., PA3) -> ESP8266 TX
 * - STM32 GPIO (e.g., PA5) -> LED Anode -> Resistor (e.g., 220 Ohm) -> GND
 * - Power: Provide appropriate VCC (3.3V) and GND to both STM32 and ESP8266.
 *
 * HOW TO USE:
 * 1. Configure the settings in the "USER CONFIGURATION" section below.
 * 2. Flash this firmware to your STM32 board using your preferred IDE (STM32CubeIDE, Keil, etc.).
 * 3. Open a serial monitor (e.g., PuTTY, Tera Term) connected to the STM32's VCP (Virtual COM Port)
 *    to see debug messages. The baud rate should be 115200.
 * 4. Power on the device. It will automatically connect to Wi-Fi and the MQTT broker.
 * 5. Use the Butler system to send commands.
 */

/* ============================================================================
 * C HEADERS
 * ============================================================================ */
#include "main.h" // Standard STM32 HAL header
#include <string.h>
#include <stdio.h>
#include <stdbool.h>

/* ============================================================================
 * USER CONFIGURATION - MODIFY THESE SETTINGS
 * ============================================================================ */

// -- Wi-Fi Settings --
const char *WIFI_SSID = "YOUR_WIFI_SSID";
const char *WIFI_PASSWORD = "YOUR_WIFI_PASSWORD";

// -- MQTT Broker Settings --
// IP address of the computer running the MQTT broker (and Butler)
const char *MQTT_BROKER_IP = "YOUR_COMPUTER_IP_ADDRESS";
const char *MQTT_BROKER_PORT = "1883";

// -- Device Identity --
const char *DEVICE_ID = "stm32-led-1";

// -- UART Buffers --
#define UART_RX_BUFFER_SIZE 1024
#define UART_TX_BUFFER_SIZE 256

/* ============================================================================
 * PRIVATE VARIABLES
 * ============================================================================ */

// -- UART Handles --
// huart1 is for debug output (printf) to your computer's serial monitor
// huart2 is for communication with the ESP8266 module
extern UART_HandleTypeDef huart1;
extern UART_HandleTypeDef huart2;

// -- Buffers --
uint8_t uart_rx_buffer[UART_RX_BUFFER_SIZE];
volatile uint16_t uart_rx_write_pos = 0;
volatile bool command_received = false;

/* ============================================================================
 * PRIVATE FUNCTION PROTOTYPES
 * ============================================================================ */

void SystemClock_Config(void);
static void MX_GPIO_Init(void);
static void MX_USART1_UART_Init(void);
static void MX_USART2_UART_Init(void);

// Helper functions for ESP8266 communication
void esp8266_init(void);
bool send_at_command(const char* cmd, const char* expected_response, uint32_t timeout);
void clear_rx_buffer(void);
void mqtt_subscribe(void);
void parse_mqtt_message(const char* msg);

// Function to allow printf to output to UART1 (for debugging)
#ifdef __GNUC__
#define PUTCHAR_PROTOTYPE int __io_putchar(int ch)
#else
#define PUTCHAR_PROTOTYPE int fputc(int ch, FILE *f)
#endif
PUTCHAR_PROTOTYPE
{
  HAL_UART_Transmit(&huart1, (uint8_t *)&ch, 1, 0xFFFF);
  return ch;
}

/* ============================================================================
 * MAIN FUNCTION
 * ============================================================================ */

int main(void) {
    // 1. Initialize HAL, System Clock, and Peripherals
    HAL_Init();
    SystemClock_Config();
    MX_GPIO_Init();
    MX_USART1_UART_Init(); // For debug prints
    MX_USART2_UART_Init(); // For ESP8266

    printf("--- STM32 Butler IoT Device Initializing ---\r\n");

    // 2. Start receiving data from ESP8266 via DMA or Interrupt
    HAL_UART_Receive_IT(&huart2, &uart_rx_buffer[0], 1);

    // 3. Initialize the ESP8266 module
    esp8266_init();

    // 4. Subscribe to the MQTT topic
    mqtt_subscribe();

    printf("--- Initialization Complete. Waiting for commands. ---\r\n");

    // 5. Main loop
    while (1) {
        if (command_received) {
            // A potential command has arrived in the buffer
            command_received = false;
            // The actual parsing happens in the UART IRQ handler to be more responsive
            // Here you could add other non-blocking tasks if needed.
        }
        HAL_Delay(100); // Small delay to prevent busy-waiting
    }
}

/* ============================================================================
 * ESP8266 & MQTT HELPER FUNCTIONS
 * ============================================================================ */

/**
 * @brief Initializes the ESP8266 module.
 */
void esp8266_init(void) {
    printf("Initializing ESP8266...\r\n");

    // Test AT command
    if (!send_at_command("AT\r\n", "OK", 2000)) {
        printf("Error: ESP8266 not responding.\r\n");
        return; // Halt on failure
    }
    printf("ESP8266 responded.\r\n");

    // Set Wi-Fi mode to Station
    send_at_command("AT+CWMODE=1\r\n", "OK", 2000);
    printf("Wi-Fi mode set to Station.\r\n");

    // Connect to Wi-Fi
    char cmd_buffer[UART_TX_BUFFER_SIZE];
    sprintf(cmd_buffer, "AT+CWJAP=\"%s\",\"%s\"\r\n", WIFI_SSID, WIFI_PASSWORD);
    if (!send_at_command(cmd_buffer, "WIFI GOT IP", 10000)) {
         printf("Error: Failed to connect to Wi-Fi.\r\n");
         return;
    }
    printf("Connected to Wi-Fi successfully.\r\n");

    // Connect to MQTT Broker
    sprintf(cmd_buffer, "AT+MQTTCONN=0,\"%s\",%s,0\r\n", MQTT_BROKER_IP, MQTT_BROKER_PORT);
    if (!send_at_command(cmd_buffer, "OK", 5000)) {
        printf("Error: Failed to connect to MQTT broker.\r\n");
        return;
    }
    printf("Connected to MQTT broker successfully.\r\n");
}

/**
 * @brief Subscribes to the device's command topic.
 */
void mqtt_subscribe(void) {
    char cmd_buffer[UART_TX_BUFFER_SIZE];
    char topic_buffer[128];
    sprintf(topic_buffer, "devices/%s/command", DEVICE_ID);

    // Note: The topic must be enclosed in quotes
    sprintf(cmd_buffer, "AT+MQTTSUB=0,\"%s\",0\r\n", topic_buffer);

    if (send_at_command(cmd_buffer, "OK", 3000)) {
        printf("Successfully subscribed to topic: %s\r\n", topic_buffer);
    } else {
        printf("Error: Failed to subscribe to topic.\r\n");
    }
}

/**
 * @brief Sends an AT command to the ESP8266 and waits for a response.
 */
bool send_at_command(const char* cmd, const char* expected_response, uint32_t timeout) {
    clear_rx_buffer();
    HAL_UART_Transmit(&huart2, (uint8_t*)cmd, strlen(cmd), HAL_MAX_DELAY);

    uint32_t start_time = HAL_GetTick();
    while ((HAL_GetTick() - start_time) < timeout) {
        if (strstr((char*)uart_rx_buffer, expected_response) != NULL) {
            return true;
        }
    }
    // For debugging, print what was actually received
    printf("Timeout waiting for '%s'. Received: %s\r\n", expected_response, (char*)uart_rx_buffer);
    return false;
}

/**
 * @brief Clears the UART receive buffer.
 */
void clear_rx_buffer(void) {
    memset(uart_rx_buffer, 0, UART_RX_BUFFER_SIZE);
    uart_rx_write_pos = 0;
}

/**
 * @brief Parses the incoming MQTT message and acts on it.
 * @param msg The full message string from the ESP8266.
 */
void parse_mqtt_message(const char* msg) {
    // ESP8266 MQTT messages typically look like: +MQTTRCVPKT: 0,0,"topic",length,{"json_payload"}
    // We are interested in the JSON part.
    const char* json_start = strchr(msg, '{');
    if (json_start == NULL) {
        return; // Not a valid message for us
    }

    printf("Parsing JSON: %s\r\n", json_start);

    // Simple manual parsing for "set_led" command
    // A real application should use a dedicated JSON parsing library (e.g., cJSON)
    // for more robust parsing.
    if (strstr(json_start, "\"command\":\"set_led\"")) {
        if (strstr(json_start, "\"value\":\"on\"")) {
            printf("Action: Turning LED ON\r\n");
            // Assuming PA5 is the LED pin
            HAL_GPIO_WritePin(GPIOA, GPIO_PIN_5, GPIO_PIN_SET);
        } else if (strstr(json_start, "\"value\":\"off\"")) {
            printf("Action: Turning LED OFF\r\n");
            HAL_GPIO_WritePin(GPIOA, GPIO_PIN_5, GPIO_PIN_RESET);
        }
    }
}

/* ============================================================================
 * STM32 HAL CALLBACKS
 * ============================================================================ */

/**
  * @brief  Rx Transfer completed callback.
  * @param  huart: UART handle
  * @retval None
  */
void HAL_UART_RxCpltCallback(UART_HandleTypeDef *huart)
{
    if (huart->Instance == USART2) // ESP8266 UART
    {
        // Check if there is space in the buffer
        if (uart_rx_write_pos < (UART_RX_BUFFER_SIZE - 1))
        {
            // The next byte will be written to the next position.
            // We already received one byte at uart_rx_buffer[uart_rx_write_pos].
            uart_rx_write_pos++;
        }

        // If we receive a newline, it might be the end of a command from ESP8266
        if (uart_rx_buffer[uart_rx_write_pos - 1] == '\n') {
            command_received = true;
            // We have a full line, let's try to parse it
            parse_mqtt_message((const char*)uart_rx_buffer);
            // We clear the buffer for the next message.
            // A more robust implementation might use a circular buffer.
            clear_rx_buffer();
        }

        // Restart the interrupt to receive the next byte
        HAL_UART_Receive_IT(&huart2, &uart_rx_buffer[uart_rx_write_pos], 1);
    }
}


/* ============================================================================
 * AUTOGENERATED STM32 INITIALIZATION CODE (from STM32CubeIDE)
 * You would typically generate this with the IDE's graphical tool.
 * ============================================================================ */
void SystemClock_Config(void) {
  // ... This function should be configured using STM32CubeIDE ...
  // This is a placeholder. A real implementation is highly dependent on the specific STM32 chip.
}

static void MX_GPIO_Init(void) {
  GPIO_InitTypeDef GPIO_InitStruct = {0};

  /* GPIO Ports Clock Enable */
  __HAL_RCC_GPIOA_CLK_ENABLE();

  /*Configure GPIO pin Output Level */
  HAL_GPIO_WritePin(GPIOA, GPIO_PIN_5, GPIO_PIN_RESET); // Default LED to OFF

  /*Configure GPIO pin : PA5 (LED Pin) */
  GPIO_InitStruct.Pin = GPIO_PIN_5;
  GPIO_InitStruct.Mode = GPIO_MODE_OUTPUT_PP;
  GPIO_InitStruct.Pull = GPIO_NOPULL;
  GPIO_InitStruct.Speed = GPIO_SPEED_FREQ_LOW;
  HAL_GPIO_Init(GPIOA, &GPIO_InitStruct);
}

static void MX_USART1_UART_Init(void) {
  // ... Configured for debug printf ...
  // Baud rate: 115200, 8-N-1
}

static void MX_USART2_UART_Init(void) {
  // ... Configured for ESP8266 ...
  // Baud rate: 115200 (or whatever your ESP8266 is configured to)
}

void Error_Handler(void) {
  __disable_irq();
  while (1) {}
}

#ifdef  USE_FULL_ASSERT
void assert_failed(uint8_t *file, uint32_t line) {
  // User can add his own implementation to report the file name and line number
}
#endif
