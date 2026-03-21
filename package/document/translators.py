import os
import requests
import uuid
from bs4 import BeautifulSoup
from dotenv import load_dotenv
from package.core_utils.config_loader import config_loader
from package.core_utils.quota_manager import quota_manager

def load_api_key():
    return config_loader.get("api.deepseek.key")

def detect_language(text):
    if not quota_manager.check_quota():
        return "quota_exceeded"

    api_key = load_api_key()
    endpoint = config_loader.get("api.deepseek.endpoint", "https://api.deepseek.com/v1") + "/chat/completions"
    
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json"
    }
    
    payload = {
        "model": "deepseek-chat",
        "messages": [
            {"role": "system", "content": "You are a language detector. Respond only with the ISO 639-1 language code of the input text (e.g., 'en', 'fr', 'ja')."},
            {"role": "user", "content": text}
        ],
        "temperature": 0
    }

    response = requests.post(endpoint, headers=headers, json=payload)
    response.raise_for_status()
    resp_json = response.json()
    
    # Update quota
    usage = resp_json.get('usage', {})
    total_tokens = usage.get('total_tokens', 0)
    if total_tokens > 0:
        quota_manager.update_usage(total_tokens)

    language = resp_json['choices'][0]['message']['content'].strip().lower()
    return language

def translate_text(text):
    if not quota_manager.check_quota():
        return "Error: API 额度已用尽。"

    api_key = load_api_key()
    endpoint = config_loader.get("api.deepseek.endpoint", "https://api.deepseek.com/v1") + "/chat/completions"

    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json"
    }

    payload = {
        "model": "deepseek-chat",
        "messages": [
            {"role": "system", "content": "You are a professional translator. Translate the following text to Simplified Chinese (zh-CN). Provide only the translated text without any explanations."},
            {"role": "user", "content": text}
        ],
        "temperature": 1.1 # DeepSeek recommended for translation
    }

    response = requests.post(endpoint, headers=headers, json=payload)
    response.raise_for_status()
    resp_json = response.json()

    # Update quota
    usage = resp_json.get('usage', {})
    total_tokens = usage.get('total_tokens', 0)
    if total_tokens > 0:
        quota_manager.update_usage(total_tokens)

    translated_text = resp_json['choices'][0]['message']['content'].strip()
    
    return translated_text

def translate_file(input_file, output_file):
    with open(input_file, 'r', encoding='utf-8') as file:
        text = file.read()

    translated_text = translate_text(text)

    with open(output_file, 'w', encoding='utf-8') as file:
        file.write(translated_text)

    print(f"文件翻译成功，已保存到 {output_file}")

def translate_website(url):
    response = requests.get(url)
    soup = BeautifulSoup(response.content, 'html.parser')

    text_elements = soup.find_all(text=True)

    text_to_translate = "\n".join([element.strip() for element in text_elements if element.strip()])

    translated_text = translate_text(text_to_translate)

    for element in text_elements:
        if element.strip():
            translated_text = translate_text(element.strip())
            element.replace_with(translated_text)

    translated_html = soup.prettify()
    print(translated_html)

def translators():
    choice = input("请选择翻译类型: 1. 文件 2. 网页\n")

    if choice == '1':
        file_path = input("请输入文件路径:\n")
        output_file = input("请输入输出文件路径:\n")
        translate_file(file_path, output_file)
    elif choice == '2':
        url = input("请输入网页URL:\n")
        translate_website(url)
    else:
        print("无效选择")

if __name__ == "__main__":
    translators()
