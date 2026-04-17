/**
 * @file butler_core.h
 * @brief Butler Embedded Core (BEC) - BitBuffer & Utilities
 * A lightweight, high-performance bit-level manipulation library for STM32.
 */

#ifndef BUTLER_CORE_H
#define BUTLER_CORE_H

#include <stdint.h>
#include <stdbool.h>
#include <string.h>

typedef struct {
    uint8_t* data;
    size_t size_bits;
    size_t capacity_bits;
} butler_bit_buffer_t;

// BitBuffer API
static inline void butler_bit_set(uint8_t* buf, size_t pos, bool val) {
    if (val) buf[pos >> 3] |= (1 << (7 - (pos & 0x07)));
    else buf[pos >> 3] &= ~(1 << (7 - (pos & 0x07)));
}

static inline bool butler_bit_get(const uint8_t* buf, size_t pos) {
    return (buf[pos >> 3] >> (7 - (pos & 0x07))) & 0x01;
}

// 仿 Flipper 风格的高层位读写封装
static inline void butler_bit_buffer_write_byte(butler_bit_buffer_t* buf, uint8_t byte) {
    if (buf->size_bits + 8 <= buf->capacity_bits) {
        buf->data[buf->size_bits >> 3] = byte;
        buf->size_bits += 8;
    }
}

#endif
