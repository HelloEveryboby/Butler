#include "butler_storage_hal.h"
#include <string.h>

/**
 * Butler Storage Implementation Template
 * Redirects to specific hardware drivers (e.g., W25Qxx)
 */

static butler_storage_device_t* current_dev = NULL;

bool butler_storage_register(butler_storage_device_t* device) {
    if (!device || !device->init) return false;
    if (device->init()) {
        current_dev = device;
        return true;
    }
    return false;
}

#define SLOT_SIZE 4096 // 每个卡槽分配 4KB (足够 Mifare 1K/4K)

bool butler_storage_save_to_slot(uint8_t slot, const uint8_t* data, uint32_t len) {
    if (!current_dev || !current_dev->write || !current_dev->erase_sector) return false;
    uint32_t addr = slot * SLOT_SIZE;
    current_dev->erase_sector(addr);
    return current_dev->write(addr, data, len);
}

bool butler_storage_load_from_slot(uint8_t slot, uint8_t* buf, uint32_t len) {
    if (!current_dev || !current_dev->read) return false;
    uint32_t addr = slot * SLOT_SIZE;
    return current_dev->read(addr, buf, len);
}

bool butler_storage_get_slot_info(uint8_t slot, char* out_info, size_t max_len) {
    uint8_t temp[16];
    if (butler_storage_load_from_slot(slot, temp, 16)) {
        // 简单通过前几个字节判断是否有数据
        if (temp[0] == 0x00 && temp[1] == 0x00) {
            snprintf(out_info, max_len, "Slot %d: Empty", slot);
        } else {
            snprintf(out_info, max_len, "Slot %d: Mifare Data (UID: %02X%02X%02X%02X)", slot, temp[0], temp[1], temp[2], temp[3]);
        }
        return true;
    }
    return false;
}
