/*
 * Butler Unified Compute Engine (BUCE) - Universal Edge Node Firmware Header
 * Version: 2.1 (PC & Embedded Hybrid Support)
 * --------------------------------------------------------------------------
 * This header provides a unified interface for hardware interaction across
 * PC (via OS syscalls) and Embedded Development Boards (via direct HAL).
 */

#ifndef BUCE_EMBEDDED_H
#define BUCE_EMBEDDED_H

#include <stdio.h>
#include <string.h>

#ifdef __linux__
    #define BUCE_PLATFORM_PC
#elif defined(_WIN32)
    #define BUCE_PLATFORM_PC
#else
    #define BUCE_PLATFORM_EMBEDDED
#endif

// BHL Protocol Primitive: JSON Response
static void buce_send_result(const char* id, const char* result_json) {
    printf("{\"jsonrpc\":\"2.0\",\"result\":%s,\"id\":\"%s\"}\n", result_json, id);
    fflush(stdout);
}

// BHL Protocol Primitive: JSON Error
static void buce_send_error(const char* id, int code, const char* message) {
    printf("{\"jsonrpc\":\"2.0\",\"error\":{\"code\":%d,\"message\":\"%s\"},\"id\":\"%s\"}\n", code, message, id);
    fflush(stdout);
}

// Hardware Abstraction Layer (HAL) Interfaces
// These must be implemented per-platform

#ifdef BUCE_PLATFORM_PC
#include <stdlib.h>
static int buce_hal_wifi_scan(char* buffer, int max_len) {
    FILE *fp = popen("nmcli -t -f SSID,SIGNAL dev wifi 2>/dev/null", "r");
    if (!fp) return -1;
    int len = fread(buffer, 1, max_len - 1, fp);
    buffer[len] = '\0';
    pclose(fp);
    return 0;
}

static int buce_hal_disk_status(char* buffer, int max_len) {
    FILE *fp = popen("df -h / --output=pcent | tail -n 1", "r");
    if (!fp) return -1;
    int len = fread(buffer, 1, max_len - 1, fp);
    buffer[len] = '\0';
    pclose(fp);
    return 0;
}
#else
// Embedded Implementation (Mock/Templates for MCU)
static int buce_hal_wifi_scan(char* buffer, int max_len) {
    // To be replaced with ESP_AT_COMMAND or direct WiFi.scanNetworks()
    strncpy(buffer, "Embedded-WiFi-1:85", max_len);
    return 0;
}

static int buce_hal_disk_status(char* buffer, int max_len) {
    // To be replaced with SD.cardSize() or Flash storage calls
    strncpy(buffer, "SD-Card: OK", max_len);
    return 0;
}
#endif

#endif // BUCE_EMBEDDED_H
