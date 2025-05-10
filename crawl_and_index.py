from app.crawler.spider import spider_main
from app.indexer.es_indexer import get_es_client, create_index_if_not_exists, bulk_index_documents
from elasticsearch import Elasticsearch
import argparse
import time
import urllib3
import ssl
import requests
from app import create_app  # 新增导入

def main():
    # 禁用SSL警告和设置
    urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
    
    # 尝试修复SSL上下文，解决证书问题
    try:
        # 创建一个不验证证书的SSL上下文
        ssl_context = ssl.create_default_context()
        ssl_context.check_hostname = False
        ssl_context.verify_mode = ssl.CERT_NONE
        
        # 应用到全局默认设置
        urllib3.util.ssl_.DEFAULT_CIPHERS = 'ALL:@SECLEVEL=1'
    except Exception as e:
        print(f"SSL设置初始化失败，但将继续尝试: {e}")
    
    # 解析命令行参数
    parser = argparse.ArgumentParser(description='爬取并索引南开大学网站')
    parser.add_argument('--max-pages', type=int, default=100, help='最大爬取页面数量')
    parser.add_argument('--delay', type=float, default=1.0, help='爬取延迟(秒)')
    parser.add_argument('--start-url', type=str, default="https://www.nankai.edu.cn/", help='起始URL')
    parser.add_argument('--skip-robots', action='store_true', help='忽略robots.txt')
    parser.add_argument('--max-depth', type=int, default=3, help='最大爬取深度')
    parser.add_argument('--use-http', action='store_true', help='使用HTTP而非HTTPS')
    args = parser.parse_args()
    
    # 如果选择使用HTTP
    if args.use_http and args.start_url.startswith('https://'):
        args.start_url = args.start_url.replace('https://', 'http://')
        print(f"将使用HTTP协议：{args.start_url}")
    
    # 连接到Elasticsearch
    start_time = time.time()
    es = Elasticsearch('http://localhost:9200')
    if not es.ping():
        print("无法连接到Elasticsearch，请确保服务已启动")
        return

    # --- 新增：创建 Flask 应用上下文 ---
    flask_app = create_app() 
    # --- 应用上下文创建结束 ---

    index_name = flask_app.config['INDEX_NAME']  # 修改：从 flask_app.config 获取 INDEX_NAME
    if not create_index_if_not_exists(es, index_name):
        print("创建索引失败")
        return
        
    print(f"开始爬取网页(最大 {args.max_pages} 个页面)...")
    
    # --- 修改：在应用上下文中执行爬虫 ---
    with flask_app.app_context():
        crawled_data = spider_main(
            start_url=args.start_url,
            max_pages=args.max_pages,
            delay=args.delay,
            respect_robots=not args.skip_robots,
            max_depth=args.max_depth
        )
    # --- 应用上下文结束 ---
    
    if crawled_data:
        print(f"\n爬取完成，共获取 {len(crawled_data)} 个页面")
        print("开始索引数据...")
        bulk_index_documents(es, index_name, crawled_data)
        print("索引完成！")

        # 显示一些统计信息
        try:
            stats = es.indices.stats(index=index_name)
            doc_count = stats['indices'][index_name]['total']['docs']['count']
            store_size = stats['indices'][index_name]['total']['store']['size_in_bytes'] / 1024 / 1024  # 转换为MB
            
            end_time = time.time()
            elapsed_time = end_time - start_time
            
            print(f"\n索引统计信息:")
            print(f"文档总数: {doc_count}")
            print(f"索引大小: {store_size:.2f} MB")
            print(f"总耗时: {elapsed_time:.2f} 秒")
            print(f"平均处理速度: {len(crawled_data) / elapsed_time:.2f} 页/秒")
        except Exception as e:
            print(f"获取索引统计信息失败: {e}")
    else:
        print("爬虫没有返回数据")

if __name__ == "__main__":
    main()