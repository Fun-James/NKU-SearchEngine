# -*- coding: utf-8 -*-
"""
测试文档标题处理逻辑
"""
from app import create_app
from app.crawler.spider import clean_document_url, get_file_info, fetch_page

# 测试URL列表 - 特别包括了我们看到的具有哈希值格式的URL
problematic_urls = [
    "http://rsc.nankai.edu.cn/_upload/article/files/ae/84/abeb6f624f32a210e42600226721/63000b8a-c2bb-47a4-a4da-f78a1e22d2f3.docx",
    "http://rsc.nankai.edu.cn/_upload/article/files/a6/6a/42937538420367facb605cdbd678/7597b8d3-595b-4f7b-9f5d-78bd39cccb1c.doc",
    "http://xxgk.nankai.edu.cn/_upload/article/8a/99/b04cbf1f42098c72a6dd4ea7f26f/047d4817-d0b2-4fbe-9dbd-22731f56e47e.doc", 
    # 添加您之前看到的其他问题URL
]

def test_doc_titles():
    print("开始测试文档标题处理...")
    
    app = create_app()
    with app.app_context():
        for url in problematic_urls:
            print(f"\n处理URL: {url}")
            
            # 测试获取文件信息
            file_info = get_file_info(url)
            if file_info:
                print(f"检测到文件类型: {file_info['file_type']}")
                
                # 测试获取页面信息（包括标题处理）
                page_info = fetch_page(url)
                if page_info:
                    print(f"生成的标题: {page_info['title']}")
                else:
                    print("获取页面信息失败")
            else:
                print("未能识别为文档")

if __name__ == "__main__":
    test_doc_titles()
