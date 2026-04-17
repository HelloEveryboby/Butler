#include <stdio.h>
#include <string.h>
#include "ui_engine.h"

/**
 * Butler Neo-Embedded UI 引擎
 * 采用极简线条风格，与 Claude Code 区分开
 */

void neo_print_banner() {
    printf("\n%s%s", CLR_CYN, CLR_BLD);
    printf(" ━━━  Butler Neo-Embedded Node  ━━━\n");
    printf(" ┃  Status: Online               ┃\n");
    printf(" ┃  Version: 2.0-Alpha           ┃\n");
    printf(" ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━%s\n", CLR_RST);
}

void neo_print_status(const char* task, const char* stage) {
    printf("%s[B]%s %-15s | %s%s%s\n", CLR_CYN, CLR_RST, task, CLR_DIM, stage, CLR_RST);
}

void neo_print_progress(int percent) {
    int bars = percent / 10;
    printf("  %s[", CLR_DIM);
    for(int i=0; i<10; i++) {
        if(i < bars) printf("━");
        else if(i == bars) printf(">");
        else printf(" ");
    }
    printf("] %d%%%s\r", percent, CLR_RST);
    fflush(stdout);
}

void neo_print_response(const char* msg) {
    printf("\n%s┃%s %s\n", CLR_CYN, CLR_RST, msg);
}

void neo_print_system_info(const char* brain_status, const char* stm32_status) {
    printf("\n%s[ SYSTEM STATUS ]%s\n", CLR_DIM, CLR_RST);
    printf("  Brain: %s%s%s\n", CLR_GRN, brain_status, CLR_RST);
    printf("  STM32: %s%s%s\n", CLR_GRN, stm32_status, CLR_RST);
    printf("────────────────────────────────\n");
}

void neo_print_alert(const char* title, const char* msg) {
    printf("\n%s%s[! %s ] %s%s%s\n", CLR_BG_MAG, CLR_BLD, title, CLR_RST, CLR_MAG, msg, CLR_RST);
}
