#include <iostream>
#include <string>
#include <vector>
#include <sstream>
#include "kernels.hpp"
#include "dispatcher.hpp"

#include <stdexcept>

// Lightweight JSON Helper (More Robust)
std::string get_json_val(const std::string& json, const std::string& key) {
    std::string k = "\"" + key + "\"";
    size_t pos = json.find(k);
    if (pos == std::string::npos) return "";

    pos = json.find(":", pos + k.length());
    if (pos == std::string::npos) return "";
    pos++;

    while (pos < json.length() && (std::isspace(json[pos]))) pos++;

    if (pos < json.length() && json[pos] == '\"') {
        pos++;
        size_t end = json.find("\"", pos);
        if (end == std::string::npos) return "";
        return json.substr(pos, end - pos);
    } else {
        size_t end = json.find_first_of(",}", pos);
        if (end == std::string::npos) return json.substr(pos);
        std::string val = json.substr(pos, end - pos);
        // Trim trailing spaces
        while(!val.empty() && std::isspace(val.back())) val.pop_back();
        return val;
    }
}

void send_error(const std::string& id, int code, const std::string& msg) {
    std::cout << "{\"jsonrpc\":\"2.0\",\"error\":{\"code\":" << code << ",\"message\":\"" << msg << "\"},\"id\":\"" << id << "\"}" << std::endl;
}

int main() {
    buce::TaskDispatcher dispatcher;
    std::string line;

    while (std::getline(std::cin, line)) {
        try {
            if (line.empty()) continue;

            std::string method = get_json_val(line, "method");
            std::string id = get_json_val(line, "id");
            if (id.empty()) id = "null";

            if (method == "stress") {
                std::string dur_str = get_json_val(line, "duration");
                int duration = dur_str.empty() ? 10 : std::stoi(dur_str);
            // Launch many mandelbrot tasks to stress the CPU
            for (int i = 0; i < 1000; ++i) {
                dispatcher.enqueue([]() {
                    for(int j=0; j<100000; ++j) {
                        buce::Kernels::mandelbrot(0.1f, 0.2f, 1000);
                    }
                });
            }
            std::cout << "{\"jsonrpc\":\"2.0\",\"result\":\"Stress test initiated\",\"id\":\"" << id << "\"}" << std::endl;
        }
        else if (method == "doc_scan") {
            std::string text = get_json_val(line, "text");
            std::string pattern_raw = get_json_val(line, "patterns"); // Expecting comma separated for simplicity in manual parser

            std::vector<std::string> patterns;
            std::stringstream ss(pattern_raw);
            std::string p;
            while(std::getline(ss, p, ',')) {
                if(!p.empty()) patterns.push_back(p);
            }

            auto future = dispatcher.enqueue([text, patterns]() {
                return buce::Kernels::multi_match(text, patterns);
            });

            auto results = future.get();
            std::cout << "{\"jsonrpc\":\"2.0\",\"result\":[";
            for(size_t i=0; i<results.size(); ++i) {
                std::cout << "{\"pattern\":\"" << results[i].pattern << "\",\"count\":" << results[i].count << "}" << (i == results.size()-1 ? "" : ",");
            }
            std::cout << "],\"id\":\"" << id << "\"}" << std::endl;
        }
        else if (method == "vector_add") {
            size_t n = 1000000;
            std::vector<float> a(n, 1.0f), b(n, 2.0f), c(n);
            auto future = dispatcher.enqueue([&]() {
                buce::Kernels::vector_add(a.data(), b.data(), c.data(), n);
                return c[0]; // just return first element for verification
            });
            std::cout << "{\"jsonrpc\":\"2.0\",\"result\":{\"first_val\":" << future.get() << "},\"id\":\"" << id << "\"}" << std::endl;
        }
        else if (method == "crypto_bench") {
            auto future = dispatcher.enqueue([]() {
                uint32_t in[16] = {0}, out[16];
                for(int i=0; i<1000000; ++i) {
                    buce::Kernels::chacha20_block(out, in);
                    in[0]++;
                }
                return out[0];
            });
            std::cout << "{\"jsonrpc\":\"2.0\",\"result\":{\"val\":" << future.get() << "},\"id\":\"" << id << "\"}" << std::endl;
        }
        else if (method == "pi_calc") {
            long long iters = std::stoll(get_json_val(line, "iterations"));
            int threads = std::thread::hardware_concurrency();
            std::vector<std::future<long long>> futures;
            for(int i=0; i<threads; ++i) {
                futures.push_back(dispatcher.enqueue([iters, threads]() {
                    return buce::Kernels::monte_carlo_pi_part(iters / threads);
                }));
            }
            long long total_inside = 0;
            for(auto& f : futures) total_inside += f.get();
            double pi = 4.0 * total_inside / iters;
            std::cout << "{\"jsonrpc\":\"2.0\",\"result\":{\"pi\":" << pi << "},\"id\":\"" << id << "\"}" << std::endl;
        }
        else if (method == "exit") {
            break;
        }
        else {
            send_error(id, -32601, "Method not found");
        }
        } catch (const std::exception& e) {
            std::cout << "{\"jsonrpc\":\"2.0\",\"error\":{\"code\":-32700,\"message\":\"Parse error or execution failed: " << e.what() << "\"},\"id\":\"null\"}" << std::endl;
        }
    }

    return 0;
}
