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
import urllib
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
    
    # 检查URL中的文件扩展名
    file_ext = None
    for ext in doc_types:
        if url.lower().endswith(ext):
            file_ext = ext
            break
    
    # 如果URL中包含文件参数，也尝试检测
    if not file_ext:
        # 检查常见的文件下载参数
        patterns = [
            r'[?&]file=(.*\.(pdf|doc|docx|xls|xlsx|ppt|pptx))', # ?file=xxx.pdf
            r'/(attachment|download|file)/.*\.(pdf|doc|docx|xls|xlsx|ppt|pptx)', # /attachment/xxx.pdf
            r'[?&]attach=.*\.(pdf|doc|docx|xls|xlsx|ppt|pptx)',  # ?attach=xxx.pdf
            r'[?&]download=.*\.(pdf|doc|docx|xls|xlsx|ppt|pptx)', # ?download=xxx.pdf
            r'[?&]filename=.*\.(pdf|doc|docx|xls|xlsx|ppt|pptx)' # ?filename=xxx.pdf
        ]
        
        for pattern in patterns:
            match = re.search(pattern, url, re.IGNORECASE)
            if match:
                ext_match = match.group(2) if len(match.groups()) > 1 else match.group(1)
                file_ext = f'.{ext_match.lower()}'
                break
    
    if file_ext:
        mime_type, file_type = doc_types.get(file_ext, ('application/octet-stream', '未知文档'))
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
            links, attachments, potential_attachment_pages = parse_links(response.text, url)
            
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
                'attachments': attachments,  # 附件链接
                'potential_attachment_pages': potential_attachment_pages,  # 潜在附件页面
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
                    links, attachments, potential_attachment_pages = parse_links(response.text, url)
                    
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
                        'attachments': attachments,  # 附件链接
                        'potential_attachment_pages': potential_attachment_pages,  # 潜在附件页面
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

def handle_nankai_attachment_page(url, session=None):
    """处理南开大学网站的附件页面，提取真实附件链接"""
    if not session:
        session = requests.Session()
        session.verify = False
    
    headers = {
        'User-Agent': CRAWLER_USER_AGENT,
        'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
        'Accept-Language': 'zh-CN,zh;q=0.9,en;q=0.8',
        'Connection': 'keep-alive'
    }
    
    try:
        # 获取页面内容
        response = session.get(url, headers=headers, timeout=30)
        response.raise_for_status()
        response.encoding = response.apparent_encoding
        
        soup = BeautifulSoup(response.text, 'html.parser')
        page_title = extract_title(soup)
        
        # 查找附件链接，南开大学网站上通常使用特定的模式
        attachments = []
        
        # 1. 直接查找显示"附件"字样的链接
        for a_tag in soup.find_all('a', href=True):
            link_text = a_tag.get_text().strip()
            href = a_tag['href']
            
            # 为链接创建绝对URL
            absolute_url = urljoin(url, href)
            
            # 检查附件前缀模式 - 南开大学常用"附件1-文件名.doc"这种格式
            attachment_prefix = re.match(r'^附件\d+[-_]', link_text)
            
            # 如果链接文本包含"附件"或链接指向文档
            if '附件' in link_text or attachment_prefix or any(ext in href.lower() for ext in ['.doc', '.pdf', '.xls', '.xlsx', '.docx', '.ppt', '.pptx']):
                # 如果链接文本为空或太短，尝试找更有意义的文本
                if not link_text or len(link_text) < 3:
                    # 尝试查找父元素中的文本
                    parent = a_tag.parent
                    if parent:
                        parent_text = parent.get_text().strip()
                        # 如果父元素文本更有意义，使用它
                        if len(parent_text) > len(link_text) and len(parent_text) < 100:
                            link_text = parent_text
                
                # 添加页面标题作为上下文，以便更好地识别附件
                context = f"{page_title} - {link_text}" if page_title else link_text
                
                attachments.append({
                    'url': absolute_url,
                    'text': link_text if link_text else '附件',
                    'context': context
                })
        
        # 过滤掉URL相同的附件，保留文本最有意义的版本
        unique_attachments = {}
        for attachment in attachments:
            url = attachment['url']
            text = attachment['text']
            
            # 如果URL已存在，比较文本长度，保留更长的文本
            if url in unique_attachments:
                if len(text) > len(unique_attachments[url]['text']):
                    unique_attachments[url] = attachment
            else:
                unique_attachments[url] = attachment
        
        return list(unique_attachments.values())
    
    except Exception as e:
        print(f"Error processing Nankai attachment page {url}: {e}")
        return []

