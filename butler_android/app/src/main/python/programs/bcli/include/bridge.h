#ifndef BRIDGE_H
#define BRIDGE_H

#include <stdio.h>

typedef struct {
    char* type;    // thought, tool, text, error, code, shell
    char* content;
    char* extra;   // tool name or language
} bridge_message_t;

void bridge_init();
void bridge_send_query(const char* query);
bridge_message_t* bridge_receive_next_nonblocking();
int bridge_is_active();
void bridge_cleanup();

#endif
