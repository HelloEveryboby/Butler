import pandas as pd
import numpy as np
from package.log_manager import LogManager
from tqdm import tqdm
import os

logger = LogManager.get_logger(__name__)

class DataAnalyzer:
    def _load_data(self, file_path, chunk_size=10000, progress_threshold_mb=10):
        """
        Loads data from a file into a pandas DataFrame.
        Currently supports CSV files.
        Shows a progress bar for files larger than progress_threshold_mb.
        """
        if not file_path.endswith('.csv'):
            return None, "目前仅支持分析CSV文件。"

        try:
            file_size_mb = os.path.getsize(file_path) / (1024 * 1024)

            if file_size_mb > progress_threshold_mb:
                # Get total number of lines for tqdm
                with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
                    total_lines = sum(1 for line in f)

                chunks = []
                with tqdm(total=total_lines, desc=f"Loading {os.path.basename(file_path)}", unit='lines') as pbar:
                    for chunk in pd.read_csv(file_path, chunksize=chunk_size, low_memory=False):
                        chunks.append(chunk)
                        pbar.update(chunk_size)

                df = pd.concat(chunks, axis=0)
            else:
                df = pd.read_csv(file_path)

            logger.info(f"Successfully loaded data from {file_path}")
            return df, None

        except FileNotFoundError:
            logger.warning(f"Data file not found: {file_path}")
            return None, f"数据文件 '{file_path}' 未找到。"
        except Exception as e:
            logger.error(f"Error loading data from {file_path}: {e}")
            return None, f"加载数据时出错: {e}"

    def get_summary(self, file_path):
        """
        Provides a basic summary of the dataset.
        """
        df, error = self._load_data(file_path)
        if error:
            return False, error

        try:
            num_rows, num_cols = df.shape
            columns = df.columns.tolist()
            summary = (
                f"数据摘要:\n"
                f"- 文件: {file_path}\n"
                f"- 行数: {num_rows}\n"
                f"- 列数: {num_cols}\n"
                f"- 列名: {', '.join(columns)}"
            )
            return True, summary
        except Exception as e:
            logger.error(f"Error generating summary for {file_path}: {e}")
            return False, f"生成摘要时出错: {e}"

    def describe_data(self, file_path):
        """
        Provides descriptive statistics for the numerical columns in the dataset.
        """
        df, error = self._load_data(file_path)
        if error:
            return False, error

        try:
            description = df.describe().to_string()
            return True, f"数据描述性统计:\n{description}"
        except Exception as e:
            logger.error(f"Error describing data for {file_path}: {e}")
            return False, f"生成描述性统计时出错: {e}"

def run():
    """
    Placeholder run function.
    """
    print("Data Analyzer module loaded. This module is intended to be used programmatically.")
    logger.info("Data Analyzer module run function executed.")
