from app.crawler.spider import spider_main
from app.indexer.es_indexer import get_es_client, create_index_if_not_exists, bulk_index_documents
from elasticsearch import Elasticsearch
import argparse
import time
import urllib3
import ssl
import requests
from app import create_app  # 新增导入
from urllib.parse import urlparse

def get_college_urls(category='all'):
    """获取学院的URL列表，排除黑名单网站"""
    all_urls = {
        # 人文社科类 (已完成爬取的学院已注释)
        'humanities': [
             ("https://wxy.nankai.edu.cn/", "文学院"),  # 已完成
             ("https://history.nankai.edu.cn/", "历史学院"),  # 已完成
             ("https://phil.nankai.edu.cn/", "哲学院"),  # 已完成
             ("https://sfs.nankai.edu.cn/", "外国语学院"),  # 已完成
            ("https://law.nankai.edu.cn/", "法学院"),  # 已完成
           ("https://zfxy.nankai.edu.cn/", "周恩来政府管理学院"),
            ("https://cz.nankai.edu.cn/", "马克思主义学院"),
            ("https://hyxy.nankai.edu.cn/", "汉语言文化学院"),
            ("https://jc.nankai.edu.cn/", "新闻与传播学院"),
            ("https://shxy.nankai.edu.cn/", "社会学院"),
            ("https://tas.nankai.edu.cn/", "旅游与服务学院"),
        ],
         'mygroup': [
          ("https://cc.nankai.edu.cn/", "计算机学院"),
            ("https://cyber.nankai.edu.cn/", "网络空间安全学院"),
            ("https://ai.nankai.edu.cn/", "人工智能学院"),
            ("https://stat.nankai.edu.cn/", "统计与数据科学学院"),
             ("https://cs.nankai.edu.cn/", "软件学院"),
        ],
        
        # 软件学院专用
        'software': [
            ("https://cs.nankai.edu.cn/", "软件学院"),
        ],

        # 经济管理类
        'economics': [
            ("https://economics.nankai.edu.cn/", "经济学院"),
            ("https://bs.nankai.edu.cn/", "商学院"),
            ("https://finance.nankai.edu.cn/", "金融学院"),
        ],
        
        # 理工类
        'science': [
            ("https://math.nankai.edu.cn/", "数学科学学院"),
            ("https://physics.nankai.edu.cn/", "物理科学学院"),
            ("https://chem.nankai.edu.cn/", "化学学院"),
            ("https://sky.nankai.edu.cn/", "生命科学学院"),
            ("https://env.nankai.edu.cn/", "环境科学与工程学院"),
            ("https://mse.nankai.edu.cn/", "材料科学与工程学院"),
            ("https://ceo.nankai.edu.cn/", "电子信息与光学工程学院"),

            
        ],
        
        # 医学类
        'medical': [
            ("https://medical.nankai.edu.cn/", "医学院"),
            ("https://pharmacy.nankai.edu.cn/", "药学院"),
        ],          # 新闻网
        'news': [
            ("https://news.nankai.edu.cn/", "南开新闻网"),
            ("https://international.nankai.edu.cn/","国际合作交流处"),
            ("http://skleoc.nankai.edu.cn/", "环境污染过程与基准教育部重点实验室"),
            ("http://sklmcb.nankai.edu.cn/", "药物化学生物学国家重点实验室"),
            ("http://chinaeconomy.nankai.edu.cn/", "中国特色社会主义经济建设协同创新中心"),
            ("https://icpm.nankai.edu.cn", "中国公司治理研究院"),
            ("http://ccsh.nankai.edu.cn/", "中国社会史研究中心"),
            ("http://mwhrc.nankai.edu.cn/", "世界近现代史研究中心"),
            ("http://apec.nankai.edu.cn/", "APEC研究中心"),
            ("http://ces.nankai.edu.cn/", "中国教育与社会发展研究院"),
            ("http://cts.nankai.edu.cn/", "陈省身数学研究所"),
            ("http://cg.org.cn/", "中国公司治理研究院(对外)"),
            # 新增研究院
            ("http://humanrights.nankai.edu.cn/", "人权研究中心"),
            ("http://www.cim.nankai.edu.cn/", "中国公司治理研究院管理学分院"),
            ("http://cfc.nankai.edu.cn/", "中国公司治理研究院财务分院"),
            ("http://www.riyan.nankai.edu.cn/", "日本研究院"),
            ("http://esd.nankai.edu.cn/", "经济与社会发展研究院"),
            ("http://ifd.nankai.edu.cn/", "金融发展研究院"),
            ("http://nkbinhai.nankai.edu.cn/", "南开大学滨海学院"),
            ("https://tm-nk.nankai.edu.cn/", "泰达微技术研究院"),
            ("http://nkise.nankai.edu.cn/", "南开大学国际经济研究所"),
            ("http://iap.nankai.edu.cn", "亚洲研究中心"),
            ("http://tedabio.nankai.edu.cn/", "泰达生物技术研究院"),
            ("https://nkszri.nankai.edu.cn/", "深圳研究院"),
            ("http://art.nankai.edu.cn/", "艺术研究院"),
            ("https://jcjd.nankai.edu.cn/", "经济建设协同创新中心"),
            ("https://21cnmarx.nankai.edu.cn/", "21世纪马克思主义研究院"),
            ("http://cingai.nankai.edu.cn/", "认知计算与应用重点实验室"),
            ("http://arc.nankai.edu.cn/", "应用研究中心"),
            ("http://lpmc.nankai.edu.cn/", "理论物理与计算物理中心"),

        ],
        'lib': [
            ("https://lib.nankai.edu.cn/", "南开图书馆网"),
        ],
        'tju': [
            ("https://www.tju.edu.cn/", "天津大学"),
        ],
        # 研究院
        'research_institutes': [



            ("http://lac.nankai.edu.cn/", "文学与艺术研究中心"),
            ("https://klfpm.nankai.edu.cn/", "开放实验室"),
            ("https://imo.nankai.edu.cn", "国际数学奥林匹克研究中心"),
            ("http://xnjj.nankai.edu.cn/", "虚拟经济与管理研究中心"),
            ("http://tourism2011.nankai.edu.cn/", "旅游研究中心"),
            ("https://ciwe.nankai.edu.cn/", "中国经济研究中心"),
            ("https://riph.nankai.edu.cn/", "人口与健康研究院"),
            ("https://cgc.nankai.edu.cn/", "中国政府治理研究院"),
            ("http://cias.nankai.edu.cn", "中国社会科学院研究中心"),
            ("https://ioip.nankai.edu.cn/", "国际问题研究院"),
            ("https://sklpmc.nankai.edu.cn/", "理论物理重点实验室"),
            ("https://sgkx.nankai.edu.cn", "社会科学研究院"),
        ]
    }
      # 根据类别返回相应的URL列表
    if category == 'all':
        urls = []
        for category_urls in all_urls.values():
            urls.extend([url for url, name in category_urls])
    elif '+' in category:
        # 处理组合类别，如 'humanities+science'
        categories = category.split('+')
        urls = []
        for cat in categories:
            if cat in all_urls:
                urls.extend([url for url, name in all_urls[cat]])
            else:
                print(f"未知类别: {cat}")
        if not urls:
            return []
    elif category in all_urls:
        urls = [url for url, name in all_urls[category]]
    else:
        print(f"未知类别: {category}")
        return []
    # 尝试从配置文件获取黑名单，如果无法获取则使用默认值
    try:
        from config import Config
        blacklist_domains = Config.CRAWLER_BLACKLIST
    except:
        # 默认黑名单
        blacklist_domains = [
            'nkzbb.nankai.edu.cn',    # 招标办网站
            'iam.nankai.edu.cn'       # 身份认证网站
        ]
    
    # 过滤黑名单网站
    filtered_urls = []
    for url in urls:
        from urllib.parse import urlparse
        parsed = urlparse(url)
        if parsed.netloc not in blacklist_domains:
            filtered_urls.append(url)
        else:
            print(f"排除黑名单网站: {url}")
    
    return filtered_urls

