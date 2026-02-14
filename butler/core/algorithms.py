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
    内部辅助函数，用于内省排序。使用插入排序对数组的子切片进行排序。

    参数:
        arr (list): 要排序的数组。
        low (int): 起始索引。
        high (int): 结束索引。
        pbar (tqdm, optional): 进度条实例。
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
    内部辅助函数，用于内省排序。使用中值三数枢轴的霍尔分区方案对数组进行分区。

    参数:
        arr (list): 要分区的数组。
        low (int): 起始索引。
        high (int): 结束索引。
        pbar (tqdm, optional): 进度条实例。

    返回:
        int: 分区索引。
    """
    # 三数取中法选择枢轴
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
    内省排序的核心递归工具。对于小分区，切换到插入排序。

    参数:
        arr (list): 要排序的数组。
        low (int): 起始索引。
        high (int): 结束索引。
        depth_limit (int): 递归深度限制，以防止最坏情况下的快速排序性能。
        pbar (tqdm, optional): 进度条实例。
    """
    while high - low > 16: # 切换到插入排序的阈值
        if depth_limit == 0:
            # 如果递归深度太高，切换到堆排序
            _heap_sort_range(arr, low, high, pbar)
            return

        pivot_index = _partition(arr, low, high, pbar)
        _introsort_util(arr, pivot_index + 1, high, depth_limit - 1, pbar)
        high = pivot_index - 1

    _insertion_sort(arr, low, high, pbar)

def quick_sort(arr, use_progress_bar=False):
    """
    使用内省排序（Introsort）对数组进行排序，这是一种结合了快速排序、堆排序和插入排序的混合算法。
    它提供了快速的平均性能，同时避免了快速排序 O(n^2) 的最坏情况时间复杂度。

    参数:
        arr (list): 需要排序的数字列表。
        use_progress_bar (bool, optional): 如果为 True，则显示进度条。默认为 False。

    返回:
        list: 包含已排序元素的新列表。
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
    使用归并排序算法对数组进行排序。它是一种稳定的、基于比较的排序算法，时间复杂度为 O(n log n)。

    参数:
        arr (list): 需要排序的数字列表。

    返回:
        list: 包含已排序元素的新列表。
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
    归并排序的内部辅助函数。将两个已排序的列表合并为一个已排序的列表。

    参数:
        left (list): 左侧已排序列表。
        right (list): 右侧已排序列表。

    返回:
        list: 合并后的已排序列表。
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
    堆排序的内部辅助函数。确保索引 i 处的子树是最大堆。

    参数:
        arr (list): 包含堆的数组。
        n (int): 堆的大小。
        i (int): 子树的根索引。
        low (int): 用于对子数组进行排序的偏移量（用于内省排序）。
        pbar (tqdm, optional): 进度条实例。
    """
    largest = i
    left = 2 * i + 1
    right = 2 * i + 2

    # 检查左子节点是否存在且大于根节点
    if left < n and arr[low + left] > arr[low + largest]:
        largest = left

    # 检查右子节点是否存在且大于根节点
    if right < n and arr[low + right] > arr[low + largest]:
        largest = right

    # 如果需要，更改根节点
    if largest != i:
        arr[low + i], arr[low + largest] = arr[low + largest], arr[low + i]
        # 对根节点进行堆化。
        _heapify(arr, n, largest, low, pbar)

