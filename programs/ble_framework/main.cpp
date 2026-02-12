#include "BLEFramework.h"
#include <iostream>
#include <string>
#include <vector>
#include <sstream>
#include <iomanip>

void printUsage() {
    std::cout << "Usage: ble_framework <command> [args...]" << std::endl;
    std::cout << "Commands:" << std::endl;
    std::cout << "  scan [duration_ms]             Scan for devices" << std::endl;
    std::cout << "  connect <address>              Connect to a device" << std::endl;
    std::cout << "  write <addr> <svc> <char> <hex_data> [fast]" << std::endl;
    std::cout << "  rssi <addr>                    Get RSSI" << std::endl;
    std::cout << "  mtu <addr> <size>              Set MTU" << std::endl;
}

std::vector<uint8_t> hexToBytes(const std::string& hex) {
    std::vector<uint8_t> bytes;
    for (size_t i = 0; i < hex.length(); i += 2) {
        std::string byteString = hex.substr(i, 2);
        uint8_t byte = (uint8_t) strtol(byteString.c_str(), NULL, 16);
        bytes.push_back(byte);
    }
    return bytes;
}

int main(int argc, char* argv[]) {
    if (argc < 2) {
        printUsage();
        return 1;
    }

    std::string command = argv[1];
    BLEFramework ble;

    if (command == "scan") {
        int duration = (argc > 2) ? std::stoi(argv[2]) : 5000;
        ble.startScan(duration);
        BLEDeviceInfo results[100];
        int count = ble.getScanResults(results, 100);
        std::cout << "{\"results\": [" ;
        for (int i = 0; i < count; ++i) {
            std::cout << "{\"address\": \"" << results[i].address
                      << "\", \"name\": \"" << results[i].name
                      << "\", \"rssi\": " << results[i].rssi << "}"
                      << (i == count - 1 ? "" : ", ");
        }
        std::cout << "]}" << std::endl;
    }
    else if (command == "connect") {
        if (argc < 3) return 1;
        bool success = ble.connect(argv[2]);
        std::cout << "{\"success\": " << (success ? "true" : "false") << "}" << std::endl;
        std::this_thread::sleep_for(std::chrono::seconds(1));
    }
    else if (command == "write") {
        if (argc < 6) return 1;
        std::string addr = argv[2];
        std::string svc = argv[3];
        std::string chr = argv[4];
        std::vector<uint8_t> data = hexToBytes(argv[5]);
        bool fast = (argc > 6 && std::string(argv[6]) == "fast");
        bool success = ble.writeData(addr, svc, chr, data.data(), data.size(), fast);
        std::cout << "{\"success\": " << (success ? "true" : "false") << "}" << std::endl;
        std::this_thread::sleep_for(std::chrono::milliseconds(500));
    }
    else if (command == "rssi") {
        if (argc < 3) return 1;
        int rssi = ble.getRSSI(argv[2]);
        std::cout << "{\"rssi\": " << rssi << "}" << std::endl;
    }
    else if (command == "mtu") {
        if (argc < 4) return 1;
        bool success = ble.setMTU(argv[2], std::stoi(argv[3]));
        std::cout << "{\"success\": " << (success ? "true" : "false") << "}" << std::endl;
    }
    else {
        printUsage();
        return 1;
    }

    return 0;
}
