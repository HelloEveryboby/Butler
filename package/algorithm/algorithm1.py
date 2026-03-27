"""
基于动态规划的模块执行路径优化算法 (Algorithm1 - 完整版)
------------------------------------------------------
功能说明：
1. 依赖管理：通过 DAG (有向无环图) 建模 Butler 系统中复杂的模块依赖关系。
2. 成本优化：每个模块都有一个“执行成本”（可以是时间、资源消耗等），算法利用动态规划寻找从初始点到目标点的最优（最低成本）执行路径。
3. 拓扑治理：自动检测依赖循环，并生成合法的拓扑执行序列。
4. 自动化演示：内置测试配置生成与执行演示。

使用方法：
- 作为 Butler 插件调用: `run()`
- 命令行直接运行: `python -m package.algorithm.algorithm1`
"""

import os
from typing import List, Tuple, Dict
from collections import defaultdict, deque

# 定义路径不可达的极大值
INFINITY = float('inf')

class ModulePathOptimizer:
    """
    模块路径优化器，使用动态规划和拓扑排序寻找最优执行序列。
    """
    def __init__(self):
        self.costs: Dict[str, int] = {}
        self.graph: Dict[str, List[str]] = defaultdict(list)
        self.all_modules: List[str] = []

    def load_config_from_file(self, file_path: str):
        """
        从文件加载配置信息。
        格式: 模块名 成本 依赖模块1,依赖模块2...
        """
        if not os.path.exists(file_path):
            raise FileNotFoundError(f"配置文件 {file_path} 不存在。")

        self.costs = {}
        self.graph = defaultdict(list)
        modules_set = set()

        with open(file_path, 'r', encoding='utf-8') as f:
            for line in f:
                line = line.strip()
                if not line or line.startswith('#'):
                    continue

                parts = line.split()
                if len(parts) < 2:
                    continue

                name = parts[0]
                cost = int(parts[1])
                deps = parts[2].split(',') if len(parts) > 2 else []

                self.costs[name] = cost
                modules_set.add(name)
                for d in deps:
                    if d:
                        self.graph[d].append(name)
                        modules_set.add(d)

        self.all_modules = list(modules_set)

    def get_topological_order(self) -> List[str]:
        """
        获取拓扑排序序列，并检测环路。
        """
        in_degree = {u: 0 for u in self.all_modules}
        for u in self.graph:
            for v in self.graph[u]:
                if v in in_degree:
                    in_degree[v] += 1

        queue = deque([u for u in in_degree if in_degree[u] == 0])
        topo_order = []

        while queue:
            u = queue.popleft()
            topo_order.append(u)
            for v in self.graph.get(u, []):
                in_degree[v] -= 1
                if in_degree[v] == 0:
                    queue.append(v)

        if len(topo_order) != len(self.all_modules):
            raise ValueError("检测到循环依赖，无法进行拓扑排序！")

        return topo_order

    def find_optimal_path(self, start_node: str, end_node: str) -> Tuple[List[str], float]:
        """
        使用动态规划寻找从起点到终点的最短（最低成本）路径。
        """
        if start_node not in self.all_modules or end_node not in self.all_modules:
            raise ValueError("起点或终点不在模块列表中。")

        topo_order = self.get_topological_order()

        # dp[v] 表示到达节点 v 的最小累计成本
        dp = {m: INFINITY for m in self.all_modules}
        parent = {m: None for m in self.all_modules}

        dp[start_node] = self.costs.get(start_node, 0)

        # 按拓扑顺序进行状态转移（松弛操作）
        for u in topo_order:
            if dp[u] == INFINITY:
                continue

            for v in self.graph.get(u, []):
                cost_v = self.costs.get(v, 0)
                if dp[u] + cost_v < dp[v]:
                    dp[v] = dp[u] + cost_v
                    parent[v] = u

        # 回溯路径
        if dp[end_node] == INFINITY:
            return [], INFINITY

        path = []
        curr = end_node
        while curr:
            path.append(curr)
            curr = parent[curr]

        return path[::-1], dp[end_node]

def create_demo_config(file_path: str):
    """创建演示用的配置文件"""
    content = [
        "# 模块名 成本 依赖项",
        "entry 0",
        "core_service 10 entry",
        "data_layer 5 core_service",
        "ui_engine 15 core_service",
        "network_module 8 data_layer",
        "plugin_system 12 data_layer,ui_engine",
        "final_app 2 network_module,plugin_system"
    ]
    with open(file_path, 'w', encoding='utf-8') as f:
        f.write("\n".join(content))

def run():
    """Butler 系统调用入口"""
    print("\n" + "="*50)
    print("      Butler 路径优化算法 (Algorithm1 - 完整版)")
    print("="*50)

    config_file = "module_execution_config.txt"
    if not os.path.exists(config_file):
        print(f"正在创建演示配置: {config_file}")
        create_demo_config(config_file)

    optimizer = ModulePathOptimizer()
    try:
        optimizer.load_config_from_file(config_file)

        start_node = "entry"
        end_node = "final_app"

        print(f"🔹 正在计算从 [{start_node}] 到 [{end_node}] 的最优执行路径...")

        path, total_cost = optimizer.find_optimal_path(start_node, end_node)

        if path:
            print(f"✅ 找到最优路径! 累计执行成本: {total_cost}")
            print(f"📍 执行序列: {' -> '.join(path)}")

            # 模拟执行过程
            print("\n开始模拟执行...")
            for i, step in enumerate(path):
                print(f"[{i+1}/{len(path)}] 正在加载模块: {step:15} | 预期成本: {optimizer.costs.get(step, 0)}")
            print("🚀 系统启动成功！")
        else:
            print("❌ 未能找到可达路径。")

    except Exception as e:
        print(f"❌ 运行错误: {e}")

if __name__ == "__main__":
    run()
