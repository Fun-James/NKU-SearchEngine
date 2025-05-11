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
    构建文档搜索查询 - 仅文件名搜索版
    
    参数:
    - query_text: 搜索关键词
    
    返回:
    - ES查询体
    """
    doc_extensions = [".pdf", ".doc", ".docx", ".xls", ".xlsx", ".ppt", ".pptx"]
    
    # URL编码查询词，用于匹配编码后的URL
    encoded_query = urllib.parse.quote(query_text)
    
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
                    # 文件URL中包含查询词 - 多种匹配方式增加命中率
                    {"wildcard": {"url": f"*{query_text}*"}},
                    {"wildcard": {"url": f"*{encoded_query}*"}},
                    
                    # 文件名部分匹配查询词
                    {"match": {"url": {"query": query_text, "analyzer": "standard"}}},
                    
                    # 标题中包含查询词（文件名被提取为标题）
                    {"match": {"title": {"query": query_text, "boost": 2}}}
                ],
                "minimum_should_match": 1  # 至少满足should中的一个条件
            }
        },
        "size": 10
    }
    
    return search_body
