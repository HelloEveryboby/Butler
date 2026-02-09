import sys
import os

# HACK: This is a workaround for the environment's issue with editable installs.
# It ensures that the 'markitdown' package can be found when this module
# is imported by the butler application.
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'markitdown', 'src')))

from markitdown.main import convert
try:
    from sklearn.feature_extraction.text import TfidfVectorizer
    HAS_SKLEARN = True
except ImportError:
    HAS_SKLEARN = False

import re

def extract_keywords(text: str, top_n: int = 5):
    """
    Extracts keywords from text using TF-IDF.
    """
    if not HAS_SKLEARN or not text.strip():
        return []

    # Strip base64 images to avoid them becoming keywords
    text = re.sub(r'data:image/[^;]+;base64,[A-Za-z0-9+/=]+', '', text)

    try:
        vectorizer = TfidfVectorizer(stop_words='english', max_features=100)
        # We need at least two documents or a very long one to make TF-IDF meaningful,
        # but here we just want some 'important' words.
        # For a single document, it's just frequency basically.
        tfidf_matrix = vectorizer.fit_transform([text])
        feature_names = vectorizer.get_feature_names_out()
        scores = tfidf_matrix.toarray()[0]

        # Sort by score
        keyword_index = scores.argsort()[::-1][:top_n]
        return [feature_names[i] for i in keyword_index]
    except Exception:
        return []

def run(file_path: str = None, engine: str = "auto", model_path: str = None, keywords: bool = False):
    """
    Butler tool to convert files to Markdown with optional keyword extraction and OCR engine selection.

    Args:
        file_path: Path to the file to convert.
        engine: OCR engine ('auto', 'easyocr', 'tesseract').
        model_path: Path to offline models.
        keywords: Whether to extract and display keywords.
    """
    if not file_path:
        file_path = input("请输入文件路径: ")

    if not os.path.exists(file_path):
        print(f"Error: File not found at '{file_path}'")
        return

    print(f"正在转换 '{file_path}' 使用引擎: {engine}...")
    try:
        markdown_content = convert(file_path, engine=engine, model_path=model_path)

        if keywords:
            print("\n--- 关键词提取 ---")
            kw = extract_keywords(markdown_content)
            print(", ".join(kw) if kw else "未提取到关键词")

        print("\n--- 转换结果 ---")
        print(markdown_content)
        return markdown_content
    except Exception as e:
        print(f"An error occurred during conversion: {e}")

if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="Butler Markdown Converter Tool")
    parser.add_argument("file_path", nargs="?", help="Path to the file to convert")
    parser.add_argument("--engine", default="auto", help="OCR engine ('auto', 'easyocr', 'tesseract')")
    parser.add_argument("--model_path", help="Path to offline models")
    parser.add_argument("--keywords", action="store_true", help="Extract keywords")

    args = parser.parse_args()
    run(file_path=args.file_path, engine=args.engine, model_path=args.model_path, keywords=args.keywords)
