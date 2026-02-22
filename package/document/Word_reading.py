import azure.cognitiveservices.speech as speechsdk
import requests
from bs4 import BeautifulSoup

def text_to_speech(text):
    # 配置 Azure Speech 服务的 API Key 和区域
    speech_key = "Your-Azure-Speech-API-Key"
    service_region = "Your-Service-Region"  # 例如 "eastus"

    # 创建语音配置对象
    speech_config = speechsdk.SpeechConfig(subscription=speech_key, region=service_region)
    audio_config = speechsdk.AudioConfig(use_default_speaker=True)
    
    # 创建语音合成器
    speech_synthesizer = speechsdk.SpeechSynthesizer(speech_config=speech_config, audio_config=audio_config)

    # 合成语音并播放
    result = speech_synthesizer.speak_text_async(text).get()

    # 检查合成结果
    if result.reason == speechsdk.ResultReason.SynthesizingAudioCompleted:
        print("语音合成成功！")
    elif result.reason == speechsdk.ResultReason.Canceled:
        cancellation_details = result.cancellation_details
        print(f"语音合成被取消: {cancellation_details.reason}")
        if cancellation_details.reason == speechsdk.CancellationReason.Error:
            print(f"错误详情: {cancellation_details.error_details}")

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
