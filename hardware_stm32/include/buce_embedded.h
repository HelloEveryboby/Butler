/**
 * @file buce_embedded.h
 * @brief Butler Unified Compute Engine (BUCE) - Embedded BHL Protocol Stack
 * @version 1.1.0
 */

#ifndef BUCE_EMBEDDED_H
#define BUCE_EMBEDDED_H

#include <stdint.h>
#include <string.h>
#include <stdio.h>
#include <stdbool.h>
#include <ctype.h>

#define BHL_MAX_PACKET_SIZE 512
#define BHL_VERSION "2.0-embedded"

typedef enum {
    BHL_OK = 0,
    BHL_ERROR_PARSE = -1,
    BHL_ERROR_METHOD_NOT_FOUND = -2,
    BHL_ERROR_BUFFER_OVERFLOW = -3
} bhl_status_t;

typedef struct {
    char method[32];
    int id;
    char params[256];
} bhl_request_t;

/**
 * @brief Robust micro-JSON parser for embedded environments.
 * Extracts "method", "id", and "params" from a JSON-RPC 2.0 string.
 */
static const char* bhl_json_get_value(const char* json, const char* key, char* out_val, size_t max_len) {
    char search_key[64];
    snprintf(search_key, sizeof(search_key), "\"%s\"", key);
    const char* key_ptr = strstr(json, search_key);
    if (!key_ptr) return NULL;

    const char* colon_ptr = strchr(key_ptr + strlen(search_key), ':');
    if (!colon_ptr) return NULL;

    const char* val_start = colon_ptr + 1;
    while (isspace((unsigned char)*val_start)) val_start++;

    if (*val_start == '\"') {
        // String value
        val_start++;
        const char* val_end = strchr(val_start, '\"');
        if (!val_end) return NULL;
        size_t len = val_end - val_start;
        if (len >= max_len) len = max_len - 1;
        strncpy(out_val, val_start, len);
        out_val[len] = '\0';
        return val_end + 1;
    } else {
        // Numeric or boolean or object
        const char* val_end = val_start;
        while (*val_end && *val_end != ',' && *val_end != '}' && !isspace((unsigned char)*val_end)) {
            val_end++;
        }
        size_t len = val_end - val_start;
        if (len >= max_len) len = max_len - 1;
        strncpy(out_val, val_start, len);
        out_val[len] = '\0';
        return val_end;
    }
}

bhl_status_t bhl_parse_request(const char* json, bhl_request_t* req) {
    char id_str[16] = {0};
    if (!bhl_json_get_value(json, "method", req->method, sizeof(req->method))) return BHL_ERROR_PARSE;
    if (bhl_json_get_value(json, "id", id_str, sizeof(id_str))) {
        req->id = atoi(id_str);
    } else {
        req->id = 0;
    }

    // Extract params as a raw JSON string (could be array or object)
    const char* p_key = strstr(json, "\"params\"");
    if (p_key) {
        const char* colon = strchr(p_key, ':');
        if (colon) {
            const char* start = colon + 1;
            while (isspace((unsigned char)*start)) start++;
            // Simple approach: copy until matching bracket/brace or end of string
            strncpy(req->params, start, sizeof(req->params) - 1);
        }
    }

    return BHL_OK;
}

void bhl_format_response(int id, const char* result_json, char* out_buffer, size_t out_size) {
    snprintf(out_buffer, out_size, "{\"jsonrpc\":\"2.0\",\"result\":%s,\"id\":%d}\n", result_json, id);
}

void bhl_format_error(int id, int code, const char* message, char* out_buffer, size_t out_size) {
    snprintf(out_buffer, out_size, "{\"jsonrpc\":\"2.0\",\"error\":{\"code\":%d,\"message\":\"%s\"},\"id\":%d}\n", code, message, id);
}

#endif
