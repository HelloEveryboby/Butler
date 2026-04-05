import os
import requests
import uuid
from bs4 import BeautifulSoup
from dotenv import load_dotenv
from package.core_utils.config_loader import config_loader
import json
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

def translate_bilingual(text, context=None):
    if not quota_manager.check_quota():
        return [{"source": "Error", "target": "API 额度已用尽。"}]

    api_key = load_api_key()
    endpoint = config_loader.get("api.deepseek.endpoint", "https://api.deepseek.com/v1") + "/chat/completions"

    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json"
    }

    prompt = "Translate the following text to Simplified Chinese. Return a JSON list of objects with 'source' and 'target' keys.\n"
    if context:
        prompt += f"Context/Metadata: {context}\n"
    prompt += f"Text:\n{text}"

    payload = {
        "model": "deepseek-chat",
        "messages": [
            {"role": "system", "content": "You are a professional translator. You must respond with a valid JSON array of objects containing 'source' and 'target' fields. No other text."},
            {"role": "user", "content": prompt}
        ],
        "temperature": 1.0
    }

    try:
        response = requests.post(endpoint, headers=headers, json=payload)
        response.raise_for_status()
        resp_json = response.json()

        usage = resp_json.get('usage', {})
        quota_manager.update_usage(usage.get('total_tokens', 0))

        content = resp_json['choices'][0]['message']['content'].strip()
        if content.startswith("```json"):
            content = content[7:]
        if content.endswith("```"):
            content = content[:-3]

        result = json.loads(content.strip())
        if isinstance(result, dict) and "translation" in result: # Handle common LLM wrapping
             result = result["translation"]
        return result
    except Exception as e:
        print(f"Error in translate_bilingual: {e}")
        return [{"source": text, "target": translate_text(text)}]

def translate_file(input_file, output_file):
    with open(input_file, 'r', encoding='utf-8') as file:
        text = file.read()

    translated_text = translate_text(text)

    with open(output_file, 'w', encoding='utf-8') as file:
        file.write(translated_text)

    print(f"文件翻译成功，已保存到 {output_file}")

def translate_website_bilingual(url):
    try:
        response = requests.get(url, timeout=10)
        response.raise_for_status()
        soup = BeautifulSoup(response.content, 'html.parser')

        # Remove scripts and styles
        for script in soup(["script", "style"]):
            script.extract()

        title = soup.title.string if soup.title else url

        # Simple heuristic for main content
        # In a real scenario, we might use a library like 'readability'
        paragraphs = soup.find_all(['p', 'h1', 'h2', 'h3', 'li'])
        content_text = "\n\n".join([p.get_text().strip() for p in paragraphs if len(p.get_text().strip()) > 20])

        # Limit content for API efficiency
        if len(content_text) > 2000:
            content_text = content_text[:2000] + "..."

        # Translate title for context
        translated_title = translate_text(title)
        if translated_title.startswith("[{") and '"target"' in translated_title:
            try:
                # In case translate_text was accidentally mocked or behaved like translate_bilingual
                parsed = json.loads(translated_title)
                if isinstance(parsed, list) and len(parsed) > 0:
                    translated_title = parsed[0].get("target", title)
            except Exception: pass

        # Translate content bilingually
        bilingual_data = translate_bilingual(content_text, context=f"Source URL: {url}, Title: {title}")

        return {
            "title_source": title,
            "title_target": translated_title,
            "url": url,
            "segments": bilingual_data
        }
    except Exception as e:
        print(f"Error in translate_website_bilingual: {e}")
        return {
            "title_source": "Error",
            "title_target": f"无法访问或解析网页: {e}",
            "url": url,
            "segments": []
        }

def translate_website(url):
    # Keep legacy for compatibility but print it nicely
    print(f"Translating website: {url}")
    data = translate_website_bilingual(url)
    print(json.dumps(data, indent=2, ensure_ascii=False))

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
