#ifndef BUCE_EMBEDDED_H
#define BUCE_EMBEDDED_H

#include <stdint.h>
#include <string.h>

// BHL-Lite Protocol for Embedded
typedef struct {
    char method[32];
    uint32_t id;
    float param_f;
    int32_t param_i;
} buce_request_t;

// 1. Lightweight ChaCha20 for MCU
static inline uint32_t rotl32(uint32_t x, int n) {
    return (x << n) | (x >> (32 - n));
}

#define QUARTERROUND(a, b, c, d) \
    a += b; d ^= a; d = rotl32(d, 16); \
    c += d; b ^= c; b = rotl32(b, 12); \
    a += b; d ^= a; d = rotl32(d, 8); \
    c += d; b ^= c; b = rotl32(b, 7);

void buce_mcu_crypto(uint32_t out[16], uint32_t in[16]) {
    for (int i = 0; i < 16; i++) out[i] = in[i];
    for (int i = 0; i < 10; i++) {
        QUARTERROUND(out[0], out[4], out[ 8], out[12])
        QUARTERROUND(out[1], out[5], out[ 9], out[13])
        QUARTERROUND(out[2], out[6], out[10], out[14])
        QUARTERROUND(out[3], out[7], out[11], out[15])
        QUARTERROUND(out[0], out[5], out[10], out[15])
        QUARTERROUND(out[1], out[6], out[11], out[12])
        QUARTERROUND(out[2], out[7], out[ 8], out[13])
        QUARTERROUND(out[3], out[4], out[ 9], out[14])
    }
    for (int i = 0; i < 16; i++) out[i] += in[i];
}

// 2. Mandelbrot for MCU (using Fixed point if no FPU, but here we use float as most modern STM32 have it)
int buce_mcu_mandelbrot(float real, float imag, int max_iter) {
    float z_real = real, z_imag = imag;
    for (int i = 0; i < max_iter; i++) {
        float r2 = z_real * z_real, i2 = z_imag * z_imag;
        if (r2 + i2 > 4.0f) return i;
        z_imag = 2.0f * z_real * z_imag + imag;
        z_real = r2 - i2 + real;
    }
    return max_iter;
}

// 3. Simple Serial Parser (Stub for STM32 HAL_UART_Receive)
int buce_parse_packet(const uint8_t* buffer, size_t len, buce_request_t* req) {
    // In a real STM32 app, this would be a robust parser.
    // For this project, we provide a template.
    if (len < 4) return -1;
    // Example: [MethodID:1][TaskID:4][Param:4] ...
    return 0;
}

#endif
