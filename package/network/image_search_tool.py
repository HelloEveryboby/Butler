import requests
from bs4 import BeautifulSoup
import os
import json
from package.core_utils.log_manager import LogManager
import urllib.parse

logger = LogManager.get_logger(__name__)

class ImageSearchTool:
    def __init__(self):
        self.headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/119.0.0.0 Safari/537.36"
        }

    def search_by_text(self, query, count=10):
        """Search images by text query using Bing."""
        logger.info(f"Searching images for: {query}")
        search_url = f"https://www.bing.com/images/search?q={urllib.parse.quote(query)}&form=HDRSC2"

        try:
            response = requests.get(search_url, headers=self.headers, timeout=10)
            response.raise_for_status()
            soup = BeautifulSoup(response.text, 'html.parser')

            images = []
            # Bing image search results are often in 'm' attributes of 'a' tags with class 'iusc'
            for img_tag in soup.find_all('a', class_='iusc'):
                m_attr = img_tag.get('m')
                if m_attr:
                    try:
                        m_data = json.loads(m_attr)
                        img_url = m_data.get('murl')
                        if img_url:
                            images.append(img_url)
                    except json.JSONDecodeError:
                        continue
                if len(images) >= count:
                    break

            return images
        except Exception as e:
            logger.error(f"Error in search_by_text: {e}")
            return []

    def reverse_search(self, image_path):
        """Reverse image search using Bing (simplified)."""
        logger.info(f"Performing reverse image search for: {image_path}")
        if not os.path.exists(image_path):
            logger.error(f"File not found: {image_path}")
            return None

        # Bing's Visual Search usually requires a POST to a specific endpoint or a multi-part form.
        # A simpler way for a tool is to provide the results page URL if possible,
        # but let's try to extract some basic info.

        # Note: True reverse search via scraping is complex due to CSRF and dynamic tokens.
        # For this version, we will provide a link and attempt to find "best guess" text if possible.

        visual_search_url = "https://www.bing.com/images/searchbyimage"
        try:
            with open(image_path, "rb") as f:
                files = {'image': (os.path.basename(image_path), f, 'image/jpeg')}
                # This is a simplified attempt; Bing might require more params
                response = requests.post(visual_search_url, files=files, headers=self.headers, allow_redirects=True)

            return {
                "results_url": response.url,
                "status": "Success" if response.status_code == 200 else "Failed"
            }
        except Exception as e:
            logger.error(f"Error in reverse_search: {e}")
            return None

def run(*args, **kwargs):
    tool = ImageSearchTool()
    query = kwargs.get('query') or kwargs.get('search_query')
    image_path = kwargs.get('image_path')

    if image_path:
        result = tool.reverse_search(image_path)
        if result:
            print(f"Reverse search results: {result['results_url']}")
            return result
    elif query:
        images = tool.search_by_text(query)
        if images:
            print(f"Found {len(images)} images for '{query}':")
            for i, url in enumerate(images, 1):
                print(f"{i}. {url}")
            return images
        else:
            print("No images found.")
    else:
        # Interactive mode
        print("--- 图片搜索工具 ---")
        choice = input("1. 关键词搜图\n2. 以图搜图\n请选择 (1/2): ")
        if choice == '1':
            q = input("请输入搜索关键词: ")
            images = tool.search_by_text(q)
            for url in images: print(url)
        elif choice == '2':
            p = input("请输入本地图片路径: ")
            res = tool.reverse_search(p)
            if res: print(f"搜索结果页面: {res['results_url']}")

if __name__ == "__main__":
    run()
