from app.crawler.spider import spider_main
from app.indexer.es_indexer import get_es_client, create_index_if_not_exists, bulk_index_documents
from elasticsearch import Elasticsearch
import argparse
import time
import urllib3
import ssl
import requests
from app import create_app  # 新增导入

def get_college_urls():
    """获取所有学院的URL列表"""
    return [
        # 人文社科类
        "https://wxy.nankai.edu.cn/",     # 文学院
        "https://history.nankai.edu.cn/", # 历史学院
        "https://phil.nankai.edu.cn/",    # 哲学院
        "https://sfs.nankai.edu.cn/",     # 外国语学院
        "https://law.nankai.edu.cn/",     # 法学院
        "https://zfxy.nankai.edu.cn/",    # 周恩来政府管理学院
        "https://cz.nankai.edu.cn/",      # 马克思主义学院
        "https://hyxy.nankai.edu.cn/",    # 汉语言文化学院
        "https://jc.nankai.edu.cn/",      # 新闻与传播学院
        "https://shxy.nankai.edu.cn/",    # 社会学院
        "https://tas.nankai.edu.cn/",     # 旅游与服务学院
        
        # 经济管理类
        "https://economics.nankai.edu.cn/", # 经济学院
        "https://bs.nankai.edu.cn/",        # 商学院
        "https://finance.nankai.edu.cn/",   # 金融学院
        
        # 理工类
        "https://math.nankai.edu.cn/",      # 数学科学学院
        "https://physics.nankai.edu.cn/",   # 物理科学学院
        "https://chem.nankai.edu.cn/",      # 化学学院
        "https://sky.nankai.edu.cn/",       # 生命科学学院
        "https://env.nankai.edu.cn/",       # 环境科学与工程学院
        "https://mse.nankai.edu.cn/",       # 材料科学与工程学院
        "https://ceo.nankai.edu.cn/",       # 电子信息与光学工程学院
        "https://cc.nankai.edu.cn/",        # 计算机学院/软件学院
        "https://cyber.nankai.edu.cn/",     # 网络空间安全学院
        "https://ai.nankai.edu.cn/",        # 人工智能学院
        "https://stat.nankai.edu.cn/",      # 统计与数据科学学院
        
        # 医学类
        "https://medical.nankai.edu.cn/",   # 医学院
        "https://pharmacy.nankai.edu.cn/",  # 药学院
    ]

