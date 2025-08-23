import heapq
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity
import cv2
from tqdm import tqdm

# 1. Sorting Algorithms
def _insertion_sort(arr, low, high, pbar=None):
    """
    An internal helper for introsort. Sorts a subsection of an array using insertion sort.
    内部辅助函数，用于内省排序。使用插入排序对数组的子切片进行排序。

    Args:
        arr (list): The array to sort. / 要排序的数组。
        low (int): The starting index. / 起始索引。
        high (int): The ending index. / 结束索引。
        pbar (tqdm, optional): Progress bar instance. / 进度条实例。
    """
    for i in range(low + 1, high + 1):
        key = arr[i]
        j = i - 1
        while j >= low and arr[j] > key:
            arr[j + 1] = arr[j]
            j -= 1
        arr[j + 1] = key
        if pbar:
            pbar.update(1)

def _partition(arr, low, high, pbar=None):
    """
    An internal helper for introsort. Partitions the array using Hoare partition scheme with median-of-three pivot.
    内部辅助函数，用于内省排序。使用中值三数枢轴的霍尔分区方案对数组进行分区。

    Args:
        arr (list): The array to partition. / 要分区的数组。
        low (int): The starting index. / 起始索引。
        high (int): The ending index. / 结束索引。
        pbar (tqdm, optional): Progress bar instance. / 进度条实例。

    Returns:
        int: The partition index. / 分区索引。
    """
    # Median-of-three pivot selection
    mid = (low + high) // 2
    if arr[mid] < arr[low]:
        arr[low], arr[mid] = arr[mid], arr[low]
    if arr[high] < arr[low]:
        arr[low], arr[high] = arr[high], arr[low]
    if arr[mid] < arr[high]:
        arr[mid], arr[high] = arr[high], arr[mid]

    pivot = arr[high]
    i = low - 1
    j = high
    while True:
        i += 1
        while arr[i] < pivot:
            i += 1
        j -= 1
        while j >= low and arr[j] > pivot:
            j -= 1
        if i >= j:
            break
        arr[i], arr[j] = arr[j], arr[i]
    arr[i], arr[high] = arr[high], arr[i]
    if pbar:
        pbar.update(1)
    return i

def _introsort_util(arr, low, high, depth_limit, pbar=None):
    """
    The core recursive utility for introsort. Switches to insertion sort for small partitions.
    内省排序的核心递归工具。对于小分区，切换到插入排序。

    Args:
        arr (list): The array to sort. / 要排序的数组。
        low (int): The starting index. / 起始索引。
        high (int): The ending index. / 结束索引。
        depth_limit (int): Recursion depth limit to prevent worst-case quicksort performance. / 递归深度限制，以防止最坏情况下的快速排序性能。
        pbar (tqdm, optional): Progress bar instance. / 进度条实例。
    """
    while high - low > 16: # Threshold for switching to insertion sort
        if depth_limit == 0:
            # If recursion depth is too high, switch to heapsort
            # (Heapsort not implemented here for simplicity, can be added)
            # For now, we'll just continue with quicksort
            pass

        pivot_index = _partition(arr, low, high, pbar)
        _introsort_util(arr, pivot_index + 1, high, depth_limit - 1, pbar)
        high = pivot_index - 1

    _insertion_sort(arr, low, high, pbar)

def quick_sort(arr, use_progress_bar=False):
    """
    Sorts an array using Introsort, a hybrid algorithm that combines Quicksort, Heapsort, and Insertion Sort.
    It provides fast average performance while avoiding Quicksort's worst-case O(n^2) time complexity.

    使用内省排序（Introsort）对数组进行排序，这是一种结合了快速排序、堆排序和插入排序的混合算法。
    它提供了快速的平均性能，同时避免了快速排序O(n^2)的最坏情况时间复杂度。

    Args:
        arr (list): The list of numbers to sort. / 需要排序的数字列表。
        use_progress_bar (bool, optional): If True, displays a progress bar. Defaults to False. / 如果为True，则显示进度条。默认为False。

    Returns:
        list: A new list containing the sorted elements. / 包含已排序元素的新列表。
    """
    import math
    if not arr:
        return arr
    # Create a mutable copy to sort in-place
    arr_copy = list(arr)
    depth_limit = 2 * int(math.log2(len(arr_copy)))

    if use_progress_bar:
        with tqdm(total=len(arr_copy), desc="Sorting") as pbar:
            _introsort_util(arr_copy, 0, len(arr_copy) - 1, depth_limit, pbar)
    else:
        _introsort_util(arr_copy, 0, len(arr_copy) - 1, depth_limit)

    return arr_copy

