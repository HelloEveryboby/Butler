/**
 * @file butler_storage_hal.h
 * @brief Butler 通用存储硬件抽象层 (Storage HAL)
 * 支持任何外部存储芯片 (Flash, EEPROM, SD)
 */

#ifndef BUTLER_STORAGE_HAL_H
#define BUTLER_STORAGE_HAL_H

#include <stdint.h>
#include <stdbool.h>

typedef struct {
    const char* name;
    uint32_t total_size;
    uint32_t sector_size;

    // 硬件回调接口
    bool (*init)(void);
    bool (*read)(uint32_t addr, uint8_t* buf, uint32_t len);
    bool (*write)(uint32_t addr, const uint8_t* buf, uint32_t len);
    bool (*erase_sector)(uint32_t addr);
} butler_storage_device_t;

// 存储管理器 API
bool butler_storage_register(butler_storage_device_t* device);
bool butler_storage_save_to_slot(uint8_t slot, const uint8_t* data, uint32_t len);
bool butler_storage_load_from_slot(uint8_t slot, uint8_t* buf, uint32_t len);
bool butler_storage_get_slot_info(uint8_t slot, char* out_info, size_t max_len);

#endif
