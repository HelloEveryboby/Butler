"""
基于动态规划的模块执行路径优化算法 (Algorithm1)
--------------------------------------------
功能：
1. 读取模块依赖图（DAG）及各模块的执行成本。
2. 使用拓扑排序确定执行顺序。
3. 应用动态规划（松弛操作）寻找从起点到终点的最短路径（最低成本路线）。
4. 自动生成最优执行序列。
"""

from typing import List, Tuple, Dict, Optional
from collections import defaultdict, deque
import importlib
from tqdm import tqdm

# 定义一个极大值，表示路径不可达
INFINITY = float('inf')

def read_module_config(file_path: str) -> Tuple[Dict[str, int], Dict[str, str], Dict[str, List[str]]]:
    """
    读取模块配置文件，构建成本字典和依赖图。

    文件格式: 模块名 成本 插入位置 依赖模块1,依赖模块2...
    """
    costs = {}
    positions = {}
    graph = defaultdict(list)

    with open(file_path, 'r', encoding='utf-8') as file:
        for line in file:
            line = line.strip()
            if not line or line.startswith('#'):
                continue

            parts = line.split()
            if len(parts) < 3:
                continue

            module_name = parts[0]
            cost = int(parts[1])
            position_key = parts[2]
            dependencies = parts[3].split(',') if len(parts) > 3 else []

            costs[module_name] = cost
            positions[module_name] = position_key

            # 构建反向图：从依赖项指向当前模块
            for dep in dependencies:
                if dep:
                    graph[dep].append(module_name)

    return costs, positions, graph

def topological_sort(graph: Dict[str, List[str]], all_modules: List[str]) -> List[str]:
    """
    Kahn 算法实现拓扑排序，用于确定 DAG 的处理顺序。
    """
    in_degree = {u: 0 for u in all_modules}
    for u in graph:
        for v in graph[u]:
            if v in in_degree:
                in_degree[v] += 1

    queue = deque([u for u in in_degree if in_degree[u] == 0])
    sorted_list = []

    while queue:
        u = queue.popleft()
        sorted_list.append(u)

        for v in graph.get(u, []):
            in_degree[v] -= 1
            if in_degree[v] == 0:
                queue.append(v)

    return sorted_list

def find_shortest_path_in_dag(
    costs: Dict[str, int],
    graph: Dict[str, List[str]],
    start_module: str,
    all_modules: List[str]
) -> Tuple[Dict[str, float], Dict[str, Optional[str]]]:
    """
    使用动态规划在 DAG 中寻找最短路径（最低执行成本）。
    """
    sorted_modules = topological_sort(graph, all_modules)

    min_costs: Dict[str, float] = {module: INFINITY for module in all_modules}
    predecessors: Dict[str, Optional[str]] = {module: None for module in all_modules}

    if start_module in min_costs:
        min_costs[start_module] = 0

    # 按拓扑顺序进行松弛操作
    for u in sorted_modules:
        if min_costs[u] == INFINITY:
            continue

        for v in graph.get(u, []):
            weight_v = costs.get(v, 0)
            if min_costs[u] + weight_v < min_costs[v]:
                min_costs[v] = min_costs[u] + weight_v
                predecessors[v] = u

    return min_costs, predecessors

def run():
    """入口函数"""
    print("--- 模块执行路径优化算法 (DP) ---")
    # 示例运行逻辑...
    pass

if __name__ == "__main__":
    run()