def get_college_names(category='all'):
    """获取学院名称列表"""
    all_urls = {
        # 人文社科类 (已完成爬取的学院已注释)
        'humanities': [
            ("https://wxy.nankai.edu.cn/", "文学院"),  # 已完成
            ("https://history.nankai.edu.cn/", "历史学院"),  # 已完成
            ("https://phil.nankai.edu.cn/", "哲学院"),  # 已完成
            ("https://sfs.nankai.edu.cn/", "外国语学院"),  # 已完成
            ("https://law.nankai.edu.cn/", "法学院"),  # 已完成
            ("https://zfxy.nankai.edu.cn/", "周恩来政府管理学院"),
            ("https://cz.nankai.edu.cn/", "马克思主义学院"),
            ("https://hyxy.nankai.edu.cn/", "汉语言文化学院"),
            ("https://jc.nankai.edu.cn/", "新闻与传播学院"),
            ("https://shxy.nankai.edu.cn/", "社会学院"),
            ("https://tas.nankai.edu.cn/", "旅游与服务学院"),
        ],        'mygroup': [
            ("https://ai.nankai.edu.cn/", "人工智能学院"),
            ("https://stat.nankai.edu.cn/", "统计与数据科学学院"),
             ("https://cs.nankai.edu.cn/", "软件学院"),
        ],
        
        # 软件学院专用
        'software': [
            ("https://cs.nankai.edu.cn/", "软件学院"),
        ],
        # 经济管理类
        'economics': [
            ("https://economics.nankai.edu.cn/", "经济学院"),
            ("https://bs.nankai.edu.cn/", "商学院"),
            ("https://finance.nankai.edu.cn/", "金融学院"),
        ],
        
        # 理工类
        'science': [
            ("https://math.nankai.edu.cn/", "数学科学学院"),
            ("https://physics.nankai.edu.cn/", "物理科学学院"),
            ("https://chem.nankai.edu.cn/", "化学学院"),
            ("https://sky.nankai.edu.cn/", "生命科学学院"),
            ("https://env.nankai.edu.cn/", "环境科学与工程学院"),
            ("https://mse.nankai.edu.cn/", "材料科学与工程学院"),
            ("https://ceo.nankai.edu.cn/", "电子信息与光学工程学院"),
            ("https://cc.nankai.edu.cn/", "计算机学院"),
            ("https://cyber.nankai.edu.cn/", "网络空间安全学院"),

        ],
        
        # 医学类
        'medical': [
            ("https://medical.nankai.edu.cn/", "医学院"),
            ("https://pharmacy.nankai.edu.cn/", "药学院"),
        ],
        # 新闻网
        'news': [
            ("https://news.nankai.edu.cn/", "南开新闻网"),
             ("https://international.nankai.edu.cn/","国际合作交流处"),
            ("http://skleoc.nankai.edu.cn/", "环境污染过程与基准教育部重点实验室"),
            ("http://sklmcb.nankai.edu.cn/", "药物化学生物学国家重点实验室"),
            ("http://chinaeconomy.nankai.edu.cn/", "中国特色社会主义经济建设协同创新中心"),
            ("https://icpm.nankai.edu.cn", "中国公司治理研究院"),
            ("http://ccsh.nankai.edu.cn/", "中国社会史研究中心"),
            ("http://mwhrc.nankai.edu.cn/", "世界近现代史研究中心"),
            ("http://apec.nankai.edu.cn/", "APEC研究中心"),
            ("http://ces.nankai.edu.cn/", "中国教育与社会发展研究院"),
            ("http://cts.nankai.edu.cn/", "陈省身数学研究所"),
            ("http://cg.org.cn/", "中国公司治理研究院(对外)"),
            # 新增研究院
            ("http://humanrights.nankai.edu.cn/", "人权研究中心"),
            ("http://www.cim.nankai.edu.cn/", "中国公司治理研究院管理学分院"),
            ("http://cfc.nankai.edu.cn/", "中国公司治理研究院财务分院"),
            ("http://www.riyan.nankai.edu.cn/", "日本研究院"),
            ("http://esd.nankai.edu.cn/", "经济与社会发展研究院"),
            ("http://ifd.nankai.edu.cn/", "金融发展研究院"),
            ("http://nkbinhai.nankai.edu.cn/", "南开大学滨海学院"),
            ("https://tm-nk.nankai.edu.cn/", "泰达微技术研究院"),
            ("http://nkise.nankai.edu.cn/", "南开大学国际经济研究所"),
            ("http://iap.nankai.edu.cn", "亚洲研究中心"),
            ("http://tedabio.nankai.edu.cn/", "泰达生物技术研究院"),
            ("https://nkszri.nankai.edu.cn/", "深圳研究院"),
            ("http://art.nankai.edu.cn/", "艺术研究院"),
            ("https://jcjd.nankai.edu.cn/", "经济建设协同创新中心"),
            ("https://nkszri.nankai.edu.cn/", "深圳研究院"),
            ("http://art.nankai.edu.cn/", "艺术研究院"),
            ("https://jcjd.nankai.edu.cn/", "经济建设协同创新中心"),
            ("https://21cnmarx.nankai.edu.cn/", "21世纪马克思主义研究院"),
            ("http://cingai.nankai.edu.cn/", "认知计算与应用重点实验室"),
            ("http://arc.nankai.edu.cn/", "应用研究中心"),
            ("http://lpmc.nankai.edu.cn/", "理论物理与计算物理中心"),
        ],    
        'lib': [
        ("https://lib.nankai.edu.cn/", "南开图书馆网"),
    ],
        'tju': [
            ("https://www.tju.edu.cn/", "天津大学"),
        ],
      # 研究院
    'research_institutes': [



        ("http://lac.nankai.edu.cn/", "文学与艺术研究中心"),
        ("https://klfpm.nankai.edu.cn/", "开放实验室"),
        ("https://imo.nankai.edu.cn", "国际数学奥林匹克研究中心"),
        ("http://xnjj.nankai.edu.cn/", "虚拟经济与管理研究中心"),
        ("http://tourism2011.nankai.edu.cn/", "旅游研究中心"),
        ("https://ciwe.nankai.edu.cn/", "中国经济研究中心"),
        ("https://riph.nankai.edu.cn/", "人口与健康研究院"),
        ("https://cgc.nankai.edu.cn/", "中国政府治理研究院"),
        ("http://cias.nankai.edu.cn", "中国社会科学院研究中心"),
        ("https://ioip.nankai.edu.cn/", "国际问题研究院"),
        ("https://sklpmc.nankai.edu.cn/", "理论物理重点实验室"),
        ("https://sgkx.nankai.edu.cn", "社会科学研究院"),
    ]
    }
      # 根据类别返回相应的名称列表
    if category == 'all':
        college_data = []
        for category_urls in all_urls.values():
            college_data.extend(category_urls)
    elif '+' in category:
        # 处理组合类别，如 'humanities+science'
        categories = category.split('+')
        college_data = []
        for cat in categories:
            if cat in all_urls:
                college_data.extend(all_urls[cat])
            else:
                print(f"未知类别: {cat}")
        if not college_data:
            return []
    elif category in all_urls:
        college_data = all_urls[category]
    else:
        print(f"未知类别: {category}")
        return []
    
    return college_data

