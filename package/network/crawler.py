import requests
import time
import random
import redis
import os
import concurrent.futures
import argparse
import sys
from bs4 import BeautifulSoup
from urllib.parse import urlparse, urljoin
from package.core_utils.log_manager import LogManager

# 日志配置
logger = LogManager.get_logger(__name__)

class ButlerCrawler:
    def __init__(self, downloaded_dir="./downloaded/", redis_host='localhost', redis_port=6379):
        self.downloaded_dir = downloaded_dir
        self.visited_urls = set()
        self.url_queue = []
        self.user_agents = [
            'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
            'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
            'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
        ]

        if not os.path.exists(self.downloaded_dir):
            os.makedirs(self.downloaded_dir)

        # 可选的 Redis 客户端
        try:
            self.redis_client = redis.StrictRedis(host=redis_host, port=redis_port, db=0, socket_timeout=2)
            self.redis_client.ping()
            logger.info("成功连接到 Redis，将用于存储状态。")
        except Exception:
            self.redis_client = None
            logger.warning("未能连接到 Redis，将使用本地内存存储状态。")

    def get_headers(self):
        return {'User-Agent': random.choice(self.user_agents)}

    def is_valid_url(self, url):
        parsed = urlparse(url)
        return bool(parsed.netloc) and bool(parsed.scheme)

    def download_file(self, url, filename=None):
        if not filename:
            filename = os.path.basename(urlparse(url).path)
            if not filename or '.' not in filename:
                # 尝试从 URL 或随机生成
                ext = ".jpg" # 默认假设图片
                filename = f"file_{int(time.time()*1000)}_{random.randint(1000, 9999)}{ext}"

        try:
            response = requests.get(url, headers=self.get_headers(), stream=True, timeout=10)
            response.raise_for_status()
            file_path = os.path.join(self.downloaded_dir, filename)
            with open(file_path, 'wb') as f:
                for chunk in response.iter_content(1024):
                    f.write(chunk)
            return True, f"成功下载: {url}"
        except Exception as e:
            return False, f"下载失败 {url}: {e}"

    def search_bing(self, query, file_type='image'):
        """在 Bing 上搜索多媒体文件"""
        search_url = 'https://www.bing.com/search'
        params = {'q': query}
        if file_type == 'image':
            params['tbm'] = 'isch'
        elif file_type == 'video':
            params['tbm'] = 'vid'

        try:
            response = requests.get(search_url, params=params, headers=self.get_headers(), timeout=10)
            response.raise_for_status()
            soup = BeautifulSoup(response.content, 'html.parser')

            file_links = []
            if file_type == 'image':
                # 增强的图片链接提取
                file_links = [img.get('src') for img in soup.find_all('img') if img.get('src') and img.get('src').startswith('http')]
            elif file_type == 'video':
                file_links = [a['href'] for a in soup.find_all('a', href=True) if 'watch' in a['href']]

            return list(set(file_links))
        except Exception as e:
            logger.error(f"Bing 搜索失败: {e}")
            return []

    def crawl_website(self, start_url, max_depth=2, restrict_domain=True):
        """递归爬取网站并下载发现的多媒体文件"""
        domain = urlparse(start_url).netloc
        self.url_queue = [(start_url, 0)]
        self.visited_urls = {start_url}

        while self.url_queue:
            url, depth = self.url_queue.pop(0)
            if depth > max_depth:
                continue

            logger.info(f"正在爬取 (深度 {depth}): {url}")

            try:
                response = requests.get(url, headers=self.get_headers(), timeout=10)
                response.raise_for_status()
                soup = BeautifulSoup(response.text, 'html.parser')

                # 提取链接进行递归
                for a_tag in soup.find_all('a', href=True):
                    full_url = urljoin(url, a_tag['href'])
                    if self.is_valid_url(full_url) and full_url not in self.visited_urls:
                        if not restrict_domain or urlparse(full_url).netloc == domain:
                            self.visited_urls.add(full_url)
                            self.url_queue.append((full_url, depth + 1))

                # 提取多媒体文件
                media_urls = []
                # 提取图片
                for img in soup.find_all('img'):
                    src = img.get('src')
                    if src: media_urls.append(urljoin(url, src))
                # 提取视频链接
                for a in soup.find_all('a', href=True):
                    href = a['href']
                    if 'watch' in href or href.endswith(('.mp4', '.avi', '.mov')):
                        media_urls.append(urljoin(url, href))

                # 下载
                if media_urls:
                    self.download_multiple(list(set(media_urls)))

            except Exception as e:
                logger.error(f"处理页面失败 {url}: {e}")

        if self.redis_client:
            try:
                self.redis_client.set('crawler_last_session_count', len(self.visited_urls))
            except: pass

        logger.info(f"爬取完成，总计访问 {len(self.visited_urls)} 个页面。")

    def download_multiple(self, urls):
        total = len(urls)
        completed = 0
        with concurrent.futures.ThreadPoolExecutor(max_workers=5) as executor:
            futures = [executor.submit(self.download_file, url) for url in urls]
            for future in concurrent.futures.as_completed(futures):
                completed += 1
                success, msg = future.result()
                if success:
                    print_progress_bar(completed, total)
                else:
                    logger.debug(msg)
        print() # 换行