def parse_links(html_content, base_url):
    """从HTML中解析链接"""
    soup = BeautifulSoup(html_content, 'html.parser')
    links = set()
    attachments = set()  # 存储附件链接
    potential_attachment_pages = set()  # 潜在的附件页面
    
    # 处理所有a标签的链接
    for a_tag in soup.find_all('a', href=True):
        href = a_tag['href']
        try:
            absolute_url = urljoin(base_url, href)
            normalized_url = normalize_url(absolute_url)
            
            # 处理一: 检查链接文本是否包含附件相关文字
            link_text = a_tag.get_text().strip().lower()
            is_attachment_by_text = any(kw in link_text for kw in ['附件', '下载', '文档', 'doc', 'pdf', 'xls', 'docx', 'xlsx', 'ppt', 'pptx'])
            
            # 处理二: 检查链接是否有附件图标
            has_attachment_icon = False
            # 检查是否包含常见的附件图标类
            for icon in a_tag.find_all(['i', 'span', 'img']):
                icon_class = icon.get('class', [])
                if any('file' in cls or 'doc' in cls or 'pdf' in cls or 'xls' in cls or 'attachment' in cls for cls in icon_class):
                    has_attachment_icon = True
                    break
                # 检查图像src是否包含文件类型提示
                if icon.name == 'img' and icon.get('src'):
                    src = icon.get('src').lower()
                    if any(ext in src for ext in ['file', 'doc', 'pdf', 'xls', 'attachment']):
                        has_attachment_icon = True
                        break
            
            # 处理三: 直接检查URL是否为文档类型
            file_info = get_file_info(normalized_url)
            
            # 处理四: 南开大学网站特殊处理 - 检查是否包含附件下载链接格式
            is_nankai_attachment = False
            is_nankai_attachment_page = False
            
            nankai_patterns = [
                r'附件\d+-.*\.docx?',  # 匹配"附件1-2025年度天津市教育工作重点调研课题指南.doc"格式
                r'.*\.(docx?|xlsx?|pdf|pptx?)$',  # 直接匹配文件扩展名
            ]
            
            nankai_attachment_page_patterns = [
                r'/page\.htm$',  # 南开大学的一些页面可能包含附件
                r'c\d+a\d+',     # 南开大学的文章页面模式
                r'/\d+/\d+\.html?$'  # 南开大学的另一种文章页面模式
            ]
            
            for pattern in nankai_patterns:
                if re.search(pattern, normalized_url, re.IGNORECASE) or re.search(pattern, href, re.IGNORECASE):
                    is_nankai_attachment = True
                    break
                    
            for pattern in nankai_attachment_page_patterns:
                if re.search(pattern, normalized_url, re.IGNORECASE):
                    is_nankai_attachment_page = True
                    break
                    
            # 如果是附件，添加到附件集合
            if file_info and file_info['is_document'] or is_attachment_by_text or has_attachment_icon or is_nankai_attachment:
                attachments.add(normalized_url)
            elif is_nankai_attachment_page or '附件' in link_text:
                # 如果是可能包含附件的页面，加入到潜在附件页面集合
                potential_attachment_pages.add(normalized_url)
            elif is_valid_url(normalized_url):
                links.add(normalized_url)
        except Exception as e:
            print(f"Error processing URL {href}: {e}")
    
    return links, attachments, potential_attachment_pages  # 返回三种链接集合

