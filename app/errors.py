"""
错误处理模块
"""
from flask import render_template, current_app
from . import create_app

def register_error_handlers(app):
    """
    注册应用的错误处理函数
    """
    
    @app.errorhandler(404)
    def page_not_found(e):
        return render_template('errors/404.html'), 404
        
    @app.errorhandler(500)
    def internal_server_error(e):
        return render_template('errors/500.html'), 500
        
    @app.errorhandler(503)
    def service_unavailable(e):
        return render_template('errors/503.html'), 503
