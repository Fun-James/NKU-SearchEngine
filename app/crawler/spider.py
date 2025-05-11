import requests
from bs4 import BeautifulSoup
import time
from urllib.parse import urljoin, urlparse, unquote
import re
from urllib.robotparser import RobotFileParser
import ssl
import urllib3
import os
import hashlib
from flask import current_app

# 禁用SSL警告
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

# 配置SSL上下文
try:
    ssl_context = ssl.create_default_context()
    ssl_context.check_hostname = False
    ssl_context.verify_mode = ssl.CERT_NONE
    urllib3.util.ssl_.DEFAULT_CIPHERS = 'ALL:@SECLEVEL=1'
except Exception as e:
    print(f"SSL设置初始化失败：{e}")

# Define a consistent User-Agent for the crawler
CRAWLER_USER_AGENT = 'Mozilla/5.0 (compatible; NKUSearchBot/1.0; +http://www.nankai.edu.cn/search_info)'

def is_valid_url(url):
    """检查URL是否属于南开大学域名"""
    try:
        parsed = urlparse(url)
        return bool(re.search(r'(nankai\.edu\.cn)$', parsed.netloc))
    except:
        return False

def normalize_url(url):
    """规范化URL"""
    # 移除URL中的fragment
    url = re.sub(r'#.*$', '', url)
    # 移除URL中的多余参数（根据需要保留有意义的参数）
    url = re.sub(r'\?.*$', '', url)
    return url

def get_file_info(url):
    """获取文件类型信息"""
    doc_types = {
        '.pdf': ('application/pdf', 'PDF文档'),
        '.doc': ('application/msword', 'Word文档'),
        '.docx': ('application/vnd.openxmlformats-officedocument.wordprocessingml.document', 'Word文档'),
        '.xls': ('application/vnd.ms-excel', 'Excel表格'),
        '.xlsx': ('application/vnd.openxmlformats-officedocument.spreadsheetml.sheet', 'Excel表格'),
        '.ppt': ('application/vnd.ms-powerpoint', 'PowerPoint演示文稿'),
        '.pptx': ('application/vnd.openxmlformats-officedocument.presentationml.presentation', 'PowerPoint演示文稿')
    }
    
    file_ext = None
    for ext in doc_types:
        if url.lower().endswith(ext):
            file_ext = ext
            break
    
    if file_ext:
        mime_type, file_type = doc_types[file_ext]
        return {
            'is_document': True,
            'file_type': file_type,
            'mime_type': mime_type,
            'extension': file_ext
        }
    return None