def calculate_pages_per_site(total_pages, category='all'):
    """
    计算每个网站应该爬取的页面数量
    
    Args:
        total_pages: 总页面数量
        category: 学院类别 ('all', 'humanities', 'economics', 'science', 'medical')
    
    Returns:
        int: 每个学院网站的页面数
    """
    college_urls = get_college_urls(category)
    num_colleges = len(college_urls)
    
    if num_colleges == 0:
        return 0
        
    pages_per_college = total_pages // num_colleges
    
    print(f"页面分配计划 ({category}):")
    print(f"- 各学院网站: 每个约 {pages_per_college} 页 (共 {num_colleges} 个学院)")
    print(f"- 预计总页面数: {pages_per_college * num_colleges}")
    
    return pages_per_college

def get_allowed_domains_for_college(college_url):
    """
    获取当前爬取的域名规则列表。这个函数会：
    1. 排除其他学院的域名
    2. 排除南开大学主站域名
    3. 对于软件学院，只允许 cs.nankai.edu.cn 域名
    4. 对于新闻网，只允许 news.nankai.edu.cn 域名
    5. 其他情况允许所有其他南开大学的域名
    
    参数:
    - college_url: 当前爬取的学院的起始URL
    
    返回:
    - 需要排除的域名列表，格式为 (domains_to_exclude, current_college_domain)
    """
    parsed = urlparse(college_url)
    current_college_domain = parsed.netloc
    
    # 获取所有已定义的学院及新闻网等域名
    all_defined_site_domains = get_all_college_domains()
    
    domains_to_exclude = ['www.nankai.edu.cn']  # 默认排除南开主站
    
    if current_college_domain == 'news.nankai.edu.cn':
        # 对于新闻网，排除所有其他已定义的域名和主站
        for domain in all_defined_site_domains:
            if domain != current_college_domain:
                domains_to_exclude.append(domain)
        return (list(set(domains_to_exclude)), current_college_domain)
        
    elif current_college_domain == 'cs.nankai.edu.cn':
        # 对于软件学院，只允许软件学院自己的域名，排除所有其他域名
        # domains_to_exclude 已包含主站
        for domain in all_defined_site_domains:
            if domain != current_college_domain:
                domains_to_exclude.append(domain)
        
        # 添加其他可能的南开域名（严格限制只在软件学院域名内）
        # 这些是额外需要排除的，以确保软件学院爬虫的纯净性
        domains_to_exclude.extend([
            'nankai.edu.cn', # 这是一个通用域名，可能需要更细致的判断，但遵循原逻辑
            'nku.edu.cn',
            # 'news.nankai.edu.cn', # news.nankai.edu.cn 已被 all_defined_site_domains 包含并处理
            'lib.nankai.edu.cn',
        ])
        # 确保不排除当前软件学院域名自身，并去重
        return (list(set(d for d in domains_to_exclude if d != current_college_domain)), current_college_domain)
    
    else: # 其他学院网站
        # 排除主站以及除了当前学院以外的所有已定义域名
        for domain in all_defined_site_domains:
            if domain != current_college_domain:
                domains_to_exclude.append(domain)
                
        return (list(set(domains_to_exclude)), current_college_domain)