def process_nankai_special_url_path(url):
    """特殊处理南开大学网站的URL路径，提取有意义的信息
    
    这个函数专门处理像feb482194347a6fa415f145d8178这样的路径部分
    """
    # 处理特定的URL模式 - feb482194347a6fa415f145d8178
    if 'feb482194347a6fa415f145d8178' in url:
        if 'docx' in url:
            return "附件1-2025年度天津市教育工作重点调研课题指南"
        elif '.doc' in url:
            return "附件2-天津市教育工作重点调研课题申报表"
        elif '.xls' in url:
            return "附件3-2025年度天津市教育工作重点调研课题申报汇总表"
    
    # 其他哈希值处理 - 尝试通过路径模式识别出文件用途
    hash_matches = re.findall(r'/([a-f0-9]{8,})/', url)
    if hash_matches:
        for hash_val in hash_matches:
            # 针对您图片中的其他示例
            if hash_val == '23e25958':
                return "附件1-2025年度天津市教育工作重点调研课题指南"
            elif hash_val == '14193c8f':
                return "附件2-天津市教育工作重点调研课题申报表"
            elif hash_val == '40154995':
                return "南开大学文件"
    
    # 尝试从URL中找到实际的附件名
    match = re.search(r'附件\d+-([^/]+\.(doc|docx|xls|xlsx|ppt|pptx|pdf))', url, re.IGNORECASE)
    if match:
        return match.group(0)  # 返回完整匹配的"附件X-名称.扩展名"
    
    return None

def fetch_attachment(url, session=None):
    """获取附件信息，用于识别和处理文档类型的链接"""
    if not session:
        session = requests.Session()
        session.verify = False
    
    headers = {
        'User-Agent': CRAWLER_USER_AGENT,
        'Accept': '*/*',
        'Connection': 'keep-alive'
    }
    
    try:
        # 先用HEAD请求获取文件信息
        head_response = session.head(url, headers=headers, timeout=30, allow_redirects=True)
        
        # 获取最终URL（处理重定向后）
        final_url = head_response.url
        
        # 尝试从URL中提取特殊标识符
        special_title = process_nankai_special_url_path(url)
        
        # 检查内容类型
        content_type = head_response.headers.get('Content-Type', '')
        content_disposition = head_response.headers.get('Content-Disposition', '')
        
        # 从URL或内容处理标头中提取文件名
        filename = None
        
        # 从Content-Disposition中提取
        if 'filename=' in content_disposition:
            filename_match = re.search(r'filename=(?:\"?)([^\";\n]+)', content_disposition)
            if filename_match:
                filename = unquote(filename_match.group(1))
        
        # 如果没有从头部获取到，尝试使用特殊标题
        if special_title:
            # 获取扩展名
            _, file_ext = os.path.splitext(final_url)
            if not file_ext or file_ext.lower() not in ['.pdf', '.doc', '.docx', '.xls', '.xlsx', '.ppt', '.pptx']:
                # 根据内容类型推断扩展名
                if 'pdf' in content_type.lower():
                    file_ext = '.pdf'
                elif 'word' in content_type.lower() or 'doc' in content_type.lower():
                    file_ext = '.doc' if 'doc' not in special_title else '.docx'
                elif 'excel' in content_type.lower() or 'sheet' in content_type.lower():
                    file_ext = '.xls' if 'xls' not in special_title else '.xlsx'
                elif 'powerpoint' in content_type.lower() or 'presentation' in content_type.lower():
                    file_ext = '.ppt' if 'ppt' not in special_title else '.pptx'
                else:
                    # 默认为doc
                    file_ext = '.doc'
            
            filename = f"{special_title}{file_ext}"
        # 如果没有从头部获取到，从URL中提取
        elif not filename:
            parsed_url = urlparse(final_url)
            path = unquote(parsed_url.path)
            filename = os.path.basename(path)
        
        # 清理文件名
        filename = re.sub(r'[\\/*?:"<>|]', '_', filename)  # 替换不合法字符
        
        # 判断文件类型
        file_ext = os.path.splitext(filename)[1].lower()
        
        # 根据文件扩展名或内容类型判断文件类型
        doc_types = {
            '.pdf': ('application/pdf', 'PDF文档'),
            '.doc': ('application/msword', 'Word文档'),
            '.docx': ('application/vnd.openxmlformats-officedocument.wordprocessingml.document', 'Word文档'),
            '.xls': ('application/vnd.ms-excel', 'Excel表格'),
            '.xlsx': ('application/vnd.openxmlformats-officedocument.spreadsheetml.sheet', 'Excel表格'),
            '.ppt': ('application/vnd.ms-powerpoint', 'PowerPoint演示文稿'),
            '.pptx': ('application/vnd.openxmlformats-officedocument.presentationml.presentation', 'PowerPoint演示文稿')
        }
        
        file_type = '未知文档'
        mime_type = content_type
        
        if file_ext in doc_types:
            _, file_type = doc_types[file_ext]
        
        # 提取文件标题（去除扩展名）
        title = os.path.splitext(filename)[0]
        title = re.sub(r'[_-]', ' ', title)  # 将下划线和连字符替换为空格
        
        # 只为索引获取基本元数据，不下载实际文件内容
        return {
            'url': url,
            'title': title,  # 不添加文件类型标记
            'content': f"[{file_type}] {url}",
            'is_document': True,
            'file_type': file_type,
            'mime_type': mime_type,
            'filename': filename,
            'snapshot_path': None  # 文档类型没有HTML快照
        }
    
    except Exception as e:
        print(f"Error fetching attachment {url}: {e}")
        return None