def fetch_page(url, max_retries=3):
    """获取单个页面的内容，支持重试机制"""
    headers = {
        'User-Agent': CRAWLER_USER_AGENT,
        'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
        'Accept-Language': 'zh-CN,zh;q=0.9,en;q=0.8',
        'Connection': 'keep-alive'
    }
    
    # 设置requests的会话，完全禁用SSL验证
    session = requests.Session()
    session.verify = False
    
    # 尝试降级到HTTP协议
    if url.startswith('https://'):
        http_url = url.replace('https://', 'http://')
        print(f"尝试使用HTTP协议: {http_url}")
    else:
        http_url = url
      # 检查是否是文档类型
    file_info = get_file_info(url)
    if file_info:
        try:
            # 对于文档类型，只获取头信息，不下载文件内容
            response = session.head(http_url, headers=headers, timeout=30)
            
            # 提取文件名并解码
            filename = url.split('/')[-1]
            try:
                decoded_filename = urllib.parse.unquote(filename)
                # 移除文件扩展名
                title = re.sub(r'\.(pdf|doc|docx|xls|xlsx|ppt|pptx)$', '', decoded_filename, flags=re.IGNORECASE)
                # 将下划线和连字符替换为空格
                title = re.sub(r'[_-]', ' ', title)
                # 添加文件类型提示
                title = f"{title} [{file_info['file_type']}]"
            except:
                title = f"{filename} [{file_info['file_type']}]"
                
            return {
                'url': url,
                'title': title,  # 使用处理后的文件名作为标题
                'content': f'[{file_info["file_type"]}] {url}',  # 在内容中标明文件类型
                'is_document': True,
                'file_type': file_info['file_type'],
                'mime_type': file_info['mime_type'],
                'snapshot_path': None  # 文档类型没有HTML快照
            }
        except requests.exceptions.RequestException:
            # 如果HTTP失败，尝试HTTPS
            try:
                response = session.head(url, headers=headers, timeout=30)
                return {
                    'url': url,
                    'title': url.split('/')[-1],
                    'content': f'[{file_info["file_type"]}] {url}',
                    'is_document': True,
                    'file_type': file_info['file_type'],
                    'mime_type': file_info['mime_type'],
                    'snapshot_path': None  # 文档类型没有HTML快照
                }
            except requests.exceptions.RequestException as e:
                print(f"Failed to fetch document {url}: {e}")
                return None
    
    # 处理普通网页
    for attempt in range(max_retries):
        try:
            # 先尝试HTTP
            response = session.get(http_url, headers=headers, timeout=30)
            response.raise_for_status()
            response.encoding = response.apparent_encoding
            
            # 检查是否有内容
            if not response.text:
                raise requests.exceptions.RequestException("Empty response")
                
            soup = BeautifulSoup(response.text, 'html.parser')
            
            # 提取页面信息
            title = extract_title(soup)
            content = extract_content(soup)
            links = parse_links(response.text, url)
            
            # --- 新增：保存网页快照 ---
            snapshot_path = None
            try:
                snapshot_folder = current_app.config['SNAPSHOT_FOLDER']
                if not os.path.exists(snapshot_folder):
                    os.makedirs(snapshot_folder)
                
                # 使用URL的MD5哈希值作为文件名，避免特殊字符和长度问题
                snapshot_filename = hashlib.md5(url.encode('utf-8')).hexdigest() + '.html'
                snapshot_path = os.path.join(snapshot_folder, snapshot_filename)
                
                with open(snapshot_path, 'w', encoding='utf-8') as f:
                    f.write(response.text)
                print(f"Saved snapshot for {url} to {snapshot_path}")
            except Exception as e:
                print(f"Error saving snapshot for {url}: {e}")
                snapshot_path = None  # 如果保存失败，则路径为None
            # --- 网页快照保存结束 ---

            return {
                'url': url,  # 保留原始URL
                'title': title,
                'content': content,  # 这是提取后的纯文本内容
                'html_content': response.text,  # 保留原始HTML文本
                'links': links,
                'is_document': False,
                'file_type': 'webpage',
                'mime_type': 'text/html',
                'snapshot_path': snapshot_path  # 新增快照路径
            }
        except requests.exceptions.RequestException as e:
            # 如果是最后一次尝试且使用的是HTTP，则尝试原始HTTPS
            if attempt == max_retries - 1 and http_url != url:
                try:
                    print(f"尝试回退到HTTPS: {url}")
                    response = session.get(url, headers=headers, timeout=30)
                    response.raise_for_status()
                    response.encoding = response.apparent_encoding
                    
                    if not response.text:
                        raise requests.exceptions.RequestException("Empty response")
                        
                    soup = BeautifulSoup(response.text, 'html.parser')
                    title = extract_title(soup)
                    content = extract_content(soup)
                    links = parse_links(response.text, url)
                    
                    # --- 新增：保存网页快照 (HTTPS回退时) ---
                    snapshot_path_https = None
                    try:
                        snapshot_folder = current_app.config['SNAPSHOT_FOLDER']
                        if not os.path.exists(snapshot_folder):
                            os.makedirs(snapshot_folder)
                        snapshot_filename = hashlib.md5(url.encode('utf-8')).hexdigest() + '.html'
                        snapshot_path_https = os.path.join(snapshot_folder, snapshot_filename)
                        with open(snapshot_path_https, 'w', encoding='utf-8') as f:
                            f.write(response.text)
                        print(f"Saved snapshot for {url} (HTTPS fallback) to {snapshot_path_https}")
                    except Exception as e_https:
                        print(f"Error saving snapshot for {url} (HTTPS fallback): {e_https}")
                        snapshot_path_https = None
                    # --- 网页快照保存结束 ---

                    return {
                        'url': url,
                        'title': title,
                        'content': content,
                        'html_content': response.text,  # 保留原始HTML文本
                        'links': links,
                        'is_document': False,
                        'file_type': 'webpage',
                        'mime_type': 'text/html',
                        'snapshot_path': snapshot_path_https  # 新增快照路径
                    }
                except requests.exceptions.RequestException as e_https_final:
                    print(f"Attempt {attempt + 1} failed for {url} (HTTPS fallback): {e_https_final}")
            else:
                print(f"Attempt {attempt + 1} failed for {http_url}: {e}")
            
            if attempt == max_retries - 1:
                print(f"Failed to fetch {url} after {max_retries} attempts")
                return None
            time.sleep(2 ** attempt)

