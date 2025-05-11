"""
测试从网页中动态识别和爬取文档链接
"""
from app import create_app
from app.crawler.spider import fetch_page, clean_document_url

def test_web_document_crawler():
    print("开始测试从网页中动态识别文档链接...")
    
    # 已知包含文档的URL
    url = "https://www.nankai.edu.cn/2025/0403/c17471a566126/page.htm"
    
    app = create_app()
    with app.app_context():
        print(f"爬取页面: {url}")
        result = fetch_page(url)
        
        if result:
            print(f"页面标题: {result.get('title', '无标题')}")
            print(f"是否可能包含嵌入文档: {result.get('has_embedded_docs', False)}")
            
            # 提取文档链接
            links = result.get('links', [])
            doc_links = []
            
            for link in links:
                # 先检查是否为JSON格式的文档链接
                if "{'title'" in link:
                    cleaned_link = clean_document_url(link)
                    doc_links.append({
                        'original': link,
                        'cleaned': cleaned_link,
                        'type': 'JSON格式'
                    })
                # 再检查普通文档链接
                elif any(ext in link.lower() for ext in ['.doc', '.docx', '.pdf', '.xls', '.xlsx', '.ppt', '.pptx']):
                    doc_links.append({
                        'original': link,
                        'cleaned': link,
                        'type': '常规格式'
                    })
            
            # 显示文档链接
            print(f"\n发现文档链接数量: {len(doc_links)}")
            for i, link in enumerate(doc_links):
                print(f"\n文档 {i+1}:")
                print(f"  类型: {link['type']}")
                print(f"  原始链接: {link['original']}")
                print(f"  处理后链接: {link['cleaned']}")
                if link['original'] != link['cleaned']:
                    print("  ✓ URL已修复")
        else:
            print("无法获取页面信息")

if __name__ == "__main__":
    test_web_document_crawler()
