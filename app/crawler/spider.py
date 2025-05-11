import requests
from bs4 import BeautifulSoup
import time
from urllib.parse import urljoin, urlparse, unquote, urlunparse
import re
from urllib.robotparser import RobotFileParser
import ssl
import urllib3
import os
import hashlib
from flask import current_app
import urllib.parse

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

def clean_document_url(url):
    """清理和标准化文档URL，修复不正确的URL格式
    
    参数:
    - url: 输入URL，可能包含JSON字符串或其他非标准格式
    
    返回:
    - 清理后的有效URL或None
    """
    if not url:
        return None
        
    # 检测URL是否包含JSON字符串部分 {'title':'文件名.扩展名'}
    json_match = re.search(r"(https?://[^/]+/[^{]*)({'title':'([^']+)'})(.*)", url)
    if json_match:
        try:
            # 获取基本URL部分
            base_part = json_match.group(1)
            # 文件名部分
            filename = json_match.group(3)
            # 去掉尾部可能的斜杠
            base_part = base_part.rstrip('/')
            # 获取域名部分
            parsed_uri = urlparse(base_part)
            domain = f"{parsed_uri.scheme}://{parsed_uri.netloc}"
            
            # 构建多个可能的文件URL并返回最有可能的那个
            possible_urls = [
                f"{domain}/_upload/article/files/{filename}",
                f"{domain}/upload/{filename}",
                f"{domain}/files/{filename}",
                f"{os.path.dirname(base_part)}/{filename}",
                f"{os.path.dirname(os.path.dirname(base_part))}/upload/files/{filename}"
            ]
            
            # 默认使用第一个URL
            return possible_urls[0]
        except Exception as e:
            print(f"Error cleaning document URL: {url}: {e}")
            return url
    
    # 如果URL包含汉字，进行URL编码
    if re.search(r'[\u4e00-\u9fff]', url):
        try:
            # 分解URL，只对路径部分进行编码
            parsed = urlparse(url)
            path_parts = parsed.path.split('/')
            encoded_parts = []
            for part in path_parts:
                if re.search(r'[\u4e00-\u9fff]', part):
                    encoded_parts.append(urllib.parse.quote(part))
                else:
                    encoded_parts.append(part)
            
            encoded_path = '/'.join(encoded_parts)
            # 重新组装URL
            cleaned_url = urlunparse((parsed.scheme, parsed.netloc, encoded_path, 
                                    parsed.params, parsed.query, parsed.fragment))
            return cleaned_url
        except Exception as e:
            print(f"Error encoding URL: {url}: {e}")
            return url
            
    return url

