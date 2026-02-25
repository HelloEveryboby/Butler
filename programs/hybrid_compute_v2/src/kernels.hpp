#ifndef BUCE_KERNELS_HPP
#define BUCE_KERNELS_HPP

#include <vector>
#include <cstdint>
#include <cmath>
#include <string>

#ifdef __AVX2__
#include <immintrin.h>
#endif

namespace buce {

class Kernels {
public:
    // 1. High-speed Vector Addition (as a SIMD demo)
    static void vector_add(const float* a, const float* b, float* c, size_t size) {
        size_t i = 0;
#ifdef __AVX2__
        for (; i + 7 < size; i += 8) {
            __m256 va = _mm256_loadu_ps(a + i);
            __m256 vb = _mm256_loadu_ps(b + i);
            __m256 vr = _mm256_add_ps(va, vb);
            _mm256_storeu_ps(c + i, vr);
        }
#endif
        for (; i < size; ++i) {
            c[i] = a[i] + b[i];
        }
    }

    // 2. Optimized Mandelbrot (Stress Test)
    static int mandelbrot(float real, float imag, int max_iter) {
        float z_real = real;
        float z_imag = imag;
        for (int i = 0; i < max_iter; ++i) {
            float r2 = z_real * z_real;
            float i2 = z_imag * z_imag;
            if (r2 + i2 > 4.0f) return i;
            z_imag = 2.0f * z_real * z_imag + imag;
            z_real = r2 - i2 + real;
        }
        return max_iter;
    }

    // 3. Fast Pattern Match (for DocAccelerator) - Multi-pattern support
    struct MatchResult {
        std::string pattern;
        size_t count;
    };

    static std::vector<MatchResult> multi_match(const std::string& text, const std::vector<std::string>& patterns) {
        std::vector<MatchResult> results;
        for (const auto& p : patterns) {
            size_t count = 0;
            if (!p.empty()) {
                size_t pos = text.find(p, 0);
                while (pos != std::string::npos) {
                    count++;
                    pos = text.find(p, pos + p.length());
                }
            }
            results.push_back({p, count});
        }
        return results;
    }

    // 4. Lightweight Hash (placeholder for BUCE-Hash)
    static uint32_t simple_hash(const uint8_t* data, size_t len) {
        uint32_t hash = 0x811c9dc5;
        for (size_t i = 0; i < len; ++i) {
            hash ^= data[i];
            hash *= 0x01000193;
        }
        return hash;
    }

    // 5. ChaCha20 Quarter Round (High-speed crypto primitive)
    static void chacha20_qr(uint32_t& a, uint32_t& b, uint32_t& c, uint32_t& d) {
        a += b; d ^= a; d = (d << 16) | (d >> 16);
        c += d; b ^= c; b = (b << 12) | (b >> 20);
        a += b; d ^= a; d = (d << 8) | (d >> 24);
        c += d; b ^= c; b = (b << 7) | (b >> 25);
    }

    static void chacha20_block(uint32_t out[16], const uint32_t in[16]) {
        for (int i = 0; i < 16; ++i) out[i] = in[i];
        for (int i = 0; i < 10; ++i) {
            chacha20_qr(out[0], out[4], out[ 8], out[12]);
            chacha20_qr(out[1], out[5], out[ 9], out[13]);
            chacha20_qr(out[2], out[6], out[10], out[14]);
            chacha20_qr(out[3], out[7], out[11], out[15]);
            chacha20_qr(out[0], out[5], out[10], out[15]);
            chacha20_qr(out[1], out[6], out[11], out[12]);
            chacha20_qr(out[2], out[7], out[ 8], out[13]);
            chacha20_qr(out[3], out[4], out[ 9], out[14]);
        }
        for (int i = 0; i < 16; ++i) out[i] += in[i];
    }

    // 6. Monte Carlo Pi (Parallel Compute Demo)
    static long long monte_carlo_pi_part(long long iterations) {
        long long inside = 0;
        uint32_t seed = (uint32_t)iterations;
        for (long long i = 0; i < iterations; ++i) {
            // Fast LCG random
            seed = seed * 1664525 + 1013904223;
            float x = (float)(seed & 0xFFFF) / 65535.0f;
            seed = seed * 1664525 + 1013904223;
            float y = (float)(seed & 0xFFFF) / 65535.0f;
            if (x*x + y*y <= 1.0f) inside++;
        }
        return inside;
    }
};

} // namespace buce

#endif
