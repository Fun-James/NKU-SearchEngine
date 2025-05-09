"""
文档搜索模块 - 专门处理文档搜索功能
"""
import urllib.parse

def build_document_search_query(query_text):
    """
    构建文档搜索查询
    
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
                    # 文件名中包含查询词时提高权重
                    {"wildcard": {"url": {"value": f"*/{query_text}*", "boost": 10}}},
                    {"wildcard": {"url": {"value": f"*/{encoded_query}*", "boost": 10}}},
                    
                    # URL任意部分包含查询词
                    {"wildcard": {"url": {"value": f"*{query_text}*", "boost": 3}}},
                    {"wildcard": {"url": {"value": f"*{encoded_query}*", "boost": 3}}},
                    
                    # 标题中包含查询词
                    {"match": {"title": {"query": query_text, "boost": 5}}}
                ],
                "minimum_should_match": 0  # 至少满足should中的一个条件
            }
        },
        "size": 10
    }
    
    return search_body
