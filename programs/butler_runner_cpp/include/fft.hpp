#ifndef FFT_HPP
#define FFT_HPP

#include <vector>
#include <complex>
#include <cmath>

#ifndef M_PI
#define M_PI 3.14159265358979323846
#endif

class FFT {
public:
    static void compute(std::vector<std::complex<double>>& data) {
        size_t n = data.size();
        if (n <= 1) return;

        std::vector<std::complex<double>> even(n / 2);
        std::vector<std::complex<double>> odd(n / 2);
        for (size_t i = 0; i < n / 2; ++i) {
            even[i] = data[2 * i];
            odd[i] = data[2 * i + 1];
        }

        compute(even);
        compute(odd);

        for (size_t k = 0; k < n / 2; ++k) {
            std::complex<double> t = std::exp(std::complex<double>(0, -2 * M_PI * k / n)) * odd[k];
            data[k] = even[k] + t;
            data[k + n / 2] = even[k] - t;
        }
    }

    static std::vector<double> get_spectrum(const std::vector<float>& samples, size_t bands) {
        size_t n = samples.size();
        size_t m = 1;
        while (m < n) m <<= 1;

        std::vector<std::complex<double>> data(m, 0);
        for (size_t i = 0; i < n; ++i) {
            double window = 0.5 * (1 - cos(2 * M_PI * i / (n - 1)));
            data[i] = std::complex<double>(samples[i] * window, 0);
        }

        compute(data);

        std::vector<double> spectrum(bands, 0);
        size_t bin_per_band = (m / 2) / bands;
        if (bin_per_band == 0) bin_per_band = 1;

        for (size_t i = 0; i < bands; ++i) {
            double sum = 0;
            for (size_t j = 0; j < bin_per_band; ++j) {
                size_t idx = i * bin_per_band + j;
                if (idx < m / 2) {
                    sum += std::abs(data[idx]);
                }
            }
            spectrum[i] = sum / bin_per_band;
        }
        return spectrum;
    }
};

#endif
