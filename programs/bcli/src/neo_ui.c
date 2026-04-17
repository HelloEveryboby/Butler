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