def extract_title(soup):
    """提取页面标题"""
    # 尝试从title标签获取标题
    if soup.title and soup.title.string and len(soup.title.string.strip()) > 0:
        title = soup.title.string.strip()
        # 处理常见标题后缀，如 "- 南开大学"
        title = re.sub(r'\s*[-_|]\s*南开大学\s*$', '', title)
        return title
        
    # 尝试从h1标签提取标题
    h1 = soup.find('h1')
    if h1 and h1.get_text() and len(h1.get_text().strip()) > 0:
        return h1.get_text().strip()
        
    # 尝试从header中查找最大的标题
    for tag in ['h2', 'h3', 'h4']:
        header = soup.find(tag)
        if header and header.get_text() and len(header.get_text().strip()) > 0:
            return header.get_text().strip()
            
    # 尝试查找页面的第一个大字体文本
    for tag in ['strong', 'b', '.title', '.header', '.heading']:
        element = soup.select_one(tag)
        if element and element.get_text() and len(element.get_text().strip()) > 0:
            return element.get_text().strip()
            
    # 如果都没找到有效标题，则返回一个默认值
    return "南开大学网页"

def extract_content(soup):
    """提取页面中的有用内容"""
    # 删除脚本和样式元素
    for script in soup(["script", "style"]):
        script.decompose()
        
    # 获取正文内容
    text = soup.body.get_text() if soup.body else soup.get_text()
    
    # 进一步清理文本
    lines = [line.strip() for line in text.splitlines()]
    # 合并多行文本，去除空行
    text = ' '.join(line for line in lines if line)
    
    return text

def parse_links(html_content, base_url):
    """从HTML中解析链接"""
    soup = BeautifulSoup(html_content, 'html.parser')
    links = set()
    for a_tag in soup.find_all('a', href=True):
        href = a_tag['href']
        try:
            absolute_url = urljoin(base_url, href)
            normalized_url = normalize_url(absolute_url)
            if is_valid_url(normalized_url):
                links.add(normalized_url)
        except Exception as e:
            print(f"Error processing URL {href}: {e}")
    return links

