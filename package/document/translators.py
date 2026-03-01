import os
import requests
import uuid
import json
from bs4 import BeautifulSoup
from package.core_utils.config_loader import config_loader
from package.core_utils.log_manager import LogManager
from package.document.document_interpreter import DocumentInterpreter

logger = LogManager.get_logger(__name__)

def get_deepseek_config():
    api_key = config_loader.get("api.deepseek.key")
    endpoint = config_loader.get("api.deepseek.endpoint", "https://api.deepseek.com/v1")
    return api_key, endpoint

def translate_text(text, target_lang='zh'):
    """使用 DeepSeek API 进行文本翻译。"""
    api_key, endpoint = get_deepseek_config()
    if not api_key:
        logger.error("DeepSeek API key missing for translation.")
        return f"Error: DeepSeek API key not found. (Text: {text[:50]}...)"

    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json"
    }

    # 使用 System Prompt 指导翻译
    system_prompt = f"You are a professional translator. Translate the following text into {target_lang}. Preserve the tone and formatting. Return ONLY the translated text without any explanations or introductory remarks."
    
    payload = {
        "model": "deepseek-chat",
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": text}
        ],
        "temperature": 0.3,
        "max_tokens": 2048
    }

    try:
        response = requests.post(f"{endpoint}/chat/completions", headers=headers, json=payload, timeout=60)
        response.raise_for_status()
        translated_text = response.json()['choices'][0]['message']['content'].strip()
        return translated_text
    except Exception as e:
        logger.error(f"DeepSeek translation failed: {e}")
        return f"Translation error: {e}"

def detect_language(text):
    """
    使用简单的启发式或 DeepSeek 识别语言。
    为了节省 API，默认返回 'auto'，让 DeepSeek 在翻译时自动处理。
    如果确实需要单独识别：
    """
    # 实际上，DeepSeek 翻译时不需要预先知道源语言，因此此函数在当前流程中可选
    # 但为了保持兼容性，提供一个基于正则的简单判断
    import re
    chinese_chars = re.findall(r'[\u4e00-\u9fff]', text[:100])
    if len(chinese_chars) > 5:
        return "zh"
    return "en"

def translate_file(input_file, output_file, skip_confirmation=True):
    """
    翻译文件。支持文本、PDF、Word、PPTX 等。
    如果 skip_confirmation=False, 则仅进行提取并返回元数据。
    """
    try:
        ext = os.path.splitext(input_file)[1].lower()
        interpreter = DocumentInterpreter()

        # 1. 提取文本
        content = interpreter.interpret(input_file)
        char_count = len(content)

        if not skip_confirmation:
            return {"status": "pending", "char_count": char_count, "content_snippet": content[:500]}

        # 2. 翻译文本
        # 注意: 如果文件过大，可能需要分片翻译。目前先直接翻译。
        translated_text = translate_text(content)

        # 3. 保存翻译后的内容 (保存为文本或 Markdown)
        with open(output_file, 'w', encoding='utf-8') as file:
            file.write(translated_text)

        logger.info(f"文件翻译成功: {input_file} -> {output_file}")
        return {"status": "success", "output_file": output_file, "char_count": char_count}
    except Exception as e:
        logger.error(f"文件翻译失败: {e}")
        return {"status": "error", "message": str(e)}

def translate_website(url):
    try:
        response = requests.get(url, timeout=15)
        response.raise_for_status()
        soup = BeautifulSoup(response.content, 'html.parser')

        # 找到所有包含文本的元素
        text_elements = soup.find_all(text=True)

        # 批量处理以节省 API (每 1000 字符分块)
        # 简单起见，这里逐个元素处理，或者收集后一次性翻译
        # 逐个处理会保持 HTML 结构更稳健，但速度慢

        for element in text_elements:
            if element.parent.name in ['script', 'style', 'head', 'title', 'meta', '[document]']:
                continue

            original_text = element.strip()
            if original_text and len(original_text) > 2:
                # 只有非中文才翻译 (简单过滤)
                if detect_language(original_text) != 'zh':
                    translated = translate_text(original_text)
                    element.replace_with(translated)

        translated_html = soup.prettify()
        print(translated_html)
        return translated_html
    except Exception as e:
        print(f"网页翻译失败: {e}")
        return None

def translators():
    print("--- 翻译工具 (Powered by DeepSeek) ---")
    choice = input("请选择翻译类型: 1. 文件 2. 网页 3. 实时文本\n")

    if choice == '1':
        file_path = input("请输入文件路径:\n")
        output_file = input("请输入输出文件路径:\n")
        translate_file(file_path, output_file)
    elif choice == '2':
        url = input("请输入网页URL:\n")
        translate_website(url)
    elif choice == '3':
        text = input("请输入要翻译的内容:\n")
        print(f"翻译结果: {translate_text(text)}")
    else:
        print("无效选择")

if __name__ == "__main__":
    translators()
