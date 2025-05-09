class Config:
    """基本配置"""
    SECRET_KEY = 'your_secret_key'  # 请务必修改为强随机值
    ELASTICSEARCH_HOST = 'http://localhost:9200'  # Elasticsearch 服务器地址
    INDEX_NAME = 'nku_web'  # Elasticsearch 索引名称

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
