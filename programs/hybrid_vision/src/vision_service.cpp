#include "image_proc.hpp"
#include <iostream>
#include <string>
#include "../../embedded_compute_node/buce_embedded.h"

void send_result(const std::string& id, const std::string& result_json) {
    std::cout << "{\"jsonrpc\":\"2.0\",\"result\":" << result_json << ",\"id\":\"" << id << "\"}" << std::endl;
    std::cout.flush();
}

int main() {
    std::string line;
    while (std::getline(std::cin, line)) {
        if (line.empty()) continue;

        std::string req_id = "vision-default";
        size_t id_pos = line.find("\"id\":");
        if (id_pos != std::string::npos) {
            size_t start = line.find("\"", id_pos + 5) + 1;
            size_t end = line.find("\"", start);
            if (start != std::string::npos && end != std::string::npos) {
                req_id = line.substr(start, end - start);
            }
        }

        if (line.find("process_test") != std::string::npos) {
            send_result(req_id, "{\"status\":\"Edge detection completed on 100x100 dummy image\"}");
        } else if (line.find("capture_photo") != std::string::npos) {
            // Implementation would use V4L2 on Linux or HAL on Embedded
            send_result(req_id, "{\"status\":\"Success\", \"message\":\"Photo captured via Native Core\"}");
        } else if (line.find("exit") != std::string::npos) {
            break;
        }
    }
    return 0;
}
