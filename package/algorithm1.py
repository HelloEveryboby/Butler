from typing import List, Tuple, Dict, Optional
from collections import defaultdict, deque
import importlib
from tqdm import tqdm

# 定义一个极大的值，表示不可达
INFINITY = float('inf')

# --- I. 辅助函数（来自原代码，用于文件操作）---

def insert_into_file(file_path: str, insert_content: str, after_marker: str):
    """将内容插入到指定文件的指定标记之后。"""
    try:
        with open(file_path, 'r') as file:
            content = file.read()
    except FileNotFoundError:
        print(f"警告: 目标文件 {file_path} 不存在，跳过插入操作。")
        return

    insert_point = content.find(after_marker)
    if insert_point == -1:
        print(f"警告: 文件 {file_path} 中未找到插入标记: {after_marker}，跳过插入。")
        return

    insert_index = insert_point + len(after_marker)

    new_content = content[:insert_index] + "\n" + insert_content + "\n" + content[insert_index:]

    with open(file_path, 'w') as file:
        file.write(new_content)
    print(f"成功将内容插入到 {file_path}，标记 {after_marker} 之后。")


# --- II. 图结构定义与构建 ---

def read_module_config(file_path: str) -> Tuple[Dict[str, int], Dict[str, str], Dict[str, List[str]]]:
    """
    读取模块配置，并构建模块成本和依赖图。
    
    Args:
        file_path: 包含 (模块名 成本 插入位置 依赖模块1,依赖模块2,...) 的文件路径。
        
    Returns:
        (costs, positions, graph)
        costs: 模块名 -> 执行成本 (优先级)
        positions: 模块名 -> 插入位置标识符
        graph: 模块名 -> [依赖于它的模块列表] (邻接表)
    """
    costs = {}
    positions = {}
    graph = defaultdict(list)
    
    with open(file_path, 'r') as file:
        for line in file:
            line = line.strip()
            if not line or line.startswith('#'):
                continue
            
            parts = line.split()
            if len(parts) < 3:
                print(f"警告: 文件行格式不完整: {line}。跳过。")
                continue
                
            module_name = parts[0]
            cost = int(parts[1])
            position_key = parts[2]
            dependencies = parts[3].split(',') if len(parts) > 3 else []
            
            costs[module_name] = cost
            positions[module_name] = position_key
            
            # 构建图：从依赖模块指向当前模块（边表示执行顺序）
            for dep in dependencies:
                if dep: # 确保依赖名非空
                    graph[dep].append(module_name)
                    
    return costs, positions, graph

def topological_sort(graph: Dict[str, List[str]], all_modules: List[str]) -> List[str]:
    """
    使用 Kahn 算法进行拓扑排序。
    """
    in_degree = {u: 0 for u in all_modules}
    # 确保图中的所有模块都在 in_degree 中被初始化
    for u in graph:
        if u not in in_degree:
             in_degree[u] = 0
        for v in graph[u]:
            if v in in_degree:
                in_degree[v] += 1
            else:
                 in_degree[v] = 1 # 依赖模块可能未在初始列表中
    
    queue = deque([u for u in in_degree if in_degree[u] == 0])
    sorted_list = []
    
    while queue:
        u = queue.popleft()
        sorted_list.append(u)
        
        for v in graph.get(u, []):
            in_degree[v] -= 1
            if in_degree[v] == 0:
                queue.append(v)
                
    if len(sorted_list) != len(in_degree):
        print("警告: 图中存在环路 (Cycle)，拓扑排序不完整。动态规划可能不准确。")
        return []

    return sorted_list


# --- III. 动态规划核心算法 (DAG 最短路径) ---

def find_shortest_path_in_dag(
    costs: Dict[str, int], 
    graph: Dict[str, List[str]], 
    start_module: str,
    all_modules: List[str]
) -> Tuple[Dict[str, float], Dict[str, Optional[str]]]:
    """
    使用动态规划（基于拓扑排序的松弛操作）找到 DAG 中的最短路径。
    """
    
    # 1. 拓扑排序，确定正确的处理顺序
    sorted_modules = topological_sort(graph, all_modules)
    if not sorted_modules:
        return {m: INFINITY for m in all_modules}, {m: None for m in all_modules}
        
    # 2. 初始化距离和前驱节点
    min_costs: Dict[str, float] = {module: INFINITY for module in all_modules}
    predecessors: Dict[str, Optional[str]] = {module: None for module in all_modules}
    
    if start_module in min_costs:
        min_costs[start_module] = 0
    else:
        print(f"错误: 起始模块 {start_module} 不在模块列表中。")
        return {m: INFINITY for m in all_modules}, {m: None for m in all_modules}
    
    # 3. 动态规划 / 松弛操作 (按拓扑顺序)
    with tqdm(total=len(sorted_modules), desc="DP/Relaxation (Shortest Path)") as pbar:
        for u in sorted_modules:
            pbar.update(1)
            
            # 只有当模块可达时才进行松弛
            if min_costs[u] == INFINITY:
                continue
                
            # 从节点 u 松弛到其所有邻居 v
            for v in graph.get(u, []):
                # 从 u 到 v 的边权重是 v 自身的执行成本（即 cost[v]）
                # 注意：图中的边 (u->v) 表示 u 必须在 v 之前，v 的执行成本是 weight。
                weight_v = costs.get(v, 0)
                
                # 松弛操作：如果通过 u 到达 v 的成本更低，则更新
                new_cost = min_costs[u] + weight_v
                
                if new_cost < min_costs[v]:
                    min_costs[v] = new_cost
                    predecessors[v] = u
                    
    return min_costs, predecessors


