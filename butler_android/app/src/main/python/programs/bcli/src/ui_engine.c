#include "ui_engine.h"
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <unistd.h>

/**
 * UI 引擎实现 - 负责所有终端渲染逻辑
 */

#define BANNER_ART \
"  ____       _   _             \n" \
" | __ ) _   | |_| | ___ _ __   \n" \
" |  _ \\| | | | __| |/ _ \\ '__|  \n" \
" | |_) | |_| | |_| |  __/ |     \n" \
" |____/ \\__,_|\\__|_|\\___|_|     \n"

// 打印启动横幅
void ui_print_banner() {
    printf("%s%s%s%s", CLR_CYN, CLR_BLD, BANNER_ART, CLR_RST);
    printf("%s Butler AI 助手 - 命令行版 (兼容 STM32)\n", CLR_DIM);
    printf(" 界面设计参考 Claude Code | 由 Jarvis 引擎驱动%s\n\n", CLR_RST);
}

// 打印“思考中”动画
void ui_print_thinking(const char* message, int step) {
    const char* spinners[] = {"⠋", "⠙", "⠹", "⠸", "⠼", "⠴", "⠦", "⠧", "⠇", "⠏"};
    int num_spinners = sizeof(spinners) / sizeof(spinners[0]);

    printf("\r%s%s%s %s... ", CLR_YLW, spinners[step % num_spinners], CLR_RST, message);
    fflush(stdout);
}

// 清除当前行
void ui_clear_line() {
    printf("\r\x1b[K");
    fflush(stdout);
}

// 打印任务开始标识
void ui_print_task(const char* task_name) {
    printf("\n%s%s▶ 正在执行任务: %s%s\n", CLR_BLD, CLR_MAG, task_name, CLR_RST);
}

// 打印工具调用信息
void ui_print_tool_call(const char* tool_name, const char* args) {
    printf("%s  🔧 工具调用: %s%s%s %s(%s)%s\n", CLR_GRN, CLR_BLD, tool_name, CLR_RST, CLR_DIM, args, CLR_RST);
}

// 打印 AI 的消息
void ui_print_ai_message(const char* message) {
    printf("\n%s%sButler > %s%s\n", CLR_BLD, CLR_BLU, CLR_RST, message);
}

// 打印错误信息
void ui_print_error(const char* message) {
    printf("%s✖ 错误: %s%s\n", CLR_RED, message, CLR_RST);
}

// 打印成功信息
void ui_print_success(const char* message) {
    printf("%s✔ 成功: %s%s\n", CLR_GRN, message, CLR_RST);
}

// 打印代码块
void ui_print_code_block(const char* language, const char* code) {
    printf("\n%s%s %s %s\n", CLR_BG_MAG, CLR_BLD, language, CLR_RST);
    printf("%s%s\n", CLR_DIM, code);
    printf("%s\n", CLR_RST);
}

// 打印 Shell 输出
void ui_print_shell_output(const char* output) {
    printf("%s%s$ Shell 输出:%s\n", CLR_BG_CYN, CLR_BLD, CLR_RST);
    printf("%s%s%s\n", CLR_ITL, output, CLR_RST);
}

// 打印文件操作
void ui_print_file_op(const char* op, const char* path) {
    printf("%s  📁 文件%s: %s%s%s%s\n", CLR_CYN, op, CLR_BLD, CLR_UND, path, CLR_RST);
}

void ui_print_voice_status(int is_listening) {
    if (is_listening) {
        printf("\n%s%s[ 🎤 语音录制中... 按任意键停止 ]%s\n", CLR_BG_RED, CLR_BLD, CLR_RST);
    } else {
        printf("\n%s%s[ 🎤 语音录制结束 ]%s\n", CLR_BG_GRN, CLR_BLD, CLR_RST);
    }
}

void ui_print_memo_card(const char* content, const char* tags, const char* time) {
    printf("\n%s╭─────────────────────────────────────────────────────────────────╮%s\n", CLR_CYN, CLR_RST);
    printf("%s│ %s备忘录 %s│ %s%s %s│%s\n", CLR_CYN, CLR_BLD, CLR_RST, CLR_DIM, time, CLR_RST, CLR_CYN);
    printf("├─────────────────────────────────────────────────────────────────┤%s\n", CLR_RST);
    printf("%s│ %s%s\n", CLR_CYN, CLR_RST, content);
    if (tags && strlen(tags) > 0) {
        printf("%s├─────────────────────────────────────────────────────────────────┤%s\n", CLR_CYN, CLR_RST);
        printf("%s│ %s标签: %s%s %s│%s\n", CLR_CYN, CLR_DIM, CLR_RST, CLR_MAG, tags, CLR_RST);
    }
    printf("%s╰─────────────────────────────────────────────────────────────────╯%s\n", CLR_CYN, CLR_RST);
}

// 调试信息打印
void ui_debug(const char* msg) {
    fprintf(stderr, "%s[调试] %s%s\n", CLR_DIM, msg, CLR_RST);
}
