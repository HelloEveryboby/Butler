import sys
import os
import tempfile
from typing import Optional

# Use consistent project root resolution
project_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
markitdown_src = os.path.join(project_root, 'markitdown', 'src')

if markitdown_src not in sys.path:
    sys.path.insert(0, markitdown_src)
if project_root not in sys.path:
    sys.path.insert(0, project_root)

try:
    from markitdown.markitdown_app import convert
    from butler.core.hybrid_link import HybridLinkClient
except ImportError as e:
    print(f"[-] 导入依赖失败: {e}")
    # Only exit if run as main script to avoid crashing the entire Butler system on import
    if __name__ == "__main__":
        sys.exit(1)

def run(file_path: Optional[str] = None):
    """
    高级混合 Markdown 转换与分析工具 (BHL-Powered)。
    """
    if not file_path:
        file_path = input("请输入要转换的文件路径: ").strip()

    if not os.path.exists(file_path):
        print(f"错误: 找不到文件 '{file_path}'")
        return

    filename = os.path.basename(file_path)
    print(f"[*] 正在处理文件: {filename} ...")

    # 1. Base Conversion
    try:
        markdown_content = convert(file_path)
    except Exception as e:
        print(f"[-] MarkItDown 转换失败: {e}")
        return

    # 2. Hybrid Analysis
    executable_path = os.path.join(project_root, "programs", "hybrid_doc_processor", "processor")

    # If binary doesn't exist, try to compile it (as a fallback/convenience)
    if not os.path.exists(executable_path):
        source_path = os.path.join(project_root, "programs", "hybrid_doc_processor", "processor.cpp")
        if os.path.exists(source_path):
            print("[*] 正在编译混合编程模块...")
            import subprocess
            try:
                subprocess.run(["g++", "-O3", source_path, "-o", executable_path], check=True)
            except subprocess.CalledProcessError as e:
                print(f"[-] 编译失败: {e}")
            except FileNotFoundError:
                print("[-] 编译失败: 未找到 g++ 编译器")

    if os.path.exists(executable_path):
        print("[*] 正在调用 C++ 模块进行高性能分析...")
        # Create a temp file for the markdown content
        with tempfile.NamedTemporaryFile(mode='w', suffix='.md', delete=False, encoding='utf-8') as tf:
            tf.write(markdown_content)
            temp_md_path = tf.name

        try:
            with HybridLinkClient(executable_path) as client:
                analysis = client.call("analyze_file", {"file_path": temp_md_path})

                print("\n" + "="*40)
                print("         混合文档分析报告 (C++)")
                print("="*40)

                if analysis and "error" not in analysis:
                    print(f"总词数: {analysis.get('word_count')}")
                    print(f"独立词数: {analysis.get('unique_words')}")
                    print(f"处理耗时: {analysis.get('processing_time_ms'):.2f} ms")
                    print("\n前 10 个高频词:")
                    for kw in analysis.get('top_keywords', []):
                        print(f"  - {kw['word']}: {kw['count']}")
                else:
                    err_msg = analysis['error']['message'] if analysis else "未知错误"
                    print(f"分析失败: {err_msg}")
                print("="*40)
        finally:
            if os.path.exists(temp_md_path):
                os.remove(temp_md_path)
    else:
        print("[-] 警告: 混合编程模块不可用，跳过高级分析。")

    # Display content snippet
    print("\n--- 转换预览 (前 500 字符) ---\n")
    print(markdown_content[:500] + ("..." if len(markdown_content) > 500 else ""))

    # Save output
    save_path = file_path + ".md"
    try:
        with open(save_path, 'w', encoding='utf-8') as f:
            f.write(markdown_content)
        print(f"\n[+] 结果已保存至: {save_path}")
    except Exception as e:
        print(f"[-] 无法保存结果: {e}")

if __name__ == "__main__":
    target = sys.argv[1] if len(sys.argv) > 1 else None
    run(target)