# --- IV. 路线回溯与执行 ---

def get_optimal_execution_route(start_module: str, end_module: str, predecessors: Dict[str, Optional[str]]) -> List[str]:
    """根据前驱节点字典，回溯构造最优执行路线。"""
    route = []
    current = end_module
    
    # 检查终点是否可达
    if predecessors.get(end_module) is None and end_module != start_module:
        return []
        
    while current is not None:
        route.append(current)
        if current == start_module:
            break
        
        current = predecessors.get(current)
        if current is None and route[-1] != start_module:
             # 路径中断，说明终点不可达或依赖图不完整
             return [] 

    return route[::-1] # 反转，得到正确的执行顺序

def execute_module(module_name: str, position_mapping: Dict[str, Tuple[str, str]], positions: Dict[str, str]):
    """执行单个模块并处理插入逻辑。"""
    print(f"--- 开始执行模块: {module_name} ---")
    
    # 1. 尝试动态导入和运行
    try:
        # module = importlib.import_module(module_name)
        # module.run() # 假设模块中有一个名为 run 的函数
        pass # 实际运行时取消注释
        print(f"--- 模块 {module_name} 运行成功 ---")
    except ImportError as error:
        print(f"导入模块失败: {error}")
    except AttributeError:
        print(f"模块中未找到运行函数: {module_name}")
    
    # 2. 处理插入逻辑（如果需要）
    position_key = positions.get(module_name)
    if position_key and position_key in position_mapping:
        target_file, placeholder = position_mapping[position_key]
        insert_content = f"# 自动插入模块: {module_name} - 最佳路线的一部分\nimport {module_name}\n"
        # 假设这里只是插入代码，而不是递归执行（DP已确定顺序）
        # 如果需要运行时动态插入文件内容，则取消注释
        # insert_into_file(target_file, insert_content, placeholder)

def execute_optimal_route(route: List[str], position_mapping: Dict[str, Tuple[str, str]], positions: Dict[str, str]):
    """按照最优路线执行模块。"""
    if not route:
        print("未找到最优执行路线，无法执行。")
        return
        
    print(f"\n--- 找到最优执行路线 ({len(route)} 步): {route} ---")
    
    with tqdm(total=len(route), desc="Executing optimal route") as pbar:
        for module_name in route:
            execute_module(module_name, position_mapping, positions)
            pbar.update(1)


# --- V. 主程序入口 ---

if __name__ == "__main__":
    file_list_path = "dp_module_config.txt"
    START_MODULE = "package.entrypoint" # 假设的起始模块
    END_MODULE = "package.finalizer"     # 假设的目标模块
    
    # 示例: 创建一个 DP 用的配置文件 (格式: 模块名 成本 插入位置 依赖模块)
    try:
        costs, positions, graph = read_module_config(file_list_path)
    except FileNotFoundError:
        print(f"Error: {file_list_path} not found. Creating example config...")
        # 示例配置：A (成本10) 或 B (成本5) 依赖于 Entry，C 依赖于 A 和 B
        with open(file_list_path, "w") as f:
            f.write(f"{START_MODULE} 0 pos_start \n")
            f.write("package.moduleA 10 posA package.entrypoint\n")
            f.write("package.moduleB 5 posB package.entrypoint\n")
            f.write("package.moduleC 2 posC package.moduleA,package.moduleB\n")
            f.write(f"{END_MODULE} 0 pos_end package.moduleC\n")
        costs, positions, graph = read_module_config(file_list_path)

    # 集合所有模块名
    all_modules = list(set(costs.keys()) | set(graph.keys()) | set(sum(graph.values(), [])))
    
    # 插入位置映射表：映射位置标识符到文件和占位符
    position_mapping = {
        "pos_start": ("main.py", "# START_MARKER"),
        "posA": ("config.py", "# CONFIG_MARKER"),
        "posB": ("utils.py", "# UTILS_MARKER"),
        "posC": ("core.py", "# CORE_MARKER"),
        "pos_end": ("main.py", "# END_MARKER"),
    }
    
    # 动态规划查找最短路径
    min_costs, predecessors = find_shortest_path_in_dag(
        costs, 
        graph, 
        START_MODULE, 
        all_modules
    )

    # 获取并执行最优路线
    optimal_route = get_optimal_execution_route(START_MODULE, END_MODULE, predecessors)
    execute_optimal_route(optimal_route, position_mapping, positions)
