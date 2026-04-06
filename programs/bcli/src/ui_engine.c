#include "ui_engine.h"
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <unistd.h>

#define BANNER_ART \
"  ____       _   _             \n" \
" | __ ) _   | |_| | ___ _ __   \n" \
" |  _ \\| | | | __| |/ _ \\ '__|  \n" \
" | |_) | |_| | |_| |  __/ |     \n" \
" |____/ \\__,_|\\__|_|\\___|_|     \n"

void ui_print_banner() {
    printf("%s%s%s%s", CLR_CYN, CLR_BLD, BANNER_ART, CLR_RST);
    printf("%s Butler AI Assistant - CLI Edition (STM32 Compatible)\n", CLR_DIM);
    printf(" Inspired by Claude Code | Powered by Jarvis Engine%s\n\n", CLR_RST);
}

void ui_print_thinking(const char* message, int step) {
    const char* spinners[] = {"⠋", "⠙", "⠹", "⠸", "⠼", "⠴", "⠦", "⠧", "⠇", "⠏"};
    int num_spinners = sizeof(spinners) / sizeof(spinners[0]);

    printf("\r%s%s%s %s... ", CLR_YLW, spinners[step % num_spinners], CLR_RST, message);
    fflush(stdout);
}

void ui_clear_line() {
    printf("\r\x1b[K");
    fflush(stdout);
}

void ui_print_task(const char* task_name) {
    printf("\n%s%s▶ Executing Task: %s%s\n", CLR_BLD, CLR_MAG, task_name, CLR_RST);
}

void ui_print_tool_call(const char* tool_name, const char* args) {
    printf("%s  🔧 Tool Call: %s%s%s %s(%s)%s\n", CLR_GRN, CLR_BLD, tool_name, CLR_RST, CLR_DIM, args, CLR_RST);
}

void ui_print_ai_message(const char* message) {
    printf("\n%s%sButler > %s%s\n", CLR_BLD, CLR_BLU, CLR_RST, message);
}

void ui_print_error(const char* message) {
    printf("%s✖ Error: %s%s\n", CLR_RED, message, CLR_RST);
}

void ui_print_success(const char* message) {
    printf("%s✔ Success: %s%s\n", CLR_GRN, message, CLR_RST);
}

void ui_print_code_block(const char* language, const char* code) {
    printf("\n%s%s %s %s\n", CLR_BG_MAG, CLR_BLD, language, CLR_RST);
    printf("%s%s\n", CLR_DIM, code);
    printf("%s\n", CLR_RST);
}

void ui_print_shell_output(const char* output) {
    printf("%s%s$ Shell Output:%s\n", CLR_BG_CYN, CLR_BLD, CLR_RST);
    printf("%s%s%s\n", CLR_ITL, output, CLR_RST);
}

void ui_print_file_op(const char* op, const char* path) {
    printf("%s  📁 %s: %s%s%s%s\n", CLR_CYN, op, CLR_BLD, CLR_UND, path, CLR_RST);
}

void ui_debug(const char* msg) {
    fprintf(stderr, "%s[DEBUG] %s%s\n", CLR_DIM, msg, CLR_RST);
}
