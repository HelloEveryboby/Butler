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

bool butler_storage_save_nfc_dump(const uint8_t* data, uint32_t len) {
    if (!current_dev || !current_dev->write || !current_dev->erase_sector) return false;

    // 假设将 NFC Dump 存储在 Flash 的起始位置 (地址 0)
    // 实际应用中应管理文件系统或偏移量
    current_dev->erase_sector(0);
    return current_dev->write(0, data, len);
}

bool butler_storage_load_nfc_dump(uint8_t* buf, uint32_t len) {
    if (!current_dev || !current_dev->read) return false;
    return current_dev->read(0, buf, len);
}