def print_progress_bar(iteration, total, length=40):
    percent = ("{0:.1f}").format(100 * (iteration / float(total)))
    filled_length = int(length * iteration // total)
    bar = '█' * filled_length + '-' * (length - filled_length)
    sys.stdout.write(f'\r|{bar}| {percent}% 完成 ({iteration}/{total})')
    sys.stdout.flush()

# --- 兼容性函数 ---

def run(*args, **kwargs):
    url = kwargs.get('url')
    search_query = kwargs.get('search_query')
    file_type = kwargs.get('type', 'image')
    max_depth = kwargs.get('max_depth', 2)

    crawler = ButlerCrawler()
    if url:
        crawler.crawl_website(url, max_depth=max_depth)
    elif search_query:
        links = crawler.search_bing(search_query, file_type)
        if links:
            logger.info(f"搜索到 {len(links)} 个链接，开始下载...")
            crawler.download_multiple(links)
        else:
            logger.info("未找到相关结果。")
    else:
        logger.warning("未提供 URL 或搜索关键词。")

def run_scrapy_crawler(query):
    crawler = ButlerCrawler()
    links = crawler.search_bing(query, 'image')
    if links:
        return "\n".join(links)
    return "未找到结果。"

# --- 交互式与命令行 ---

def run_interactive():
    crawler = ButlerCrawler()
    print("\n" + "="*30)
    print("   Butler 综合爬虫工具")
    print("="*30)
    print("1. 搜索并下载 (Bing)")
    print("2. 递归爬取网站 (广度优先)")
    print("q. 退出")
    choice = input("\n请选择模式: ").strip().lower()

    if choice == '1':
        query = input("输入搜索关键词: ").strip()
        if not query: return
        file_type = input("文件类型 (image/video, 默认 image): ").strip() or 'image'
        links = crawler.search_bing(query, file_type)

        if not links:
            print("未找到相关结果。")
            return

        print(f"\n找到 {len(links)} 个结果:")
        for i, link in enumerate(links):
            print(f"{i+1}. {link}")

        indices = input("\n输入要下载的编号 (例如 1,2,3 或 'all', 'q' 退出): ").strip().lower()
        if indices == 'q': return

        to_download = []
        if indices == 'all':
            to_download = links
        else:
            try:
                idx_list = [int(x.strip()) - 1 for x in indices.split(',')]
                to_download = [links[i] for i in idx_list if 0 <= i < len(links)]
            except (ValueError, IndexError):
                print("输入无效。")
                return

        if to_download:
            print(f"正在下载 {len(to_download)} 个文件...")
            crawler.download_multiple(to_download)

    elif choice == '2':
        url = input("输入起始 URL: ").strip()
        if not url: return
        try:
            depth = int(input("输入爬取深度 (默认 2): ").strip() or 2)
        except ValueError:
            depth = 2
        restrict = input("是否限制在同一域名下 (y/n, 默认 y): ").strip().lower() != 'n'
        crawler.crawl_website(url, max_depth=depth, restrict_domain=restrict)
    
    elif choice == 'q':
        sys.exit(0)

def main():
    parser = argparse.ArgumentParser(description="Butler Multimedia Crawler & Search Tool")
    parser.add_argument('--url', type=str, help='起始爬取 URL')
    parser.add_argument('--query', type=str, help='搜索关键词')
    parser.add_argument('--type', type=str, default='image', choices=['image', 'video'], help='搜索文件类型')
    parser.add_argument('--depth', type=int, default=2, help='爬取深度')
    args = parser.parse_args()

    if args.url or args.query:
        run(url=args.url, search_query=args.query, type=args.type, max_depth=args.depth)
    else:
        while True:
            try:
                run_interactive()
            except KeyboardInterrupt:
                print("\n用户中断。")
                break
            except Exception as e:
                print(f"\n发生错误: {e}")

if __name__ == '__main__':
    main()
