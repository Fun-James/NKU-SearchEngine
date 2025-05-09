from app.crawler.spider import fetch_page, get_file_info
from app.indexer.es_indexer import get_es_client, index_documents
from elasticsearch import Elasticsearch
import json

# 测试文档URL列表
test_urls = [
    # 添加一些已知的文档URL，比如：
    "https://cc.nankai.edu.cn/2021/0325/c13297a310964/page.pdf",
    "https://cc.nankai.edu.cn/2021/0325/c13297a310965/page.doc",
    # 添加更多文档URL...
]

def test_document_crawler():
    print("开始测试文档爬虫...")
    
    # 测试文件类型识别
    for url in test_urls:
        file_info = get_file_info(url)
        if file_info:
            print(f"\n检测到文档: {url}")
            print(f"文件类型: {file_info['file_type']}")
            print(f"MIME类型: {file_info['mime_type']}")
            
            # 尝试获取文档信息
            page_info = fetch_page(url)
            if page_info:
                print("成功获取文档信息:")
                print(f"标题: {page_info['title']}")
                print(f"文档类型: {page_info['file_type']}")
            else:
                print("无法获取文档信息")
        else:
            print(f"\n不是文档: {url}")

def test_document_indexing():
    print("\n测试文档索引...")
    
    # 获取ES客户端
    es = get_es_client()
    if not es:
        print("无法连接到Elasticsearch")
        return
    
    # 收集所有成功爬取的文档
    documents = []
    for url in test_urls:
        page_info = fetch_page(url)
        if page_info and page_info.get('is_document'):
            documents.append(page_info)
    
    if documents:
        # 索引文档
        indexed = index_documents(documents)
        print(f"成功索引 {indexed} 个文档")
    else:
        print("没有找到可索引的文档")

if __name__ == "__main__":
    print("=== 文档爬虫和索引测试 ===")
    test_document_crawler()
    test_document_indexing()
