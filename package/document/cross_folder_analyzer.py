import os
import re
from package.document.document_interpreter import DocumentInterpreter
from package.core_utils.log_manager import LogManager

logger = LogManager.get_logger(__name__)

class CrossFolderAnalyzer:
    """
    Scans folders and reveals patterns across documents.
    """
    def __init__(self):
        self.interpreter = DocumentInterpreter()

    def analyze_folders(self, folder_paths, query):
        results = []
        for folder in folder_paths:
            if not os.path.isdir(folder):
                continue

            for root, _, files in os.walk(folder):
                for file in files:
                    if file.lower().endswith(('.pdf', '.docx', '.xlsx', '.txt', '.md')):
                        file_path = os.path.join(root, file)
                        content = self.interpreter.interpret(file_path)
                        # Simple check for patterns
                        if re.search(query, content, re.IGNORECASE):
                            results.append({
                                "file": file,
                                "path": file_path,
                                "match_context": "Found matching pattern"
                            })

        return results

analyzer = CrossFolderAnalyzer()

def run(jarvis_app, entities, **kwargs):
    folders = entities.get("folders", [])
    query = entities.get("query", "")
    if not folders or not query:
        return "请提供文件夹路径和查询关键词。"

    findings = analyzer.analyze_folders(folders, query)
    if findings:
        summary = "在以下文件中发现了模式：\n" + "\n".join([f"- {f['file']} ({f['path']})" for f in findings])
        return summary
    return "未发现匹配模式。"
