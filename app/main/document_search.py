"""
文档搜索模块 - 专门处理文档搜索功能
增强版 - 改进了文档标题和内容的相关性计算
"""
import urllib.parse
import re

def clean_filename(filename):
    """
    清理文件名，提取更有可读性的标题
    
    参数:
    - filename: 文件名
    
    返回:
    - 清理后的标题
    """
    # 移除扩展名
    clean_name = re.sub(r'\.(pdf|doc|docx|xls|xlsx|ppt|pptx)$', '', filename, flags=re.IGNORECASE)
    # 将下划线和连字符替换为空格
    clean_name = re.sub(r'[_\-]', ' ', clean_name)
    # 移除多余空格
    clean_name = re.sub(r'\s+', ' ', clean_name).strip()
    return clean_name

def build_document_search_query(query_text):
    """
    构建文档搜索查询 - 增强版
    
    参数:
    - query_text: 搜索关键词
    
    返回:
    - ES查询体
    """
    doc_extensions = [".pdf", ".doc", ".docx", ".xls", ".xlsx", ".ppt", ".pptx"]
    
    # 创建文档名称匹配条件
    # 1. 对于URL的最后一部分(文件名)进行匹配
    # 2. 同时匹配原始查询和URL编码后的查询
    # 3. 对于URL中包含查询词的文档提高相关度
    # 4. 对标题和内容中包含查询词的文档提高权重
    
    encoded_query = urllib.parse.quote(query_text)
      # 将查询拆分为词组，用于多词匹配
    query_terms = query_text.split()
    
    search_body = {
        "query": {
            "bool": {
                "must": [
                    # 必须是文档类型
                    {
                        "bool": {
                            "should": [
                                {"wildcard": {"url": f"*{ext}"}} for ext in doc_extensions
                            ],
                            "minimum_should_match": 1
                        }
                    }
                ],
                "should": [
                    # 标题中包含查询词的权重最高
                    {"match_phrase": {"title": {"query": query_text, "boost": 15}}},
                    {"match": {"title": {"query": query_text, "boost": 10, "fuzziness": "AUTO"}}},
                    
                    # 文件名中包含查询词
                    {"wildcard": {"url": {"value": f"*/{query_text}*", "boost": 8}}},
                    {"wildcard": {"url": {"value": f"*/{encoded_query}*", "boost": 8}}},
                    
                    # URL任意部分包含查询词
                    {"wildcard": {"url": {"value": f"*{query_text}*", "boost": 3}}},
                    {"wildcard": {"url": {"value": f"*{encoded_query}*", "boost": 3}}},
                    
                    # 内容中包含查询词
                    {"match_phrase": {"content": {"query": query_text, "boost": 6}}},
                    {"match": {"content": {"query": query_text, "boost": 4, "fuzziness": "AUTO"}}}
                ],
                "minimum_should_match": 0  # 至少满足should中的一个条件
            }        },
        "size": 10
    }
    
    return search_body
