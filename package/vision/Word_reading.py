import requests
from bs4 import BeautifulSoup
from package.core_utils.config_loader import config_loader
from package.core_utils.log_manager import LogManager
import tempfile
import os
import time

logger = LogManager.get_logger(__name__)

def text_to_speech(text):
    """使用百度语音 (Baidu TTS) 作为 Azure 的替代方案。"""
    try:
        from aip import AipSpeech
        app_id = config_loader.get("api.baidu.app_id")
        api_key = config_loader.get("api.baidu.api_key")
        secret_key = config_loader.get("api.baidu.secret_key")

        if not (app_id and api_key and secret_key):
             logger.warning("Baidu API keys missing. Falling back to offline TTS.")
             _offline_fallback_speak(text)
             return

        client = AipSpeech(app_id, api_key, secret_key)
        result = client.synthesis(text, 'zh', 1, {'vol': 5, 'per': 4})

        if not isinstance(result, dict):
            with tempfile.NamedTemporaryFile(delete=False, suffix='.mp3') as f:
                f.write(result)
                temp_file = f.name
            _play_audio(temp_file)
            os.remove(temp_file)
        else:
            logger.error(f"Baidu TTS error: {result}")
            _offline_fallback_speak(text)
    except Exception as e:
        logger.error(f"TTS Exception: {e}")
        _offline_fallback_speak(text)

def _offline_fallback_speak(text):
    try:
        import pyttsx3
        engine = pyttsx3.init()
        engine.say(text)
        engine.runAndWait()
    except Exception as e:
        logger.warning(f"Offline fallback TTS failed: {e}")

def _play_audio(file_path):
    try:
        import pygame
        if not pygame.mixer.get_init():
            pygame.mixer.init()
        pygame.mixer.music.load(file_path)
        pygame.mixer.music.play()
        while pygame.mixer.music.get_busy():
            time.sleep(0.1)
    except Exception as e:
        logger.warning(f"Could not play audio {file_path}: {e}")

def extract_webpage_content(url):
    try:
        response = requests.get(url, timeout=10)
        soup = BeautifulSoup(response.text, 'html.parser')
        return soup.get_text()
    except Exception as e:
        logger.error(f"无法获取网页内容: {e}")
        return ""

def read_text_from_file(file_path):
    try:
        with open(file_path, "r", encoding="utf-8") as file:
            return file.read()
    except Exception as e:
        logger.error(f"无法读取文档: {e}")
        return ""

if __name__ == "__main__":
    print("--- 网页/文档阅读工具 (Baidu TTS) ---")
    choice = input("输入 '1' 来阅读网页，或输入 '2' 来阅读文本文档: ")

    if choice == '1':
        url = input("请输入网页的URL: ")
        text = extract_webpage_content(url)
        if text: text_to_speech(text)
    elif choice == '2':
        path = input("请输入文本文档的路径: ")
        text = read_text_from_file(path)
        if text: text_to_speech(text)
    else:
        print("无效选择")
