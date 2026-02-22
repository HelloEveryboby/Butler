import os
import hashlib
from package.log_manager import LogManager

logger = LogManager.get_logger(__name__)

def run(folder_path=None):
    logger.info("OrganizeIT tool started")
    if not folder_path:
        folder_path = input("Please enter the folder path to organize: ")
    organize_files(folder_path)

def get_file_hash(file_path):
    """
    计算文件的SHA-256哈希值
    :param file_path: 文件路径
    :return: 文件的SHA-256哈希值
    """
    with open(file_path, 'rb') as f:
        return hashlib.sha256(f.read()).hexdigest()

def organize_files(folder_path):
    """
    整理指定文件夹中的文件，按字母大小顺序排列，名字长短
    :param folder_path: 需要整理的文件夹路径
    """
    logger.info(f"Organizing files in folder: {folder_path}")
    # 创建一个字典来存储基于文件扩展名的目标文件夹
    extension_folders = {}

    # 创建一个字典来存储文件哈希值
    file_hashes = {}

    # 遍历文件夹中的文件
    for filename in os.listdir(folder_path):
        file_path = os.path.join(folder_path, filename)
        if os.path.isfile(file_path):
            # 获取文件扩展名
            _, extension = os.path.splitext(filename)
            extension = extension.lower()  # 将扩展名转换为小写

            # 确定目标文件夹
            if extension in extension_folders:
                destination_folder = extension_folders[extension]
            else:
                destination_folder = os.path.join(folder_path, extension[1:])  # 去掉扩展名前的点
                os.makedirs(destination_folder, exist_ok=True)
                extension_folders[extension] = destination_folder

            # 计算文件哈希值
            file_hash = get_file_hash(file_path)

            # 检查是否有重复文件
            if file_hash in file_hashes:
                # 文件是重复的，重命名文件
                file_counter = 1
                name, ext = os.path.splitext(filename)
                new_filename = f"{name}_{file_counter}{ext}"
                new_file_path = os.path.join(destination_folder, new_filename)
                
                # 确保新文件名不冲突
                while os.path.exists(new_file_path):
                    file_counter += 1
                    new_filename = f"{name}_{file_counter}{ext}"
                    new_file_path = os.path.join(destination_folder, new_filename)
                
                os.rename(file_path, new_file_path)
                logger.info(f"Renamed duplicate file {filename} to {new_filename} in {destination_folder}")
            else:
                # 存储文件哈希值
                file_hashes[file_hash] = filename
                # 处理目标文件夹中的同名文件
                new_file_path = os.path.join(destination_folder, filename)
                
                # 如果目标存在同名文件，进行重命名
                if os.path.exists(new_file_path):
                    file_counter = 1
                    name, ext = os.path.splitext(filename)
                    new_filename = f"{name}_{file_counter}{ext}"
                    new_file_path = os.path.join(destination_folder, new_filename)
                    
                    while os.path.exists(new_file_path):
                        file_counter += 1
                        new_filename = f"{name}_{file_counter}{ext}"
                        new_file_path = os.path.join(destination_folder, new_filename)
                    
                    os.rename(file_path, new_file_path)
                    logger.info(f"Renamed {filename} to {new_filename} in {destination_folder} due to existing file")
                else:
                    os.rename(file_path, new_file_path)
                    logger.info(f"Moved {filename} to {destination_folder}")

    # 对每个目标文件夹中的文件进行排序
    for folder in extension_folders.values():
        files = [f for f in os.listdir(folder) if os.path.isfile(os.path.join(folder, f))]
        sorted_files = sorted(files, key=lambda x: (len(x), x))
        
        for i, filename in enumerate(sorted_files, 1):
            old_path = os.path.join(folder, filename)
            new_filename = f"{i:03d}_{filename}"
            new_path = os.path.join(folder, new_filename)
            
            # 确保新文件名不冲突
            temp_path = os.path.join(folder, f"temp_{i}")
            os.rename(old_path, temp_path)
            os.rename(temp_path, new_path)
            logger.info(f"Renamed {filename} to {new_filename}")


