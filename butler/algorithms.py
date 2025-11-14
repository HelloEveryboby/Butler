import heapq
from collections import deque

import cv2
import numpy as np
from sklearn.cluster import KMeans
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity
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
            _heap_sort_range(arr, low, high, pbar)
            return

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

def _heapify(arr, n, i, low, pbar=None):
    """
    Internal helper for heap_sort. Ensures the subtree at index i is a max-heap.
    堆排序的内部辅助函数。确保索引i处的子树是最大堆。

    Args:
        arr (list): The array containing the heap. / 包含堆的数组。
        n (int): The size of the heap. / 堆的大小。
        i (int): The root index of the subtree. / 子树的根索引。
        low (int): The offset for sorting a sub-array (for introsort). / 用于对子数组进行排序的偏移量（用于内省排序）。
        pbar (tqdm, optional): Progress bar instance. / 进度条实例。
    """
    largest = i
    left = 2 * i + 1
    right = 2 * i + 2

    # Check if left child exists and is greater than root
    if left < n and arr[low + left] > arr[low + largest]:
        largest = left

    # Check if right child exists and is greater than root
    if right < n and arr[low + right] > arr[low + largest]:
        largest = right

    # Change root if needed
    if largest != i:
        arr[low + i], arr[low + largest] = arr[low + largest], arr[low + i]
        # Heapify the root.
        _heapify(arr, n, largest, low, pbar)