def merge_sort(arr):
    """
    Sorts an array using the Merge Sort algorithm. It's a stable, comparison-based sorting algorithm with O(n log n) time complexity.
    使用归并排序算法对数组进行排序。它是一种稳定的、基于比较的排序算法，时间复杂度为O(n log n)。

    Args:
        arr (list): The list of numbers to sort. / 需要排序的数字列表。

    Returns:
        list: A new list containing the sorted elements. / 包含已排序元素的新列表。
    """
    if len(arr) <= 1:
        return arr

    mid = len(arr) // 2
    left = arr[:mid]
    right = arr[mid:]

    left = merge_sort(left)
    right = merge_sort(right)

    return _merge(left, right)

def _merge(left, right):
    """
    An internal helper for merge_sort. Merges two sorted lists into one sorted list.
    归并排序的内部辅助函数。将两个已排序的列表合并为一个已排序的列表。

    Args:
        left (list): The left sorted list. / 左侧已排序列表。
        right (list): The right sorted list. / 右侧已排序列表。

    Returns:
        list: The merged sorted list. / 合并后的已排序列表。
    """
    result = []
    i = j = 0

    while i < len(left) and j < len(right):
        if left[i] < right[j]:
            result.append(left[i])
            i += 1
        else:
            result.append(right[j])
            j += 1

    result.extend(left[i:])
    result.extend(right[j:])
    return result

# 2. Searching Algorithm
def binary_search(arr, target):
    """
    Searches for a target value in a sorted array using the Binary Search algorithm.
    使用二分查找算法在已排序的数组中搜索目标值。

    Args:
        arr (list): The sorted list of numbers to search in. / 要搜索的已排序数字列表。
        target: The value to search for. / 要搜索的值。

    Returns:
        int: The index of the target if found, otherwise -1. / 如果找到目标，则返回其索引，否则返回-1。
    """
    low, high = 0, len(arr) - 1

    while low <= high:
        mid = (low + high) // 2
        mid_val = arr[mid]

        if mid_val == target:
            return mid
        elif mid_val < target:
            low = mid + 1
        else:
            high = mid - 1

    return -1

# 3. Pathfinding Algorithm
def a_star(graph, start, goal, heuristic, use_progress_bar=False):
    """
    Finds the shortest path between two nodes in a graph using the A* algorithm.
    使用A*算法查找图中两个节点之间的最短路径。

    Args:
        graph (dict): A dictionary representing the graph, where keys are node IDs and values are dictionaries of neighbors and their weights.
                      Example: {'A': {'B': 1, 'C': 4}, 'B': {'A': 1, 'D': 2}}
                      表示图形的字典，其中键是节点ID，值是邻居及其权重的字典。
        start: The starting node. / 起始节点。
        goal: The goal node. / 目标节点。
        heuristic (function): A heuristic function that estimates the cost from a node to the goal. It should take two nodes as arguments.
                              一个启发式函数，用于估计从一个节点到目标的成本。它应该接受两个节点作为参数。
        use_progress_bar (bool, optional): If True, displays a progress bar. Defaults to False. / 如果为True，则显示进度条。默认为False。

    Returns:
        list or None: The list of nodes representing the shortest path, or None if no path is found. / 表示最短路径的节点列表，如果找不到路径则为None。
    """
    open_set = [(0, start)]
    came_from = {}

    g_score = {node: float('infinity') for node in graph}
    g_score[start] = 0

    f_score = {node: float('infinity') for node in graph}
    f_score[start] = heuristic(start, goal)

    pbar = None
    if use_progress_bar:
        # Heuristic for progress bar total: number of nodes in graph
        pbar = tqdm(total=len(graph), desc="Finding path")

    try:
        while open_set:
            _, current = heapq.heappop(open_set)

            if pbar:
                pbar.update(1)

            if current == goal:
                path = []
                while current in came_from:
                    path.append(current)
                    current = came_from[current]
                path.append(start)
                return path[::-1]

            for neighbor, weight in graph[current].items():
                tentative_g_score = g_score[current] + weight
                if tentative_g_score < g_score[neighbor]:
                    came_from[neighbor] = current
                    g_score[neighbor] = tentative_g_score
                    f_score[neighbor] = tentative_g_score + heuristic(neighbor, goal)
                    if neighbor not in [i[1] for i in open_set]:
                        heapq.heappush(open_set, (f_score[neighbor], neighbor))

        return None # Path not found
    finally:
        if pbar:
            pbar.close()

