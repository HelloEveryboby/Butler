#include <iostream>
#include <fstream>
#include <string>
#include <vector>
#include <sstream>
#include <map>
#include <algorithm>
#include <chrono>

/**
 * BHL V2.0 Protocol Implementation for Document Processing
 * Robust version using file-based input to avoid JSON escaping issues.
 */

// Robust JSON value extraction helper (replaces manual parsing logic)
std::string get_json_value(const std::string& json, const std::string& key) {
    std::string search_key = "\"" + key + "\"";
    size_t pos = json.find(search_key);
    if (pos == std::string::npos) return "";

    size_t after_key = pos + search_key.length();
    // Move past the key and whitespace/colon
    while (after_key < json.length() && (std::isspace((unsigned char)json[after_key]) || json[after_key] == ':')) after_key++;

    if (after_key < json.length() && json[after_key] == '\"') {
        size_t start = after_key + 1;
        std::string result;
        bool escaped = false;
        // Correctly handle escaped characters within the string
        for (size_t i = start; i < json.length(); ++i) {
            char c = json[i];
            if (escaped) {
                result += c;
                escaped = false;
            } else if (c == '\\') {
                escaped = true;
            } else if (c == '\"') {
                return result;
            } else {
                result += c;
            }
        }
        return ""; // Improperly terminated string
    } else {
        // Handle numeric or boolean values
        size_t start = after_key;
        size_t end = json.find_first_of(",} ", start);
        if (end == std::string::npos) end = json.length();
        return json.substr(start, end - start);
    }
}

// Tokenizer that supports basic UTF-8 (treats non-ASCII as part of words)
std::vector<std::string> tokenize(const std::string& text) {
    std::vector<std::string> tokens;
    std::string current;
    for (size_t i = 0; i < text.length(); ++i) {
        unsigned char c = text[i];
        // ASCII Alphanumeric
        if (std::isalnum(c)) {
            current += std::tolower(c);
        }
        // Simple UTF-8 start byte (0x80 and above)
        else if (c >= 128) {
            current += (char)c;
        }
        else if (!current.empty()) {
            tokens.push_back(current);
            current.clear();
        }
    }
    if (!current.empty()) tokens.push_back(current);
    return tokens;
}

void handle_analyze_file(const std::string& line, const std::string& id) {
    std::string file_path = get_json_value(line, "file_path");
    if (file_path.empty()) {
        std::cout << "{\"jsonrpc\":\"2.0\",\"error\":{\"code\":-1,\"message\":\"Missing file_path\"},\"id\":\"" << id << "\"}" << std::endl;
        return;
    }

    auto start = std::chrono::high_resolution_clock::now();

    std::ifstream file(file_path);
    if (!file.is_open()) {
        std::cout << "{\"jsonrpc\":\"2.0\",\"error\":{\"code\":-2,\"message\":\"Could not open file\"},\"id\":\"" << id << "\"}" << std::endl;
        return;
    }

    std::stringstream buffer;
    buffer << file.rdbuf();
    std::string text = buffer.str();
    file.close();

    std::vector<std::string> tokens = tokenize(text);
    std::map<std::string, int> freq;
    for (const auto& token : tokens) {
        if (token.length() > 2) {
            freq[token]++;
        }
    }

    std::vector<std::pair<std::string, int>> sorted_freq(freq.begin(), freq.end());
    std::sort(sorted_freq.begin(), sorted_freq.end(), [](const auto& a, const auto& b) {
        if (a.second != b.second) return b.second < a.second;
        return a.first < b.first;
    });

    auto end = std::chrono::high_resolution_clock::now();
    std::chrono::duration<double, std::milli> duration = end - start;

    std::stringstream ss;
    ss << "{\"jsonrpc\":\"2.0\",\"result\":{";
    ss << "\"word_count\":" << tokens.size() << ",";
    ss << "\"unique_words\":" << freq.size() << ",";
    ss << "\"top_keywords\":[";
    for (size_t i = 0; i < std::min(sorted_freq.size(), (size_t)10); ++i) {
        // Basic JSON escaping for word
        std::string word = sorted_freq[i].first;
        size_t q_pos = 0;
        while ((q_pos = word.find('\"', q_pos)) != std::string::npos) {
            word.replace(q_pos, 1, "\\\"");
            q_pos += 2;
        }
        ss << "{\"word\":\"" << word << "\",\"count\":" << sorted_freq[i].second << "}";
        if (i < std::min(sorted_freq.size(), (size_t)10) - 1) ss << ",";
    }
    ss << "],";
    ss << "\"processing_time_ms\":" << duration.count();
    ss << "},\"id\":\"" << id << "\"}";

    std::cout << ss.str() << std::endl;
}

int main() {
    std::string line;
    while (std::getline(std::cin, line)) {
        if (line.empty()) continue;

        std::string method = get_json_value(line, "method");
        std::string id = get_json_value(line, "id");

        if (method == "analyze_file") {
            handle_analyze_file(line, id);
        } else if (method == "exit") {
            return 0;
        } else {
            std::cout << "{\"jsonrpc\":\"2.0\",\"error\":{\"code\":-32601,\"message\":\"Method not found\"},\"id\":\"" << id << "\"}" << std::endl;
        }
    }
    return 0;
}
