#include <stdio.h>
#include "buce_embedded.h"

// This is a simulation of the STM32 main loop
int main() {
    printf("BUCE STM32 Node Started\n");

    uint32_t in[16] = {0}, out[16];
    in[0] = 0xdeadbeef;

    // Demonstrate crypto performance
    buce_mcu_crypto(out, in);
    printf("Crypto Test: out[0] = %08x\n", out[0]);

    // Demonstrate mandelbrot
    int iter = buce_mcu_mandelbrot(0.1, 0.2, 100);
    printf("Mandelbrot Test: %d iterations\n", iter);

    return 0;
}
