#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <unistd.h>
#include <time.h>
#include "ui_engine.h"
#include "bridge.h"
#include "hcp_protocol.h"

/**
 * Butler REPL - 主交互循环
 * 负责处理用户输入、调度指令以及通过 Bridge 与 Python 后端交互
 */

// 处理 STM32 硬件控制指令 (HCP 协议)
void handle_hcp_command(const char* input) {
    if (strstr(input, "led on")) {
        ui_print_task("硬件控制: 开启 LED");
        hcp_print_packet(TYPE_CTRL, DEV_LED, 0x01, 0x0000FF00);
        ui_print_success("LED 控制数据包已生成。");
    } else if (strstr(input, "motor start")) {
        ui_print_task("硬件控制: 启动电机");
        hcp_print_packet(TYPE_CTRL, DEV_MOTOR, 0x01, 0x00000064);
        ui_print_success("电机控制数据包已生成。");
    } else if (strstr(input, "nfc query")) {
        ui_print_task("硬件控制: 查询 NFC");
        hcp_print_packet(TYPE_QUERY, DEV_NFC, 0x00, 0x00000000);
        ui_print_success("NFC 查询数据包已生成。");
    } else if (strstr(input, "lock")) {
        ui_print_task("硬件控制: 紧急锁定系统");
        hcp_print_packet(TYPE_ALARM, DEV_SYSTEM, 0x00, 0xDEADBEEF);
        ui_print_success("系统锁定数据包已生成。");
    } else {
        ui_print_error("未知的硬件指令。");
    }
}

// 处理用户输入的通用函数
void handle_input(const char* input) {
    if (strlen(input) == 0) return;

    // 退出判断
    if (strcmp(input, "exit") == 0 || strcmp(input, "quit") == 0 || strcmp(input, "退出") == 0) {
        printf("再见！\n");
        exit(0);
    }

    // 硬件控制前缀判断
    if (strncmp(input, "hw ", 3) == 0) {
        handle_hcp_command(input + 3);
        return;
    }

    // 通过 Bridge 向 Python 发送查询
    bridge_send_query(input);

    if (strcmp(input, "/voice") == 0) {
        ui_print_voice_status(1);
    }

    bridge_message_t* msg;
    int step = 0;
    char current_thinking_msg[512] = "正在思考";

    // 循环监听 Python 后端的消息，直到进程结束
    while (bridge_is_active()) {
        msg = bridge_receive_next_nonblocking();
        if (msg) {
            if (msg->type) {
                // 根据消息类型调用不同的 UI 渲染函数
                if (strcmp(msg->type, "thought") == 0) {
                    if (msg->content) strncpy(current_thinking_msg, msg->content, sizeof(current_thinking_msg) - 1);
                } else if (strcmp(msg->type, "tool") == 0) {
                    ui_clear_line();
                    ui_print_tool_call(msg->content ? msg->content : "未知工具", msg->extra ? msg->extra : "无参数");
                } else if (strcmp(msg->type, "code") == 0) {
                    ui_clear_line();
                    ui_print_code_block(msg->extra ? msg->extra : "代码", msg->content ? msg->content : "");
                } else if (strcmp(msg->type, "shell") == 0) {
                    ui_clear_line();
                    ui_print_shell_output(msg->content ? msg->content : "");
                } else if (strcmp(msg->type, "text") == 0) {
                    ui_clear_line();
                    ui_print_ai_message(msg->content ? msg->content : "");
                } else if (strcmp(msg->type, "error") == 0) {
                    ui_clear_line();
                    ui_print_error(msg->content ? msg->content : "发生错误");
                } else if (strcmp(msg->type, "file") == 0) {
                    ui_clear_line();
                    ui_print_file_op(msg->content ? msg->content : "操作", msg->extra ? msg->extra : "路径");
                } else if (strcmp(msg->type, "voice_status") == 0) {
                    ui_clear_line();
                    ui_print_voice_status(strcmp(msg->content, "true") == 0);
                } else if (strcmp(msg->type, "memo_card") == 0) {
                    ui_clear_line();
                    ui_print_memo_card(msg->content ? msg->content : "", msg->extra ? msg->extra : "", "刚刚");
                }
            }

            // 释放消息内存
            if (msg->type) free(msg->type);
            if (msg->content) free(msg->content);
            if (msg->extra) free(msg->extra);
            free(msg);
        } else {
            // 没有消息时更新旋转动画
            ui_print_thinking(current_thinking_msg, step++);
            usleep(100000);
        }
    }

    // 处理 Python 退出前最后留下的消息
    while ((msg = bridge_receive_next_nonblocking()) != NULL) {
         if (msg->type) {
                if (strcmp(msg->type, "tool") == 0) {
                    ui_clear_line();
                    ui_print_tool_call(msg->content ? msg->content : "未知工具", msg->extra ? msg->extra : "无参数");
                } else if (strcmp(msg->type, "code") == 0) {
                    ui_clear_line();
                    ui_print_code_block(msg->extra ? msg->extra : "代码", msg->content ? msg->content : "");
                } else if (strcmp(msg->type, "shell") == 0) {
                    ui_clear_line();
                    ui_print_shell_output(msg->content ? msg->content : "");
                } else if (strcmp(msg->type, "text") == 0) {
                    ui_clear_line();
                    ui_print_ai_message(msg->content ? msg->content : "");
                } else if (strcmp(msg->type, "error") == 0) {
                    ui_clear_line();
                    ui_print_error(msg->content ? msg->content : "发生错误");
                } else if (strcmp(msg->type, "file") == 0) {
                    ui_clear_line();
                    ui_print_file_op(msg->content ? msg->content : "操作", msg->extra ? msg->extra : "路径");
                } else if (strcmp(msg->type, "voice_status") == 0) {
                    ui_clear_line();
                    ui_print_voice_status(strcmp(msg->content, "true") == 0);
                } else if (strcmp(msg->type, "memo_card") == 0) {
                    ui_clear_line();
                    ui_print_memo_card(msg->content ? msg->content : "", msg->extra ? msg->extra : "", "刚刚");
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
    printf("%s (提示: 使用 'hw <指令>' 进行 STM32 硬件控制)%s\n", CLR_DIM, CLR_RST);

    // 主输入循环
    while (1) {
        printf("%s%s╭─ %s%s用户%s\n", CLR_BLD, CLR_GRN, CLR_RST, CLR_BLD, CLR_RST);
        printf("%s%s╰─> %s", CLR_BLD, CLR_GRN, CLR_RST);
        fflush(stdout);

        if (fgets(input, sizeof(input), stdin) == NULL) break;

        // 移除换行符
        input[strcspn(input, "\n")] = 0;

        handle_input(input);
        printf("\n");
    }

    return 0;
}
