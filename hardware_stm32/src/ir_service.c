/**
 * @file ir_service.c
 * @brief STM32 InfraRed Service - Pulse Timing & PWM Implementation
 */

#include "buce_embedded.h"

#define IR_MAX_SAMPLES 100
static uint32_t ir_samples[IR_MAX_SAMPLES];
static uint16_t ir_sample_count = 0;

// --- Hardware Control (To be implemented with STM32 TIM Capture/PWM) ---
extern void hw_ir_start_capture(void);
extern void hw_ir_stop_capture(void);
extern uint32_t hw_ir_get_captured_pulse(void);
extern void hw_ir_send_pwm(uint32_t* pulses, uint16_t count);

/**
 * Logic: Learning IR signal
 */
void handle_ir_learn(int id, char* out_buf, size_t out_len) {
    hw_ir_start_capture();
    // In a real STM32 environment, the interrupt would fill ir_samples
    // This function sets the mode.
    bhl_format_response(id, "{\"status\":\"learning\",\"msg\":\"Waiting for IR signal...\"}", out_buf, out_len);
}

/**
 * Logic: Fetching learned signal
 */
void handle_ir_get_learned(int id, char* out_buf, size_t out_len) {
    char samples_str[256] = "[";
    for(int i=0; i < ir_sample_count && i < 10; i++) { // Limit for BHL buffer
        sprintf(samples_str + strlen(samples_str), "%lu%s", ir_samples[i], (i == ir_sample_count-1) ? "" : ",");
    }
    strcat(samples_str, "]");

    char res[300];
    snprintf(res, sizeof(res), "{\"count\":%d,\"samples\":%s}", ir_sample_count, samples_str);
    bhl_format_response(id, res, out_buf, out_len);
}

/**
 * Logic: Transmitting IR signal
 */
void handle_ir_transmit(int id, const char* params, char* out_buf, size_t out_len) {
    // In a full implementation, params would be parsed to get the timing array
    // Here we use the buffered samples if available
    if (ir_sample_count > 0) {
        hw_ir_send_pwm(ir_samples, ir_sample_count);
        bhl_format_response(id, "{\"status\":\"ok\",\"msg\":\"Signal transmitted\"}", out_buf, out_len);
    } else {
        bhl_format_error(id, -32003, "No signal to transmit", out_buf, out_len);
    }
}