def _heap_sort_range(arr, low, high, pbar=None):
    """
    内省排序的内部辅助函数。使用堆排序对数组的子切片进行排序。
    """
    n = high - low + 1
    # 从未排序的数组构建最大堆。
    # 我们从最后一个非叶子节点开始。
    for i in range(n // 2 - 1, -1, -1):
        _heapify(arr, n, i, low, pbar)

    # 从堆中逐个提取元素
    for i in range(n - 1, 0, -1):
        # 将当前根（最大元素）移动到末尾
        arr[low], arr[low + i] = arr[low + i], arr[low]
        if pbar:
            pbar.update(1)
        # 对缩小的堆调用 max _heapify
        _heapify(arr, i, 0, low, pbar)

def heap_sort(arr, use_progress_bar=False):
    """
    使用堆排序算法对数组进行排序。它是一种不稳定的、基于比较的原地排序算法，时间复杂度为 O(n log n)。

    参数:
        arr (list): 需要排序的数字列表。
        use_progress_bar (bool, optional): 如果为 True，则显示进度条。默认为 False。

    返回:
        list: 包含已排序元素的新列表。
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
    使用二分查找算法在已排序的数组中搜索目标值。

    参数:
        arr (list): 要搜索的已排序数字列表。
        target: 要搜索的值。

    返回:
        int: 如果找到目标，则返回其索引，否则返回 -1。
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
    使用 A* 算法查找图中两个节点之间的最短路径。

    参数:
        graph (dict): 表示图形的字典，其中键是节点 ID，值是邻居及其权重的字典。
                      例如：{'A': {'B': 1, 'C': 4}, 'B': {'A': 1, 'D': 2}}
        start: 起始节点。
        goal: 目标节点。
        heuristic (function): 一个启发式函数，用于估计从一个节点到目标的成本。它应该接受两个节点作为参数。
        use_progress_bar (bool, optional): 如果为 True，则显示进度条。默认为 False。

    返回:
        list or None: 表示最短路径的节点列表，如果找不到路径则为 None。
    """
    open_set = [(0, start)]
    came_from = {}

    g_score = {node: float('infinity') for node in graph}
    g_score[start] = 0

    f_score = {node: float('infinity') for node in graph}
    f_score[start] = heuristic(start, goal)

    pbar = None
    if use_progress_bar:
        # 进度条总数的启发式方法：图中的节点数
        pbar = tqdm(total=len(graph), desc="正在查找路径")

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
    使用 Dijkstra 算法在加权图中查找从起始节点到所有其他节点的最短路径。
    此实现使用最小优先队列以提高效率。

    参数:
        graph (dict): 图形表示，其中键是节点 ID，值是邻居及其边权重的字典。
                      例如：{'A': {'B': 1, 'C': 4}, 'B': {'A': 1, 'D': 2, 'C': 5}, ...}
        start_node: 开始搜索的节点。

    返回:
        tuple: 一个包含两个字典的元组：
               - distances (dict): 将每个节点映射到其与起始节点最短距离的字典。
               - predecessors (dict): 将每个节点映射到其在最短路径中的前驱节点的字典。
    """
    # 将所有节点的距离初始化为无穷大，起始节点除外
    distances = {node: float('infinity') for node in graph}
    distances[start_node] = 0

    # 存储 (距离, 节点) 的优先队列
    priority_queue = [(0, start_node)]

    # 存储最短路径树的字典
    predecessors = {}

    while priority_queue:
        # 获取距离最小的节点
        current_distance, current_node = heapq.heappop(priority_queue)

        # 如果我们已经找到了一条更短的路径，则跳过
        if current_distance > distances[current_node]:
            continue

        # 探索邻居
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
    从起始节点对图执行广度优先搜索（BFS）。

    参数:
        graph (dict): 图形表示（邻接表）。
        start_node: 开始搜索的节点。

    返回:
        list: 按访问顺序排列的节点列表。
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
    从起始节点对图执行深度优先搜索（DFS）。

    参数:
        graph (dict): 图形表示（邻接表）。
        start_node: 开始搜索的节点。
        visited (set, optional): 已访问节点的集合。默认为 None。

    返回:
        list: 按访问顺序排列的节点列表。
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
    使用 TF-IDF 向量计算两个文本字符串之间的余弦相似度。

    参数:
        text1 (str): 第一个文本字符串。
        text2 (str): 第二个文本字符串。

    返回:
        float: 介于 0.0 和 1.0 之间的余弦相似度得分。
    """
    vectorizer = TfidfVectorizer()
    tfidf_matrix = vectorizer.fit_transform([text1, text2])
    similarity = cosine_similarity(tfidf_matrix[0:1], tfidf_matrix[1:2])
    return similarity[0][0]

# 5. Image Processing Algorithm
def edge_detection(image_path):
    """
    使用 Canny 边缘检测算法检测图像中的边缘。

    参数:
        image_path (str): 输入图像的文件路径。

    返回:
        numpy.ndarray or None: 突出显示边缘的新图像，如果无法读取图像则为 None。
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
    斐波那契的内部辅助函数。将两个 2x2 矩阵相乘。
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
    使用矩阵求幂计算第 n 个斐波那契数，这是一个 O(log n) 的算法。

    参数:
        n (int): 要计算的斐波那契数的索引（非负）。

    返回:
        int: 第 n 个斐波那契数。
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
    对数据集执行 K-Means 聚类。

    参数:
        data (array-like or sparse matrix, shape (n_samples, n_features)): 输入数据。
        n_clusters (int): 要形成的簇数。
        random_state (int, RandomState 实例或 None, optional): 确定质心初始化的随机数生成。使用整数可使随机性具有确定性。默认为 None。

    返回:
        tuple: 一个包含以下内容的元组：
               - labels (numpy.ndarray): 每个样本所属的簇的索引。
               - cluster_centers (numpy.ndarray): 簇中心的坐标。
    """
    if not isinstance(data, np.ndarray):
        data = np.array(data)

    # n_init='auto' is the future default, but 10 is the current default and setting it suppresses a warning.
    kmeans = KMeans(n_clusters=n_clusters, random_state=random_state, n_init=10)
    kmeans.fit(data)

    return kmeans.labels_, kmeans.cluster_centers_
