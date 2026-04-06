#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <unistd.h>
#include <time.h>
#include "ui_engine.h"
#include "bridge.h"
#include "hcp_protocol.h"

void handle_hcp_command(const char* input) {
    if (strstr(input, "led on")) {
        ui_print_task("Hardware Control: LED ON");
        hcp_print_packet(TYPE_CTRL, DEV_LED, 0x01, 0x0000FF00);
        ui_print_success("LED control packet generated.");
    } else if (strstr(input, "motor start")) {
        ui_print_task("Hardware Control: Motor Start");
        hcp_print_packet(TYPE_CTRL, DEV_MOTOR, 0x01, 0x00000064);
        ui_print_success("Motor control packet generated.");
    } else if (strstr(input, "nfc query")) {
        ui_print_task("Hardware Control: NFC Query");
        hcp_print_packet(TYPE_QUERY, DEV_NFC, 0x00, 0x00000000);
        ui_print_success("NFC query packet generated.");
    } else if (strstr(input, "lock")) {
        ui_print_task("Hardware Control: Emergency Lock");
        hcp_print_packet(TYPE_ALARM, DEV_SYSTEM, 0x00, 0xDEADBEEF);
        ui_print_success("System lock packet generated.");
    } else {
        ui_print_error("Unknown hardware command.");
    }
}

void handle_input(const char* input) {
    if (strlen(input) == 0) return;

    if (strcmp(input, "exit") == 0 || strcmp(input, "quit") == 0) {
        printf("Goodbye!\n");
        exit(0);
    }

    if (strncmp(input, "hw ", 3) == 0) {
        handle_hcp_command(input + 3);
        return;
    }

    bridge_send_query(input);

    bridge_message_t* msg;
    int step = 0;
    char current_thinking_msg[512] = "Thinking";

    while (bridge_is_active()) {
        msg = bridge_receive_next_nonblocking();
        if (msg) {
            if (msg->type) {
                if (strcmp(msg->type, "thought") == 0) {
                    if (msg->content) strncpy(current_thinking_msg, msg->content, sizeof(current_thinking_msg) - 1);
                } else if (strcmp(msg->type, "tool") == 0) {
                    ui_clear_line();
                    ui_print_tool_call(msg->content ? msg->content : "Unknown", msg->extra ? msg->extra : "none");
                } else if (strcmp(msg->type, "code") == 0) {
                    ui_clear_line();
                    ui_print_code_block(msg->extra ? msg->extra : "code", msg->content ? msg->content : "");
                } else if (strcmp(msg->type, "shell") == 0) {
                    ui_clear_line();
                    ui_print_shell_output(msg->content ? msg->content : "");
                } else if (strcmp(msg->type, "text") == 0) {
                    ui_clear_line();
                    ui_print_ai_message(msg->content ? msg->content : "");
                } else if (strcmp(msg->type, "error") == 0) {
                    ui_clear_line();
                    ui_print_error(msg->content ? msg->content : "An error occurred");
                }
            }

            if (msg->type) free(msg->type);
            if (msg->content) free(msg->content);
            if (msg->extra) free(msg->extra);
            free(msg);
        } else {
            ui_print_thinking(current_thinking_msg, step++);
            usleep(100000);
        }
    }

    // Process any remaining messages that might have been sent right before closing
    while ((msg = bridge_receive_next_nonblocking()) != NULL) {
         if (msg->type) {
                if (strcmp(msg->type, "thought") == 0) {
                    // ignore final thoughts
                } else if (strcmp(msg->type, "tool") == 0) {
                    ui_clear_line();
                    ui_print_tool_call(msg->content ? msg->content : "Unknown", msg->extra ? msg->extra : "none");
                } else if (strcmp(msg->type, "code") == 0) {
                    ui_clear_line();
                    ui_print_code_block(msg->extra ? msg->extra : "code", msg->content ? msg->content : "");
                } else if (strcmp(msg->type, "shell") == 0) {
                    ui_clear_line();
                    ui_print_shell_output(msg->content ? msg->content : "");
                } else if (strcmp(msg->type, "text") == 0) {
                    ui_clear_line();
                    ui_print_ai_message(msg->content ? msg->content : "");
                } else if (strcmp(msg->type, "error") == 0) {
                    ui_clear_line();
                    ui_print_error(msg->content ? msg->content : "An error occurred");
                }
            }
            if (msg->type) free(msg->type);
            if (msg->content) free(msg->content);
            if (msg->extra) free(msg->extra);
            free(msg);
    }

    ui_clear_line();
}

int main() {
    char input[1024];

    ui_print_banner();
    printf("%s (Tip: Use 'hw <cmd>' for STM32 hardware control)%s\n", CLR_DIM, CLR_RST);

    while (1) {
        printf("%s%s╭─ %s%suser%s\n", CLR_BLD, CLR_GRN, CLR_RST, CLR_BLD, CLR_RST);
        printf("%s%s╰─> %s", CLR_BLD, CLR_GRN, CLR_RST);
        fflush(stdout);

        if (fgets(input, sizeof(input), stdin) == NULL) break;

        input[strcspn(input, "\n")] = 0;

        handle_input(input);
        printf("\n");
    }

    return 0;
}
