#ifndef HYBRID_ARCHIVE_H
#define HYBRID_ARCHIVE_H

#include <stddef.h>
#include <stdint.h>

/*
 * Archive Entry structure
 */
typedef struct {
    char filename[256];
    uint32_t file_size;
    uint32_t offset;
    uint32_t crc32;
} archive_entry_t;

/**
 * @brief 原子流式替换压缩包中的文件
 *
 * @param archive_path 原压缩包路径
 * @param target_file 要替换的文件名
 * @param new_content_path 新文件的路径（通常在 Flash 缓存区）
 * @param sector_buffer 扇区交换缓冲区指针
 * @return int 0 为成功，非 0 为错误码
 *
 * 技术原理：双扇区交换 (Sector Swapping)
 * 1. 使用 miniz 按块读取原包头。
 * 2. 在写入 Update_Buffer 时，实时计算 CRC。
 * 3. 利用 LittleFS 的原子重命名特性进行替换。
 */
int archive_stream_replace(const char* archive_path,
                           const char* target_file,
                           const char* new_content_path,
                           void* sector_buffer);

/**
 * @brief 提取文件至缓冲区 (内存受限型设计)
 */
int archive_extract_to_buffer(const char* archive_path,
                             const char* target_file,
                             uint8_t* out_buf,
                             size_t buf_size);

#endif // HYBRID_ARCHIVE_H
