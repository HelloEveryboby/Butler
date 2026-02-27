/**
 * @file main.c
 * @brief STM32 Main Node - BHL Command Dispatcher
 */

#include "buce_embedded.h"

// External service handlers
extern void handle_nfc_get_uid(int id, char* out_buf, size_t out_len);
extern void handle_nfc_read_sector(int id, int sector, char* out_buf, size_t out_len);
extern void handle_ir_learn(int id, char* out_buf, size_t out_len);
extern void handle_ir_transmit(int id, const char* params, char* out_buf, size_t out_len);
extern bool nfc_init(void);

char rx_buffer[BHL_MAX_PACKET_SIZE];
char tx_buffer[BHL_MAX_PACKET_SIZE];

// Mock Hardware Communication for PN532 (To be replaced by HAL I2C/UART)
void pn532_write_command(uint8_t* cmd, uint8_t len) { /* Implementation-specific */ }
bool pn532_read_response(uint8_t* res, uint8_t len) { return false; }

void process_command(const char* cmd) {
    bhl_request_t req;
    if (bhl_parse_request(cmd, &req) == BHL_OK) {
        if (strcmp(req.method, "nfc_get_uid") == 0) {
            handle_nfc_get_uid(req.id, tx_buffer, sizeof(tx_buffer));
        } else if (strcmp(req.method, "nfc_read_sector") == 0) {
            int sector = 0;
            char sector_str[8] = {0};
            if (bhl_json_get_value(req.params, "sector", sector_str, 8)) {
                sector = atoi(sector_str);
            }
            handle_nfc_read_sector(req.id, sector, tx_buffer, sizeof(tx_buffer));
        } else if (strcmp(req.method, "ir_learn") == 0) {
            handle_ir_learn(req.id, tx_buffer, sizeof(tx_buffer));
        } else if (strcmp(req.method, "ir_transmit") == 0) {
            handle_ir_transmit(req.id, req.params, tx_buffer, sizeof(tx_buffer));
        } else if (strcmp(req.method, "ping") == 0) {
            bhl_format_response(req.id, "{\"status\":\"pong\"}", tx_buffer, sizeof(tx_buffer));
        } else {
            bhl_format_error(req.id, -32601, "Method not found", tx_buffer, sizeof(tx_buffer));
        }
        // Send response via UART
        printf("%s", tx_buffer);
    }
}

int main(void) {
    // Hardware initialization
    nfc_init();

    // Boot notification
    printf("{\"jsonrpc\":\"2.0\",\"method\":\"node_ready\",\"params\":{\"type\":\"STM32_NFC_IR\",\"version\":\"" BHL_VERSION "\"}}\n");

    while (1) {
        // Main Loop: Poll UART
        if (fgets(rx_buffer, sizeof(rx_buffer), stdin)) {
            process_command(rx_buffer);
        }
    }
    return 0;
}
