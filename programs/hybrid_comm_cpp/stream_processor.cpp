#include <iostream>
#include <vector>
#include <string>
#include <thread>
#include <chrono>
#include <sstream>
#include <iomanip>
#include <cstring>
#include <sys/ipc.h>
#include <sys/shm.h>

// BHL C++ 数据处理器
// 负责大块数据的处理与转换，通过 C 层建立的共享内存总线进行交互

class DataProcessor {
public:
    DataProcessor(int shm_key) : shm_key_(shm_key) {}

    bool connect() {
        shmid_ = shmget((key_t)shm_key_, 1024 * 1024, 0666);
        if (shmid_ == -1) return false;
        shm_addr_ = shmat(shmid_, (void*)0, 0);
        return shm_addr_ != (void*)-1;
    }

    std::string process_data(const std::string& input) {
        std::stringstream ss;
        ss << "Processed[" << input.length() << " bytes]: ";
        for(size_t i=0; i < std::min(input.length(), (size_t)16); ++i) {
            ss << std::hex << std::setw(2) << std::setfill('0') << (int)(unsigned char)input[i] << " ";
        }
        return ss.str();
    }

    ~DataProcessor() {
        if (shm_addr_ && shm_addr_ != (void*)-1) {
            shmdt(shm_addr_);
        }
    }

private:
    int shm_key_;
    int shmid_;
    void* shm_addr_ = nullptr;
};

int main() {
    DataProcessor processor(0x1337);

    std::string line;
    while (std::getline(std::cin, line)) {
        if (line.empty()) continue;

        if (line.find("\"method\":\"process_stream\"") != std::string::npos) {
            // 解析 ID (简单正则式模拟)
            size_t id_pos = line.find("\"id\":\"");
            std::string msg_id = "cpp_task";
            if (id_pos != std::string::npos) {
                msg_id = line.substr(id_pos + 6);
                size_t end_quote = msg_id.find("\"");
                if (end_quote != std::string::npos) {
                    msg_id = msg_id.substr(0, end_quote);
                }
            }

            if (processor.connect()) {
                std::string result = processor.process_data("BHL_HIGH_SPEED_DATA_STREAM");
                std::cout << "{\"jsonrpc\":\"2.0\",\"result\":{\"output\":\"" << result << "\"},\"id\":\"" << msg_id << "\"}" << std::endl;
            } else {
                std::cout << "{\"jsonrpc\":\"2.0\",\"error\":{\"message\":\"bus connection failed\"},\"id\":\"" << msg_id << "\"}" << std::endl;
            }
        } else if (line.find("\"method\":\"exit\"") != std::string::npos) {
            break;
        }
    }
    return 0;
}
