#include "bhl_ipc.h"
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <sys/ipc.h>
#include <sys/shm.h>
#include <unistd.h>

bhl_shm_t* bhl_shm_create(int key, size_t size) {
    bhl_shm_t* shm = (bhl_shm_t*)malloc(sizeof(bhl_shm_t));
    shm->key = key;
    shm->size = size;

    shm->shmid = shmget((key_t)key, size, 0666 | IPC_CREAT);
    if (shm->shmid == -1) {
        free(shm);
        return NULL;
    }

    shm->addr = shmat(shm->shmid, (void*)0, 0);
    if (shm->addr == (void*)-1) {
        free(shm);
        return NULL;
    }

    return shm;
}

bhl_shm_t* bhl_shm_attach(int key, size_t size) {
    bhl_shm_t* shm = (bhl_shm_t*)malloc(sizeof(bhl_shm_t));
    shm->key = key;
    shm->size = size;

    shm->shmid = shmget((key_t)key, size, 0666);
    if (shm->shmid == -1) {
        free(shm);
        return NULL;
    }

    shm->addr = shmat(shm->shmid, (void*)0, 0);
    if (shm->addr == (void*)-1) {
        free(shm);
        return NULL;
    }

    return shm;
}

int bhl_shm_write(bhl_shm_t* shm, const void* data, size_t len) {
    if (!shm || !shm->addr || len > shm->size) return -1;
    memcpy(shm->addr, data, len);
    return 0;
}

int bhl_shm_read(bhl_shm_t* shm, void* buf, size_t len) {
    if (!shm || !shm->addr || len > shm->size) return -1;
    memcpy(buf, shm->addr, len);
    return 0;
}

void bhl_shm_detach(bhl_shm_t* shm) {
    if (shm && shm->addr) {
        shmdt(shm->addr);
    }
    free(shm);
}

void bhl_shm_destroy(bhl_shm_t* shm) {
    if (shm) {
        shmctl(shm->shmid, IPC_RMID, 0);
        bhl_shm_detach(shm);
    }
}

// BHL 兼容的主程序入口
int main() {
    char line[4096];
    while (fgets(line, sizeof(line), stdin)) {
        if (strstr(line, "\"method\":\"init_bus\"")) {
            char* id_start = strstr(line, "\"id\":\"");
            char msg_id[64] = "null";
            if (id_start) {
                char* id_val = id_start + 6;
                char* id_end = strchr(id_val, '\"');
                if (id_end) {
                    size_t len = id_end - id_val;
                    if (len > 63) len = 63;
                    strncpy(msg_id, id_val, len);
                    msg_id[len] = '\0';
                }
            }

            bhl_shm_t* shm = bhl_shm_create(0x1337, 1024 * 1024); // 1MB Bus
            if (shm) {
                fprintf(stdout, "{\"jsonrpc\":\"2.0\",\"result\":{\"status\":\"bus_ready\",\"key\":4919},\"id\":\"%s\"}\n", msg_id);
            } else {
                fprintf(stdout, "{\"jsonrpc\":\"2.0\",\"error\":{\"message\":\"failed to create shm\"},\"id\":\"%s\"}\n", msg_id);
            }
            fflush(stdout);
        } else if (strstr(line, "\"method\":\"exit\"")) {
            break;
        }
    }
    return 0;
}
