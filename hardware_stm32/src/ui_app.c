/**
 * @file ui_app.c
 * @brief LVGL-based UI Implementation for STM32 Multi-tool
 */

#include "lvgl.h"

// External references (Sensor/NFC data)
extern float g_current_temp;
extern float g_current_hum;
extern char g_nfc_last_uid[16];

// UI Objects
static lv_obj_t * main_tile_view;
static lv_obj_t * home_page;
static lv_obj_t * nfc_page;
static lv_obj_t * ir_page;
static lv_obj_t * info_page;
static lv_obj_t * status_label;
static lv_obj_t * nfc_data_label;

/**
 * @brief Create a Card style object (Apple/Glassmorphism style)
 */
lv_obj_t * create_glass_card(lv_obj_t * parent) {
    lv_obj_t * card = lv_obj_create(parent);
    lv_obj_set_size(card, lv_pct(90), 100);
    lv_obj_set_style_bg_color(card, lv_palette_main(LV_PALETTE_GREY), 0);
    lv_obj_set_style_bg_opa(card, 30, 0); // Low opacity for glass effect
    lv_obj_set_style_border_color(card, lv_palette_main(LV_PALETTE_GREY), 0);
    lv_obj_set_style_border_opa(card, 50, 0);
    lv_obj_set_style_radius(card, 15, 0);
    return card;
}

/**
 * @brief Initialize Home Page (Sensors & Clock)
 */
void ui_home_init(lv_obj_t * parent) {
    lv_obj_t * cont = lv_obj_create(parent);
    lv_obj_set_size(cont, LV_HOR_RES, LV_VER_RES);

    lv_obj_t * clock = lv_label_create(cont);
    lv_label_set_text(clock, "12:00");
    lv_obj_set_style_text_font(clock, &lv_font_montserrat_48, 0);
    lv_obj_align(clock, LV_ALIGN_TOP_MID, 0, 40);

    lv_obj_t * sensor_card = create_glass_card(cont);
    lv_obj_align(sensor_card, LV_ALIGN_CENTER, 0, 40);

    status_label = lv_label_create(sensor_card);
    lv_label_set_text(status_label, "Temp: --C | Hum: --%");
    lv_obj_align(status_label, LV_ALIGN_CENTER, 0, 0);
}

/**
 * @brief Initialize NFC Page
 */
void ui_nfc_init(lv_obj_t * parent) {
    lv_obj_t * cont = lv_obj_create(parent);
    lv_obj_set_size(cont, LV_HOR_RES, LV_VER_RES);

    lv_obj_t * title = lv_label_create(cont);
    lv_label_set_text(title, "NFC Scanner");
    lv_obj_set_style_text_font(title, &lv_font_montserrat_24, 0);
    lv_obj_align(title, LV_ALIGN_TOP_MID, 0, 20);

    lv_obj_t * btn = lv_btn_create(cont);
    lv_obj_set_size(btn, 120, 50);
    lv_obj_align(btn, LV_ALIGN_CENTER, 0, 0);
    lv_obj_t * btn_label = lv_label_create(btn);
    lv_label_set_text(btn_label, "READ TAG");

    nfc_data_label = lv_label_create(cont);
    lv_label_set_text(nfc_data_label, "No Tag Scanned");
    lv_obj_align(nfc_data_label, LV_ALIGN_CENTER, 0, 60);
}

/**
 * @brief Initialize Hardware Info Page
 */
void ui_info_init(lv_obj_t * parent) {
    lv_obj_t * cont = lv_obj_create(parent);
    lv_obj_set_size(cont, LV_HOR_RES, LV_VER_RES);

    lv_obj_t * title = lv_label_create(cont);
    lv_label_set_text(title, "Hardware Info");
    lv_obj_align(title, LV_ALIGN_TOP_MID, 0, 20);

    lv_obj_t * info = lv_label_create(cont);
    lv_label_set_text(info, "MCU: STM32F411\n"
                            "RTOS: FreeRTOS\n"
                            "UI: LVGL v8.x\n"
                            "NFC: PN532\n"
                            "IR: VS1838B");
    lv_obj_set_style_text_align(info, LV_TEXT_ALIGN_CENTER, 0);
    lv_obj_align(info, LV_ALIGN_CENTER, 0, 20);
}

/**
 * @brief Main UI Setup with Sliding Tile View
 */
void ui_init(void) {
    // Create Tile View for horizontal sliding (MP4 Style)
    main_tile_view = lv_tileview_create(lv_scr_act());
    lv_obj_set_style_bg_color(main_tile_view, lv_color_hex(0x000000), 0);

    // Add Tiles (Home, NFC, IR)
    home_page = lv_tileview_add_tile(main_tile_view, 0, 0, LV_DIR_HOR);
    nfc_page  = lv_tileview_add_tile(main_tile_view, 1, 0, LV_DIR_HOR);
    ir_page   = lv_tileview_add_tile(main_tile_view, 2, 0, LV_DIR_HOR);
    info_page = lv_tileview_add_tile(main_tile_view, 3, 0, LV_DIR_HOR);

    ui_home_init(home_page);
    ui_nfc_init(nfc_page);
    ui_info_init(info_page);
    // ui_ir_init(ir_page);
}

/**
 * @brief Update UI with latest data
 */
void ui_update_data(float temp, float hum, const char* nfc_uid) {
    if (status_label) {
        lv_label_set_text_fmt(status_label, "Temp: %.1fC | Hum: %.1f%%", temp, hum);
    }
    if (nfc_data_label && nfc_uid) {
        lv_label_set_text_fmt(nfc_data_label, "UID: %s", nfc_uid);
    }
}
