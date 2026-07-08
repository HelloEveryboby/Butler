#ifndef STATS_H
#define STATS_H

#include <vector>
#include <numeric>
#include <cmath>
#include <algorithm>
#include <map>

namespace hybrid_math {

class Statistics {
public:
    static double mean(const std::vector<double>& data) {
        if (data.empty()) return 0.0;
        return std::accumulate(data.begin(), data.end(), 0.0) / data.size();
    }

    static double variance(const std::vector<double>& data) {
        if (data.size() < 2) return 0.0;
        double avg = mean(data);
        double sum_sq = 0.0;
        for (double x : data) sum_sq += (x - avg) * (x - avg);
        return sum_sq / (data.size() - 1);
    }

    static double stddev(const std::vector<double>& data) {
        return std::sqrt(variance(data));
    }

    static double median(std::vector<double> data) {
        if (data.empty()) return 0.0;
        std::sort(data.begin(), data.end());
        size_t n = data.size();
        if (n % 2 == 0) return (data[n/2 - 1] + data[n/2]) / 2.0;
        else return data[n/2];
    }

    static std::vector<double> mode(const std::vector<double>& data) {
        if (data.empty()) return {};
        std::map<double, int> counts;
        for (double x : data) counts[x]++;
        int max_count = 0;
        for (auto const& [val, count] : counts) if (count > max_count) max_count = count;
        std::vector<double> modes;
        for (auto const& [val, count] : counts) if (count == max_count) modes.push_back(val);
        return modes;
    }
};

} // namespace hybrid_math

#endif
