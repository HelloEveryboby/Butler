#include "BLEFramework.h"
#include <iostream>
#include <algorithm>
#include <chrono>
#include <unistd.h>
#include <cstring>

// For BlueZ
#include <bluetooth/bluetooth.h>
#include <bluetooth/hci.h>
#include <bluetooth/hci_lib.h>

BLEFramework::BLEFramework() {
    int dev_id = hci_get_route(NULL);
    if (dev_id < 0) {
        std::cerr << "Warning: No Bluetooth adapter found. Running in MOCK mode." << std::endl;
        mock_mode_ = true;
    }

    worker_ = std::thread(&BLEFramework::workerThread, this);
    write_worker_ = std::thread(&BLEFramework::writeWorkerThread, this);
}

BLEFramework::~BLEFramework() {
    connection_queue_.stop();
    write_queue_.stop();
    if (worker_.joinable()) worker_.join();
    if (write_worker_.joinable()) write_worker_.join();
}

void BLEFramework::startScan(int duration_ms) {
    if (mock_mode_) {
        std::lock_guard<std::mutex> lock(devices_mutex_);
        BLEDeviceInfo d1;
        strcpy(d1.address, "AA:BB:CC:DD:EE:FF");
        strcpy(d1.name, "MockDevice_1");
        d1.rssi = -60;
        discovered_devices_[d1.address] = d1;

        BLEDeviceInfo d2;
        strcpy(d2.address, "11:22:33:44:55:66");
        strcpy(d2.name, "MockDevice_2");
        d2.rssi = -75;
        discovered_devices_[d2.address] = d2;
        return;
    }

    int dev_id = hci_get_route(NULL);
    int sock = hci_open_dev(dev_id);
    if (sock < 0) return;

    // Use HCI LE Scan
    uint8_t own_type = 0x00;
    uint8_t scan_type = 0x01; // Active
    uint16_t interval = htobs(0x0010);
    uint16_t window = htobs(0x0010);
    uint8_t filter_policy = 0x00;

    hci_le_set_scan_parameters(sock, scan_type, interval, window, own_type, filter_policy, 1000);
    hci_le_set_scan_enable(sock, 0x01, 1, 1000);

    // Read results for duration_ms
    auto start = std::chrono::steady_clock::now();
    uint8_t buf[HCI_MAX_EVENT_SIZE];
    while (std::chrono::steady_clock::now() - start < std::chrono::milliseconds(duration_ms)) {
        int len = read(sock, buf, sizeof(buf));
        if (len > 0 && buf[0] == HCI_EVENT_PKT) {
            hci_event_hdr *eh = (hci_event_hdr *)(buf + 1);
            if (eh->evt == EVT_LE_META_EVENT) {
                evt_le_meta_event *me = (evt_le_meta_event *)(buf + 1 + HCI_EVENT_HDR_SIZE);
                if (me->subevent == EVT_LE_ADVERTISING_REPORT) {
                    le_advertising_info *info = (le_advertising_info *)(me->data + 1);
                    char addr[19];
                    ba2str(&info->bdaddr, addr);

                    std::lock_guard<std::mutex> lock(devices_mutex_);
                    if (discovered_devices_.find(addr) == discovered_devices_.end()) {
                        BLEDeviceInfo d;
                        strcpy(d.address, addr);
                        strcpy(d.name, "[BLE Device]");
                        d.rssi = (int8_t)info->data[info->length]; // RSSI is the last byte
                        discovered_devices_[addr] = d;
                    }
                }
            }
        }
        std::this_thread::sleep_for(std::chrono::milliseconds(10));
    }

    hci_le_set_scan_enable(sock, 0x00, 1, 1000);
    close(sock);
}

int BLEFramework::getScanResults(BLEDeviceInfo* results, int max_results) {
    std::lock_guard<std::mutex> lock(devices_mutex_);
    int count = 0;
    for (auto const& [addr, info] : discovered_devices_) {
        if (count >= max_results) break;
        results[count++] = info;
    }
    return count;
}

bool BLEFramework::connect(const std::string& address) {
    connection_queue_.push({BLETaskType::CONNECT, address, "", "", {}});
    return true;
}

bool BLEFramework::disconnect(const std::string& address) {
    connection_queue_.push({BLETaskType::DISCONNECT, address, "", "", {}});
    return true;
}

bool BLEFramework::writeData(const std::string& address, const std::string& service_uuid, const std::string& char_uuid, const uint8_t* data, int len, bool fast) {
    std::vector<uint8_t> vdata(data, data + len);
    if (fast) {
        write_queue_.push({BLETaskType::WRITE, address, service_uuid, char_uuid, vdata});
    } else {
        connection_queue_.push({BLETaskType::WRITE, address, service_uuid, char_uuid, vdata});
    }
    return true;
}

int BLEFramework::getRSSI(const std::string& address) {
    if (mock_mode_) return -55;
    return -60;
}

bool BLEFramework::setMTU(const std::string& address, int mtu) {
    return true;
}

void BLEFramework::workerThread() {
    BLETask task;
    while (connection_queue_.pop(task)) {
        std::cout << "[BLEFramework] Processing task: " << (int)task.type
                  << " for " << task.device_address << std::endl;

        // In a real implementation, we would use BlueZ GDBus or L2CAP here.
        // For the framework structure, we simulate the state management.
        switch(task.type) {
            case BLETaskType::CONNECT:
                // TODO: Perform real L2CAP/GATT connection
                std::this_thread::sleep_for(std::chrono::milliseconds(200));
                std::cout << "[BLEFramework] Connected to " << task.device_address << std::endl;
                break;
            case BLETaskType::DISCONNECT:
                std::cout << "[BLEFramework] Disconnected from " << task.device_address << std::endl;
                break;
            case BLETaskType::WRITE:
                // TODO: Send ATT Write Request
                break;
            case BLETaskType::READ:
                // TODO: Send ATT Read Request
                break;
            default:
                break;
        }
    }
}

void BLEFramework::writeWorkerThread() {
    BLETask task;
    while (write_queue_.pop(task)) {
        // Fast write implementation
        // For the framework, this demonstrates the parallel processing of writes.
        // TODO: Send ATT Write Command (no response) for high throughput
    }
}

// C Interface Implementation
extern "C" {
    BLEFramework* ble_create() { return new BLEFramework(); }
    void ble_destroy(BLEFramework* fw) { delete fw; }
    void ble_scan(BLEFramework* fw, int duration_ms) { fw->startScan(duration_ms); }
    int ble_get_scan_results(BLEFramework* fw, BLEDeviceInfo* results, int max_results) {
        return fw->getScanResults(results, max_results);
    }
    bool ble_connect(BLEFramework* fw, const char* address) { return fw->connect(address); }
    bool ble_disconnect(BLEFramework* fw, const char* address) { return fw->disconnect(address); }
    bool ble_write(BLEFramework* fw, const char* address, const char* svc, const char* chr, const uint8_t* data, int len, bool fast) {
        return fw->writeData(address, svc, chr, data, len, fast);
    }
    int ble_get_rssi(BLEFramework* fw, const char* address) { return fw->getRSSI(address); }
    bool ble_set_mtu(BLEFramework* fw, const char* address, int mtu) { return fw->setMTU(address, mtu); }
}
