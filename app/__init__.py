from flask import Flask
from config import config
from elasticsearch import Elasticsearch
import logging
from logging.handlers import RotatingFileHandler
import os

def create_app(config_name='default'):
    app = Flask(__name__)
    app.config.from_object(config[config_name])
    config[config_name].init_app(app)

    # 配置 Elasticsearch
    try:
        if app.config['ELASTICSEARCH_HOST']:
            app.elasticsearch = Elasticsearch(app.config['ELASTICSEARCH_HOST'])
            app.logger.info(f"Connected to Elasticsearch at {app.config['ELASTICSEARCH_HOST']}")
        else:
            app.elasticsearch = None
            app.logger.warning("Elasticsearch host not configured")
    except Exception as e:
        app.logger.error(f"Failed to connect to Elasticsearch: {e}")
        app.elasticsearch = None

    # 注册蓝图
    from .main import main as main_blueprint
    app.register_blueprint(main_blueprint)

    # 注册错误处理
    from .errors import register_error_handlers
    register_error_handlers(app)

    # 配置日志
    if not app.debug:
        if not os.path.exists('logs'):
            os.mkdir('logs')
        file_handler = RotatingFileHandler('logs/search_engine.log', maxBytes=10*1024*1024, backupCount=10)
        file_handler.setFormatter(logging.Formatter(
            '%(asctime)s %(levelname)s: %(message)s [in %(pathname)s:%(lineno)d]'
        ))
        file_handler.setLevel(logging.INFO)
        app.logger.addHandler(file_handler)
        app.logger.setLevel(logging.INFO)
        app.logger.info('Search Engine startup')

    return app
