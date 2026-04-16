/**
 * @file ui_lcd1602.c
 * @brief Lite Text-based Menu for LCD1602 (16x2 Character Display)
 */

#include <stdio.h>
#include <string.h>
#include <stdbool.h>

// Global Sensor Data (Shared with other tasks)
extern float g_current_temp;
extern float g_current_hum;
extern char g_nfc_last_uid[16];

// LCD1602 Driver Primitives (To be implemented with I2C HAL)
extern void lcd1602_clear(void);
extern void lcd1602_set_cursor(uint8_t row, uint8_t col);
extern void lcd1602_print(const char* str);

typedef enum {
    MENU_HOME,
    MENU_NFC,
    MENU_IR,
    MENU_SENSORS,
    MENU_INFO,
    MENU_MAX
} menu_state_t;

static menu_state_t current_menu = MENU_HOME;

/**
 * @brief Render the current menu state to the 16x2 screen
 */
void ui_lcd1602_render(void) {
    char line1[17] = {0};
    char line2[17] = {0};

    lcd1602_clear();

    switch (current_menu) {
        case MENU_HOME:
            snprintf(line1, 17, "Butler v2.0-Lite");
            snprintf(line2, 17, "-> NFC | IR | SN");
            break;

        case MENU_NFC:
            snprintf(line1, 17, "NFC Scanner");
            if (strcmp(g_nfc_last_uid, "None") == 0) {
                snprintf(line2, 17, "Wait for Tag...");
            } else {
                snprintf(line2, 17, "UID: %s", g_nfc_last_uid);
            }
            break;

        case MENU_IR:
            snprintf(line1, 17, "IR Controller");
            snprintf(line2, 17, "1:Learn  2:Send");
            break;

        case MENU_SENSORS:
            snprintf(line1, 17, "T: %.1fC", g_current_temp);
            snprintf(line2, 17, "H: %.1f%%", g_current_hum);
            break;

        case MENU_INFO:
            snprintf(line1, 17, "F411 | FreeRTOS");
            snprintf(line2, 17, "NFC/IR/DHT V2.0");
            break;

        default:
            break;
    }

    lcd1602_set_cursor(0, 0);
    lcd1602_print(line1);
    lcd1602_set_cursor(1, 0);
    lcd1602_print(line2);
}

/**
 * @brief Navigate the menu (triggered by button or encoder)
 */
void ui_lcd1602_next(void) {
    current_menu = (current_menu + 1) % MENU_MAX;
    ui_lcd1602_render();
}

void ui_lcd1602_back(void) {
    if (current_menu == 0) current_menu = MENU_MAX - 1;
    else current_menu--;
    ui_lcd1602_render();
}
