import os

class Config:
    """基本配置"""
    SECRET_KEY = 'your_secret_key'  # 请务必修改为强随机值
    ELASTICSEARCH_HOST = 'http://localhost:9200'  # Elasticsearch 服务器地址
    INDEX_NAME = 'nku_web'  # Elasticsearch 索引名称
    SNAPSHOT_FOLDER = os.path.join(os.path.abspath(os.path.dirname(__file__)), 'app', 'data', 'snapshots')  # 新增：网页快照存储路径
    
    # 爬虫黑名单配置 - 需要排除的网站域名
    CRAWLER_BLACKLIST = [
        'nkzbb.nankai.edu.cn',    # 招标办网站
        'iam.nankai.edu.cn'       # 身份认证网站
    ]

    @staticmethod
    def init_app(app):
        pass

class DevelopmentConfig(Config):
    DEBUG = True

class ProductionConfig(Config):
    DEBUG = False
    # 生产环境特定配置，例如日志等

config = {
    'development': DevelopmentConfig,
    'production': ProductionConfig,
    'default': DevelopmentConfig
}
