#ifndef SIGNAL_H
#define SIGNAL_H

#include <vector>
#include <complex>
#include <cmath>

namespace hybrid_math {

class SignalProcessing {
public:
    using Complex = std::complex<double>;

    // Cooley-Tukey FFT algorithm
    static void fft(std::vector<Complex>& a, bool invert) {
        int n = a.size();
        for (int i = 1, j = 0; i < n; i++) {
            int bit = n >> 1;
            for (; j & bit; bit >>= 1) j ^= bit;
            j ^= bit;
            if (i < j) swap(a[i], a[j]);
        }

        for (int len = 2; len <= n; len <<= 1) {
            double ang = 2 * M_PI / len * (invert ? -1 : 1);
            Complex wlen(cos(ang), sin(ang));
            for (int i = 0; i < n; i += len) {
                Complex w(1);
                for (int j = 0; j < len / 2; j++) {
                    Complex u = a[i + j], v = a[i + j + len / 2] * w;
                    a[i + j] = u + v;
                    a[i + j + len / 2] = u - v;
                    w *= wlen;
                }
            }
        }

        if (invert) {
            for (Complex& x : a) x /= n;
        }
    }

    static std::vector<double> convolve(const std::vector<double>& a, const std::vector<double>& b) {
        std::vector<Complex> fa(a.begin(), a.end()), fb(b.begin(), b.end());
        size_t n = 1;
        while (n < a.size() + b.size()) n <<= 1;
        fa.resize(n);
        fb.resize(n);

        fft(fa, false);
        fft(fb, false);
        for (size_t i = 0; i < n; i++) fa[i] *= fb[i];
        fft(fa, true);

        std::vector<double> result(n);
        for (size_t i = 0; i < n; i++) result[i] = fa[i].real();
        return result;
    }
};

} // namespace hybrid_math

#endif
