import os
import sys
import tempfile
import argparse
import time
from typing import Optional, List

# 使用一致的项目根路径解析
project_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if project_root not in sys.path:
    sys.path.insert(0, project_root)

from package.document.document_interpreter import DocumentInterpreter
from butler.core.hybrid_link import HybridLinkClient
from package.core_utils.log_manager import LogManager

logger = LogManager.get_logger(__name__)

class WorkingPrincipleAnalyzer:
    """工作原理分析器，结合 Python 编排和 C++ 高性能筛选。"""
    def __init__(self):
        self.interpreter = DocumentInterpreter()
        self.executable_path = os.path.join(project_root, "programs", "hybrid_doc_processor", "processor")

        # 确保二进制文件存在
        if not os.path.exists(self.executable_path):
            self._compile_module()

    def _compile_module(self):
        source_path = os.path.join(project_root, "programs", "hybrid_doc_processor", "processor.cpp")
        if os.path.exists(source_path):
            logger.info("正在编译 C++ 混合文档处理器...")
            import subprocess
            try:
                subprocess.run(["g++", "-O3", source_path, "-o", self.executable_path], check=True)
            except Exception as e:
                logger.error(f"编译失败: {e}")

    def analyze(self, file_path: str):
        if not os.path.exists(file_path):
            print(f"[-] 错误: 未找到文件: {file_path}")
            return

        print(f"[*] 正在分析工作原理: {os.path.basename(file_path)}")

        # 1. 使用 DocumentInterpreter 提取全文
        print("[*] 正在从文档中提取文本...")
        content = self.interpreter.interpret(file_path)
        if not content or len(content) < 10:
            print("[-] 错误: 无法从文档中提取有效文本。")
            return

        # 2. 使用 C++ 混合模块寻找与工作原理相关的关键章节
        sections = []
        if os.path.exists(self.executable_path):
            print("[*] 正在调用 C++ 混合模块进行高性能章节提取...")

            # 将内容写入临时文件供 C++ 读取
            fd, temp_txt_path = tempfile.mkstemp(suffix='.txt')
            try:
                with os.fdopen(fd, 'w', encoding='utf-8') as tf:
                    tf.write(content)

                with HybridLinkClient(self.executable_path, fallback_enabled=False) as client:
                    # 调用远程方法 (HybridLinkClient 内部处理进程启动和同步)
                    response = client.call("extract_key_sections", {"file_path": temp_txt_path})

                    if response and isinstance(response, dict) and "sections" in response:
                        sections = response.get("sections", [])
                        print(f"[*] 使用 C++ 模块发现了 {len(sections)} 个关键章节。")
                    elif response:
                        print(f"[*] 调试: 混合模块原始响应: {response}")
            except Exception as e:
                print(f"[-] 混合调用失败: {e}")
            finally:
                if os.path.exists(temp_txt_path):
                    os.remove(temp_txt_path)
        else:
            print("[!] 警告: 混合模块不可用。回退到全文 AI 分析。")

        # 3. 通过 AI 总结工作原理
        print("[*] 正在通过 AI 生成工作原理报告...")

        context_for_ai = ""
        if sections:
            # 合并提取章节的唯一内容
            seen_content = set()
            for s in sections:
                if s['content'] not in seen_content:
                    context_for_ai += f"--- 章节 (关键字: {s['keyword']}) ---\n{s['content']}\n\n"
                    seen_content.add(s['content'])
        else:
            context_for_ai = content[:15000] # 回退到前 15k 字符

        prompt = "你是一个专业的技术分析师。请根据提供的文档内容，分析并总结该设备或系统的工作原理（Working Principles）。请从架构、核心机制、运行流程和技术关键点四个方面进行详细阐述。"

        # 重用 DocumentInterpreter 的提问功能
        try:
            report = self.interpreter.ask_question(context_for_ai, prompt)
        except Exception as e:
            report = f"AI 分析失败: {e}"

        print("\n" + "="*50)
        print("          工作原理深度分析报告 (混合编程驱动)")
        print("="*50)
        print(report)
        print("="*50)

        # 保存到文件 (Markdown)
        save_path_md = file_path + "_principles.md"
        with open(save_path_md, 'w', encoding='utf-8') as f:
            f.write(f"# 工作原理分析报告: {os.path.basename(file_path)}\n\n")
            f.write(report)
        print(f"\n[+] Markdown 报告已保存至: {save_path_md}")

        # 导出为 PDF
        self._export_to_pdf(report, file_path + "_principles.pdf", os.path.basename(file_path))

    def _export_to_pdf(self, content: str, output_path: str, source_name: str):
        """将报告内容导出为 PDF。"""
        try:
            from fpdf import FPDF

            # 创建 PDF 对象
            pdf = FPDF()
            pdf.add_page()

            # 尝试使用系统中常见的的中文字体 (Linux/Debian 常用路径)
            font_found = False
            font_paths = [
                "/usr/share/fonts/truetype/wqy/wqy-microhei.ttc",
                "/usr/share/fonts/truetype/droid/DroidSansFallbackFull.ttf",
                "/usr/share/fonts/truetype/liberation/LiberationSans-Regular.ttf"
            ]

            for fp in font_paths:
                if os.path.exists(fp):
                    pdf.add_font("Chinese", "", fp)
                    pdf.set_font("Chinese", size=12)
                    font_found = True
                    break

            if not font_found:
                # 回退到标准字体 (可能不支持中文)
                pdf.set_font("Helvetica", size=12)
                logger.warning("未找到中文字体，PDF 导出可能出现乱码。")

            # 标题
            title_style = "B" if not font_found else "" # 中文字体通常不支持直接 set_font B
            pdf.set_font(pdf.font_family, style=title_style, size=16)

            title = f"工作原理分析报告: {source_name}"
            if not font_found:
                title = title.encode('ascii', 'ignore').decode('ascii')

            pdf.cell(0, 10, title, ln=True, align='C')
            pdf.ln(5)

            # 内容 (简单处理换行)
            pdf.set_font(pdf.font_family, size=12)
            for line in content.split('\n'):
                # 清除非 ASCII 字符如果未找到中文字体
                if not font_found:
                    line = line.encode('ascii', 'ignore').decode('ascii')
                pdf.multi_cell(0, 10, line)

            pdf.output(output_path)
            print(f"[+] PDF 报告已保存至: {output_path}")
        except Exception as e:
            logger.error(f"导出 PDF 失败: {e}")
            print(f"[-] 导出 PDF 失败: {e}")

def run(file_path: Optional[str] = None):
    if not file_path:
        file_path = input("请输入文档路径: ").strip().strip('"').strip("'")

    analyzer = WorkingPrincipleAnalyzer()
    analyzer.analyze(file_path)

if __name__ == "__main__":
    path = sys.argv[1] if len(sys.argv) > 1 else None
    run(path)
