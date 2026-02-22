import pandas as pd
import os

def convert_csv(file_path: str, output_file: str = None) -> str:
    """
    将CSV文件转换为Markdown表格
    
    参数:
        file_path (str): 要转换的CSV文件路径
        output_file (str, 可选): 保存Markdown输出的文件路径。如果为None，则返回字符串
    
    返回:
        str: CSV数据的Markdown表格表示，如果指定了output_file则返回文件路径
    """
    try:
        # 检查文件是否存在
        if not os.path.exists(file_path):
            return f"错误：找不到文件 '{file_path}'"
        
        # 读取CSV文件
        df = pd.read_csv(file_path)
        
        # 检查DataFrame是否为空
        if df.empty:
            return "错误：CSV文件内容为空"
        
        # 转换为Markdown格式
        markdown_table = df.to_markdown(index=False)
        
        # 如果提供了输出路径，则保存到文件
        if output_file:
            try:
                with open(output_file, 'w', encoding='utf-8') as f:
                    f.write(markdown_table)
                return f"成功将CSV转换为Markdown并保存到: {output_file}"
            except Exception as write_error:
                return f"保存文件时出错: {write_error}"
        
        return markdown_table
        
    except pd.errors.EmptyDataError:
        return "错误：CSV文件为空"
    except pd.errors.ParserError:
        return "错误：无法解析CSV文件，请检查文件格式"
    except PermissionError:
        return "错误：没有文件读取权限"
    except Exception as e:
        return f"转换CSV文件时出错: {e}"