def get_file_info(url):
    """获取文件类型信息，支持更广泛的文档类型检测"""
    # 扩展支持的文档类型
    doc_types = {
        '.pdf': ('application/pdf', 'PDF文档'),
        '.doc': ('application/msword', 'Word文档'),
        '.docx': ('application/vnd.openxmlformats-officedocument.wordprocessingml.document', 'Word文档'),
        '.xls': ('application/vnd.ms-excel', 'Excel表格'),
        '.xlsx': ('application/vnd.openxmlformats-officedocument.spreadsheetml.sheet', 'Excel表格'),
        '.ppt': ('application/vnd.ms-powerpoint', 'PowerPoint演示文稿'),
        '.pptx': ('application/vnd.openxmlformats-officedocument.presentationml.presentation', 'PowerPoint演示文稿'),
        '.txt': ('text/plain', '文本文档'),
        '.csv': ('text/csv', 'CSV表格'),
        '.rtf': ('application/rtf', 'RTF文档'),
        '.zip': ('application/zip', 'ZIP压缩包'),
        '.rar': ('application/x-rar-compressed', 'RAR压缩包'),
        '.7z': ('application/x-7z-compressed', '7Z压缩包'),
        '.tar': ('application/x-tar', 'TAR归档'),
        '.gz': ('application/gzip', 'GZIP压缩包'),
        '.mp4': ('video/mp4', '视频文件'),
        '.mp3': ('audio/mpeg', '音频文件'),
        '.jpg': ('image/jpeg', '图片文件'),
        '.jpeg': ('image/jpeg', '图片文件'),
        '.png': ('image/png', '图片文件'),
        '.gif': ('image/gif', '图片文件'),
        '.bmp': ('image/bmp', '图片文件')
    }
    
    # 1. 先尝试直接匹配文件扩展名
    parsed_url = urlparse(url)
    path = parsed_url.path.lower()
    
    file_ext = None
    for ext in doc_types:
        if path.endswith(ext):
            file_ext = ext
            break
    
    # 2. 如果没有扩展名匹配，尝试从URL中提取文件名和扩展名
    if not file_ext:
        # 从URL提取文件名
        filename = os.path.basename(parsed_url.path)
        # 尝试找到扩展名
        for ext in doc_types:
            if filename.lower().endswith(ext):
                file_ext = ext
                break
    
    # 3. 尝试从URL参数中寻找文件类型线索
    if not file_ext and parsed_url.query:
        query_params = urllib.parse.parse_qs(parsed_url.query)
        # 检查常见的文件类型参数
        for param in ['type', 'format', 'file', 'fileType', 'fileFormat']:
            if param in query_params:
                param_value = query_params[param][0].lower()
                for ext in doc_types:
                    if ext.lstrip('.') == param_value:
                        file_ext = ext
                        break
    
    # 4. 检查URL是否包含指示文件下载的关键词
    doc_keywords = ['download', 'attachment', 'file', 'document', 'doc', '附件', '文件', '下载']
    if not file_ext:
        url_lower = url.lower()
        if any(keyword in url_lower for keyword in doc_keywords):
            # 如果URL中包含这些关键词，尝试进一步分析
            for ext in doc_types:
                ext_without_dot = ext.lstrip('.')
                if ext_without_dot in url_lower:
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
            response = session.head(http_url, headers=headers, timeout=30)            # 提取文件名并解码
            filename = url.split('/')[-1]
            try:
                decoded_filename = urllib.parse.unquote(filename)
                
                # 初始化文档标题相关变量
                looks_like_hash = False
                document_title_found = False
                real_title = None
                
                # 尝试从引用页获取实际文档标题
                referrer_title = get_document_title_from_referrer(url, http_url)
                if referrer_title:
                    real_title = referrer_title
                    document_title_found = True
                    print(f"从引用页获取到文档标题: {real_title}")
                
                # 如果没有找到实际标题，检查文件名是否需要特殊处理
                if not document_title_found:
                    # 1. 检查常见的哈希/ID格式（更宽松的模式匹配）
                    if (re.search(r'[a-f0-9]{8}[-\s][a-f0-9]{4}[-\s][a-f0-9]{4}', decoded_filename, re.IGNORECASE) or  # UUID格式
                        re.match(r'^[a-f0-9-]{20,}', decoded_filename, re.IGNORECASE) or  # 长哈希
                        re.match(r'^[0-9]{6,}', decoded_filename) or  # 纯数字ID
                        len(re.findall(r'[a-f0-9]', decoded_filename)) / len(decoded_filename) > 0.7):  # 超过70%是十六进制字符
                        looks_like_hash = True
                        print(f"检测到哈希值类文件名: {decoded_filename}")
                    
                    # 2. 直接检查我们在搜索结果中看到的特定格式
                    if re.search(r'^[a-f0-9]{8}\s[a-f0-9]{4}\s[a-f0-9]{4}\s[a-f0-9]{4}\s[a-f0-9]{12}', decoded_filename, re.IGNORECASE):
                        looks_like_hash = True
                        print(f"检测到UUID格式: {decoded_filename}")
                
                # 查找更好的标题替代品
                if not document_title_found and (looks_like_hash or len(decoded_filename) > 30):
                    # 尝试多种方法获取更好的标题
                    
                    # 方法1: 从URL路径中提取有意义的部分
                    path_parts = url.split('/')
                    meaningful_part = None
                    
                    # 寻找最接近文件名的有意义部分，但不是纯数字或十六进制字符串
                    for i in range(len(path_parts) - 2, 0, -1):
                        part = path_parts[i]
                        # 跳过看起来像哈希值或ID的路径部分
                        if (part and 
                            not part.startswith('c') and 
                            not re.match(r'^[0-9a-f]+$', part) and
                            len(part) > 1 and
                            not re.match(r'^a[0-9]+$', part)):  # 跳过类似a123456的格式
                            meaningful_part = part
                            break
                    
                    # 方法2: 从文件扩展名推断文档类型和用途
                    doc_purpose = ""
                    if file_info['extension'].lower() in ['.doc', '.docx']:
                        doc_purpose = "文档"
                    elif file_info['extension'].lower() in ['.xls', '.xlsx']:
                        doc_purpose = "表格"
                    elif file_info['extension'].lower() in ['.pdf']:
                        doc_purpose = "PDF文档"
                    elif file_info['extension'].lower() in ['.ppt', '.pptx']:
                        doc_purpose = "演示文稿"
                    else:
                        doc_purpose = file_info['file_type']
                        
                    # 生成标题
                    if meaningful_part:
                        # 如果找到有意义的部分，使用它
                        title = f"南开大学{doc_purpose} - {meaningful_part}"
                    else:
                        # 使用域名的子域部分作为部门/学院信息
                        domain = urlparse(url).netloc
                        subdomain = domain.split('.')[0] if '.' in domain else ''
                        
                        if subdomain and subdomain != "www":
                            # 把子域名转换为更可读的形式
                            readable_subdomain = subdomain.upper() if len(subdomain) <= 4 else subdomain.capitalize()
                            title = f"南开大学{readable_subdomain}{doc_purpose}"
                        else:
                            # 最后的后备选项
                            title = f"南开大学{doc_purpose}"
                else:
                    # 正常处理常规文件名
                    # 移除文件扩展名
                    title = re.sub(r'\.(pdf|doc|docx|xls|xlsx|ppt|pptx|zip|rar)$', '', decoded_filename, flags=re.IGNORECASE)
                    # 将下划线和连字符替换为空格
                    title = re.sub(r'[_-]', ' ', title)
                    
                    # 如果标题还是很长或不可读，也尝试简化它
                    if len(title) > 40:
                        title = title[:37] + "..."
                
                # 添加文件类型提示
                title = f"{title} [{file_info['file_type']}]"
                print(f"生成的文档标题: {title}")
            except Exception as e:
                print(f"处理文档标题时出错: {e}")
                title = f"南开大学{file_info['file_type']}"
                
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
                response = session.head(url, headers=headers, timeout=30)                # 使用上面相同的增强标题处理逻辑
                filename = url.split('/')[-1]
                try:
                    decoded_filename = urllib.parse.unquote(filename)
                    
                    # 全面检测哈希值或ID格式（覆盖不同格式）
                    looks_like_hash = False
                    
                    # 1. 检查常见的哈希/ID格式（更宽松的模式匹配）
                    if (re.search(r'[a-f0-9]{8}[-\s][a-f0-9]{4}[-\s][a-f0-9]{4}', decoded_filename, re.IGNORECASE) or  # UUID格式
                        re.match(r'^[a-f0-9-]{20,}', decoded_filename, re.IGNORECASE) or  # 长哈希
                        re.match(r'^[0-9]{6,}', decoded_filename) or  # 纯数字ID
                        len(re.findall(r'[a-f0-9]', decoded_filename)) / len(decoded_filename) > 0.7):  # 超过70%是十六进制字符
                        looks_like_hash = True
                        print(f"HTTPS回退:检测到哈希值类文件名: {decoded_filename}")
                    
                    # 2. 直接检查我们在搜索结果中看到的特定格式
                    if re.search(r'^[a-f0-9]{8}\s[a-f0-9]{4}\s[a-f0-9]{4}\s[a-f0-9]{4}\s[a-f0-9]{12}', decoded_filename, re.IGNORECASE):
                        looks_like_hash = True
                        print(f"HTTPS回退:检测到UUID格式: {decoded_filename}")
                    
                    # 查找更好的标题替代品
                    if looks_like_hash or len(decoded_filename) > 30:
                        # 尝试从URL路径中提取有意义的部分
                        path_parts = url.split('/')
                        meaningful_part = None
                        
                        # 寻找最接近文件名的有意义部分
                        for i in range(len(path_parts) - 2, 0, -1):
                            part = path_parts[i]
                            if (part and 
                                not part.startswith('c') and 
                                not re.match(r'^[0-9a-f]+$', part) and
                                len(part) > 1 and
                                not re.match(r'^a[0-9]+$', part)):
                                meaningful_part = part
                                break
                        
                        # 从文件扩展名推断文档类型和用途
                        doc_purpose = ""
                        if file_info['extension'].lower() in ['.doc', '.docx']:
                            doc_purpose = "文档"
                        elif file_info['extension'].lower() in ['.xls', '.xlsx']:
                            doc_purpose = "表格"
                        elif file_info['extension'].lower() in ['.pdf']:
                            doc_purpose = "PDF文档"
                        elif file_info['extension'].lower() in ['.ppt', '.pptx']:
                            doc_purpose = "演示文稿"
                        else:
                            doc_purpose = file_info['file_type']
                            
                        # 生成标题
                        if meaningful_part:
                            title = f"南开大学{doc_purpose} - {meaningful_part}"
                        else:
                            # 使用域名的子域部分作为部门/学院信息
                            domain = urlparse(url).netloc
                            subdomain = domain.split('.')[0] if '.' in domain else ''
                            
                            if subdomain and subdomain != "www":
                                readable_subdomain = subdomain.upper() if len(subdomain) <= 4 else subdomain.capitalize()
                                title = f"南开大学{readable_subdomain}{doc_purpose}"
                            else:
                                title = f"南开大学{doc_purpose}"
                    else:
                        # 正常处理常规文件名
                        title = re.sub(r'\.(pdf|doc|docx|xls|xlsx|ppt|pptx|zip|rar)$', '', decoded_filename, flags=re.IGNORECASE)
                        title = re.sub(r'[_-]', ' ', title)
                        
                        # 如果标题还是很长或不可读，也尝试简化它
                        if len(title) > 40:
                            title = title[:37] + "..."
                    
                    # 添加文件类型提示
                    title = f"{title} [{file_info['file_type']}]"
                    print(f"HTTPS回退:生成的文档标题: {title}")
                except Exception as e:
                    print(f"HTTPS回退中处理文档标题时出错: {e}")
                    title = f"南开大学{file_info['file_type']}"
                
                return {
                    'url': url,
                    'title': title,
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
                snapshot_path = None  # 如果保存失败，则路径为None            # --- 网页快照保存结束 ---
            
            # 检查页面中是否包含嵌入文档的特征
            has_embedded_docs = False
            embedded_doc_info = None
            soup = BeautifulSoup(response.text, 'html.parser')
            
            # 检查页面标题或内容是否包含文档关键词
            doc_keywords = ['文件', '附件', '下载', '申报', '申请表', '汇总表']
            title_text = title.lower() if title else ""
            if any(keyword in title_text for keyword in doc_keywords) or any(keyword in content[:500].lower() for keyword in doc_keywords):
                has_embedded_docs = True
            
            return {
                'url': url,  # 保留原始URL
                'title': title,
                'content': content,  # 这是提取后的纯文本内容
                'html_content': response.text,  # 保留原始HTML文本
                'links': links,
                'is_document': False,
                'file_type': 'webpage',
                'mime_type': 'text/html',
                'snapshot_path': snapshot_path,  # 新增快照路径
                'has_embedded_docs': has_embedded_docs  # 标记页面是否可能包含嵌入文档
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
    """从HTML中解析链接，增强版本可以识别更多类型的链接"""
    soup = BeautifulSoup(html_content, 'html.parser')
    links = set()
      # 1. 处理常规的<a href>标签链接
    for a_tag in soup.find_all('a', href=True):
        href = a_tag['href']
        try:
            absolute_url = urljoin(base_url, href)
            # 清理文档URL，特别是对可能是文档的链接
            if any(ext in href.lower() for ext in ['.doc', '.docx', '.pdf', '.xls', '.xlsx', '.ppt', '.pptx', '附件']):
                absolute_url = clean_document_url(absolute_url)
            normalized_url = normalize_url(absolute_url)
            if is_valid_url(normalized_url):
                links.add(normalized_url)
        except Exception as e:
            print(f"Error processing URL {href}: {e}")
    
    # 2. 处理可能包含文档的img标签 (图标链接常用于文档)
    for img_tag in soup.find_all('img', src=True):
        src = img_tag.get('src', '')
        if 'icon' in src.lower() or 'doc' in src.lower() or '文件' in src:
            # 查找该图像是否在一个<a>标签内部
            parent_a = img_tag.find_parent('a', href=True)
            if parent_a and parent_a.get('href'):
                try:
                    absolute_url = urljoin(base_url, parent_a['href'])
                    normalized_url = normalize_url(absolute_url)
                    if is_valid_url(normalized_url):
                        links.add(normalized_url)
                except Exception as e:
                    print(f"Error processing URL from img parent: {parent_a['href']}: {e}")
    
    # 3. 查找包含文件扩展名关键词的链接
    doc_patterns = [r'\.pdf', r'\.doc', r'\.docx', r'\.xls', r'\.xlsx', r'\.ppt', r'\.pptx', r'\.zip', r'\.rar', r'\.gz']
    for tag in soup.find_all(True):
        # 检查标签的所有属性
        for attr_name, attr_value in tag.attrs.items():
            if isinstance(attr_value, str) and any(re.search(pattern, attr_value.lower()) for pattern in doc_patterns):
                try:
                    absolute_url = urljoin(base_url, attr_value)
                    normalized_url = normalize_url(absolute_url)
                    if is_valid_url(normalized_url):
                        links.add(normalized_url)
                except Exception as e:
                    print(f"Error processing URL from attribute: {attr_value}: {e}")
      # 4. 寻找页面中可能的附件引用，这些附件可能没有明确的链接
    attachment_patterns = [
        r'附件\d+-[\w\-]+\.(doc|docx|xls|xlsx|pdf|ppt|pptx)', 
        r'file\d+[\w\-]+\.(doc|docx|xls|xlsx|pdf|ppt|pptx)',
        r'附件\s*\d+\s*[：:]\s*([\w\-]+\.(doc|docx|xls|xlsx|pdf|ppt|pptx))',
        r'下载\s*([\w\-]+\.(doc|docx|xls|xlsx|pdf|ppt|pptx))'
    ]
    
    # 从URL中提取父目录，可能包含文件
    base_dir = os.path.dirname(base_url)
    # 提取网站域名部分，用于构建可能的文件服务器URL
    domain = f"{urlparse(base_url).scheme}://{urlparse(base_url).netloc}"
    # 常见文件服务器路径
    common_file_paths = [
        f"{domain}/_upload/article/files/",
        f"{domain}/upload/",
        f"{domain}/files/",
        f"{domain}/download/"
    ]
    
    # 在页面文本中寻找这些模式
    for pattern in attachment_patterns:
        matches = re.findall(pattern, html_content, re.IGNORECASE)
        for match in matches:
            try:
                # 提取匹配的文件名
                if isinstance(match, tuple):
                    filename = match[0]  # 对于有捕获组的模式
                else:
                    filename = match  # 对于没有捕获组的模式
                
                # 尝试多种可能的URL构建方式
                possible_urls = []
                
                # 1. 尝试基于当前页面URL构建
                possible_urls.append(f"{base_dir}/{filename}")
                
                # 2. 尝试基于父目录URL构建
                possible_urls.append(f"{base_dir}/../_upload/article/files/{filename}")
                
                # 3. 尝试常见文件服务器路径
                for file_path in common_file_paths:
                    possible_urls.append(f"{file_path}{filename}")
                
                # 4. 尝试处理JSON字符串形式的链接 (解决{'title':'文件名.扩展名'}格式问题)
                clean_filename = filename.replace("'", "").replace('"', '')
                possible_urls.append(f"{base_dir}/uploads/{clean_filename}")
                  # 添加所有可能的URL
                for url in possible_urls:
                    # 清理和标准化URL
                    cleaned_url = clean_document_url(url)
                    normalized_url = normalize_url(cleaned_url)
                    if is_valid_url(normalized_url):
                        links.add(normalized_url)
            except Exception as e:
                print(f"Error processing attachment match: {match}: {e}")
      # 5. 查找JavaScript onclick事件中的下载链接
    for tag in soup.find_all(True):
        if tag.has_attr('onclick'):
            onclick = tag['onclick']
            # 寻找常见的JavaScript下载函数
            url_match = re.search(r'(window\.location|downloadFile|window\.open|href)\s*=\s*[\'"]([^\'"]+)[\'"]', onclick)
            if url_match:
                try:
                    js_url = url_match.group(2)
                    absolute_url = urljoin(base_url, js_url)
                    normalized_url = normalize_url(absolute_url)
                    if is_valid_url(normalized_url):
                        links.add(normalized_url)
                except Exception as e:
                    print(f"Error processing URL from onclick: {onclick}: {e}")
    
    # 6. 使用增强的文档引用提取功能
    try:
        doc_reference_links = extract_document_references(soup, base_url)
        links.update(doc_reference_links)
    except Exception as e:
        print(f"Error during document reference extraction: {e}")
    
    return links

def extract_document_references(soup, base_url):
    """从网页内容中提取可能提到的文档引用，如"附件1"、"下载文件"等
    
    参数:
    - soup: BeautifulSoup对象
    - base_url: 基础URL，用于构建绝对路径
    
    返回:
    - 可能包含文档的URL列表
    """
    doc_urls = set()
    
    # 1. 查找包含"附件"、"文件"等关键词的元素
    keywords = ['附件', '文件', '下载', '申请表', '报名表', '汇总表', 'attachment', 'document', 'file', 'download']
    
    for keyword in keywords:
        elements = soup.find_all(text=lambda text: text and keyword in text)
        for element in elements:
            parent = element.parent
            
            # 检查父元素或其周围是否有链接
            if parent.name == 'a' and parent.get('href'):
                try:
                    url = urljoin(base_url, parent['href'])
                    if is_valid_url(url):
                        doc_urls.add(url)
                except Exception as e:
                    print(f"Error processing URL from document reference: {parent.get('href', '')}: {e}")
            
            # 查找同级元素中的链接
            siblings = list(parent.next_siblings) + list(parent.previous_siblings)
            for sibling in siblings[:5]:  # 只看最近的5个兄弟元素
                if hasattr(sibling, 'name') and sibling.name == 'a' and sibling.get('href'):
                    try:
                        url = urljoin(base_url, sibling['href'])
                        if is_valid_url(url):
                            doc_urls.add(url)
                    except Exception as e:
                        print(f"Error processing URL from sibling: {sibling.get('href', '')}: {e}")
            
            # 查找父元素的下一级中的链接
            surrounding_links = parent.find_all('a', href=True)
            for link in surrounding_links:
                try:
                    url = urljoin(base_url, link['href'])
                    if is_valid_url(url):
                        doc_urls.add(url)
                except Exception as e:
                    print(f"Error processing URL from surrounding link: {link.get('href', '')}: {e}")
    
    # 2. 查找表格中可能包含的文档链接
    tables = soup.find_all('table')
    for table in tables:
        rows = table.find_all('tr')
        for row in rows:
            cells = row.find_all(['td', 'th'])
            for cell in cells:
                # 检查单元格是否包含"附件"或"文件"等关键词
                cell_text = cell.get_text().lower()
                if any(keyword in cell_text for keyword in keywords):
                    # 查找同一行中的其他单元格是否包含链接
                    row_links = row.find_all('a', href=True)
                    for link in row_links:
                        try:
                            url = urljoin(base_url, link['href'])
                            if is_valid_url(url):
                                doc_urls.add(url)
                        except Exception as e:
                            print(f"Error processing URL from table: {link.get('href', '')}: {e}")
    
    # 3. 特别处理可能是文档链接但没有明确扩展名的链接
    # 查找包含"附件"数字模式的文本，如"附件1"、"附件2-3"等
    attachment_patterns = [
        r'附件\s*\d+[\s\-]*([^\s]+)',
        r'文件\s*\d+[\s\-]*([^\s]+)',
        r'attachment\s*\d+[\s\-]*([^\s]+)'
    ]
    
    for pattern in attachment_patterns:
        for text_element in soup.find_all(text=re.compile(pattern, re.IGNORECASE)):
            # 查找该文本周围的链接
            parent = text_element.parent
            if parent:
                nearby_links = []
                # 向上查找最近的3层父元素
                for i in range(3):
                    if parent:
                        nearby_links.extend(parent.find_all('a', href=True))
                        parent = parent.parent
                
                for link in nearby_links:
                    try:
                        url = urljoin(base_url, link['href'])
                        if is_valid_url(url):
                            doc_urls.add(url)
                    except Exception as e:
                        print(f"Error processing URL from attachment pattern: {link.get('href', '')}: {e}")
    
    return doc_urls

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
        'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8,application/pdf,application/msword,application/vnd.openxmlformats-officedocument.*,application/vnd.ms-*',
        'Accept-Language': 'zh-CN,zh;q=0.9,en;q=0.8',
        'Connection': 'keep-alive'
    }
    session.headers.update(headers)
    
    # 使用优先队列，确保文档链接优先被处理
    priority_pages = {}  # 高优先级队列：文档页面
        
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
    
    while (pages_to_visit or priority_pages) and len(visited_pages) < max_pages:
        # 优先处理文档链接
        if priority_pages:
            # 从优先队列中获取URL
            current_url = next(iter(priority_pages))
            current_depth = priority_pages.pop(current_url)
            print(f"Processing priority document URL: {current_url}")
        else:
            # 从普通队列获取URL
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
                
                # 检查该页面是否可能包含嵌入文档
                is_doc_page = page_data.get('has_embedded_docs', False)
                  # 对可能包含文档的页面进行特殊处理
                if is_doc_page:
                    # 将这些链接加入优先访问队列
                    for link in new_links_from_page:
                        # 检查是否可能是文档链接
                        file_info = get_file_info(link)
                        if file_info:
                            # 将文档链接放在优先队列中
                            if link not in visited_pages:
                                # 清理URL，确保是有效格式
                                cleaned_link = clean_document_url(link)
                                priority_pages[cleaned_link] = current_depth  # 保持同样的深度，但会被优先访问
                                print(f"发现可能的文档链接: {cleaned_link}")
                        # 特殊检查JSON格式链接
                        elif "{'title'" in link:
                            # 尝试清理JSON格式链接
                            cleaned_link = clean_document_url(link)
                            if cleaned_link != link:  # 如果清理操作改变了URL
                                priority_pages[cleaned_link] = current_depth
                                print(f"修复并添加JSON格式文档链接: {cleaned_link}")
                
                # 处理剩余链接
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
