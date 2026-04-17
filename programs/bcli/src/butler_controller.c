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
extern int serial_init(const char* device, int baudrate);
extern int serial_send(const char* data);
extern int serial_receive(char* buffer, size_t size);

void process_user_command(const char* input) {
    char brain_res[1024];
    char serial_res[512];

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
        // 实际克隆过程较长，此处采用流式反馈
        neo_print_status("PROCESS", "Data streaming to external Flash...");
        usleep(1000000);
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
    if (serial_init(dev, 115200) == 0) {
        printf("%s[SYSTEM] Connected to STM32 on %s%s\n", CLR_DIM, dev, CLR_RST);
    } else {
        printf("%s[SYSTEM] Running in Offline mode (Serial failed)%s\n", CLR_RED, CLR_RST);
    }

    while (1) {
        printf("\n%s━> %s", CLR_CYN, CLR_RST);
        if (!fgets(input, sizeof(input), stdin)) break;
        input[strcspn(input, "\n")] = 0;

        if (strcmp(input, "exit") == 0) break;
        process_user_command(input);
    }

    return 0;
}
