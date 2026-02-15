"""
网络爬虫工具。支持指定 URL 爬取资源或通过搜索引擎搜索并下载图片和视频。
"""
import requests
import time
import random
import redis
from bs4 import BeautifulSoup
import os
import concurrent.futures
import argparse
from package.log_manager import LogManager
from urllib.parse import urlparse, urljoin
from scrapy.crawler import CrawlerProcess
from scrapy.utils.project import get_project_settings
import scrapy

# 设置日志配置
logging = LogManager.get_logger(__name__)
downloaded = "./downloaded/"  # 存储数据文件

# 设置User Agent列表
user_agents = [
    'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/58.0.3029.110 Safari/537.3',
    # 在这里添加更多用户代理
]

# 随机选择 User Agent
def get_random_user_agent():
    return random.choice(user_agents)

# 设置headers
def get_headers():
    user_agent = get_random_user_agent()
    headers = {'User-Agent': user_agent}
    return headers

# 设置爬虫的起始url
start_url = 'https://www.bing.com'

# 设置爬虫的深度限制
max_depth = 2

# 设置爬虫的延迟时间
delay_time = 1

# 创建一个set来存储已经访问过的url
visited_urls = set()

# 创建一个队列来存储需要访问的url
url_queue = [start_url]

# 创建一个Redis客户端来存储爬虫的状态
redis_client = redis.StrictRedis(host='localhost', port=6379, db=0)

# 创建一个文件夹用于存储下载的文件
if not os.path.exists(downloaded):
    os.makedirs(downloaded)

def download_file(url, filename):
    try:
        response = requests.get(url, stream=True)
        response.raise_for_status()
        file_path = os.path.join(downloaded, filename)
        with open(file_path, 'wb') as f:
            for chunk in response.iter_content(1024):
                f.write(chunk)
        logging.info(f"下载 {url}")
    except requests.RequestException as e:
        logging.error(f"下载 {url}: {e}")

def search_and_crawl_files(search_query, file_type):
    search_url = 'https://www.bing.com/search'
    params = {'q': search_query}
    if file_type == 'image':
        params['tbm'] = 'isch'
    elif file_type == 'video':
        params['tbm'] = 'vid'
    headers = get_headers()
    try:
        response = requests.get(search_url, params=params, headers=headers)
        response.raise_for_status()
        soup = BeautifulSoup(response.content, 'html.parser')
        if file_type == 'image':
            file_links = [img.get('src') for img in soup.find_all('img')]
        elif file_type == 'video':
            file_links = [a['href'] for a in soup.find_all('a', href=True) if 'watch' in a['href']]
        logging.info("搜索结果:")
        for i, file_link in enumerate(file_links):
            logging.info(f"{i+1}. {file_link}")
        logging.info("")
        while True:
            choice = input(f"输入要下载的{file_type}编号(或'q'退出): ")
            if choice.lower() == 'q':
                break
            try:
                choice = int(choice)
                if 0 < choice <= len(file_links):
                    file_url = file_links[choice-1]
                    download_file(file_url, os.path.basename(file_url))
                else:
                    logging.warning("无效的选择")
            except ValueError:
                logging.warning("无效的输入")
    except requests.RequestException as e:
        logging.error(f"Failed to search {file_type}: {e}")
        return False  # 返回False表示失败
    return True  # 返回True表示成功

def print_progress_bar(iteration, total, length=40):
    percent = ("{0:.1f}").format(100 * (iteration / float(total)))
    filled_length = int(length * iteration // total)
    bar = '█' * filled_length + '-' * (length - filled_length)
    sys.stdout.write(f'\r|{bar}| {percent}% 完成')
    sys.stdout.flush()

def crawl_website(start_url, max_depth):
    while url_queue:
        url = url_queue.pop(0)
        if url in visited_urls:
            continue
        visited_urls.add(url)
        try:
            response = requests.get(url, headers=get_headers())
            response.raise_for_status()
            soup = BeautifulSoup(response.content, 'html.parser')
            links = [link.get('href') for link in soup.find_all('a', href=True)]
            for link in links:
                if link not in visited_urls:
                    url_queue.append(link)
            files = [img.get('src') for img in soup.find_all('img')] + \
                    [a['href'] for a in soup.find_all('a', href=True) if 'watch' in a['href']]
            print_progress_bar(0, len(files))   
            with concurrent.futures.ThreadPoolExecutor() as executor:
                futures = [executor.submit(download_file, file_url, os.path.basename(file_url)) for file_url in files]
                for i, future in enumerate(concurrent.futures.as_completed(futures)):
                    print_progress_bar(i + 1, len(files))
                time.sleep(delay_time + random.random())
        except requests.RequestException as e:
            logging.error(f"爬取 {url} 失败: {e}")
        if len(visited_urls) >= max_depth:
            break
    redis_client.set('crawler_state', str(len(visited_urls)))
    return True  # 返回True表示成功

def controlled_crawl(urls, delay):
    for url in urls:
        response = requests.get(url, headers=get_headers())
        # 处理响应
        time.sleep(delay)    

class MyScrapySpider(scrapy.Spider):
    name = "my_scrapy_spider"

    def __init__(self, search_query=None, *args, **kwargs):
        super(MyScrapySpider, self).__init__(*args, **kwargs)
        self.start_urls = [f'https://www.bing.com/images/search?q={search_query}']

    def parse(self, response):
        images = response.css('img::attr(src)').extract()
        for image_url in images:
            yield scrapy.Request(url=image_url, callback=self.download_image)

    def download_image(self, response):
        path = f'{downloaded}/{os.path.basename(response.url)}'
        with open(path, 'wb') as f:
            f.write(response.body)
        self.log(f'下载 {response.url}')    

def run(search_query=None, file_type='image', **kwargs):
    """
    运行爬虫工具。
    """
    try:
        # Avoid broken Jarvis.takecommand()
        pass
    except Exception:
        pass

    parser = argparse.ArgumentParser(description="Multimedia Search and Crawler")
    parser.add_argument('search_query', type=str, nargs='?', help='输入搜索查询')
    parser.add_argument('--type', type=str, default='image', choices=['image', 'video'], help='文件类型')
    args = parser.parse_args()
    search_query = args.search_query
    file_type = args.type
    
    if not search_query:
        search_query = input('搜索内容: ')
    
    # Fix input_str vs search_query
    input_str = search_query if search_query else input('搜索内容或URL: ')

    if urlparse(input_str).scheme:  # 如果输入的是网址
        success = crawl_website(input_str, max_depth)
        if not success:
            logging.info("切换到Scrapy爬虫")
            # run_scrapy_crawler(search_query) # Scrapy not fully set up
            
    else:  # 如果输入不是网址，作为搜索查询
        success = search_and_crawl_files(input_str, file_type)
        if not success:
            logging.info("切换到Scrapy爬虫")
            # run_scrapy_crawler(search_query)
    logging.info('爬虫结束！')

def crawler():
    run()
    
if __name__ == '__main__':
    run()
