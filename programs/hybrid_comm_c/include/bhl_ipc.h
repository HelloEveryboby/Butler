#ifndef BHL_IPC_H
#define BHL_IPC_H

#include <stddef.h>

// BHL 跨进程同步原语 (C 语言实现)
// 用于在不同语言的二进制模块之间通过共享内存或命名管道进行协调

typedef struct {
    int key;
    size_t size;
    void* addr;
    int shmid;
} bhl_shm_t;

// 初始化共享内存
bhl_shm_t* bhl_shm_create(int key, size_t size);
// 连接到现有的共享内存
bhl_shm_t* bhl_shm_attach(int key, size_t size);
// 读写数据
int bhl_shm_write(bhl_shm_t* shm, const void* data, size_t len);
int bhl_shm_read(bhl_shm_t* shm, void* buf, size_t len);
// 释放
void bhl_shm_detach(bhl_shm_t* shm);
void bhl_shm_destroy(bhl_shm_t* shm);

#endif
