from flask import Blueprint

main = Blueprint('main', __name__)

from . import routes # 导入路由，确保在蓝图创建后
