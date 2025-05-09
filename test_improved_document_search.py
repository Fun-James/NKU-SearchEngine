"""
测试文档搜索功能
"""
from elasticsearch import Elasticsearch
import json
import urllib.parse
import sys
sys.path.insert(0, '.') # 将当前目录添加到路径以便导入app模块

# 导入文档搜索模块
try:
    from app.main.document_search import build_document_search_query
except ImportError:
    print("无法导入文档搜索模块，请确保文件位置正确")
    exit(1)

# 连接到Elasticsearch
es = Elasticsearch('http://localhost:9200')

def test_document_search(query_text):
    """测试文档搜索功能"""
    if not es.ping():
        print("无法连接到Elasticsearch，请确保服务已启动")
        return
    
    print(f"\n===== 测试文档搜索: '{query_text}' =====")
    
    # 构建查询
    search_body = build_document_search_query(query_text)
    print("\n查询结构:")
    print(json.dumps(search_body, indent=2, ensure_ascii=False))
    
    try:
        # 执行查询
        result = es.search(
            index="nku_web",
            body=search_body
        )
        
        # 解析结果
        total_hits = result.get('hits', {}).get('total', {}).get('value', 0)
        hits = result.get('hits', {}).get('hits', [])
        
        print(f"\n找到 {total_hits} 个文档结果:")
        
        if hits:
            for i, hit in enumerate(hits):
                doc = hit['_source']
                url = doc.get('url', '无URL')
                
                # 从URL中提取文件名
                filename = url.split('/')[-1]
                try:
                    decoded_filename = urllib.parse.unquote(filename)
                except:
                    decoded_filename = filename
                
                print(f"\n结果 {i+1} (相关度: {hit['_score']}):")
                print(f"文件名: {decoded_filename}")
                print(f"URL: {url}")
                print(f"类型: {doc.get('file_type', '未知')}")
        else:
            print("未找到匹配的文档")
            
    except Exception as e:
        print(f"查询出错: {str(e)}")

if __name__ == "__main__":
    # 测试一些典型查询
    test_queries = ["值班表", "寒假", "2025", "南开大学"]
    
    for query in test_queries:
        test_document_search(query)
        print("\n" + "="*50)
    
    # 允许用户输入自定义查询进行测试
    while True:
        custom_query = input("\n请输入要测试的文档搜索关键词 (输入exit退出): ")
        if custom_query.lower() == 'exit':
            break
        test_document_search(custom_query)
