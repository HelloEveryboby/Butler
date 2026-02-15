"""
翻译工具。支持使用 Azure 翻译服务进行文本、文件和网页的翻译。
"""
import os
import requests
import uuid
from bs4 import BeautifulSoup
from dotenv import load_dotenv

def load_api_key():
    load_dotenv()
    return os.getenv('AZURE_TRANSLATE_KEY')

def detect_language(text):
    api_key = load_api_key()
    endpoint = "https://api.cognitive.microsofttranslator.com"
    
    path = '/detect'
    constructed_url = endpoint + path

    headers = {
        'Ocp-Apim-Subscription-Key': api_key,
        'Content-Type': 'application/json',
        'X-ClientTraceId': str(uuid.uuid4())
    }
    body = [{ 'text': text }]
    
    response = requests.post(constructed_url, headers=headers, json=body)
    response.raise_for_status()
    
    language = response.json()[0]['language']
    return language

def translate_text(text):
    api_key = load_api_key()
    endpoint = "https://api.cognitive.microsofttranslator.com"

    detected_language = detect_language(text)

    headers = {
        "Ocp-Apim-Subscription-Key": api_key,
        "Content-Type": "application/json",
        "X-ClientTraceId": str(uuid.uuid4())
    }
    params = {
        "api-version": "3.0",
        "from": detected_language,
        "to": 'zh'
    }

    translate_url = f"{endpoint}/translate"
    body = [{"text": text}]
    response = requests.post(translate_url, headers=headers, params=params, json=body)
    response.raise_for_status()
    translated_text = response.json()[0]['translations'][0]['text']
    
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

def run(text=None, **kwargs):
    """
    运行翻译工具。
    :param text: 要翻译的文本。
    """
    if text:
        result = translate_text(text)
        print(f"翻译结果: {result}")
        return result
    return translators()

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
