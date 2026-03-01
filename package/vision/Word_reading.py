import os
import requests
import tempfile
import time
from bs4 import BeautifulSoup
from package.core_utils.config_loader import config_loader

def text_to_speech(text):
    # 配置 Baidu Speech 服务的 API Key 等
    try:
        from aip import AipSpeech
    except ImportError:
        print("错误：请安装 baidu-aip 库 (pip install baidu-aip)")
        return

    app_id = config_loader.get("api.baidu.app_id")
    api_key = config_loader.get("api.baidu.api_key")
    secret_key = config_loader.get("api.baidu.secret_key")

    if not all([app_id, api_key, secret_key]):
        print("错误：未在配置中找到完整的百度 API 信息。")
        return

    client = AipSpeech(app_id, api_key, secret_key)

    # 合成语音
    result = client.synthesis(text, 'zh', 1, {
        'vol': 5,
        'per': 4, # 4 是常用女声
    })

    # 检查合成结果并播放
    if not isinstance(result, dict):
        with tempfile.NamedTemporaryFile(delete=False, suffix='.mp3') as f:
            f.write(result)
            temp_file = f.name

        try:
            import pygame
            if not pygame.mixer.get_init():
                pygame.mixer.init()
            pygame.mixer.music.load(temp_file)
            pygame.mixer.music.play()
            while pygame.mixer.music.get_busy():
                time.sleep(0.1)
            print("语音合成成功并播放完毕！")
        except ImportError:
            print(f"语音合成成功，已保存到 {temp_file} (未安装 pygame，无法直接播放)")
        except Exception as e:
            print(f"播放失败: {e}")
        finally:
            if os.path.exists(temp_file):
                os.remove(temp_file)
    else:
        print(f"语音合成失败: {result}")

def extract_webpage_content(url):
    try:
        response = requests.get(url)
        soup = BeautifulSoup(response.text, 'html.parser')
        content = soup.get_text()  # 提取网页上的所有文本
        return content
    except Exception as e:
        print(f"无法获取网页内容: {e}")
        return ""

def read_text_from_file(file_path):
    try:
        with open(file_path, "r", encoding="utf-8") as file:
            return file.read()
    except Exception as e:
        print(f"无法读取文档: {e}")
        return ""

if __name__ == "__main__":
    choice = input("输入 '1' 来阅读网页，或输入 '2' 来阅读文本文档: ")

    if choice == '1':
        url = input("请输入网页的URL: ")
        webpage_text = extract_webpage_content(url)
        if webpage_text:
            print("网页内容：", webpage_text)
            text_to_speech(webpage_text)
    
    elif choice == '2':
        file_path = input("请输入文本文档的路径: ")
        document_text = read_text_from_file(file_path)
        if document_text:
            print("文档内容：", document_text)
            text_to_speech(document_text)
    
    else:
        print("无效选择，请输入 '1' 或 '2'")
