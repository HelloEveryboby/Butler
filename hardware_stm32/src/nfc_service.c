/**
 * @file nfc_service.c
 * @brief STM32 NFC Service - Functional Implementation for PN532
 */

#include "buce_embedded.h"

// --- PN532 Constants ---
#define PN532_COMMAND_GETFIRMWAREVERSION 0x02
#define PN532_COMMAND_SAMCONFIGURATION   0x14
#define PN532_COMMAND_INLISTPASSIVETARGET 0x4A
#define PN532_COMMAND_INDATAEXCHANGE     0x40
#define PN532_MIFARE_ISO14443A           0x00

// --- NFC Context ---
typedef struct {
    uint8_t uid[7];
    uint8_t uid_len;
    uint8_t sector_buffer[16][64]; // Buffer for Mifare Classic 1K cloning
} nfc_context_t;

static nfc_context_t nfc_ctx;

// --- Hardware Abstraction Primitives (To be linked with STM32 HAL) ---
extern void pn532_write_command(uint8_t* cmd, uint8_t len);
extern bool pn532_read_response(uint8_t* res, uint8_t len);

bool nfc_init(void) {
    uint8_t sam_cmd[] = {PN532_COMMAND_SAMCONFIGURATION, 0x01, 0x14, 0x01};
    pn532_write_command(sam_cmd, 4);
    return true;
}

bool nfc_scan_tag(void) {
    uint8_t scan_cmd[] = {PN532_COMMAND_INLISTPASSIVETARGET, 0x01, PN532_MIFARE_ISO14443A};
    uint8_t res[32];
    pn532_write_command(scan_cmd, 3);
    if (pn532_read_response(res, 32) && res[7] > 0) {
        nfc_ctx.uid_len = res[12];
        memcpy(nfc_ctx.uid, &res[13], nfc_ctx.uid_len);
        return true;
    }
    return false;
}

void nfc_auto_poll_task(void) {
    static uint8_t last_uid[10] = {0};
    static uint8_t last_len = 0;
    static uint32_t last_detection_time = 0;

    if (nfc_scan_tag()) {
        // 如果是新卡，或者已经过去了一段时间（防止抖动）
        if (nfc_ctx.uid_len != last_len || memcmp(nfc_ctx.uid, last_uid, nfc_ctx.uid_len) != 0) {
            char hex_uid[20] = {0};
            for(int i=0; i<nfc_ctx.uid_len; i++) sprintf(hex_uid + strlen(hex_uid), "%02X", nfc_ctx.uid[i]);
            printf("{\"jsonrpc\":\"2.0\",\"method\":\"tag_detected\",\"params\":{\"uid\":\"%s\",\"type\":\"ISO14443A\"}}\n", hex_uid);

            memcpy(last_uid, nfc_ctx.uid, nfc_ctx.uid_len);
            last_len = nfc_ctx.uid_len;
        }
    } else {
        // 卡片离开，清空记录以便下次能再次识别同一张卡
        last_len = 0;
    }
}

/**
 * Mifare Classic 1K Read/Write Logic
 */
bool mifare_auth(uint8_t block, uint8_t* key) {
    uint8_t auth_cmd[13] = {PN532_COMMAND_INDATAEXCHANGE, 0x01, 0x60, block}; // 0x60 is Auth A
    memcpy(&auth_cmd[4], key, 6);
    memcpy(&auth_cmd[10], nfc_ctx.uid, 4);
    pn532_write_command(auth_cmd, 13);
    uint8_t res[8];
    return pn532_read_response(res, 8) && res[7] == 0x00;
}

bool mifare_read_block(uint8_t block, uint8_t* out_data) {
    uint8_t read_cmd[] = {PN532_COMMAND_INDATAEXCHANGE, 0x01, 0x30, block};
    pn532_write_command(read_cmd, 4);
    uint8_t res[25];
    if (pn532_read_response(res, 25) && res[7] == 0x00) {
        memcpy(out_data, &res[8], 16);
        return true;
    }
    return false;
}