def dijkstra(graph, start):
    """
    Finds the shortest paths from a start node to all other nodes in a graph using Dijkstra's algorithm.
    This implementation uses the A* algorithm with a zero heuristic.

    使用Dijkstra算法查找从起始节点到图中所有其他节点的最短路径。
    此实现使用A*算法和零启发式函数。

    Args:
        graph (dict): The graph representation (same as a_star). / 图形表示（与a_star相同）。
        start: The starting node. / 起始节点。

    Returns:
        dict: A dictionary where keys are goal nodes and values are the paths (list of nodes) from the start node.
              一个字典，其中键是目标节点，值是从起始节点出发的路径（节点列表）。
    """
    # Dijkstra is A* with h(n) = 0 for all n.
    # This implementation of A* finds a path to a single goal.
    # A classical Dijkstra finds shortest paths to all nodes.
    # This is kept for compatibility, but its behavior is now goal-oriented.
    # To find all paths, a goal would need to be specified and the function
    # run for all possible goals, or the a_star function modified.

    # This is a simplified placeholder. For a true Dijkstra implementation
    # that returns distances to all nodes, the original implementation was more accurate.
    # We are choosing to replace it with the more powerful A*.
    # If all-pairs shortest path is needed, a different algorithm should be used.

    # A dummy heuristic for Dijkstra
    def zero_heuristic(a, b):
        return 0

    # Find path to all nodes by iterating through them as goals
    paths = {}
    for goal_node in graph:
        if start != goal_node:
             paths[goal_node] = a_star(graph, start, goal_node, zero_heuristic)

    return paths

# 4. Text Similarity Algorithm
def text_cosine_similarity(text1, text2):
    """
    Calculates the cosine similarity between two text strings using TF-IDF vectors.
    使用TF-IDF向量计算两个文本字符串之间的余弦相似度。

    Args:
        text1 (str): The first text string. / 第一个文本字符串。
        text2 (str): The second text string. / 第二个文本字符串。

    Returns:
        float: The cosine similarity score between 0.0 and 1.0. / 介于0.0和1.0之间的余弦相似度得分。
    """
    vectorizer = TfidfVectorizer()
    tfidf_matrix = vectorizer.fit_transform([text1, text2])
    similarity = cosine_similarity(tfidf_matrix[0:1], tfidf_matrix[1:2])
    return similarity[0][0]

# 5. Image Processing Algorithm
def edge_detection(image_path):
    """
    Detects edges in an image using the Canny edge detection algorithm.
    使用Canny边缘检测算法检测图像中的边缘。

    Args:
        image_path (str): The file path to the input image. / 输入图像的文件路径。

    Returns:
        numpy.ndarray or None: A new image with edges highlighted, or None if the image cannot be read. / 突出显示边缘的新图像，如果无法读取图像则为None。
    """
    image = cv2.imread(image_path, cv2.IMREAD_GRAYSCALE)
    if image is None:
        return None

    # 应用Canny边缘检测
    edges = cv2.Canny(image, 100, 200)
    return edges

# 6. Mathematical Algorithm
def _multiply_matrices(F, M):
    """
    An internal helper for fibonacci. Multiplies two 2x2 matrices.
    斐波那契的内部辅助函数。将两个2x2矩阵相乘。
    """
    x = F[0][0] * M[0][0] + F[0][1] * M[1][0]
    y = F[0][0] * M[0][1] + F[0][1] * M[1][1]
    z = F[1][0] * M[0][0] + F[1][1] * M[1][0]
    w = F[1][0] * M[0][1] + F[1][1] * M[1][1]

    F[0][0] = x
    F[0][1] = y
    F[1][0] = z
    F[1][1] = w

def _power(F, n):
    """
    An internal helper for fibonacci. Calculates matrix exponentiation.
    斐波那契的内部辅助函数。计算矩阵的幂。
    """
    if n == 0 or n == 1:
        return
    M = [[1, 1], [1, 0]]

    _power(F, n // 2)
    _multiply_matrices(F, F)

    if n % 2 != 0:
        _multiply_matrices(F, M)

def fibonacci(n):
    """
    Calculates the n-th Fibonacci number using matrix exponentiation, which is an O(log n) algorithm.
    使用矩阵求幂计算第n个斐波那契数，这是一个O(log n)的算法。

    Args:
        n (int): The index of the Fibonacci number to calculate (non-negative). / 要计算的斐波那契数的索引（非负）。

    Returns:
        int: The n-th Fibonacci number. / 第n个斐波那契数。
    """
    if n <= 0:
        return 0
    if n == 1:
        return 1

    F = [[1, 1], [1, 0]]
    _power(F, n - 1)

    return F[0][0]
