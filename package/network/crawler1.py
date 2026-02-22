import requests
from bs4 import BeautifulSoup
import logging
from urllib.parse import urljoin, urlparse

# 日志配置
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class AutoCrawler:
    def __init__(self, start_url="https://www.bing.com", max_depth=2):
        self.start_url = start_url
        self.max_depth = max_depth
        self.visited_urls = set()
        self.url_queue = []
        self.domain_restriction = None  # 可选：限制爬取同一域名

    def is_valid_url(self, url):
        """检查URL是否合法"""
        parsed = urlparse(url)
        return bool(parsed.netloc) and bool(parsed.scheme)

    def get_domain(self, url):
        """提取主域名（用于限制爬取范围）"""
        return urlparse(url).netloc

    def extract_links(self, url):
        """从页面提取所有有效链接"""
        try:
            response = requests.get(url, timeout=5)
            soup = BeautifulSoup(response.text, 'html.parser')
            links = set()
            for a_tag in soup.find_all('a', href=True):
                href = a_tag['href']
                full_url = urljoin(url, href)  # 处理相对路径
                if self.is_valid_url(full_url):
                    if not self.domain_restriction or self.get_domain(full_url) == self.domain_restriction:
                        links.add(full_url)
            return links
        except Exception as e:
            logger.error(f"提取链接失败 {url}: {e}")
            return set()

    def crawl(self):
        """自动爬取网站"""
        self.url_queue.append((self.start_url, 0))  # (url, current_depth)
        self.domain_restriction = self.get_domain(self.start_url)  # 限制同一域名

        while self.url_queue:
            url, depth = self.url_queue.pop(0)
            if url in self.visited_urls or depth > self.max_depth:
                continue

            logger.info(f"正在爬取: {url} (深度: {depth})")
            self.visited_urls.add(url)

            try:
                links = self.extract_links(url)
                for link in links:
                    if link not in self.visited_urls:
                        self.url_queue.append((link, depth + 1))
            except Exception as e:
                logger.error(f"爬取失败 {url}: {e}")

        logger.info(f"爬取完成！总计访问 {len(self.visited_urls)} 个页面。")

if __name__ == '__main__':
    crawler = AutoCrawler(start_url="https://www.bing.com", max_depth=1)
    crawler.crawl()
