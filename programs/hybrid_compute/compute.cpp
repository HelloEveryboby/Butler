#include <iostream>
#include <string>
#include <vector>
#include <sstream>
#include <cmath>
#include <algorithm>

// A very simple "manual" JSON parser for BHL Protocol (PC/MCU compatible style)
// For a real production system, use a library like nlohmann/json or RapidJSON.

std::string get_json_value(const std::string& json, const std::string& key) {
    // Robust search for "key":
    std::string search_key = "\"" + key + "\"";
    size_t pos = 0;
    while ((pos = json.find(search_key, pos)) != std::string::npos) {
        size_t after_key = pos + search_key.length();
        // Skip whitespace
        while (after_key < json.length() && std::isspace(json[after_key])) after_key++;

        if (after_key < json.length() && json[after_key] == ':') {
            pos = after_key + 1;
            goto found;
        }
        pos += search_key.length();
    }
    return "";

found:
    // Skip spaces
    while (pos < json.length() && std::isspace(json[pos])) pos++;

    if (pos < json.length() && json[pos] == '\"') {
        // String value
        pos++;
        size_t end = json.find('\"', pos);
        if (end == std::string::npos) return "";
        return json.substr(pos, end - pos);
    } else {
        // Numeric or other value
        size_t end = json.find_first_of(",} ", pos);
        if (end == std::string::npos) end = json.length();
        return json.substr(pos, end - pos);
    }
}

std::vector<long long> factorize(long long n) {
    std::vector<long long> factors;
    while (n % 2 == 0) {
        factors.push_back(2);
        n /= 2;
    }
    for (long long i = 3; i <= std::sqrt(n); i += 2) {
        while (n % i == 0) {
            factors.push_back(i);
            n /= i;
        }
    }
    if (n > 2) factors.push_back(n);
    return factors;
}

void process_request(const std::string& line) {
    std::string method = get_json_value(line, "method");
    std::string id = get_json_value(line, "id");

    if (method == "factorize") {
        std::string number_str = get_json_value(line, "number");
        if (number_str.empty()) {
             std::cout << "{\"jsonrpc\":\"2.0\",\"error\":{\"code\":-1,\"message\":\"Missing number\"},\"id\":\"" << id << "\"}" << std::endl;
             return;
        }

        long long n = std::stoll(number_str);
        std::vector<long long> factors = factorize(n);

        std::stringstream ss;
        ss << "{\"jsonrpc\":\"2.0\",\"result\":{\"factors\":[";
        for (size_t i = 0; i < factors.size(); ++i) {
            ss << factors[i] << (i == factors.size() - 1 ? "" : ",");
        }
        ss << "],\"count\":" << factors.size() << "},\"id\":\"" << id << "\"}";
        std::cout << ss.str() << std::endl;
    } else if (method == "exit") {
        std::exit(0);
    } else {
        std::cout << "{\"jsonrpc\":\"2.0\",\"error\":{\"code\":-32601,\"message\":\"Method not found\"},\"id\":\"" << id << "\"}" << std::endl;
    }
}

int main() {
    std::string line;
    while (std::getline(std::cin, line)) {
        if (line.empty()) continue;
        process_request(line);
    }
    return 0;
}
