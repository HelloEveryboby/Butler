#include <stdio.h>
#include <string.h>
#include <stdlib.h>
#include "ui_engine.h"

/**
 * Butler Hybrid Command Processor
 * Dispatches commands between Local UI, Python Brain, and STM32 Hardware.
 */

#include "hcp_protocol.h"

extern int brain_call(const char* command, char* out_buffer, size_t out_size);
extern void neo_print_banner();
extern void neo_print_status(const char* task, const char* stage);
extern void neo_print_response(const char* msg);
extern void neo_print_system_info(const char* b, const char* s);
extern void neo_print_alert(const char* t, const char* m);
extern int serial_init(const char* device, int baudrate);
extern int serial_send(const char* data);
extern int serial_receive(char* buffer, size_t size);

typedef enum {
    MODE_IDLE,
    MODE_WAITING_SOURCE,
    MODE_WAITING_TARGET
} auto_mode_t;

static auto_mode_t current_auto_mode = MODE_IDLE;
static char last_uid[20] = {0};

void handle_serial_event(const char* event_json) {
    // 简单的 JSON 解析逻辑 (实际应调用 cJSON 或类似库)
    if (strstr(event_json, "tag_detected")) {
        char current_uid[20] = {0};
        char* uid_ptr = strstr(event_json, "\"uid\":\"");
        if (uid_ptr) {
            strncpy(current_uid, uid_ptr + 7, 8); // 假设 UID 长度
            current_uid[8] = '\0';
        }

        if (current_auto_mode == MODE_WAITING_SOURCE) {
            neo_print_alert("DETECTED", "Source card found! Starting full dump...");
            neo_print_status("AUTO", "Source detected, reading...");
            serial_send("{\"jsonrpc\":\"2.0\",\"method\":\"nfc_clone\",\"id\":10}\n");
            strncpy(last_uid, current_uid, sizeof(last_uid));
            current_auto_mode = MODE_WAITING_TARGET;
            neo_print_response("源卡已存入 Slot 0。请移开源卡，放入【目标卡】。");
        } else if (current_auto_mode == MODE_WAITING_TARGET) {
            if (strcmp(current_uid, last_uid) != 0) {
                neo_print_alert("DETECTED", "Target card found! Initiating hardware burn...");
                neo_print_status("AUTO", "Target detected, burning...");
                serial_send("{\"jsonrpc\":\"2.0\",\"method\":\"nfc_burn\",\"params\":{\"slot\":0},\"id\":11}\n");
                current_auto_mode = MODE_IDLE;
                neo_print_response("全自动克隆完成！");
            }
        }
    }
}

void process_user_command(const char* input) {
    char brain_res[1024];
    char serial_res[512];

    if (strcmp(input, "nfc auto") == 0) {
        current_auto_mode = MODE_WAITING_SOURCE;
        neo_print_status("AUTO", "Entering Auto-Clone Mode...");
        neo_print_response("请将【源卡】靠近读卡器。");
        return;
    }

    if (strcmp(input, "nfc scan") == 0) {
        neo_print_status("HARDWARE", "Sending command to STM32...");
        serial_send("{\"jsonrpc\":\"2.0\",\"method\":\"nfc_get_uid\",\"id\":1}\n");
        usleep(500000);
        if (serial_receive(serial_res, sizeof(serial_res)) > 0) {
            neo_print_response(serial_res);
        } else {
            neo_print_response("STM32 无响应。");
        }
    } else if (strncmp(input, "ask ", 4) == 0) {
        neo_print_status("BRAIN", "Consulting Python AI...");
        if (brain_call(input + 4, brain_res, sizeof(brain_res)) == 0) {
            neo_print_response(brain_res);
        } else {
            ui_print_error("无法连接到 Python 大脑。");
        }
    } else if (strcmp(input, "nfc clone") == 0) {
        neo_print_status("CLONE", "Initiating STM32 Clone Sequence...");
        serial_send("{\"jsonrpc\":\"2.0\",\"method\":\"nfc_clone\",\"id\":2}\n");
        neo_print_status("PROCESS", "Data streaming to external Flash...");
        usleep(2000000); // 增加等待时间以确保 STM32 完成读取和存储
        if (serial_receive(serial_res, sizeof(serial_res)) > 0) {
            neo_print_response(serial_res);
        }
    } else if (strncmp(input, "nfc burn ", 9) == 0) {
        int slot = atoi(input + 9);
        char cmd[128];
        snprintf(cmd, sizeof(cmd), "{\"jsonrpc\":\"2.0\",\"method\":\"nfc_burn\",\"params\":{\"slot\":%d},\"id\":3}\n", slot);
        neo_print_status("HARDWARE", "Burning to target card...");
        serial_send(cmd);
        usleep(2000000);
        if (serial_receive(serial_res, sizeof(serial_res)) > 0) {
            neo_print_response(serial_res);
        }
    } else {
        if (brain_call(input, brain_res, sizeof(brain_res)) == 0) {
            neo_print_response(brain_res);
        }
    }
}

int main(int argc, char** argv) {
    char input[256];
    const char* dev = (argc > 1) ? argv[1] : "/dev/ttyUSB0";

    neo_print_banner();
    neo_print_system_info("Active (Python 3.10)", "Connected (UART)");

    if (serial_init(dev, 115200) == 0) {
        printf("%s[SYSTEM] Serial stream established on %s%s\n", CLR_DIM, dev, CLR_RST);
    } else {
        printf("%s[SYSTEM] Running in Offline mode (Serial failed)%s\n", CLR_RED, CLR_RST);
    }

    // 设置非阻塞读取以支持事件监听
    int flags = fcntl(0, F_GETFL, 0);
    fcntl(0, F_SETFL, flags | O_NONBLOCK);

    while (1) {
        // 尝试接收硬件事件
        if (serial_receive(serial_res, sizeof(serial_res)) > 0) {
            handle_serial_event(serial_res);
        }

        // 尝试接收用户输入
        if (fgets(input, sizeof(input), stdin)) {
            input[strcspn(input, "\n")] = 0;
            if (strcmp(input, "exit") == 0) break;
            process_user_command(input);
            printf("\n%s━> %s", CLR_CYN, CLR_RST);
            fflush(stdout);
        }

        usleep(10000); // 避免 CPU 空转
    }

    return 0;
}
