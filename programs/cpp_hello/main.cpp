#include <iostream>
#include <vector>

int main(int argc, char* argv[]) {
    std::cout << "Hello from C++!" << std::endl;
    if (argc > 1) {
        std::cout << "Received arguments:" << std::endl;
        for (int i = 1; i < argc; ++i) {
            std::cout << "- " << argv[i] << std::endl;
        }
    }
    return 0;
}
