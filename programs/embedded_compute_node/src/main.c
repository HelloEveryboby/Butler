#include <stdio.h>
#include "buce_embedded.h"

/*
 * 推荐方案：在高性能 Edge 协同算力节点中使用 RTOS
 * ------------------------------------------------
 * 理由：
 * 1. 任务隔离：可以将“通讯任务(Comm Task)”与“高强度计算任务(Compute Task)”分离。
 * 2. 响应性：确保在进行极致算力榨取时，Edge 节点仍能即时响应来自 Butler PC 端的指令。
 * 3. 资源调度：RTOS 的优先级机制能保证数据链路的稳定性。
 */

// #include "FreeRTOS.h"
// #include "task.h"

// 高性能计算任务
void StartComputeTask(void *argument) {
    uint32_t in[16] = {0}, out[16];
    while(1) {
        // 执行极致算力榨取
        buce_mcu_crypto(out, in);
        in[0]++;
    }
}

// 实时通讯任务
void StartCommTask(void *argument) {
    while(1) {
        // 接收来自 Butler 指控中心的数据包
    }
}

int main() {
    // 硬件抽象层初始化
    printf("BUCE Universal Edge Node Logic Ready\n");

    /* 如果使用 RTOS，请取消以下任务创建注释 */
    // xTaskCreate(StartCommTask, "Comm", 128, NULL, 5, NULL);
    // xTaskCreate(StartComputeTask, "Compute", 256, NULL, 2, NULL);
    // vTaskStartScheduler();

    // 裸机模式
    while (1) {
        int iter = buce_mcu_mandelbrot(0.1, 0.2, 100);
        (void)iter;
    }
    return 0;
}
