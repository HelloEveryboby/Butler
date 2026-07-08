#define _GNU_SOURCE
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <dirent.h>
#include <unistd.h>
#include <sys/stat.h>
#include <sys/sysinfo.h>
#include <ctype.h>
#include <glob.h>

/**
 * Butler 高性能系统工具集 (C 语言版) - V2.1 修复版
 * --------------------------------
 * 修复了 JSON 转义、缓冲区限制和功能回归问题。
 */

// 正确的 JSON 字符串转义处理
void print_json_string(const char* str) {
    putchar('"');
    for (const char* p = str; *p; p++) {
        if (*p == '\\') {
            printf("\\\\");
        } else if (*p == '"') {
            printf("\\\"");
        } else if (*p == '\n') {
            printf("\\n");
        } else if (*p == '\r') {
            printf("\\r");
        } else if (*p == '\t') {
            printf("\\t");
        } else if ((unsigned char)*p < 32) {
            // 跳过控制字符
        } else {
            putchar(*p);
        }
    }
    putchar('"');
}

// BHL 协议响应助手
void send_result(const char* id, const char* result_json) {
    printf("{\"jsonrpc\":\"2.0\",\"result\":%s,\"id\":\"%s\"}\n", result_json, id);
    fflush(stdout);
}

void send_error(const char* id, int code, const char* message) {
    printf("{\"jsonrpc\":\"2.0\",\"error\":{\"code\":%d,\"message\":\"%s\"},\"id\":\"%s\"}\n", code, message, id);
    fflush(stdout);
}

