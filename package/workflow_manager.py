import logging
from typing import List, Tuple, Dict, Optional
from collections import defaultdict, deque
import importlib
from tqdm import tqdm

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

class WorkflowManager:
    """
    Manages the execution of complex workflows defined by module dependencies and costs.
    This class reads a configuration file, builds a dependency graph, and uses dynamic
    programming to find the optimal execution path.
    """

    INFINITY = float('inf')

    def __init__(self, stop_on_error: bool = True):
        """
        Initializes the WorkflowManager.
        Args:
            stop_on_error: If True, the workflow will stop immediately if a module fails.
                           If False, it will log the error and continue.
        """
        self.stop_on_error = stop_on_error
        self.costs: Dict[str, int] = {}
        self.positions: Dict[str, str] = {}
        self.graph: Dict[str, List[str]] = defaultdict(list)
        self.position_mapping: Dict[str, Tuple[str, str]] = {}

    def _read_module_config(self, file_path: str):
        """
        Reads the module configuration file and populates the costs, positions, and graph.
        """
        try:
            with open(file_path, 'r') as file:
                for line in file:
                    line = line.strip()
                    if not line or line.startswith('#'):
                        continue

                    parts = line.split()
                    if len(parts) < 3:
                        logging.warning(f"Skipping malformed line in config: {line}")
                        continue

                    try:
                        module_name, cost, position_key = parts[0], int(parts[1]), parts[2]
                    except ValueError:
                        logging.warning(f"Invalid cost value in config line, skipping: {line}")
                        continue

                    dependencies = parts[3].split(',') if len(parts) > 3 else []

                    self.costs[module_name] = cost
                    self.positions[module_name] = position_key

                    for dep in dependencies:
                        if dep:
                            self.graph[dep].append(module_name)
        except FileNotFoundError:
            logging.error(f"Configuration file not found: {file_path}")
            raise

    def _topological_sort(self, all_modules: List[str]) -> List[str]:
        """
        Performs a topological sort on the dependency graph.
        """
        in_degree = {u: 0 for u in all_modules}
        for u in self.graph:
            if u not in in_degree:
                in_degree[u] = 0
            for v in self.graph[u]:
                in_degree[v] = in_degree.get(v, 0) + 1

        queue = deque([u for u in in_degree if in_degree[u] == 0])
        sorted_list = []

        while queue:
            u = queue.popleft()
            sorted_list.append(u)

            for v in self.graph.get(u, []):
                in_degree[v] -= 1
                if in_degree[v] == 0:
                    queue.append(v)

        if len(sorted_list) != len(in_degree):
            logging.warning("A cycle was detected in the dependency graph. The workflow may not be accurate.")
            return []

        return sorted_list

    def _find_shortest_path(self, start_module: str, all_modules: List[str]) -> Tuple[Dict[str, float], Dict[str, Optional[str]]]:
        """
        Finds the shortest path in the DAG using dynamic programming.
        """
        sorted_modules = self._topological_sort(all_modules)
        if not sorted_modules:
            return {m: self.INFINITY for m in all_modules}, {m: None for m in all_modules}

        min_costs = {module: self.INFINITY for module in all_modules}
        predecessors = {module: None for module in all_modules}

        if start_module in min_costs:
            min_costs[start_module] = 0
        else:
            logging.error(f"Start module '{start_module}' not found in the module list.")
            return min_costs, predecessors

        for u in tqdm(sorted_modules, desc="Calculating Optimal Path"):
            if min_costs[u] == self.INFINITY:
                continue
            for v in self.graph.get(u, []):
                weight_v = self.costs.get(v, 0)
                if min_costs[u] + weight_v < min_costs[v]:
                    min_costs[v] = min_costs[u] + weight_v
                    predecessors[v] = u

        return min_costs, predecessors

    def _get_optimal_route(self, start_module: str, end_module: str, predecessors: Dict[str, Optional[str]]) -> List[str]:
        """
        Constructs the optimal execution route from the predecessors dictionary.
        """
        route = []
        current = end_module

        if predecessors.get(end_module) is None and end_module != start_module:
            return []

        while current is not None:
            route.append(current)
            if current == start_module:
                break
            current = predecessors.get(current)

        return route[::-1]

    def _execute_module(self, module_name: str):
        """
        Executes a single module.
        """
        logging.info(f"--- Executing module: {module_name} ---")
        try:
            module = importlib.import_module(module_name)
            run_func = getattr(module, 'run')
            run_func()
            logging.info(f"--- Module {module_name} executed successfully ---")
        except ImportError:
            logging.error(f"Module '{module_name}' not found. Check if the file exists and is in the correct path.")
            if self.stop_on_error:
                raise
        except AttributeError:
            logging.error(f"Module '{module_name}' does not have a 'run' function.")
            if self.stop_on_error:
                raise
        except Exception as e:
            logging.error(f"An unexpected error occurred while running module '{module_name}': {e}")
            if self.stop_on_error:
                raise

    def run(self, config_path: str, start_module: str, end_module: str):
        """
        Executes a workflow defined in a configuration file.
        Args:
            config_path: Path to the workflow configuration file.
            start_module: The starting module of the workflow.
            end_module: The target (end) module of the workflow.
        """
        self._read_module_config(config_path)
        all_modules = list(set(self.costs.keys()) | set(self.graph.keys()) | set(sum(self.graph.values(), [])))

        if not all_modules:
            logging.info("No modules found to execute.")
            return

        min_costs, predecessors = self._find_shortest_path(start_module, all_modules)
        optimal_route = self._get_optimal_route(start_module, end_module, predecessors)

        if not optimal_route:
            logging.warning(f"No valid execution route found from '{start_module}' to '{end_module}'.")
            return

        logging.info(f"Optimal execution route found: {' -> '.join(optimal_route)}")

        for module_name in tqdm(optimal_route, desc="Executing Workflow"):
            self._execute_module(module_name)

        logging.info("Workflow execution complete.")
