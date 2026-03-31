from typing import List, Tuple
import importlib
from tqdm import tqdm


def read_file_list(file_path: str) -> List[Tuple[str, int, str]]:
    """
    读取文件列表，并获取每个文件的优先级、插入位置标识符。

    文件格式示例:
    package.module1 1 pos1
    """
    with open(file_path, "r") as file:
        return [
            (line.split()[0], int(line.split()[1]), line.split()[2])
            for line in file
            if line.strip()
        ]


def hybrid_sort_with_progress(arr: List[Tuple[str, int, str]]):
    """
    使用 tqdm 进度条包装混合排序算法。
    """
    with tqdm(total=len(arr), desc="正在排序模块") as pbar:
        hybridSort(arr, pbar=pbar)


def hybridSort(
    arr: List[Tuple[str, int, str]], left=None, right=None, depth=0, pbar=None
):
    """
    混合排序算法实现，结合了快速排序（用于大数组）和插入排序（用于小数组）。

    Args:
        arr: 待排序列表，元素为 (模块名, 优先级, 位置标识符)。
        left: 子数组起始索引。
        right: 子数组结束索引。
        depth: 递归深度。
        pbar: tqdm 进度条对象。
    """
    if left is None:
        left = 0
    if right is None:
        right = len(arr) - 1

    # 插入排序优化: 当数组规模较小时，插入排序效率更高
    if right - left < 10:
        insertionSort(arr, left, right)
        if pbar:
            pbar.update(right - left + 1)
        return

    if left < right:
        pivot_index = partition(arr, left, right, depth, pbar)
        # 递归处理，优先处理较短的一侧以优化递归深度
        if pivot_index - left < right - pivot_index:
            hybridSort(arr, left, pivot_index - 1, depth + 1, pbar)
            hybridSort(arr, pivot_index + 1, right, depth + 1, pbar)
        else:
            hybridSort(arr, pivot_index + 1, right, depth + 1, pbar)
            hybridSort(arr, left, pivot_index - 1, depth + 1, pbar)


def partition(
    arr: List[Tuple[str, int, str]], left: int, right: int, depth: int, pbar=None
) -> int:
    """
    快速排序的分区操作，采用“三数取中法”选择枢轴。
    """
    mid = (left + right) // 2
    pivot = median_of_three(arr, left, mid, right)
    arr[left], arr[pivot] = arr[pivot], arr[left]
    pivot = left

    i = left + 1
    j = right
    while True:
        while i <= j and arr[i][1] < arr[pivot][1]:
            i += 1
        while i <= j and arr[j][1] >= arr[pivot][1]:
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


def median_of_three(
    arr: List[Tuple[str, int, str]], left: int, mid: int, right: int
) -> int:
    """
    三数取中，返回中位数的索引，减少快排在已排序数组上的退化风险。
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
    插入排序实现。
    """
    for i in range(left + 1, right + 1):
        key = arr[i]
        j = i - 1
        while j >= left and key[1] < arr[j][1]:
            arr[j + 1] = arr[j]
            j -= 1
        arr[j + 1] = key


def execute_program(
    module_name: str,
    modules: List[Tuple[str, int, str]],
    position_mapping: dict,
    pbar=None,
):
    """
    执行指定模块，并处理动态插入逻辑。
    """
    print(f"--- 正在执行模块: {module_name} ---")
    try:
        module = importlib.import_module(module_name)
        if hasattr(module, "run"):
            module.run()
        print(f"--- 模块 {module_name} 执行完毕 ---")
    except ImportError as error:
        print(f"导入模块失败: {error}")
    except Exception as e:
        print(f"执行模块时出错: {e}")

    if pbar:
        pbar.update(1)


def run():
    """
    算法包入口。
    """
    file_list_path = "file_list.txt"

    try:
        files_with_priority = read_file_list(file_list_path)
        hybrid_sort_with_progress(files_with_priority)
        print("排序完成：", files_with_priority)
    except FileNotFoundError:
        print(f"未找到文件列表: {file_list_path}")


if __name__ == "__main__":
    run()