// 1. 系统资源状态获取
void get_system_info(const char* id) {
    struct sysinfo info;
    if (sysinfo(&info) != 0) {
        send_error(id, -1, "无法获取系统信息");
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

// 2. 进程列表扫描
void list_processes(const char* id) {
    DIR* dir = opendir("/proc");
    if (!dir) {
        send_error(id, -1, "无法打开 /proc 目录");
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
                for (size_t i = 0; i < len; i++) if (cmdline[i] == '\0') cmdline[i] = ' ';
                cmdline[len] = '\0';

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

// 3. 高性能 Grep 搜索 (带递归和限制)
static int global_match_count = 0;
static void recursive_grep(const char* dir_path, const char* pattern, int case_sensitive) {
    if (global_match_count >= 500) return;

    DIR* dir = opendir(dir_path);
    if (!dir) return;

    struct dirent* entry;
    while ((entry = readdir(dir)) != NULL) {
        if (global_match_count >= 500) break;
        if (strcmp(entry->d_name, ".") == 0 || strcmp(entry->d_name, "..") == 0) continue;
        if (entry->d_name[0] == '.' && strcmp(entry->d_name, ".env") != 0) continue;

        char path[1024];
        snprintf(path, sizeof(path), "%s/%s", dir_path, entry->d_name);

        struct stat st;
        if (lstat(path, &st) == 0) {
            if (S_ISDIR(st.st_mode)) {
                if (strstr(path, "/proc") || strstr(path, "/sys") || strstr(path, "/dev") ||
                    strstr(path, "/.git") || strstr(path, "/node_modules") || strstr(path, "/obj")) continue;
                recursive_grep(path, pattern, case_sensitive);
            } else if (S_ISREG(st.st_mode)) {
                FILE* f = fopen(path, "r");
                if (f) {
                    char line[8192];
                    int line_num = 0;
                    while (fgets(line, sizeof(line), f)) {
                        line_num++;
                        char* found = case_sensitive ? strstr(line, pattern) : strcasestr(line, pattern);
                        if (found) {
                            if (global_match_count > 0) printf(",");
                            printf("{\"file\":");
                            print_json_string(path);
                            printf(",\"line\":%d,\"content\":", line_num);
                            print_json_string(line);
                            printf("}");
                            global_match_count++;
                            if (global_match_count >= 500) break;
                        }
                    }
                    fclose(f);
                }
            }
        }
    }
    closedir(dir);
}

void grep_search(const char* id, const char* root, const char* pattern, int case_sensitive) {
    printf("{\"jsonrpc\":\"2.0\",\"result\":{\"matches\":[");
    global_match_count = 0;
    recursive_grep(root, pattern, case_sensitive);
    printf("],\"total\":%d},\"id\":\"%s\"}\n", global_match_count, id);
    fflush(stdout);
}

// 4. Glob 列表
void glob_list(const char* id, const char* pattern) {
    glob_t glob_result;
    memset(&glob_result, 0, sizeof(glob_result));

    int return_value = glob(pattern, GLOB_TILDE | GLOB_BRACE, NULL, &glob_result);
    if (return_value != 0) {
        if (return_value == GLOB_NOMATCH) {
            send_result(id, "{\"files\":[],\"count\":0}");
        } else {
            send_error(id, -1, "Glob 匹配执行出错");
        }
        return;
    }

    printf("{\"jsonrpc\":\"2.0\",\"result\":{\"files\":[");
    for (size_t i = 0; i < glob_result.gl_pathc; i++) {
        if (i > 0) printf(",");
        print_json_string(glob_result.gl_pathv[i]);
    }
    printf("],\"count\":%zu},\"id\":\"%s\"}\n", glob_result.gl_pathc, id);
    fflush(stdout);
    globfree(&glob_result);
}

// 5. 增强版原子 Patch 编辑 (移除长度限制)
void patch_edit(const char* id, const char* path, const char* old_text, const char* new_text) {
    FILE* f = fopen(path, "r");
    if (!f) {
        send_error(id, -32001, "无法打开目标文件进行读取");
        return;
    }

    fseek(f, 0, SEEK_END);
    long fsize = ftell(f);
    fseek(f, 0, SEEK_SET);

    char* content = malloc(fsize + 1);
    if (!content) {
        fclose(f);
        send_error(id, -32006, "内存分配失败");
        return;
    }
    fread(content, 1, fsize, f);
    content[fsize] = '\0';
    fclose(f);

    char* pos = strstr(content, old_text);
    if (!pos) {
        free(content);
        send_error(id, -32002, "在文件中未找到指定的原始文本块");
        return;
    }

    if (strstr(pos + strlen(old_text), old_text)) {
        free(content);
        send_error(id, -32003, "指定的原始文本块在文件中不唯一");
        return;
    }

    long old_len = strlen(old_text);
    long new_len = strlen(new_text);
    long new_fsize = fsize - old_len + new_len;
    char* new_content = malloc(new_fsize + 1);
    if (!new_content) {
        free(content);
        send_error(id, -32006, "内存分配失败");
        return;
    }

    size_t prefix_len = pos - content;
    memcpy(new_content, content, prefix_len);
    memcpy(new_content + prefix_len, new_text, new_len);
    memcpy(new_content + prefix_len + new_len, pos + old_len, fsize - prefix_len - old_len);
    new_content[new_fsize] = '\0';

    char tmp_path[1024];
    snprintf(tmp_path, sizeof(tmp_path), "%s.tmp", path);
    FILE* wf = fopen(tmp_path, "w");
    if (!wf) {
        free(content); free(new_content);
        send_error(id, -32004, "无法创建临时文件");
        return;
    }
    fwrite(new_content, 1, new_fsize, wf);
    fclose(wf);

    if (rename(tmp_path, path) != 0) {
        send_error(id, -32005, "重命名失败");
    } else {
        send_result(id, "{\"status\":\"success\"}");
    }

    free(content);
    free(new_content);
}

// 6. 恢复的 Display 检测
void detect_displays(const char* id) {
    int display_count = 0;
    char details[512] = "";
    int offset = 0;

    DIR* dir = opendir("/sys/class/drm");
    if (dir) {
        struct dirent* entry;
        while ((entry = readdir(dir)) != NULL) {
            if (strncmp(entry->d_name, "card", 4) == 0 && strstr(entry->d_name, "-")) {
                char path[512];
                snprintf(path, sizeof(path), "/sys/class/drm/%s/status", entry->d_name);
                FILE* f = fopen(path, "r");
                if (f) {
                    char status[16];
                    if (fgets(status, sizeof(status), f) && strncmp(status, "connected", 9) == 0) {
                        display_count++;
                        offset += snprintf(details + offset, sizeof(details) - offset, "%s ", entry->d_name);
                    }
                    fclose(f);
                }
            }
        }
        closedir(dir);
    }
    if (getenv("DISPLAY") && display_count == 0) display_count = 1;

    printf("{\"jsonrpc\":\"2.0\",\"result\":{\"display_count\":%d,\"details\":", display_count);
    print_json_string(details);
    printf("},\"id\":\"%s\"}\n", id);
    fflush(stdout);
}

// 7. 恢复的连接检测
void check_connections(const char* id) {
    int connection_count = 0;
    char devices[512] = "";
    int offset = 0;

    DIR* dir = opendir("/dev");
    if (dir) {
        struct dirent* entry;
        while ((entry = readdir(dir)) != NULL) {
            if (strstr(entry->d_name, "ttyUSB") || strstr(entry->d_name, "ttyACM")) {
                connection_count++;
                offset += snprintf(devices + offset, sizeof(devices) - offset, "%s ", entry->d_name);
            }
        }
        closedir(dir);
    }

    printf("{\"jsonrpc\":\"2.0\",\"result\":{\"count\":%d,\"devices\":", connection_count);
    print_json_string(devices);
    printf("},\"id\":\"%s\"}\n", id);
    fflush(stdout);
}

// 8. 健壮的 JSON 解析器 (支持大文本和基本转义)
char* get_json_val(const char* json, const char* key, char** out_buf) {
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
        const char* end_ptr = p;
        size_t len = 0;
        // 第一次遍历计算长度并处理转义
        while (*end_ptr) {
            if (*end_ptr == '"' && *(end_ptr - 1) != '\\') break;
            len++;
            end_ptr++;
        }

        char* buf = malloc(len + 1);
        size_t i = 0;
        const char* src = p;
        while (src < end_ptr) {
            if (*src == '\\') {
                src++;
                if (*src == 'n') buf[i++] = '\n';
                else if (*src == 'r') buf[i++] = '\r';
                else if (*src == 't') buf[i++] = '\t';
                else if (*src == '\\') buf[i++] = '\\';
                else if (*src == '"') buf[i++] = '"';
                else buf[i++] = *src;
            } else {
                buf[i++] = *src;
            }
            src++;
        }
        buf[i] = '\0';
        *out_buf = buf;
        return buf;
    } else {
        const char* end = p;
        while (*end && !isspace(*end) && *end != ',' && *end != '}' && *end != ']') end++;
        size_t len = end - p;
        char* buf = malloc(len + 1);
        strncpy(buf, p, len);
        buf[len] = '\0';
        *out_buf = buf;
        return buf;
    }
}

int main() {
    // 动态增加输入缓冲区大小以处理超大 Patch
    size_t line_cap = 65536 * 4; // 256KB
    char* line = malloc(line_cap);

    while (fgets(line, line_cap, stdin)) {
        if (strlen(line) < 5) continue;
        char *method = NULL, *id = NULL;
        if (!get_json_val(line, "method", &method)) continue;
        get_json_val(line, "id", &id);

        if (strcmp(method, "get_system_info") == 0) {
            get_system_info(id ? id : "null");
        } else if (strcmp(method, "list_processes") == 0) {
            list_processes(id ? id : "null");
        } else if (strcmp(method, "grep_search") == 0) {
            char *root = NULL, *pattern = NULL;
            get_json_val(line, "root", &root);
            get_json_val(line, "pattern", &pattern);
            grep_search(id ? id : "null", root ? root : ".", pattern ? pattern : "", 0);
            if (root) free(root); if (pattern) free(pattern);
        } else if (strcmp(method, "glob_list") == 0) {
            char *pattern = NULL;
            get_json_val(line, "pattern", &pattern);
            glob_list(id ? id : "null", pattern ? pattern : "");
            if (pattern) free(pattern);
        } else if (strcmp(method, "patch_edit") == 0) {
            char *path = NULL, *old_text = NULL, *new_text = NULL;
            get_json_val(line, "path", &path);
            get_json_val(line, "old_text", &old_text);
            get_json_val(line, "new_text", &new_text);
            if (path && old_text && new_text) {
                patch_edit(id ? id : "null", path, old_text, new_text);
            } else {
                send_error(id ? id : "null", -32602, "参数缺失");
            }
            if (path) free(path); if (old_text) free(old_text); if (new_text) free(new_text);
        } else if (strcmp(method, "detect_displays") == 0) {
            detect_displays(id ? id : "null");
        } else if (strcmp(method, "check_connections") == 0) {
            check_connections(id ? id : "null");
        } else if (strcmp(method, "exit") == 0) {
            if (method) free(method); if (id) free(id);
            break;
        } else {
            send_error(id ? id : "null", -32601, "未找到该方法");
        }
        if (method) free(method); if (id) free(id);
    }
    free(line);
    return 0;
}