def _heap_sort_range(arr, low, high, pbar=None):
    """
    An internal helper for introsort. Sorts a subsection of an array using heapsort.
    内省排序的内部辅助函数。使用堆排序对数组的子切片进行排序。
    """
    n = high - low + 1
    # Build a max-heap from the unsorted array.
    # We start from the last non-leaf node.
    for i in range(n // 2 - 1, -1, -1):
        _heapify(arr, n, i, low, pbar)

    # Extract elements one by one from the heap
    for i in range(n - 1, 0, -1):
        # Move current root (max element) to the end
        arr[low], arr[low + i] = arr[low + i], arr[low]
        if pbar:
            pbar.update(1)
        # Call max _heapify on the reduced heap
        _heapify(arr, i, 0, low, pbar)

def heap_sort(arr, use_progress_bar=False):
    """
    Sorts an array using the Heapsort algorithm. It's an in-place, non-stable sorting algorithm.
    使用堆排序算法对数组进行排序。它是一种不稳定的、基于比较的原地排序算法，时间复杂度为O(n log n)。

    Args:
        arr (list): The list of numbers to sort. / 需要排序的数字列表。
        use_progress_bar (bool, optional): If True, displays a progress bar. Defaults to False. / 如果为True，则显示进度条。默认为False。

    Returns:
        list: A new list containing the sorted elements. / 包含已排序元素的新列表。
    """
    if not arr:
        return arr
    arr_copy = list(arr)
    n = len(arr_copy)

    pbar = None
    if use_progress_bar:
        pbar = tqdm(total=n, desc="Sorting")

    _heap_sort_range(arr_copy, 0, n - 1, pbar)

    if pbar:
        pbar.close()

    return arr_copy

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

def dijkstra(graph, start_node):
    """
    Finds the shortest paths from a start node to all other nodes in a weighted graph using Dijkstra's algorithm.
    This implementation uses a min-priority queue for efficiency.

    使用Dijkstra算法在加权图中查找从起始节点到所有其他节点的最短路径。
    此实现使用最小优先队列以提高效率。

    Args:
        graph (dict): The graph representation where keys are node IDs and values are dictionaries
                      of neighbors and their edge weights.
                      Example: {'A': {'B': 1, 'C': 4}, 'B': {'A': 1, 'D': 2, 'C': 5}, ...}
                      图形表示，其中键是节点ID，值是邻居及其边权重的字典。
        start_node: The node from which to start the search. / 开始搜索的节点。

    Returns:
        tuple: A tuple containing two dictionaries:
               - distances (dict): A dictionary mapping each node to its shortest distance from the start_node.
               - predecessors (dict): A dictionary mapping each node to its predecessor in the shortest path.
               一个包含两个字典的元组：
               - distances (dict): 将每个节点映射到其与起始节点最短距离的字典。
               - predecessors (dict): 将每个节点映射到其在最短路径中的前驱节点的字典。
    """
    # Initialize distances to all nodes as infinity, except for the start_node
    distances = {node: float('infinity') for node in graph}
    distances[start_node] = 0

    # Priority queue to store (distance, node)
    priority_queue = [(0, start_node)]

    # Dictionary to store the shortest path tree
    predecessors = {}

    while priority_queue:
        # Get the node with the smallest distance
        current_distance, current_node = heapq.heappop(priority_queue)

        # If we have already found a shorter path, skip
        if current_distance > distances[current_node]:
            continue

        # Explore neighbors
        for neighbor, weight in graph[current_node].items():
            distance = current_distance + weight

            # If a shorter path to the neighbor is found
            if distance < distances[neighbor]:
                distances[neighbor] = distance
                predecessors[neighbor] = current_node
                heapq.heappush(priority_queue, (distance, neighbor))

    return distances, predecessors

def breadth_first_search(graph, start_node):
    """
    Performs a Breadth-First Search on a graph from a starting node.
    从起始节点对图执行广度优先搜索（BFS）。

    Args:
        graph (dict): The graph representation (adjacency list). / 图形表示（邻接表）。
        start_node: The node to start the search from. / 开始搜索的节点。

    Returns:
        list: A list of nodes in the order they were visited. / 按访问顺序排列的节点列表。
    """
    if start_node not in graph:
        return []

    visited = set()
    queue = deque([start_node])
    visited.add(start_node)
    order_visited = []

    while queue:
        vertex = queue.popleft()
        order_visited.append(vertex)

        for neighbor in graph.get(vertex, []):
            if neighbor not in visited:
                visited.add(neighbor)
                queue.append(neighbor)

    return order_visited

def depth_first_search(graph, start_node, visited=None):
    """
    Performs a Depth-First Search on a graph from a starting node.
    从起始节点对图执行深度优先搜索（DFS）。

    Args:
        graph (dict): The graph representation (adjacency list). / 图形表示（邻接表）。
        start_node: The node to start the search from. / 开始搜索的节点。
        visited (set, optional): A set of already visited nodes. Defaults to None. / 已访问节点的集合。默认为None。

    Returns:
        list: A list of nodes in the order they were visited. / 按访问顺序排列的节点列表。
    """
    if visited is None:
        visited = set()

    order_visited = []
    if start_node not in visited:
        visited.add(start_node)
        order_visited.append(start_node)
        for neighbor in graph.get(start_node, []):
            order_visited.extend(depth_first_search(graph, neighbor, visited))

    return order_visited

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


# 7. Clustering Algorithm
def k_means_clustering(data, n_clusters, random_state=None):
    """
    Performs K-Means clustering on a dataset.
    对数据集执行K-Means聚类。

    Args:
        data (array-like or sparse matrix, shape (n_samples, n_features)): The input data. / 输入数据。
        n_clusters (int): The number of clusters to form. / 要形成的簇数。
        random_state (int, RandomState instance or None, optional): Determines random number generation for centroid initialization.
                                                                    Use an int to make the randomness deterministic. Defaults to None.
                                                                    确定质心初始化的随机数生成。使用整数可使随机性具有确定性。默认为None。

    Returns:
        tuple: A tuple containing:
               - labels (numpy.ndarray): Index of the cluster each sample belongs to. / 每个样本所属的簇的索引。
               - cluster_centers (numpy.ndarray): Coordinates of cluster centers. / 簇中心的坐标。
    """
    if not isinstance(data, np.ndarray):
        data = np.array(data)

    # n_init='auto' is the future default, but 10 is the current default and setting it suppresses a warning.
    kmeans = KMeans(n_clusters=n_clusters, random_state=random_state, n_init=10)
    kmeans.fit(data)

    return kmeans.labels_, kmeans.cluster_centers_

# 8. Fuzzy String Matching
def levenshtein_distance(s1, s2):
    """
    Calculates the Levenshtein distance between two strings.
    This is the minimum number of single-character edits (insertions, deletions or substitutions)
    required to change one word into the other.
    """
    if len(s1) < len(s2):
        return levenshtein_distance(s2, s1)

    if len(s2) == 0:
        return len(s1)

    previous_row = range(len(s2) + 1)
    for i, c1 in enumerate(s1):
        current_row = [i + 1]
        for j, c2 in enumerate(s2):
            insertions = previous_row[j + 1] + 1
            deletions = current_row[j] + 1
            substitutions = previous_row[j] + (c1 != c2)
            current_row.append(min(insertions, deletions, substitutions))
        previous_row = current_row

    return previous_row[-1]

def find_best_match(query, candidates):
    """
    Finds the best match for a query string from a list of candidate strings using Levenshtein distance.
    """
    if not candidates:
        return None, float('inf')

    best_match = None
    min_distance = float('inf')

    for candidate in candidates:
        distance = levenshtein_distance(query.lower(), candidate.lower())
        if distance < min_distance:
            min_distance = distance
            best_match = candidate

    return best_match, min_distance
