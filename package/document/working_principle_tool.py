import os
import sys
import tempfile
import argparse
import time
from typing import Optional, List

# Use consistent project root resolution
project_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if project_root not in sys.path:
    sys.path.insert(0, project_root)

from package.document.document_interpreter import DocumentInterpreter
from butler.core.hybrid_link import HybridLinkClient
from package.core_utils.log_manager import LogManager

logger = LogManager.get_logger(__name__)

class WorkingPrincipleAnalyzer:
    def __init__(self):
        self.interpreter = DocumentInterpreter()
        self.executable_path = os.path.join(project_root, "programs", "hybrid_doc_processor", "processor")

        # Ensure binary exists
        if not os.path.exists(self.executable_path):
            self._compile_module()

    def _compile_module(self):
        source_path = os.path.join(project_root, "programs", "hybrid_doc_processor", "processor.cpp")
        if os.path.exists(source_path):
            logger.info("Compiling C++ hybrid_doc_processor...")
            import subprocess
            try:
                subprocess.run(["g++", "-O3", source_path, "-o", self.executable_path], check=True)
            except Exception as e:
                logger.error(f"Compilation failed: {e}")

    def analyze(self, file_path: str):
        if not os.path.exists(file_path):
            print(f"[-] Error: File not found: {file_path}")
            return

        print(f"[*] Analyzing working principles for: {os.path.basename(file_path)}")

        # 1. Extract full text using DocumentInterpreter
        print("[*] Extracting text from document...")
        content = self.interpreter.interpret(file_path)
        if not content or len(content) < 10:
            print("[-] Error: Could not extract meaningful text from the document.")
            return

        # 2. Use C++ Hybrid module to find key sections related to working principles
        sections = []
        if os.path.exists(self.executable_path):
            print("[*] Using C++ Hybrid module for high-speed section extraction...")

            # Write content to a temp file for C++ to read
            fd, temp_txt_path = tempfile.mkstemp(suffix='.txt')
            try:
                with os.fdopen(fd, 'w', encoding='utf-8') as tf:
                    tf.write(content)

                with HybridLinkClient(self.executable_path, fallback_enabled=False) as client:
                    # Give it a moment to stabilize
                    time.sleep(0.5)
                    response = client.call("extract_key_sections", {"file_path": temp_txt_path})

                    if response and isinstance(response, dict) and "sections" in response:
                        sections = response.get("sections", [])
                        print(f"[*] Found {len(sections)} key sections using C++ module.")
                    elif response:
                        print(f"[*] Debug: Raw hybrid response: {response}")
            except Exception as e:
                print(f"[-] Hybrid call failed: {e}")
            finally:
                if os.path.exists(temp_txt_path):
                    os.remove(temp_txt_path)
        else:
            print("[!] Warning: Hybrid module not available. Falling back to full-text AI analysis.")

        # 3. AI Summarization of Working Principles
        print("[*] Generating Working Principle report via AI...")

        context_for_ai = ""
        if sections:
            # Join the unique content from extracted sections
            seen_content = set()
            for s in sections:
                if s['content'] not in seen_content:
                    context_for_ai += f"--- Section (Keyword: {s['keyword']}) ---\n{s['content']}\n\n"
                    seen_content.add(s['content'])
        else:
            context_for_ai = content[:15000] # Fallback to first 15k chars

        prompt = "你是一个专业的技术分析师。请根据提供的文档内容，分析并总结该设备或系统的工作原理（Working Principles）。请从架构、核心机制、运行流程和技术关键点四个方面进行详细阐述。"

        # We reuse DocumentInterpreter's ask_question or summarize but with custom prompt
        try:
            report = self.interpreter.ask_question(context_for_ai, prompt)
        except Exception as e:
            report = f"AI Analysis failed: {e}"

        print("\n" + "="*50)
        print("          工作原理深度分析报告 (混合编程驱动)")
        print("="*50)
        print(report)
        print("="*50)

        # Save to file
        save_path = file_path + "_principles.md"
        with open(save_path, 'w', encoding='utf-8') as f:
            f.write(f"# 工作原理分析报告: {os.path.basename(file_path)}\n\n")
            f.write(report)
        print(f"\n[+] 报告已保存至: {save_path}")

def run(file_path: Optional[str] = None):
    if not file_path:
        file_path = input("请输入文档路径: ").strip().strip('"').strip("'")

    analyzer = WorkingPrincipleAnalyzer()
    analyzer.analyze(file_path)

if __name__ == "__main__":
    path = sys.argv[1] if len(sys.argv) > 1 else None
    run(path)
