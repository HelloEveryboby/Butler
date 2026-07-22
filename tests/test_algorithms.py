"""
Butler 核心算法测试

覆盖 algorithms.py 中的排序、搜索、路径算法。
"""

import pytest
from butler.core.algorithms import (
    quick_sort,
    merge_sort,
    heap_sort,
    binary_search,
    a_star,
)


# ==========================================
# 排序算法
# ==========================================

class TestQuickSort:
    """内省排序 (Introsort)"""

    def test_empty(self):
        assert quick_sort([]) == []

    def test_single(self):
        assert quick_sort([1]) == [1]

    def test_sorted(self):
        assert quick_sort([1, 2, 3, 4, 5]) == [1, 2, 3, 4, 5]

    def test_reverse(self):
        assert quick_sort([5, 4, 3, 2, 1]) == [1, 2, 3, 4, 5]

    def test_duplicates(self):
        assert quick_sort([3, 1, 4, 1, 5, 9, 2, 6, 5, 3]) == [1, 1, 2, 3, 3, 4, 5, 5, 6, 9]

    def test_negative(self):
        assert quick_sort([-3, -1, -4, 0, 2]) == [-4, -3, -1, 0, 2]

    def test_large(self):
        import random
        arr = random.sample(range(10000), 1000)
        result = quick_sort(arr)
        assert result == sorted(arr)

    def test_does_not_mutate_input(self):
        original = [3, 1, 2]
        copy = list(original)
        quick_sort(original)
        assert original == copy

    def test_progress_bar(self):
        result = quick_sort([3, 1, 2], use_progress_bar=True)
        assert result == [1, 2, 3]


class TestMergeSort:
    """归并排序"""

    def test_empty(self):
        assert merge_sort([]) == []

    def test_single(self):
        assert merge_sort([42]) == [42]

    def test_basic(self):
        assert merge_sort([38, 27, 43, 3, 9, 82, 10]) == [3, 9, 10, 27, 38, 43, 82]

    def test_stable(self):
        """归并排序是稳定的"""
        # 用 (value, original_index) 验证稳定性
        arr = [(3, 'a'), (1, 'b'), (3, 'c'), (2, 'd')]
        result = merge_sort(arr)
        # 相同值的元素应保持原始顺序
        assert result[0] == (1, 'b')
        assert result[1] == (2, 'd')
        assert result[2] == (3, 'a')  # a 在 c 之前
        assert result[3] == (3, 'c')


class TestHeapSort:
    """堆排序"""

    def test_empty(self):
        assert heap_sort([]) == []

    def test_single(self):
        assert heap_sort([1]) == [1]

    def test_basic(self):
        assert heap_sort([12, 11, 13, 5, 6, 7]) == [5, 6, 7, 11, 12, 13]

    def test_all_same(self):
        assert heap_sort([5, 5, 5, 5]) == [5, 5, 5, 5]

    def test_large(self):
        import random
        arr = random.sample(range(5000), 500)
        result = heap_sort(arr)
        assert result == sorted(arr)


class TestSortConsistency:
    """三种排序结果一致"""

    @pytest.mark.parametrize("arr", [
        [],
        [1],
        [3, 1, 2],
        [5, 4, 3, 2, 1],
        [1, 2, 3, 4, 5],
        [3, 3, 1, 1, 2, 2],
        [-5, 0, 3, -1, 2],
    ])
    def test_all_sorts_agree(self, arr):
        assert quick_sort(arr) == merge_sort(arr) == heap_sort(arr) == sorted(arr)


# ==========================================
# 搜索算法
# ==========================================

class TestBinarySearch:
    """二分查找"""

    def test_found(self):
        assert binary_search([1, 2, 3, 4, 5], 3) == 2

    def test_not_found(self):
        assert binary_search([1, 2, 3, 4, 5], 6) == -1

    def test_first_element(self):
        assert binary_search([1, 2, 3], 1) == 0

    def test_last_element(self):
        assert binary_search([1, 2, 3], 3) == 2

    def test_empty(self):
        assert binary_search([], 1) == -1

    def test_single_found(self):
        assert binary_search([5], 5) == 0

    def test_single_not_found(self):
        assert binary_search([5], 3) == -1


# ==========================================
# 路径算法
# ==========================================

class TestAStar:
    """A* 最短路径"""

    def test_simple_path(self):
        graph = {
            'A': {'B': 1, 'C': 4},
            'B': {'A': 1, 'D': 2, 'C': 1},
            'C': {'A': 4, 'B': 1, 'D': 3},
            'D': {'B': 2, 'C': 3},
        }
        heuristic = lambda a, b: 0  # Dijkstra 特例
        path = a_star(graph, 'A', 'D', heuristic)
        assert path is not None
        assert path[0] == 'A'
        assert path[-1] == 'D'

    def test_no_path(self):
        graph = {
            'A': {'B': 1},
            'B': {'A': 1},
            'C': {'D': 1},
            'D': {'C': 1},
        }
        heuristic = lambda a, b: 0
        path = a_star(graph, 'A', 'D', heuristic)
        assert path is None

    def test_start_equals_goal(self):
        graph = {'A': {'B': 1}, 'B': {'A': 1}}
        heuristic = lambda a, b: 0
        path = a_star(graph, 'A', 'A', heuristic)
        assert path == ['A']

    def test_optimal_path(self):
        graph = {
            'A': {'B': 1, 'C': 10},
            'B': {'A': 1, 'C': 2},
            'C': {'A': 10, 'B': 2},
        }
        heuristic = lambda a, b: 0
        path = a_star(graph, 'A', 'C', heuristic)
        # A -> B -> C (cost 3) 比 A -> C (cost 10) 更优
        assert path == ['A', 'B', 'C']