def get_all_college_domains():
    """
    获取所有学院的域名列表
    
    返回:
    - 包含所有学院域名的列表
    """
    domains = []
    college_data = get_college_names('all')
    for url, _ in college_data:
        parsed = urlparse(url)
        domains.append(parsed.netloc)
    return list(set(domains)) #确保返回唯一的域名列表

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
        print(f"SSL设置初始化失败，但将继续尝试: {e}")    # 解析命令行参数
    parser = argparse.ArgumentParser(description='爬取并索引南开大学各学院网站')
    parser.add_argument('--total-pages', type=int, default=30000, help='总的爬取页面数量')
    parser.add_argument('--category', type=str, default='research_institutes',
                       help='要爬取的学院类别，支持组合如: humanities+science，software表示只爬取软件学院')
    parser.add_argument('--delay', type=float, default=0.1, help='爬取延迟(秒)')
    parser.add_argument('--skip-robots', action='store_true', help='忽略robots.txt')
    parser.add_argument('--max-depth', type=int, default=200, help='最大爬取深度')
    parser.add_argument('--use-http', action='store_true', help='使用HTTP而非HTTPS')
    parser.add_argument('--batch-size', type=int, default=100, help='批处理大小，每多少个页面进行一次索引 (默认100)')
    args = parser.parse_args()      
    
    # 计算每个网站的页面分配
    pages_per_college = calculate_pages_per_site(args.total_pages, args.category)
      # 准备爬取列表
    crawl_tasks = []
    college_data = get_college_names(args.category)
    
    # 添加学院网站爬取任务
    for url, name in college_data:
        if args.use_http and url.startswith('https://'):
            url = url.replace('https://', 'http://')
        crawl_tasks.append((name, url, pages_per_college))
    
    print(f"\n准备爬取 {args.category} 类别的 {len(crawl_tasks)} 个学院")
    print(f"每个学院爬取页面数: {pages_per_college}")
    print(f"预计总页面数: {sum(task[2] for task in crawl_tasks)}")
      # 连接到Elasticsearch，配置超时参数
    start_time = time.time()
    es = Elasticsearch(
        'http://localhost:9200',
        timeout=60,  # 60秒连接超时
        max_retries=3,  # 最大重试次数
        retry_on_timeout=True,  # 超时时重试
        http_compress=True,  # 启用HTTP压缩
        request_timeout=300  # 5分钟请求超时
    )
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
    all_crawled_data = []    # 创建动态批处理回调函数
    current_batch_size = args.batch_size
    consecutive_successes = 0
    consecutive_failures = 0
    def batch_index_callback(batch_data):
        """优化的动态调整批处理大小的索引回调函数"""
        nonlocal current_batch_size, consecutive_successes, consecutive_failures
        
        if batch_data:
            try:
                start_time = time.time()
                print(f"📊 准备索引 {len(batch_data)} 个页面（当前批处理大小: {current_batch_size}）...")
                
                # 检查ES服务是否可用
                if not es.ping():
                    print("⚠️ ES服务连接异常，尝试重新连接...")
                    time.sleep(5)
                    if not es.ping():
                        raise Exception("ES服务不可用")
                
                # 获取当前索引文档数量，用于动态调整
                try:
                    stats = es.indices.stats(index=index_name)
                    current_doc_count = stats['indices'][index_name]['total']['docs']['count']
                except:
                    current_doc_count = 0
                
                # 创建数据副本进行索引，避免内存引用问题
                batch_copy = []
                for item in batch_data:
                    # 只保留必要的字段，减少内存占用
                    cleaned_item = {
                        'url': item.get('url'),
                        'title': item.get('title'),
                        'content': item.get('content', '')[:10000],  # 限制内容长度
                        'file_info': item.get('file_info', {}),
                        'crawled_at': item.get('crawled_at'),
                        'is_attachment': item.get('is_attachment', False)
                    }
                    batch_copy.append(cleaned_item)
                
                bulk_index_documents(es, index_name, batch_copy)
                elapsed_time = time.time() - start_time
                
                print(f"✅ 已索引 {len(batch_copy)} 个页面到 Elasticsearch (耗时: {elapsed_time:.2f}秒)")
                
                # 清理内存
                del batch_copy
                import gc
                gc.collect()
                
                # 成功索引，增加连续成功计数
                consecutive_successes += 1
                consecutive_failures = 0
                
                # 智能调整批处理大小
                if current_doc_count > 10000:  # 当文档数超过10000时开始保守调整
                    if elapsed_time > 90:  # 如果处理时间超过1.5分钟，减小批处理大小
                        if current_batch_size > 15:
                            current_batch_size = max(15, current_batch_size - 15)
                            print(f"🔄 批处理时间较长({elapsed_time:.1f}s)，调整批处理大小至: {current_batch_size}")
                    elif elapsed_time < 30 and consecutive_successes >= 5:  # 如果处理很快且连续成功，可以适当增加
                        if current_batch_size < 40:
                            current_batch_size = min(40, current_batch_size + 5)
                            print(f"⚡ 处理速度良好，适当增加批处理大小至: {current_batch_size}")
                            consecutive_successes = 0  # 重置计数
                elif current_doc_count > 5000:
                    if elapsed_time > 60:
                        if current_batch_size > 20:
                            current_batch_size = max(20, current_batch_size - 10)
                            print(f"🔄 调整批处理大小至: {current_batch_size}")
                
                # 显示当前索引统计
                try:
                    stats = es.indices.stats(index=index_name)
                    doc_count = stats['indices'][index_name]['total']['docs']['count']
                    store_size = stats['indices'][index_name]['total']['store']['size_in_bytes'] / 1024 / 1024  # MB
                    print(f"📈 当前索引总文档数: {doc_count}, 大小: {store_size:.1f}MB")
                except:
                    pass
                    
            except Exception as e:
                print(f"❌ 批处理索引失败: {e}")
                consecutive_failures += 1
                consecutive_successes = 0
                
                # 如果连续失败，大幅减小批处理大小
                if consecutive_failures >= 2 and current_batch_size > 10:
                    current_batch_size = max(10, current_batch_size - 20)
                    print(f"🔻 连续失败，大幅减小批处理大小至: {current_batch_size}")
                
                raise  # 重新抛出异常，让爬虫处理
            
    with flask_app.app_context():
        for i, (site_name, url, max_pages) in enumerate(crawl_tasks, 1):
            print(f"\n[{i}/{len(crawl_tasks)}] 开始爬取 {site_name} ({url})")
            print(f"目标页面数: {max_pages}")
            print(f"💡 使用动态批处理模式：初始批处理大小{args.batch_size}，会根据索引大小和性能自动调整")
            
            # 如果是学院网站，设置域名过滤规则
            allowed_domains = None
            if site_name != "南开大学主站":
                domains_to_exclude, current_college_domain = get_allowed_domains_for_college(url)
                allowed_domains = (domains_to_exclude, current_college_domain)
                print(f"🎯 域名限制: 当前学院域名 {current_college_domain}")
                print(f"🚫 排除域名: {', '.join(domains_to_exclude)}")
            
            try:
                crawled_data = spider_main(
                    start_url=url,
                    max_pages=max_pages,
                    delay=args.delay,
                    respect_robots=not args.skip_robots,
                    max_depth=args.max_depth,
                    batch_callback=batch_index_callback,
                    batch_size=current_batch_size,  # 使用动态调整的批处理大小
                    allowed_domains=allowed_domains
                )
                # 注意：现在数据已经通过批处理回调函数自动索引了
                # crawled_data 可能为空或只包含最后一批不足batch_size个的数据
                if crawled_data:
                    print(f"✓ {site_name} 爬取完成: 最后剩余 {len(crawled_data)} 个页面")
                    all_crawled_data.extend(crawled_data)
                else:
                    print(f"✓ {site_name} 爬取完成: 所有数据已通过批处理索引")
                    
            except Exception as e:
                print(f"✗ {site_name} 爬取出错: {e}")
                continue
            
            # 显示进度（注意：all_crawled_data 现在只包含未批处理的剩余数据）
            # 真实的已索引数据需要从 Elasticsearch 查询
            try:
                current_stats = es.indices.stats(index=index_name)
                current_doc_count = current_stats['indices'][index_name]['total']['docs']['count']
                print(f"📊 当前索引中文档数: {current_doc_count}")
            except:
                print(f"📊 累计处理页面: {len(all_crawled_data)} (仅剩余数据)")
        print(f"\n🎉 全部爬取完成！")
        print(f"💡 说明：大部分数据已通过批处理（每{args.batch_size}页）自动索引，节省了内存使用")
        
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
            if doc_count > 0:
                print(f"平均处理速度: {doc_count / elapsed_time:.2f} 页/秒")
            print(f"✅ 批处理模式：内存使用得到有效控制")
        except Exception as e:
            print(f"获取索引统计信息失败: {e}")

if __name__ == "__main__":
    main()