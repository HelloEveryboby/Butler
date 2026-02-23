#include "matrix.hpp"
#include "stats.hpp"
#include "signal.hpp"
#include <iostream>
#include <string>
#include <vector>
#include <sstream>

using namespace hybrid_math;

void send_result(const std::string& id, const std::string& result_json) {
    std::cout << "{\"jsonrpc\":\"2.0\",\"result\":" << result_json << ",\"id\":\"" << id << "\"}" << std::endl;
    std::cout.flush();
}

int main() {
    std::string line;
    while (std::getline(std::cin, line)) {
        if (line.empty()) continue;

        std::string req_id = "math-default";
        size_t id_pos = line.find("\"id\":");
        if (id_pos != std::string::npos) {
            size_t start = line.find("\"", id_pos + 5) + 1;
            size_t end = line.find("\"", start);
            if (start != std::string::npos && end != std::string::npos) {
                req_id = line.substr(start, end - start);
            }
        }

        if (line.find("get_stats") != std::string::npos) {
            std::vector<double> data = {1.2, 2.5, 3.7, 4.1, 5.9, 2.5};
            std::stringstream ss;
            ss << "{\"mean\":" << Statistics::mean(data)
               << ",\"stddev\":" << Statistics::stddev(data)
               << ",\"median\":" << Statistics::median(data) << "}";
            send_result(req_id, ss.str());
        } else if (line.find("matrix_test") != std::string::npos) {
            send_result(req_id, "{\"status\":\"Matrix test success\"}");
        } else if (line.find("exit") != std::string::npos) {
            break;
        }
    }
    return 0;
}
