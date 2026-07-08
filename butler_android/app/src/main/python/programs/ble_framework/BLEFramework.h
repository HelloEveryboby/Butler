#ifndef BLE_FRAMEWORK_H
#define BLE_FRAMEWORK_H

#include <string>
#include <vector>
#include <map>
#include <queue>
#include <mutex>
#include <thread>
#include <condition_variable>
#include <functional>
#include <iostream>
#include <atomic>

// Structure for BLE Device Information
struct BLEDeviceInfo {
    char address[19];
    char name[256];
    int rssi;
};

// Task types for the queues
enum class BLETaskType {
    CONNECT,
    DISCONNECT,
    WRITE,
    READ,
    ENABLE_NOTIFY,
    DISABLE_NOTIFY
};

struct BLETask {
    BLETaskType type;
    std::string device_address;
    std::string service_uuid;
    std::string char_uuid;
    std::vector<uint8_t> data;
};

class BLETaskQueue {
public:
    void push(BLETask task) {
        std::lock_guard<std::mutex> lock(mutex_);
        queue_.push(task);
        cond_.notify_one();
    }

    bool pop(BLETask& task) {
        std::unique_lock<std::mutex> lock(mutex_);
        cond_.wait(lock, [this] { return !queue_.empty() || stop_; });
        if (stop_ && queue_.empty()) return false;
        task = queue_.front();
        queue_.pop();
        return true;
    }

    void stop() {
        stop_ = true;
        cond_.notify_all();
    }

private:
    std::queue<BLETask> queue_;
    std::mutex mutex_;
    std::condition_variable cond_;
    std::atomic<bool> stop_{false};
};

class BLEFramework {
public:
    BLEFramework();
    ~BLEFramework();

    // Core API
    void startScan(int duration_ms);
    int getScanResults(BLEDeviceInfo* results, int max_results);

    bool connect(const std::string& address);
    bool disconnect(const std::string& address);

    bool writeData(const std::string& address, const std::string& service_uuid, const std::string& char_uuid, const uint8_t* data, int len, bool fast = false);

    int getRSSI(const std::string& address);
    bool setMTU(const std::string& address, int mtu);

private:
    void workerThread();
    void writeWorkerThread();

    BLETaskQueue connection_queue_;
    BLETaskQueue write_queue_;

    std::thread worker_;
    std::thread write_worker_;

    std::map<std::string, BLEDeviceInfo> discovered_devices_;
    std::mutex devices_mutex_;

    bool mock_mode_ = false;
};

// C interface for ctypes
extern "C" {
    BLEFramework* ble_create();
    void ble_destroy(BLEFramework* fw);
    void ble_scan(BLEFramework* fw, int duration_ms);
    int ble_get_scan_results(BLEFramework* fw, BLEDeviceInfo* results, int max_results);
    bool ble_connect(BLEFramework* fw, const char* address);
    bool ble_disconnect(BLEFramework* fw, const char* address);
    bool ble_write(BLEFramework* fw, const char* address, const char* svc, const char* chr, const uint8_t* data, int len, bool fast);
    int ble_get_rssi(BLEFramework* fw, const char* address);
    bool ble_set_mtu(BLEFramework* fw, const char* address, int mtu);
}

#endif // BLE_FRAMEWORK_H