bool mifare_write_block(uint8_t block, uint8_t* data) {
    uint8_t write_cmd[20] = {PN532_COMMAND_INDATAEXCHANGE, 0x01, 0xA0, block};
    memcpy(&write_cmd[4], data, 16);
    pn532_write_command(write_cmd, 20);
    uint8_t res[8];
    return pn532_read_response(res, 8) && res[7] == 0x00;
}

// --- BHL RPC Handlers ---

void handle_nfc_get_uid(int id, char* out_buf, size_t out_len) {
    if (nfc_scan_tag()) {
        char hex_uid[20] = {0};
        for(int i=0; i<nfc_ctx.uid_len; i++) sprintf(hex_uid + strlen(hex_uid), "%02X", nfc_ctx.uid[i]);
        char res[64];
        snprintf(res, sizeof(res), "{\"uid\":\"%s\",\"len\":%d}", hex_uid, nfc_ctx.uid_len);
        bhl_format_response(id, res, out_buf, out_len);
    } else {
        bhl_format_error(id, -32001, "Tag not found", out_buf, out_len);
    }
}

void handle_nfc_read_sector(int id, int sector, char* out_buf, size_t out_len) {
    uint8_t key_default[] = {0xFF, 0xFF, 0xFF, 0xFF, 0xFF, 0xFF};
    uint8_t block = sector * 4;
    if (mifare_auth(block, key_default)) {
        uint8_t data[16];
        if (mifare_read_block(block, data)) {
            char hex_data[40] = {0};
            for(int i=0; i<16; i++) sprintf(hex_data + strlen(hex_data), "%02X", data[i]);
            char res[128];
            snprintf(res, sizeof(res), "{\"sector\":%d,\"data\":\"%s\"}", sector, hex_data);
            bhl_format_response(id, res, out_buf, out_len);
            return;
        }
    }
    bhl_format_error(id, -32002, "Read failed", out_buf, out_len);
}

#include "butler_storage_hal.h"

void handle_nfc_clone(int id, char* out_buf, size_t out_len) {
    // Stage 1: Reading and buffering source card (Mifare 1K)
    if (nfc_scan_tag()) {
        uint8_t full_card_data[1024];
        bool success = true;
        uint8_t key_default[] = {0xFF, 0xFF, 0xFF, 0xFF, 0xFF, 0xFF};

        for (int b = 0; b < 64; b++) {
            if (mifare_auth(b, key_default)) {
                if (!mifare_read_block(b, &full_card_data[b * 16])) {
                    success = false; break;
                }
            } else {
                success = false; break;
            }
        }

        if (success) {
            // Persist to External Storage via HAL (Default to Slot 0)
            if (butler_storage_save_to_slot(0, full_card_data, 1024)) {
                bhl_format_response(id, "{\"status\":\"cloned_to_storage\",\"slot\":0}", out_buf, out_len);
            } else {
                bhl_format_error(id, -32003, "Storage write failed", out_buf, out_len);
            }
        } else {
            bhl_format_error(id, -32002, "Card read incomplete", out_buf, out_len);
        }
    } else {
        bhl_format_error(id, -32001, "Source tag not found", out_buf, out_len);
    }
}

void handle_nfc_burn(int id, int slot, char* out_buf, size_t out_len) {
    uint8_t full_card_data[1024];
    if (butler_storage_load_from_slot(slot, full_card_data, 1024)) {
        if (nfc_scan_tag()) {
            bool success = true;
            for (int b = 0; b < 64; b++) {
                // 跳过厂商块或其他受限块的逻辑应在此处处理
                if (!mifare_write_block(b, &full_card_data[b * 16])) {
                    success = false; break;
                }
            }
            if (success) {
                bhl_format_response(id, "{\"status\":\"success\",\"msg\":\"Burned from slot\"}", out_buf, out_len);
            } else {
                bhl_format_error(id, -32004, "Write failed", out_buf, out_len);
            }
        } else {
            bhl_format_error(id, -32001, "Target tag not found", out_buf, out_len);
        }
    } else {
        bhl_format_error(id, -32005, "Slot empty", out_buf, out_len);
    }
}