def basic_crawler(start_url, max_pages=2000, delay=1, respect_robots=True, max_depth=5):
    """增强的爬虫逻辑
    
    参数:
    - start_url: 起始URL
    - max_pages: 最大爬取页面数
    - delay: 爬取延迟时间(秒)
    - respect_robots: 是否遵守robots.txt
    - max_depth: 最大爬取深度
    """
    if not is_valid_url(start_url):
        start_url = "https://www.nankai.edu.cn/"
    
    # 尝试使用HTTP协议访问
    if start_url.startswith('https://'):
        http_url = start_url.replace('https://', 'http://')
        print(f"同时尝试HTTP协议: {http_url}")
        pages_to_visit = {start_url: 1, http_url: 1}  # 同时加入HTTP和HTTPS版本
    else:
        pages_to_visit = {start_url: 1}
    
    # 创建一个会话用于所有请求
    session = requests.Session()
    session.verify = False  # 禁用SSL验证
    
    # 设置请求头
    headers = {
        'User-Agent': CRAWLER_USER_AGENT,
        'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
        'Accept-Language': 'zh-CN,zh;q=0.9,en;q=0.8',
        'Connection': 'keep-alive'
    }
    session.headers.update(headers)
        
    # Initialize RobotFileParser if needed
    rp = None
    if respect_robots:
        parsed_uri = urlparse(start_url)
        robots_url = f"{parsed_uri.scheme}://{parsed_uri.netloc}/robots.txt"
        try:
            print(f"Fetching robots.txt from: {robots_url}")
            
            # 使用会话请求robots.txt
            response = session.get(robots_url, timeout=30)
            if response.status_code == 200:
                rp = RobotFileParser()
                rp.parse(response.text.splitlines())
                print(f"Successfully read and parsed {robots_url}")
            else:
                print(f"Failed to fetch robots.txt, status code: {response.status_code}")
                rp = None
        except Exception as e:
            print(f"Could not fetch or parse robots.txt from {robots_url}: {str(e)}")
            print("Warning: Proceeding without robots.txt rules. This is not recommended for polite crawling.")
            rp = None

    visited_pages = set()
    crawled_data = []
    
    while pages_to_visit and len(visited_pages) < max_pages:
        # 获取下一个URL及其深度
        current_url = next(iter(pages_to_visit))
        current_depth = pages_to_visit.pop(current_url)
        
        if current_url in visited_pages:
            continue
        
        # 检查是否超过最大深度
        if current_depth > max_depth:
            continue
            
        # 检查robots.txt权限
        if rp and not rp.can_fetch(CRAWLER_USER_AGENT, current_url):
            print(f"Skipping (disallowed by robots.txt): {current_url}")
            visited_pages.add(current_url)  # 添加到已访问列表以避免重复检查
            continue
            
        print(f"Crawling ({len(visited_pages)+1}/{max_pages}): {current_url}")
        page_data = fetch_page(current_url)
        visited_pages.add(current_url)
        
        if page_data:
            if page_data['is_document']:
                crawled_data.append({
                    'url': current_url,
                    'title': page_data['title'],
                    'content': page_data['content'],  # 文档内容已经是处理过的文本或路径
                    'file_info': {
                        'file_type': page_data['file_type'],
                        'mime_type': page_data['mime_type']
                    },
                    'crawled_at': time.strftime('%Y-%m-%d %H:%M:%S'),
                    'snapshot_path': page_data.get('snapshot_path')  # 文档类型快照路径为None
                })
            else:
                # page_data['content'] 是已经处理过的文本内容
                content_text = page_data['content']
                
                crawled_data.append({
                    'url': current_url,
                    'title': page_data['title'],
                    'content': content_text,  # 索引纯文本内容
                    'crawled_at': time.strftime('%Y-%m-%d %H:%M:%S'),
                    'snapshot_path': page_data.get('snapshot_path')  # 新增快照路径
                })
            
            # 解析并添加新链接，设置新深度
            if not page_data['is_document']:
                # 直接使用 fetch_page 返回的 'links' 字段
                # 'links' 字段是由 fetch_page 中的 parse_links 从原始HTML生成的
                new_links_from_page = page_data.get('links', set())
                for link in new_links_from_page:
                    if link not in visited_pages and link not in pages_to_visit:
                        pages_to_visit[link] = current_depth + 1
            
            # 控制抓取速度
            time.sleep(delay)  # 可配置的爬取延迟
            
            # 每抓取100个页面，暂停较长时间，避免对服务器压力过大
            if len(visited_pages) % 100 == 0:
                print(f"Crawled {len(visited_pages)} pages, taking a short break...")
                time.sleep(delay * 5)
    
    return crawled_data

def spider_main(start_url="https://www.nankai.edu.cn/", 
             max_pages=100, 
             delay=1, 
             respect_robots=True, 
             max_depth=3):
    """爬虫主函数，便于从外部调用"""
    data = basic_crawler(start_url, max_pages, delay, respect_robots, max_depth)
    return data

if __name__ == '__main__':
    seed_url = "https://www.nankai.edu.cn/"
    data = basic_crawler(seed_url, max_pages=10, delay=1, respect_robots=True, max_depth=2)  # 测试时使用较小的页面数
    print(f"\nCrawling Summary:")
    print(f"Total pages crawled: {len(data)}")
    print("\nSample of crawled content:")
    for item in data[:3]:  # 显示前3个页面的信息
        print(f"\nTitle: {item['title']}")
        print(f"URL: {item['url']}")
        print(f"Content length: {len(item['content'])} characters")