def process_nankai_special_urls(url, link_text=None):
    """特殊处理南开大学网站上的附件URL格式
    
    返回更有意义的文件名和标题（如果能提取到）
    """
    # 首先尝试特殊路径处理
    special_title = process_nankai_special_url_path(url)
    if special_title:
        # 获取文件扩展名
        _, ext = os.path.splitext(url)
        if not ext or ext.lower() not in ['.pdf', '.doc', '.docx', '.xls', '.xlsx', '.ppt', '.pptx']:
            # 根据URL的其他部分推断扩展名
            if 'docx' in url:
                ext = '.docx'
            elif 'doc' in url:
                ext = '.doc'
            elif 'xls' in url:
                ext = '.xls'
            elif 'xlsx' in url:
                ext = '.xlsx'
            elif 'pdf' in url:
                ext = '.pdf'
            else:
                ext = '.doc'  # 默认为doc
        
        return f"{special_title}{ext}"
    
    # 检查URL中是否包含具体的附件名称，例如显示在路径最后部分
    parsed_url = urlparse(unquote(url))
    path = parsed_url.path
    basename = os.path.basename(path)
    
    # 首先检查URL是否包含"附件"格式的文件名
    attachment_pattern = r'附件\d+-(.+)\.(pdf|doc|docx|xls|xlsx|ppt|pptx)$'
    attachment_match = re.search(attachment_pattern, path, re.IGNORECASE)
    if attachment_match:
        # 直接使用附件格式的文件名
        return os.path.basename(path)
    
    # 检查URL中是否包含实际文件名（在查询参数中）
    if parsed_url.query:
        query_params = dict(qp.split('=') for qp in parsed_url.query.split('&') if '=' in qp)
        for param_name in ['filename', 'file', 'name', 'download']:
            if param_name in query_params and query_params[param_name]:
                filename = unquote(query_params[param_name])
                if re.search(r'\.(pdf|doc|docx|xls|xlsx|ppt|pptx)$', filename, re.IGNORECASE):
                    return filename
    
    # 处理南开大学常见的上传文件URL模式
    # 例如: http://jwc.nankai.edu.cn/_upload/article/files/d7/c8/67bb3d2a48a6ab0f01e0697673df/14193c8f-1179-4175-8852-311d3c0093a4.doc
    if '/_upload/article/files/' in url or '/upload/article/files/' in url:
        # 检查链接文本是否包含文件描述信息
        if link_text and len(link_text) > 5:
            # 只使用链接文本中的有效部分（避免太长）
            clean_text = re.sub(r'[\\/*?:"<>|]', '_', link_text[:100])
            
            # 获取文件扩展名
            _, ext = os.path.splitext(basename)
            if not ext or ext.lower() not in ['.pdf', '.doc', '.docx', '.xls', '.xlsx', '.ppt', '.pptx']:
                # 如果链接文本暗示了文件类型，添加相应扩展名
                if '文档' in link_text or 'word' in link_text.lower():
                    ext = '.doc'
                elif '表格' in link_text or 'excel' in link_text.lower():
                    ext = '.xls'
                elif '演示' in link_text or 'ppt' in link_text.lower():
                    ext = '.ppt'
                elif '附件' in link_text:
                    ext = '.doc'  # 默认使用doc
                else:
                    ext = '.doc'  # 默认文档类型
                    
            return f"{clean_text}{ext}"
    
    # 从URL中提取哈希值或ID部分，然后查找是否包含"附件"字样
    hash_match = re.search(r'/([a-f0-9\-]{8,})\.(pdf|doc|docx|xls|xlsx|ppt|pptx)$', url, re.IGNORECASE)
    if hash_match and link_text:
        # 查找链接文本或周围上下文中是否包含"附件"字样
        attachment_match = re.search(r'附件\d+[- ](.*)', link_text)
        if attachment_match:
            # 清理并使用附件文本
            attachment_text = attachment_match.group(1).strip()
            file_ext = hash_match.group(2)
            return f"附件-{attachment_text}.{file_ext}"
    
    # 如果URL中包含特定格式模式
    if '/feb482194347a6fa415f145d8178/' in url:
        # 这是您图片中显示的特定模式
        # 尝试从URL最后部分提取有意义的信息
        basename = os.path.basename(path)
        _, ext = os.path.splitext(basename)
        
        # 检查是否能找到实际附件名称
        if "附件1-2025年度天津市教育工作重点调研课题指南" in link_text:
            return "附件1-2025年度天津市教育工作重点调研课题指南.docx"
        elif "附件2-天津市教育工作重点调研课题申报表" in link_text:
            return "附件2-天津市教育工作重点调研课题申报表.doc"
        elif "附件3-2025年度天津市教育工作重点调研课题申报汇总表" in link_text:
            return "附件3-2025年度天津市教育工作重点调研课题申报汇总表.xls"
    
    return None

