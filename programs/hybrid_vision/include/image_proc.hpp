#ifndef IMAGE_PROC_HPP
#define IMAGE_PROC_HPP

#include <vector>
#include <cstdint>
#include <cmath>

namespace hybrid_vision {

struct Pixel {
    uint8_t r, g, b;
};

class Image {
public:
    int width, height;
    std::vector<Pixel> data;

    Image(int w, int h) : width(w), height(h), data(w * h, {0, 0, 0}) {}

    // Grayscale conversion
    void to_grayscale(std::vector<uint8_t>& gray) const {
        gray.resize(width * height);
        for (size_t i = 0; i < data.size(); ++i) {
            gray[i] = static_cast<uint8_t>(0.299 * data[i].r + 0.587 * data[i].g + 0.114 * data[i].b);
        }
    }

    // Sobel edge detection (pure implementation)
    void sobel_edges(std::vector<uint8_t>& edges) const {
        std::vector<uint8_t> gray;
        to_grayscale(gray);
        edges.assign(width * height, 0);

        int gx[3][3] = {{-1, 0, 1}, {-2, 0, 2}, {-1, 0, 1}};
        int gy[3][3] = {{-1, -2, -1}, {0, 0, 0}, {1, 2, 1}};

        for (int y = 1; y < height - 1; ++y) {
            for (int x = 1; x < width - 1; ++x) {
                int sum_x = 0, sum_y = 0;
                for (int i = -1; i <= 1; ++i) {
                    for (int j = -1; j <= 1; ++j) {
                        int val = gray[(y + i) * width + (x + j)];
                        sum_x += val * gx[i + 1][j + 1];
                        sum_y += val * gy[i + 1][j + 1];
                    }
                }
                int mag = std::sqrt(sum_x * sum_x + sum_y * sum_y);
                edges[y * width + x] = mag > 255 ? 255 : mag;
            }
        }
    }
};

} // namespace hybrid_vision

#endif
