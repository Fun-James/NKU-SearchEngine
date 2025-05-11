# -*- coding: utf-8 -*-
from app import create_app
from app.crawler.spider import fetch_page
import ssl
import urllib3
import traceback

def test_doc_recognition():
    # 禁用SSL警告和设置
    urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
    
    # SSL安全设置
    ssl._create_default_https_context = ssl._create_unverified_context

    print('开始测试文档识别功能...')
    
    try:
        app = create_app()
        with app.app_context():
            print('初始化Flask应用上下文完成')
            
            # 测试南开大学带附件的通知页面
            url = 'https://www.nankai.edu.cn/2025/0403/c17471a566126/page.htm'
            print(f'\n正在爬取URL: {url}')
            
            try:
                result = fetch_page(url)
                print('页面获取完成')
                
                if result:
                    print(f'页面标题: {result.get("title", "Unknown")}')
                    print(f'是否可能包含嵌入文档: {result.get("has_embedded_docs", False)}')
                    
                    # 打印可能的文档链接
                    doc_links = []
                    for link in result.get('links', []):
                        if any(ext in link.lower() for ext in ['.doc', '.docx', '.pdf', '.xls', '.xlsx']):
                            doc_links.append(link)
                    
                    print(f'发现的文档链接数量: {len(doc_links)}')
                    for i, link in enumerate(doc_links[:3]):  # 只显示前3个
                        print(f'  文档 {i+1}: {link}')
                else:
                    print('无法获取页面信息')
            except Exception as e:
                print(f'爬取时出错: {str(e)}')
    except Exception as e:
        print(f'初始化过程中出错: {str(e)}')

if __name__ == '__main__':
    test_doc_recognition()