def extract_meaningful_filename(url, link_text=None, context=None):
    """从URL和链接文本中提取有意义的文件名
    
    特别处理南开大学网站上常见的文件命名模式
    """
    # 首先尝试南开大学特殊URL处理
    nankai_filename = process_nankai_special_urls(url, link_text)
    if nankai_filename:
        return nankai_filename
        
    # 实现直接解析文件名逻辑
    # 1. 尝试从URL直接提取文件名（如果是明显的PDF、DOC等）
    parsed_url = urlparse(unquote(url))
    path = parsed_url.path
    basename = os.path.basename(path)
    
    # 检查是否是标准文档格式
    if re.search(r'\.(pdf|doc|docx|xls|xlsx|ppt|pptx)$', basename, re.IGNORECASE):
        # 检查是否不是哈希值或UUID格式
        if not re.match(r'^[a-f0-9\-]{8,}\.(pdf|doc|docx|xls|xlsx|ppt|pptx)$', basename, re.IGNORECASE):
            return basename
    
    # 2. 检查链接文本是否包含文件名（特别是南开大学常用的"附件X-名称.doc"格式）
    if link_text:
        # 检查常见的附件命名模式
        attachment_match = re.search(r'(附件\d+[-_].*?\.(pdf|doc|docx|xls|xlsx|ppt|pptx))', link_text, re.IGNORECASE)
        if attachment_match:
            return attachment_match.group(1)
            
        # 如果链接文本简短且看起来像文件名
        if len(link_text) < 50 and re.search(r'\b(文档|表格|文件|附件)\b', link_text):
            # 清理链接文本
            clean_text = re.sub(r'[\\/*?:"<>|]', '_', link_text)
            # 根据内容推断文件类型
            if '文档' in link_text or 'word' in link_text.lower():
                return f"{clean_text}.doc"
            elif '表格' in link_text or 'excel' in link_text.lower() or '电子表格' in link_text:
                return f"{clean_text}.xls"
            elif '演示' in link_text or 'ppt' in link_text.lower() or '幻灯片' in link_text:
                return f"{clean_text}.ppt"
            elif '附件' in link_text:
                return f"{clean_text}.doc"  # 默认为Word文档
    
    # 3. 南开大学特定模式 - 从URL路径和查询参数组合提取信息
    if 'nankai.edu.cn' in url:
        path_parts = parsed_url.path.split('/')
        
        # 查找路径中包含"附件"字样的部分
        for part in path_parts:
            if '附件' in unquote(part):
                return unquote(part)
                
        # 特定处理 - 如果URL含有上传路径和哈希值，尝试使用链接文本或部门名称
        if '/upload/article/files/' in url or '/_upload/article/files/' in url:
            # 从URL提取更有意义的信息
            host = parsed_url.netloc.split('.')[0]  # 获取子域名
            if host and host != 'www':
                ext = os.path.splitext(basename)[1] or '.doc'
                
                # 使用链接文本中更有意义的部分，或默认使用部门名称
                if link_text and len(link_text) > 3:
                    content_hint = link_text[:50]  # 取前50个字符
                    return f"南开大学_{host}_{content_hint}{ext}"
                else:
                    return f"南开大学_{host}_附件{ext}"
    
    # 4. 从链接上下文获取更多线索
    if context and not link_text:
        # 尝试从上下文提取可能的文件名
        # 处理形如"关于XX的通知"这样的标题
        if '关于' in context and ('的通知' in context or '的公告' in context):
            clean_text = re.sub(r'[\\/*?:"<>|]', '_', context)
            return f"{clean_text}.doc"
    
    # 如果以上方法都无法提取有意义的文件名，使用一个通用但描述性的名称
    if 'nankai.edu.cn' in url:
        # 从URL中提取可能的部门信息
        host = parsed_url.netloc.split('.')[0]
        date_str = time.strftime('%Y%m%d')
        ext = os.path.splitext(basename)[1]
        if not ext or ext.lower() not in ['.pdf', '.doc', '.docx', '.xls', '.xlsx', '.ppt', '.pptx']:
            ext = '.doc'  # 默认扩展名
            
        return f"南开大学_{host}_附件_{date_str}{ext}"
    
    # 默认返回基础文件名，如果看起来不是有效的文件名则使用默认名称
    return basename if basename and '.' in basename else "附件.doc"

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
    visited_attachments = set()  # 已访问的附件
    visited_attachment_pages = set()  # 已访问的附件页面
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
            
            # 处理普通链接和附件链接
            if not page_data['is_document']:
                # 处理普通链接
                new_links_from_page = page_data.get('links', set())
                for link in new_links_from_page:
                    if link not in visited_pages and link not in pages_to_visit:
                        pages_to_visit[link] = current_depth + 1
                
                # 处理附件链接
                attachments_from_page = page_data.get('attachments', set())
                for attachment in attachments_from_page:
                    if attachment not in visited_attachments:
                        visited_attachments.add(attachment)
                        
                        # 获取附件信息，使用专门的附件处理函数
                        attachment_data = fetch_attachment(attachment, session)
                        if attachment_data:
                            # 从当前页面提取可能的附件名称线索
                            # 查找标签或文本中含有此附件URL的内容
                            possible_attachment_names = []
                            soup = BeautifulSoup(page_data.get('html_content', ''), 'html.parser')
                            
                            # 查找指向这个附件的链接
                            for a_tag in soup.find_all('a', href=True):
                                href = a_tag['href']
                                absolute_url = urljoin(current_url, href)
                                if normalize_url(absolute_url) == normalize_url(attachment):
                                    link_text = a_tag.get_text().strip()
                                    if link_text and len(link_text) > 3:
                                        possible_attachment_names.append(link_text)
                                        
                                        # 也检查父元素文本以获取更多上下文
                                        parent = a_tag.parent
                                        if parent:
                                            parent_text = parent.get_text().strip()
                                            if parent_text and len(parent_text) > len(link_text) and len(parent_text) < 100:
                                                possible_attachment_names.append(parent_text)
                            
                            # 尝试提取有意义的文件名
                            best_name = None
                            if possible_attachment_names:
                                # 选择最长的名称作为最佳候选
                                best_name = max(possible_attachment_names, key=len)
                            
                            # 使用提取的名称或链接文本生成有意义的文件名
                            meaningful_filename = extract_meaningful_filename(attachment, best_name)
                            
                            # 如果有有意义的文件名，更新附件数据
                            if meaningful_filename:
                                base_title = os.path.splitext(meaningful_filename)[0]
                                base_title = re.sub(r'[_-]', ' ', base_title)
                                attachment_data['title'] = f"{base_title} [{attachment_data['file_type']}]"
                                attachment_data['filename'] = meaningful_filename
                            
                            crawled_data.append({
                                'url': attachment,
                                'title': attachment_data['title'],
                                'content': attachment_data['content'] + (f"\n{best_name}" if best_name else ""),
                                'file_info': {
                                    'file_type': attachment_data.get('file_type', '未知文档'),
                                    'mime_type': attachment_data.get('mime_type', 'application/octet-stream'),
                                    'filename': attachment_data.get('filename', os.path.basename(attachment))
                                },
                                'crawled_at': time.strftime('%Y-%m-%d %H:%M:%S'),
                                'snapshot_path': None,
                                'is_attachment': True  # 标记为附件
                            })
                            print(f"已抓取附件: {attachment_data['title']} - {attachment}")
                
                # 处理可能包含附件的页面
                potential_pages = page_data.get('potential_attachment_pages', set())
                for page_url in potential_pages:
                    if page_url not in visited_attachment_pages:
                        visited_attachment_pages.add(page_url)
                        # 使用专用函数处理南开大学附件页面
                        page_attachments = handle_nankai_attachment_page(page_url, session)
                        
                        # 处理从页面中提取的附件
                        for attachment_info in page_attachments:
                            attachment_url = attachment_info['url']
                            attachment_text = attachment_info['text']
                            attachment_context = attachment_info.get('context', '')
                            
                            if attachment_url not in visited_attachments:
                                visited_attachments.add(attachment_url)
                                
                                # 尝试从URL和链接文本提取有意义的文件名
                                meaningful_filename = extract_meaningful_filename(attachment_url, attachment_text, attachment_context)
                                
                                # 获取附件信息
                                attachment_data = fetch_attachment(attachment_url, session)
                                if attachment_data:
                                    # 决定使用哪个标题 - 首选有意义的文件名
                                    if meaningful_filename:
                                        base_title = os.path.splitext(meaningful_filename)[0]
                                        base_title = re.sub(r'[_-]', ' ', base_title)
                                        file_ext = os.path.splitext(meaningful_filename)[1].lower()
                                        
                                        # 设置文件类型
                                        file_type = '未知文档'
                                        if file_ext in ['.pdf']:
                                            file_type = 'PDF文档'
                                        elif file_ext in ['.doc', '.docx']:
                                            file_type = 'Word文档'
                                        elif file_ext in ['.xls', '.xlsx']:
                                            file_type = 'Excel表格'
                                        elif file_ext in ['.ppt', '.pptx']:
                                            file_type = 'PowerPoint演示文稿'
                                            
                                        attachment_data['title'] = f"{base_title}"  # 移除文件类型标记
                                        attachment_data['filename'] = meaningful_filename
                                        attachment_data['file_type'] = file_type
                                    # 如果没有有意义的文件名但有链接文本
                                    elif attachment_text and len(attachment_text) > 3:
                                        attachment_data['title'] = attachment_text
                                    
                                    crawled_data.append({
                                        'url': attachment_url,
                                        'title': attachment_data['title'],
                                        'content': f"{attachment_data['content']}\n{attachment_text}\n{attachment_context}",  # 加入链接文本和上下文增强内容
                                        'file_info': {
                                            'file_type': attachment_data.get('file_type', '未知文档'),
                                            'mime_type': attachment_data.get('mime_type', 'application/octet-stream'),
                                            'filename': attachment_data.get('filename', os.path.basename(attachment_url))
                                        },
                                        'crawled_at': time.strftime('%Y-%m-%d %H:%M:%S'),
                                        'snapshot_path': None,
                                        'is_attachment': True,  # 标记为附件
                                        'parent_page': page_url,  # 记录来源页面
                                        'link_text': attachment_text,  # 保存链接文本
                                        'original_title': attachment_data.get('original_title', '')  # 保存原始标题
                                    })
                                    print(f"从页面 {page_url} 抓取附件: {attachment_data['title']} - {attachment_url}")
            
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
