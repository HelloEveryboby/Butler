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
            soup = BeautifulSoup(response.text, "html.parser")

            images = []
            # Bing image search results are often in 'm' attributes of 'a' tags with class 'iusc'
            for img_tag in soup.find_all("a", class_="iusc"):
                m_attr = img_tag.get("m")
                if m_attr:
                    try:
                        m_data = json.loads(m_attr)
                        img_url = m_data.get("murl")
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

        visual_search_url = "https://www.bing.com/images/searchbyimage"
        try:
            with open(image_path, "rb") as f:
                files = {"image": (os.path.basename(image_path), f, "image/jpeg")}
                response = requests.post(
                    visual_search_url,
                    files=files,
                    headers=self.headers,
                    allow_redirects=True,
                )

            return {
                "results_url": response.url,
                "status": "Success" if response.status_code == 200 else "Failed",
            }
        except Exception as e:
            logger.error(f"Error in reverse_search: {e}")
            return None

    def search_local_images(self, directory, pattern=""):
        """Search for image files in a local directory."""
        logger.info(f"Searching local images in {directory} with pattern: {pattern}")
        image_extensions = (".jpg", ".jpeg", ".png", ".gif", ".bmp", ".webp")
        found_images = []

        if not os.path.isdir(directory):
            logger.error(f"Not a directory: {directory}")
            return []

        for root, _, files in os.walk(directory):
            for file in files:
                if file.lower().endswith(image_extensions):
                    if not pattern or pattern.lower() in file.lower():
                        found_images.append(os.path.join(root, file))

        return found_images

    def batch_reverse_search(self, directory):
        """Perform reverse searches for all images in a local directory."""
        logger.info(f"Batch reverse search for images in: {directory}")
        images = self.search_local_images(directory)
        batch_results = {}

        for img_path in images:
            res = self.reverse_search(img_path)
            if res:
                batch_results[img_path] = res["results_url"]

        return batch_results


def run(*args, **kwargs):
    tool = ImageSearchTool()
    query = kwargs.get("query") or kwargs.get("search_query")
    path = kwargs.get("path") or kwargs.get("image_path")

    if path:
        if os.path.isdir(path):
            # If a directory is provided, we can search local images or batch reverse search
            mode = kwargs.get("mode", "local")  # 'local' or 'batch'
            if mode == "batch":
                results = tool.batch_reverse_search(path)
                print(f"Batch reverse search complete for {len(results)} images.")
                for p, url in results.items():
                    print(f"{os.path.basename(p)}: {url}")
                return results
            else:
                found = tool.search_local_images(path, query or "")
                print(f"Found {len(found)} local images in {path}:")
                for p in found[:20]:  # Show first 20
                    print(p)
                return found
        elif os.path.isfile(path):
            result = tool.reverse_search(path)
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
        print("1. 互联网关键词搜图")
        print("2. 互联网以图搜图")
        print("3. 本地文件夹搜索图片")
        print("4. 本地文件夹批量以图搜图")
        choice = input("请选择 (1/2/3/4): ")
        if choice == "1":
            q = input("请输入搜索关键词: ")
            images = tool.search_by_text(q)
            for url in images:
                print(url)
        elif choice == "2":
            p = input("请输入本地图片路径: ")
            res = tool.reverse_search(p)
            if res:
                print(f"搜索结果页面: {res['results_url']}")
        elif choice == "3":
            d = input("请输入本地文件夹路径: ")
            q = input("请输入文件名关键词 (可选): ")
            found = tool.search_local_images(d, q)
            for f in found:
                print(f)
        elif choice == "4":
            d = input("请输入本地文件夹路径: ")
            results = tool.batch_reverse_search(d)
            for p, url in results.items():
                print(f"{os.path.basename(p)}: {url}")


if __name__ == "__main__":
    run()
