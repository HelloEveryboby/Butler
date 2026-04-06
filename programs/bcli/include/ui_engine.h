#ifndef UI_ENGINE_H
#define UI_ENGINE_H

#include <stdio.h>

// Colors
#define CLR_RED     "\x1b[31m"
#define CLR_GRN     "\x1b[32m"
#define CLR_YLW     "\x1b[33m"
#define CLR_BLU     "\x1b[34m"
#define CLR_MAG     "\x1b[35m"
#define CLR_CYN     "\x1b[36m"
#define CLR_RST     "\x1b[0m"
#define CLR_BLD     "\x1b[1m"
#define CLR_DIM     "\x1b[2m"
#define CLR_ITL     "\x1b[3m"
#define CLR_UND     "\x1b[4m"
#define CLR_BG_RED     "\x1b[41m"
#define CLR_BG_GRN     "\x1b[42m"
#define CLR_BG_YLW     "\x1b[43m"
#define CLR_BG_BLU     "\x1b[44m"
#define CLR_BG_MAG     "\x1b[45m"
#define CLR_BG_CYN     "\x1b[46m"

// UI Components
void ui_print_banner();
void ui_print_thinking(const char* message, int step);
void ui_print_task(const char* task_name);
void ui_print_tool_call(const char* tool_name, const char* args);
void ui_print_error(const char* message);
void ui_print_success(const char* message);
void ui_print_ai_message(const char* message);
void ui_clear_line();
void ui_print_code_block(const char* language, const char* code);
void ui_print_shell_output(const char* output);
void ui_debug(const char* msg);
void ui_print_file_op(const char* op, const char* path);

#endif
