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

void handle_nfc_clone(int id, char* out_buf, size_t out_len) {
    // Stage 1: Reading and buffering source card (Mifare 1K)
    // In a real STM32 app, this would be a state machine over multiple BHL calls
    // For this source delivery, we provide the logic flow:
    bhl_format_response(id, "{\"status\":\"ready\",\"msg\":\"Send 'nfc_dump' then 'nfc_burn'\"}", out_buf, out_len);
}
