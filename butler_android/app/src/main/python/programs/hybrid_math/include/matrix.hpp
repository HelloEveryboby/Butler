#ifndef MATRIX_H
#define MATRIX_H

#include <vector>
#include <iostream>
#include <stdexcept>
#include <cmath>

namespace hybrid_math {

class Matrix {
public:
    int rows, cols;
    std::vector<double> data;

    Matrix(int r, int c) : rows(r), cols(c), data(r * c, 0.0) {}

    double& operator()(int r, int c) {
        if (r < 0 || r >= rows || c < 0 || c >= cols) throw std::out_of_range("Matrix index out of bounds");
        return data[r * cols + c];
    }

    const double& operator()(int r, int c) const {
        if (r < 0 || r >= rows || c < 0 || c >= cols) throw std::out_of_range("Matrix index out of bounds");
        return data[r * cols + c];
    }

    static Matrix identity(int n) {
        Matrix res(n, n);
        for (int i = 0; i < n; ++i) res(i, i) = 1.0;
        return res;
    }

    Matrix transpose() const {
        Matrix res(cols, rows);
        for (int i = 0; i < rows; ++i)
            for (int j = 0; j < cols; ++j)
                res(j, i) = (*this)(i, j);
        return res;
    }

    Matrix operator+(const Matrix& other) const {
        if (rows != other.rows || cols != other.cols) throw std::invalid_argument("Matrix dimensions mismatch");
        Matrix res(rows, cols);
        for (size_t i = 0; i < data.size(); ++i) res.data[i] = data[i] + other.data[i];
        return res;
    }

    Matrix operator*(const Matrix& other) const {
        if (cols != other.rows) throw std::invalid_argument("Matrix multiplication dimensions mismatch");
        Matrix res(rows, other.cols);
        for (int i = 0; i < rows; ++i)
            for (int k = 0; k < cols; ++k)
                for (int j = 0; j < other.cols; ++j)
                    res(i, j) += (*this)(i, k) * other(k, j);
        return res;
    }

    // LU Decomposition for solving linear systems
    void lu_decomposition(Matrix& L, Matrix& U) const {
        if (rows != cols) throw std::invalid_argument("Square matrix required for LU");
        int n = rows;
        L = Matrix(n, n);
        U = Matrix(n, n);
        for (int i = 0; i < n; i++) {
            for (int k = i; k < n; k++) {
                double sum = 0;
                for (int j = 0; j < i; j++) sum += (L(i, j) * U(j, k));
                U(i, k) = (*this)(i, k) - sum;
            }
            for (int k = i; k < n; k++) {
                if (i == k) L(i, i) = 1;
                else {
                    double sum = 0;
                    for (int j = 0; j < i; j++) sum += (L(k, j) * U(j, i));
                    L(k, i) = ((*this)(k, i) - sum) / U(i, i);
                }
            }
        }
    }
};

} // namespace hybrid_math

#endif
