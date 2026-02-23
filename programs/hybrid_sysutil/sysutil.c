#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <dirent.h>
#include <unistd.h>
#include <sys/stat.h>
#include <sys/sysinfo.h>
#include <ctype.h>

// Simple JSON helper
void print_json_string(const char* str) {
    putchar('"');
    for (const char* p = str; *p; p++) {
        if (*p == '"' || *p == '\\') {
            putchar('\\');
            putchar(*p);
        } else if (*p == '\n') {
            printf("\\n");
        } else if (*p == '\r') {
            printf("\\r");
        } else if (*p == '\t') {
            printf("\\t");
        } else if ((unsigned char)*p < 32) {
            // skip other control chars
        } else {
            putchar(*p);
        }
    }
    putchar('"');
}

// BHL Protocol helper
void send_result(const char* id, const char* result_json) {
    printf("{\"jsonrpc\":\"2.0\",\"result\":%s,\"id\":\"%s\"}\n", result_json, id);
    fflush(stdout);
}

void send_error(const char* id, int code, const char* message) {
    printf("{\"jsonrpc\":\"2.0\",\"error\":{\"code\":%d,\"message\":\"%s\"},\"id\":\"%s\"}\n", code, message, id);
    fflush(stdout);
}

// System Info
void get_system_info(const char* id) {
    struct sysinfo info;
    if (sysinfo(&info) != 0) {
        send_error(id, -1, "Failed to get sysinfo");
        return;
    }

    double load = info.loads[0] / 65536.0;
    unsigned long total_ram = info.totalram * info.mem_unit / (1024 * 1024);
    unsigned long free_ram = info.freeram * info.mem_unit / (1024 * 1024);
    unsigned long uptime = info.uptime;

    char buffer[512];
    snprintf(buffer, sizeof(buffer),
             "{\"uptime\":%lu,\"load_1m\":%.2f,\"total_mb\":%lu,\"free_mb\":%lu}",
             uptime, load, total_ram, free_ram);
    send_result(id, buffer);
}

// Process Listing (Butler specific)
void list_processes(const char* id) {
    DIR* dir = opendir("/proc");
    if (!dir) {
        send_error(id, -1, "Cannot open /proc");
        return;
    }

    printf("{\"jsonrpc\":\"2.0\",\"result\":{\"processes\":[");
    struct dirent* entry;
    int first = 1;

    while ((entry = readdir(dir)) != NULL) {
        if (!isdigit(entry->d_name[0])) continue;

        char path[512];
        snprintf(path, sizeof(path), "/proc/%s/cmdline", entry->d_name);
        FILE* f = fopen(path, "r");
        if (f) {
            char cmdline[2048];
            size_t len = fread(cmdline, 1, sizeof(cmdline) - 1, f);
            fclose(f);
            if (len > 0) {
                // cmdline is null-separated, replace with spaces for easier reading
                for (size_t i = 0; i < len; i++) if (cmdline[i] == '\0') cmdline[i] = ' ';
                cmdline[len] = '\0';

                // Simple heuristic to find Butler-related processes
                if (strstr(cmdline, "butler") || strstr(cmdline, "package.") || strstr(cmdline, "hybrid_") || strstr(cmdline, "sysutil")) {
                    if (!first) printf(",");
                    printf("{\"pid\":%s,\"cmd\":", entry->d_name);
                    print_json_string(cmdline);
                    printf("}");
                    first = 0;
                }
            }
        }
    }
    closedir(dir);
    printf("]},\"id\":\"%s\"}\n", id);
    fflush(stdout);
}

// Fast File Search
void recursive_search(const char* dir_path, const char* pattern, int* count, int max) {
    if (*count >= max) return;
    DIR* dir = opendir(dir_path);
    if (!dir) return;

    struct dirent* entry;
    while ((entry = readdir(dir)) != NULL) {
        if (strcmp(entry->d_name, ".") == 0 || strcmp(entry->d_name, "..") == 0) continue;

        char path[1024];
        snprintf(path, sizeof(path), "%s/%s", dir_path, entry->d_name);

        struct stat st;
        if (lstat(path, &st) == 0) {
            if (S_ISDIR(st.st_mode)) {
                // Avoid infinite loops and permission issues
                if (strstr(path, "/proc") || strstr(path, "/sys") || strstr(path, "/dev") || strstr(path, ".git")) continue;
                recursive_search(path, pattern, count, max);
            } else if (strstr(entry->d_name, pattern)) {
                if (*count > 0) printf(",");
                print_json_string(path);
                (*count)++;
                if (*count >= max) break;
            }
        }
        if (*count >= max) break;
    }
    closedir(dir);
}

void fast_file_search(const char* id, const char* root, const char* pattern) {
    printf("{\"jsonrpc\":\"2.0\",\"result\":{\"files\":[");
    int count = 0;
    recursive_search(root, pattern, &count, 100);
    printf("],\"count\":%d},\"id\":\"%s\"}\n", count, id);
    fflush(stdout);
}

// Manual JSON value extractor
char* get_json_val(const char* json, const char* key, char* buf, int size) {
    char search[128];
    snprintf(search, sizeof(search), "\"%s\"", key);
    const char* p = strstr(json, search);
    if (!p) return NULL;
    p = strchr(p + strlen(search), ':');
    if (!p) return NULL;
    p++;
    while (isspace(*p)) p++;
    if (*p == '"') {
        p++;
        const char* end = strchr(p, '"');
        if (!end) return NULL;
        int len = end - p;
        if (len >= size) len = size - 1;
        strncpy(buf, p, len);
        buf[len] = '\0';
        return buf;
    } else {
        const char* end = p;
        while (*end && !isspace(*end) && *end != ',' && *end != '}' && *end != ']') end++;
        int len = end - p;
        if (len >= size) len = size - 1;
        strncpy(buf, p, len);
        buf[len] = '\0';
        return buf;
    }
}

int main() {
    char line[4096];
    while (fgets(line, sizeof(line), stdin)) {
        if (strlen(line) < 5) continue;
        char method[64], id[64];
        if (!get_json_val(line, "method", method, sizeof(method))) continue;
        if (!get_json_val(line, "id", id, sizeof(id))) strcpy(id, "null");

        if (strcmp(method, "get_system_info") == 0) {
            get_system_info(id);
        } else if (strcmp(method, "list_processes") == 0) {
            list_processes(id);
        } else if (strcmp(method, "fast_file_search") == 0) {
            char root[512] = ".", pattern[256] = "";
            get_json_val(line, "root", root, sizeof(root));
            get_json_val(line, "pattern", pattern, sizeof(pattern));
            fast_file_search(id, root, pattern);
        } else if (strcmp(method, "exit") == 0) {
            break;
        } else {
            send_error(id, -32601, "Method not found");
        }
    }
    return 0;
}
