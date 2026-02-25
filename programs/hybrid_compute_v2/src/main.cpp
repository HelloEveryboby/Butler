#include <iostream>
#include <string>
#include <vector>
#include <sstream>
#include <fstream>
#include <stdexcept>
#include <chrono>
#include <map>
#include <memory>
#include <functional>
#include <algorithm>
#include "kernels.hpp"
#include "dispatcher.hpp"

namespace buce {

// Security Constants
constexpr size_t MAX_INPUT_LINE = 10 * 1024 * 1024; // 10MB

/**
 * @brief Simple & Secure JSON Parser for BHL Protocol
 */
struct ProtocolUtils {
    static std::string get_val(const std::string& json, const std::string& key) {
        if (json.length() > MAX_INPUT_LINE) throw std::runtime_error("Line too long");
        std::string k = "\"" + key + "\"";
        size_t pos = json.find(k);
        if (pos == std::string::npos) return "";
        pos = json.find(":", pos + k.length());
        if (pos == std::string::npos) return "";
        pos++;
        while (pos < json.length() && std::isspace(json[pos])) pos++;
        if (pos < json.length() && json[pos] == '\"') {
            pos++;
            size_t end = json.find("\"", pos);
            return (end == std::string::npos) ? "" : json.substr(pos, end - pos);
        } else {
            size_t end = json.find_first_of(",}", pos);
            std::string val = (end == std::string::npos) ? json.substr(pos) : json.substr(pos, end - pos);
            while (!val.empty() && std::isspace(val.back())) val.pop_back();
            return val;
        }
    }

    static void send_response(const std::string& id, const std::string& result_json) {
        std::cout << "{\"jsonrpc\":\"2.0\",\"result\":" << result_json << ",\"id\":\"" << id << "\"}" << std::endl;
    }

    static void send_error(const std::string& id, int code, const std::string& msg) {
        std::cout << "{\"jsonrpc\":\"2.0\",\"error\":{\"code\":" << code << ",\"message\":\"" << msg << "\"},\"id\":\"" << id << "\"}" << std::endl;
    }
};

/**
 * @brief BUCE Compute Engine - Logic Controller
 */
class ComputeEngine {
public:
    ComputeEngine() : dispatcher(std::thread::hardware_concurrency()) {
        register_commands();
    }

    void run() {
        std::cin.tie(NULL);
        std::ios_base::sync_with_stdio(false);
        std::string line;
        while (std::getline(std::cin, line)) {
            if (line.empty()) continue;
            process_line(line);
        }
    }

private:
    TaskDispatcher dispatcher;
    using CommandHandler = std::function<void(const std::string&, const std::string&)>;
    std::map<std::string, CommandHandler> commands;

    void register_commands() {
        commands["stress"] = [this](const std::string& id, const std::string& line) {
            std::string dur_str = ProtocolUtils::get_val(line, "duration");
            int sec = dur_str.empty() ? 5 : std::clamp(std::stoi(dur_str), 1, 3600);
            int cores = std::thread::hardware_concurrency();
            for (int i = 0; i < cores; ++i) {
                dispatcher.enqueue([sec]() {
                    auto start = std::chrono::steady_clock::now();
                    while (std::chrono::duration_cast<std::chrono::seconds>(std::chrono::steady_clock::now() - start).count() < sec) {
                        Kernels::mandelbrot(0.1f, 0.2f, 500);
                    }
                });
            }
            ProtocolUtils::send_response(id, "\"Stress test started for " + std::to_string(sec) + "s\"");
        };

        commands["doc_scan"] = [this](const std::string& id, const std::string& line) {
            std::string path = ProtocolUtils::get_val(line, "file_path");
            std::string pat_raw = ProtocolUtils::get_val(line, "patterns");
            if (path.empty()) { ProtocolUtils::send_error(id, -32602, "Missing file_path"); return; }

            auto f = dispatcher.enqueue([path, pat_raw]() {
                std::ifstream file(path);
                if (!file) throw std::runtime_error("Open failed: " + path);
                std::string text((std::istreambuf_iterator<char>(file)), std::istreambuf_iterator<char>());
                std::vector<std::string> pats;
                std::stringstream ss(pat_raw);
                std::string p;
                while (std::getline(ss, p, ',')) if (!p.empty()) pats.push_back(p);
                return Kernels::multi_match(text, pats);
            });

            auto res = f.get();
            std::stringstream oss; oss << "[";
            for (size_t i = 0; i < res.size(); ++i) {
                oss << "{\"pattern\":\"" << res[i].pattern << "\",\"count\":" << res[i].count << "}" << (i == res.size() - 1 ? "" : ",");
            }
            oss << "]";
            ProtocolUtils::send_response(id, oss.str());
        };

        commands["pi_calc"] = [this](const std::string& id, const std::string& line) {
            std::string it_str = ProtocolUtils::get_val(line, "iterations");
            long long total_it = it_str.empty() ? 1000000 : std::clamp(std::stoll(it_str), 1LL, 1000000000LL);
            int cores = std::thread::hardware_concurrency();
            std::vector<std::future<long long>> futures;
            for (int i = 0; i < cores; ++i) {
                futures.push_back(dispatcher.enqueue([total_it, cores]() { return Kernels::monte_carlo_pi_part(total_it / cores); }));
            }
            long long inside = 0;
            for (auto& fut : futures) inside += fut.get();
            ProtocolUtils::send_response(id, "{\"pi\":" + std::to_string(4.0 * inside / total_it) + "}");
        };

        commands["vector_add"] = [this](const std::string& id, const std::string& line) {
            auto f = dispatcher.enqueue([]() {
                size_t n = 1000000;
                std::vector<float> a(n, 1.1f), b(n, 2.2f), c(n);
                Kernels::vector_add(a.data(), b.data(), c.data(), n);
                return c[0];
            });
            ProtocolUtils::send_response(id, "{\"first_val\":" + std::to_string(f.get()) + "}");
        };

        commands["crypto_bench"] = [this](const std::string& id, const std::string& line) {
            auto f = dispatcher.enqueue([]() {
                uint32_t in[16] = {0}, out[16];
                for (int i = 0; i < 1000000; ++i) { Kernels::chacha20_block(out, in); in[0]++; }
                return out[0];
            });
            ProtocolUtils::send_response(id, "{\"val\":" + std::to_string(f.get()) + "}");
        };

        commands["exit"] = [](const std::string& id, const std::string& line) { std::exit(0); };
    }

    void process_line(const std::string& line) {
        try {
            std::string method = ProtocolUtils::get_val(line, "method");
            std::string id = ProtocolUtils::get_val(line, "id");
            if (id.empty()) id = "null";
            if (commands.count(method)) {
                commands[method](id, line);
            } else {
                ProtocolUtils::send_error(id, -32601, "Method not found: " + method);
            }
        } catch (const std::exception& e) {
            ProtocolUtils::send_error("null", -32000, std::string("Engine Error: ") + e.what());
        }
    }
};

} // namespace buce

int main() {
    try {
        buce::ComputeEngine engine;
        engine.run();
    } catch (...) {
        return 1;
    }
    return 0;
}
