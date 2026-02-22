#include <iostream>
#include <vector>
#include <string>

// Simple prime factorization
std::vector<long long> factorize(long long n) {
    std::vector<long long> factors;
    for (long long i = 2; i * i <= n; i++) {
        while (n % i == 0) {
            factors.push_back(i);
            n /= i;
        }
    }
    if (n > 1) factors.push_back(n);
    return factors;
}

int main() {
    std::string line;
    while (std::getline(std::cin, line)) {
        if (line.empty()) continue;
        // Manual JSON parsing for the simple "factorize" method
        if (line.find("\"method\":\"factorize\"") != std::string::npos) {
            size_t pos = line.find("[");
            if (pos != std::string::npos) {
                long long n = std::stoll(line.substr(pos + 1));
                auto factors = factorize(n);

                std::cout << "{\"jsonrpc\":\"2.0\",\"result\":[";
                for (size_t i = 0; i < factors.size(); ++i) {
                    std::cout << factors[i] << (i == factors.size() - 1 ? "" : ",");
                }
                std::cout << "],\"id\":null}" << std::endl;
            }
        } else if (line.find("\"method\":\"exit\"") != std::string::npos) {
            break;
        }
    }
    return 0;
}
