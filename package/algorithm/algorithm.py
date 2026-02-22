from typing import List, Tuple
import importlib
from tqdm import tqdm

def read_file_list(file_path: str) -> List[Tuple[str, int, str]]:
    """读取文件列表，并获取每个文件的优先级、插入位置标识符。"""
    with open(file_path, 'r', encoding='utf-8') as file:
        return [(line.split()[0], int(line.split()[1]), line.split()[2]) for line in file if line.strip()]

def hybrid_sort_with_progress(arr: List[Tuple[str, int, str]]):
    """
    使用 tqdm 包装 hybridSort 以显示进度条。
    """
    with tqdm(total=len(arr), desc="正在排序模块") as pbar:
        hybridSort(arr, pbar=pbar)

def hybridSort(arr: List[Tuple[str, int, str]], left=None, right=None, depth=0, pbar=None):
    """
    混合排序算法，结合快速排序和插入排序。

    参数:
        arr: 要排序的列表。
        left: 排序子数组的起始索引。
        right: 排序子数组的结束索引。
        depth: 递归深度（用于调试输出缩进）。
        pbar: tqdm 进度条实例。
    """
    if left is None:
        left = 0
    if right is None:
        right = len(arr) - 1

    # 插入排序优化: 对于小数组使用插入排序
    if right - left < 10:
        insertionSort(arr, left, right)
        if pbar:
            pbar.update(right - left + 1)
        return

    if left < right:
        pivot_index = partition(arr, left, right, depth, pbar)
        # 优化：先对较短的一边进行排序，减少递归深度
        if pivot_index - left < right - pivot_index:
            hybridSort(arr, left, pivot_index - 1, depth + 1, pbar)
            hybridSort(arr, pivot_index + 1, right, depth + 1, pbar)
        else:
            hybridSort(arr, pivot_index + 1, right, depth + 1, pbar)
            hybridSort(arr, left, pivot_index - 1, depth + 1, pbar)

def partition(arr: List[Tuple[str, int, str]], left: int, right: int, depth: int, pbar=None) -> int:
    """
    对列表进行分区，并将枢轴放置在正确的位置。

    参数:
        arr: 要分区的列表。
        left: 分区子数组的起始索引。
        right: 分区子数组的结束索引。
        depth: 递归深度（用于调试输出缩进）。
        pbar: tqdm 进度条实例。

    返回:
        枢轴的最终位置。
    """
    mid = (left + right) // 2
    pivot = median_of_three(arr, left, mid, right)
    arr[left], arr[pivot] = arr[pivot], arr[left]
    pivot = left

    i = left + 1
    j = right
    while True:
        while i <= j and arr[i] < arr[pivot]:
            i += 1
        while i <= j and arr[j] >= arr[pivot]:
            j -= 1
        if i <= j:
            arr[i], arr[j] = arr[j], arr[i]
            i += 1
            j -= 1
        else:
            break
    arr[pivot], arr[j] = arr[j], arr[pivot]
    if pbar:
        pbar.update(1)
    return j

def median_of_three(arr: List[Tuple[str, int, str]], left: int, mid: int, right: int) -> int:
    """
    返回三个元素的中位数的索引。

    参数:
        arr: 包含三个元素的列表。
        left: 列表中第一个元素的索引。
        mid: 列表中第二个元素的索引。
        right: 列表中第三个元素的索引。

    返回:
        三个元素中位数的索引。
    """
    if arr[left][1] < arr[mid][1]:
        if arr[mid][1] < arr[right][1]:
            return mid
        elif arr[left][1] < arr[right][1]:
            return right
        else:
            return left
    else:
        if arr[left][1] < arr[right][1]:
            return left
        elif arr[mid][1] < arr[right][1]:
            return right
        else:
            return mid

def insertionSort(arr: List[Tuple[str, int, str]], left: int, right: int):
    """
    插入排序算法，对小数组进行排序。

    参数:
        arr: 要排序的列表。
        left: 排序子数组的起始索引。
        right: 排序子数组的结束索引。
    """
    for i in range(left + 1, right + 1):
        key = arr[i]
        j = i - 1
        while j >= left and key < arr[j]:
            arr[j + 1] = arr[j]
            j -= 1
        arr[j + 1] = key
        
def execute_program(module_name: str, modules: List[Tuple[str, int, str]], position_mapping: dict, pbar=None):
    """执行指定模块，并在适当位置插入和执行其他模块。"""
    print(f"--- 开始执行模块: {module_name} ---")
    try:
        module = importlib.import_module(module_name)
        module.run()  # 假设模块中有一个名为 run 的函数
        print(f"--- 模块 {module_name} 执行完毕 ---")
    except ImportError as error:
        print(f"导入模块失败: {error}")
    except AttributeError:
        print(f"模块中未找到运行函数: {module_name}")
    if pbar:
        pbar.update(1)

    # 执行后检查是否有其他模块插入到该模块后
    for mod, _, position_key in modules:
        if position_key == module_name:  # 如果模块的插入点是当前模块
            target_file, placeholder = position_mapping.get(position_key, (None, None))
            if target_file and placeholder:
                insert_content = f"# 插入模块: {mod}\nimport {mod}\n"
                insert_into_file(target_file, insert_content, placeholder)
                execute_program(mod, modules, position_mapping)  # 递归执行插入的模块

def insert_into_file(file_path: str, insert_content: str, after_marker: str):
    """将内容插入到指定文件的指定标记之后。"""
    with open(file_path, 'r', encoding='utf-8') as file:
        content = file.read()

    insert_point = content.find(after_marker)
    if insert_point == -1:
        raise ValueError(f"未找到插入标记: {after_marker}")

    insert_index = insert_point + len(after_marker)

    new_content = content[:insert_index] + "\n" + insert_content + "\n" + content[insert_index:]

    with open(file_path, 'w', encoding='utf-8') as file:
        file.write(new_content)

if __name__ == "__main__":
    # 读取模块优先级列表
    file_list_path = "file_list.txt"
    
    # 读取文件列表（包括优先级）
    try:
        files_with_priority = read_file_list(file_list_path)
    except FileNotFoundError:
        print(f"错误: 找不到 {file_list_path}。正在创建一个示例。")
        # 创建一个示例 file_list.txt
        with open(file_list_path, "w", encoding='utf-8') as f:
            f.write("package.module1 1 pos1\n")
            f.write("package.module2 3 pos2\n")
            f.write("package.module3 2 pos3\n")
        files_with_priority = read_file_list(file_list_path)


    # 使用混合排序算法排序文件列表（按优先级排序）
    hybrid_sort_with_progress(files_with_priority)

    # 插入位置映射表：映射位置标识符到文件和占位符
    position_mapping = {
        "pos1": ("main.py", "#PLACEHOLDER_1"),
        "pos2": ("utils.py", "#PLACEHOLDER_2"),
        "pos3": ("config.py", "#PLACEHOLDER_3")
    }
    
    # 执行排序后的程序文件
    with tqdm(total=len(files_with_priority), desc="正在执行模块") as pbar:
        for module_name, _, _ in files_with_priority:
            execute_program(module_name, files_with_priority, position_mapping, pbar)
