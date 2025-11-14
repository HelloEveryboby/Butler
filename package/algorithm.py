from typing import List, Tuple
import importlib
from tqdm import tqdm

def read_file_list(file_path: str) -> List[Tuple[str, int, str]]:
    """读取文件列表，并获取每个文件的优先级、插入位置标识符。"""
    with open(file_path, 'r') as file:
        return [(line.split()[0], int(line.split()[1]), line.split()[2]) for line in file if line.strip()]

def hybrid_sort_with_progress(arr: List[Tuple[str, int, str]]):
    """
    使用tqdm包装hybridSort以显示进度条。
    """
    with tqdm(total=len(arr), desc="Sorting modules") as pbar:
        hybridSort(arr, pbar=pbar)

def hybridSort(arr: List[Tuple[str, int, str]], left=None, right=None, depth=0, pbar=None):
    """
    混合排序算法，结合快速排序和插入排序。

    Args:
        arr: 要排序的列表。
        left: 排序子数组的起始索引。
        right: 排序子数组的结束索引。
        depth: 递归深度（用于调试输出缩进）。
        pbar: tqdm progress bar instance.
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

    Args:
        arr: 要分区的列表。
        left: 分区子数组的起始索引。
        right: 分区子数组的结束索引。
        depth: 递归深度（用于调试输出缩进）。
        pbar: tqdm progress bar instance.

    Returns:
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

    Args:
        arr: 包含三个元素的列表。
        left: 列表中第一个元素的索引。
        mid: 列表中第二个元素的索引。
        right: 列表中第三个元素的索引。

    Returns:
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

    Args:
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
        
def execute_program(module_name: str, pbar=None):
    """
    动态导入并执行指定模块的 run() 函数。

    Args:
        module_name (str): 要执行的模块的完整名称 (例如, 'package.my_module').
        pbar (tqdm, optional): 用于更新进度的 tqdm 进度条实例. Defaults to None.
    """
    print(f"--- 开始执行模块: {module_name} ---")
    try:
        module = importlib.import_module(module_name)
        if hasattr(module, 'run'):
            module.run()
            print(f"--- 模块 {module_name} 执行完毕 ---")
        else:
            print(f"模块 {module_name} 中未找到可执行的 run 函数。")
    except ImportError as error:
        print(f"导入模块失败: {error}")
    except Exception as e:
        print(f"执行模块 {module_name} 时发生错误: {e}")
    if pbar:
        pbar.update(1)

def main():
    """
    主函数，用于演示模块加载、排序和执行。
    """
    # 定义模块优先级列表文件的路径
    file_list_path = "file_list.txt"
    
    # 尝试读取文件列表
    try:
        files_with_priority = read_file_list(file_list_path)
    except FileNotFoundError:
        print(f"错误: 未找到 {file_list_path}。正在创建一个示例文件。")
        # 如果文件不存在，创建一个示例文件
        with open(file_list_path, "w") as f:
            f.write("package.module1 1 placeholder1\n")
            f.write("package.module2 3 placeholder2\n")
            f.write("package.module3 2 placeholder3\n")
        files_with_priority = read_file_list(file_list_path)

    # 根据优先级对模块列表进行排序
    print("正在根据优先级对模块进行排序...")
    hybrid_sort_with_progress(files_with_priority)
    print("模块排序完成。")

    # 依次执行排序后的模块
    print("开始执行已排序的模块...")
    with tqdm(total=len(files_with_priority), desc="Executing modules") as pbar:
        for module_name, _, _ in files_with_priority:
            execute_program(module_name, pbar)
    print("所有模块执行完毕。")

if __name__ == "__main__":
    main()
