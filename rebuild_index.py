from app import create_app
from app.indexer.es_indexer import get_es_client, create_index_if_not_exists
from config import Config
import os

app = create_app()

def rebuild_index():
    with app.app_context():
        # 获取ES客户端
        es = get_es_client()
        if not es:
            print("无法连接到Elasticsearch")
            return
        
        # 删除旧索引
        if es.indices.exists(index=Config.ELASTICSEARCH_INDEX):
            es.indices.delete(index=Config.ELASTICSEARCH_INDEX)
            print(f"已删除旧索引 {Config.ELASTICSEARCH_INDEX}")
        
        # 创建新索引
        create_index_if_not_exists(es, Config.ELASTICSEARCH_INDEX)
        print(f"已创建新索引 {Config.ELASTICSEARCH_INDEX}")
        
        # 重新运行爬虫和索引
        from app.crawler.spider import crawl
        from app.indexer.es_indexer import index_documents
        
        # 开始爬取
        pages = crawl(Config.START_URLS, Config.MAX_PAGES)
        print(f"爬取完成，共获取 {len(pages)} 个页面")
        
        # 索引文档
        indexed = index_documents(pages)
        print(f"索引完成，共索引 {indexed} 个文档")

if __name__ == "__main__":
    rebuild_index()
