# -*- coding: utf-8 -*-
from app import create_app
from app.crawler.spider import fetch_page

def test_simple():
    print("开始测试...")
    app = create_app()
    with app.app_context():
        url = "https://www.nankai.edu.cn/2025/0403/c17471a566126/page.htm"
        print(f"爬取URL: {url}")
        result = fetch_page(url)
        if result:
            print(f"标题: {result.get('title')}")
            print(f"包含嵌入文档: {result.get('has_embedded_docs', False)}")
            
            doc_links = []
            for link in result.get('links', []):
                if any(ext in link.lower() for ext in ['.doc', '.docx', '.pdf', '.xls', '.xlsx']):
                    doc_links.append(link)
            
            print(f"发现文档链接: {len(doc_links)}")
            for i, link in enumerate(doc_links[:3]):
                print(f"  文档 {i+1}: {link}")

if __name__ == "__main__":
    test_simple()