def calculate_pages_per_site(total_pages, main_site_ratio=0.3):
    """
    计算每个网站应该爬取的页面数量
    
    Args:
        total_pages: 总页面数量
        main_site_ratio: 主站点（南开官网）占总数的比例
    
    Returns:
        tuple: (主站点页面数, 每个学院页面数)
    """
    college_urls = get_college_urls()
    num_colleges = len(college_urls)
    
    main_pages = int(total_pages * main_site_ratio)
    remaining_pages = total_pages - main_pages
    pages_per_college = remaining_pages // num_colleges
    
    print(f"页面分配计划:")
    print(f"- 南开大学主站: {main_pages} 页")
    print(f"- 各学院网站: 每个约 {pages_per_college} 页 (共 {num_colleges} 个学院)")
    print(f"- 预计总页面数: {main_pages + pages_per_college * num_colleges}")
    
    return main_pages, pages_per_college

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
    parser = argparse.ArgumentParser(description='爬取并索引南开大学网站及各学院网站')
    parser.add_argument('--total-pages', type=int, default=100000, help='总的爬取页面数量')
    parser.add_argument('--main-ratio', type=float, default=0.09, help='主站点页面占比 (0.0-1.0)')
    parser.add_argument('--delay', type=float, default=0.2, help='爬取延迟(秒)')
    parser.add_argument('--skip-robots', action='store_true', help='忽略robots.txt')
    parser.add_argument('--max-depth', type=int, default=6, help='最大爬取深度')
    parser.add_argument('--use-http', action='store_true', help='使用HTTP而非HTTPS')
    parser.add_argument('--colleges-only', action='store_true', help='仅爬取学院网站，不爬取主站')
    parser.add_argument('--main-only', action='store_true', help='仅爬取主站，不爬取学院网站')
    args = parser.parse_args()
      
    # 计算页面分配
    main_pages, pages_per_college = calculate_pages_per_site(args.total_pages, args.main_ratio)
    
    # 准备爬取列表
    crawl_tasks = []
    
    if not args.colleges_only:
        # 添加主站点爬取任务
        main_url = "https://www.nankai.edu.cn/"
        if args.use_http:
            main_url = main_url.replace('https://', 'http://')
        crawl_tasks.append(("南开大学主站", main_url, main_pages))
    
    if not args.main_only:
        # 添加学院网站爬取任务
        college_urls = get_college_urls()
        for url in college_urls:
            if args.use_http and url.startswith('https://'):
                url = url.replace('https://', 'http://')
            # 从URL提取学院名称
            college_name = url.split('//')[1].split('.')[0]
            crawl_tasks.append((f"{college_name}学院", url, pages_per_college))
    
    print(f"\n准备爬取 {len(crawl_tasks)} 个网站，预计总页面数: {sum(task[2] for task in crawl_tasks)}")
    
    # 连接到Elasticsearch
    start_time = time.time()
    es = Elasticsearch('http://localhost:9200')
    if not es.ping():
        print("无法连接到Elasticsearch，请确保服务已启动")
        return

    # 创建 Flask 应用上下文
    flask_app = create_app() 
    index_name = flask_app.config['INDEX_NAME']
    
    if not create_index_if_not_exists(es, index_name):
        print("创建索引失败")
        return
    
    # 开始爬取所有网站
    all_crawled_data = []
    
    with flask_app.app_context():
        for i, (site_name, url, max_pages) in enumerate(crawl_tasks, 1):
            print(f"\n[{i}/{len(crawl_tasks)}] 开始爬取 {site_name} ({url})")
            print(f"目标页面数: {max_pages}")
            
            try:
                crawled_data = spider_main(
                    start_url=url,
                    max_pages=max_pages,
                    delay=args.delay,
                    respect_robots=not args.skip_robots,
                    max_depth=args.max_depth
                )
                
                if crawled_data:
                    print(f"✓ {site_name} 爬取完成: {len(crawled_data)} 个页面")
                    all_crawled_data.extend(crawled_data)
                    
                    # 每爬取完一个网站就进行一次索引，避免内存占用过大
                    print(f"正在索引 {site_name} 的数据...")
                    bulk_index_documents(es, index_name, crawled_data)
                    print(f"✓ {site_name} 索引完成")
                else:
                    print(f"✗ {site_name} 爬取失败或无数据")
                    
            except Exception as e:
                print(f"✗ {site_name} 爬取出错: {e}")
                continue
            
            # 显示进度
            total_crawled = len(all_crawled_data)
            print(f"累计已爬取: {total_crawled} 个页面")
        
        print(f"\n🎉 全部爬取完成！总共获取 {len(all_crawled_data)} 个页面")
        
        # 显示最终统计信息
        try:
            stats = es.indices.stats(index=index_name)
            doc_count = stats['indices'][index_name]['total']['docs']['count']
            store_size = stats['indices'][index_name]['total']['store']['size_in_bytes'] / 1024 / 1024  # 转换为MB
            
            end_time = time.time()
            elapsed_time = end_time - start_time
            
            print(f"\n📊 最终统计信息:")
            print(f"索引中文档总数: {doc_count}")
            print(f"索引大小: {store_size:.2f} MB")
            print(f"总耗时: {elapsed_time/60:.1f} 分钟 ({elapsed_time:.2f} 秒)")
            if len(all_crawled_data) > 0:
                print(f"平均处理速度: {len(all_crawled_data) / elapsed_time:.2f} 页/秒")
        except Exception as e:
            print(f"获取索引统计信息失败: {e}")

if __name__ == "__main__":
    main()