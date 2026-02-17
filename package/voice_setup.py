import os
import zipfile
import requests
from tqdm import tqdm
from package.log_manager import LogManager

logger = LogManager.get_logger(__name__)

VOSK_CN_MODEL_URL = "https://alphacephei.com/vosk/models/vosk-model-small-cn-0.22.zip"
MODEL_NAME = "vosk-model-small-cn-0.22"

def download_model(url, save_path):
    print(f"正在从 {url} 下载语音模型...")
    response = requests.get(url, stream=True)
    total_size = int(response.headers.get('content-length', 0))

    with open(save_path, 'wb') as f, tqdm(
        desc=save_path,
        total=total_size,
        unit='iB',
        unit_scale=True,
        unit_divisor=1024,
    ) as bar:
        for data in response.iter_content(chunk_size=1024):
            size = f.write(data)
            bar.update(size)

def extract_zip(zip_path, extract_to):
    print(f"正在解压 {zip_path}...")
    with zipfile.ZipFile(zip_path, 'r') as zip_ref:
        zip_ref.extractall(extract_to)

def run(*args, **kwargs):
    """环境配置工具入口。"""
    print("=== Jarvis 语音环境配置工具 ===")

    # 1. 检查 API Keys
    keys = ["DEEPSEEK_API_KEY", "PICOVOICE_ACCESS_KEY", "AZURE_SPEECH_KEY"]
    for key in keys:
        val = os.getenv(key)
        status = "✅ 已设置" if val else "❌ 未设置"
        print(f"{key}: {status}")

    # 2. 检查并下载 Vosk 模型
    if not os.path.exists(MODEL_NAME):
        print(f"\n未发现中文语音模型 ({MODEL_NAME})。")
        confirm = input("是否现在下载并配置？(y/n): ").strip().lower()
        if confirm == 'y':
            zip_name = MODEL_NAME + ".zip"
            try:
                download_model(VOSK_CN_MODEL_URL, zip_name)
                extract_zip(zip_name, ".")
                os.remove(zip_name)
                print("\n✅ 中文语音模型配置成功！")
            except Exception as e:
                print(f"\n❌ 下载失败: {e}")
        else:
            print("\n跳过模型下载。注意：离线识别功能将不可用。")
    else:
        print(f"\n✅ 语音模型 {MODEL_NAME} 已就绪。")

    # 3. 检查资源文件
    res_path = "butler/core/resources"
    if not os.path.exists(res_path):
        os.makedirs(res_path)

    print("\n配置检查完成。")
    return "Setup check finished."

if __name__ == "__main__":
    run()
