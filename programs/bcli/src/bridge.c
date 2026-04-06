#include "bridge.h"
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <unistd.h>
#include <sys/wait.h>
#include <fcntl.h>
#include <errno.h>
#include "ui_engine.h"

static int py_fd = -1;
static pid_t child_pid = -1;
static char line_buf[65536];
static int line_idx = 0;

void bridge_init() {
}

static char* extract_json_field(const char* json, const char* field) {
    char search[128];
    snprintf(search, sizeof(search), "\"%s\": \"", field);
    const char* start = strstr(json, search);
    if (!start) return NULL;
    start += strlen(search);

    const char* end = start;
    while (*end) {
        if (*end == '"' && (end == start || *(end-1) != '\\')) break;
        end++;
    }

    if (!end || *end == '\0') return NULL;
    int len = end - start;
    char* result = malloc(len + 1);
    strncpy(result, start, len);
    result[len] = '\0';

    char* src = result;
    char* dst = result;
    while (*src) {
        if (*src == '\\' && *(src+1) == '"') {
            *dst++ = '"';
            src += 2;
        } else if (*src == '\\' && *(src+1) == 'n') {
            *dst++ = '\n';
            src += 2;
        } else if (*src == '\\' && *(src+1) == '\\') {
            *dst++ = '\\';
            src += 2;
        } else {
            *dst++ = *src++;
        }
    }
    *dst = '\0';

    return result;
}

void bridge_send_query(const char* query) {
    int pipefd[2];
    if (pipe(pipefd) == -1) return;

    child_pid = fork();
    if (child_pid == 0) {
        close(pipefd[0]);
        dup2(pipefd[1], STDOUT_FILENO);
        int devnull = open("/dev/null", O_WRONLY);
        dup2(devnull, STDERR_FILENO);
        char* args[] = {"python3", "programs/bcli/agent_backend.py", "agent", (char*)query, NULL};
        execvp("python3", args);
        exit(1);
    } else {
        close(pipefd[1]);
        py_fd = pipefd[0];
        // Set non-blocking
        int flags = fcntl(py_fd, F_GETFL, 0);
        fcntl(py_fd, F_SETFL, flags | O_NONBLOCK);
        line_idx = 0;
    }
}

bridge_message_t* bridge_receive_next_nonblocking() {
    if (py_fd == -1) return NULL;

    char c;
    while (read(py_fd, &c, 1) > 0) {
        if (c == '\n') {
            line_buf[line_idx] = '\0';
            line_idx = 0;

            if (line_buf[0] != '{') continue;

            bridge_message_t* msg = (bridge_message_t*)malloc(sizeof(bridge_message_t));
            memset(msg, 0, sizeof(bridge_message_t));

            msg->type = extract_json_field(line_buf, "type");
            msg->content = extract_json_field(line_buf, "content");
            msg->extra = extract_json_field(line_buf, "extra");

            if (msg->type) {
                return msg;
            } else {
                if (msg->content) free(msg->content);
                if (msg->extra) free(msg->extra);
                free(msg);
            }
        } else {
            if ((size_t)line_idx < sizeof(line_buf) - 1) {
                line_buf[line_idx++] = c;
            }
        }
    }

    return NULL;
}

int bridge_is_active() {
    if (py_fd == -1) return 0;
    int status;
    if (waitpid(child_pid, &status, WNOHANG) != 0) {
        close(py_fd);
        py_fd = -1;
        return 0;
    }
    return 1;
}

void bridge_cleanup() {
    if (py_fd != -1) {
        close(py_fd);
        py_fd = -1;
    }
}
