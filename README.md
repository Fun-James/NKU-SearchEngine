# 南开校内资源搜索引擎

这是一个用于搜索南开大学校内资源的搜索引擎项目，基于Flask和Elasticsearch开发。

## 功能特点

- **网页爬虫**：支持对南开大学域名下的网站进行爬取，遵循robots.txt规则
- **全文索引**：使用Elasticsearch存储和索引爬取的内容，支持中文分词
- **搜索功能**：
  - 支持基本关键词搜索
  - 支持复杂查询语法（AND、OR、NOT运算）
  - 支持短语搜索（使用引号）
  - 提供高级搜索表单
- **用户体验**：
  - 搜索结果高亮显示
  - 搜索结果聚类
  - 搜索建议和拼写纠正
  - 搜索结果分页
  - 搜索历史记录
  - 响应式网页设计

## 项目结构

```
hw4/                      # 项目根目录
├── app/                  # Flask应用目录
│   ├── __init__.py       # 应用初始化
│   ├── errors.py         # 错误处理
│   ├── crawler/          # 爬虫模块
│   │   ├── __init__.py
│   │   └── spider.py     # 爬虫实现
│   ├── indexer/          # 索引模块
│   │   ├── __init__.py
│   │   └── es_indexer.py # ES索引器
│   ├── main/             # 主要蓝图
│   │   ├── __init__.py
│   │   ├── routes.py     # 路由定义
│   │   ├── query_parser.py    # 查询解析
│   │   ├── result_clustering.py  # 结果聚类
│   │   └── search_suggestion.py  # 搜索建议
│   ├── static/           # 静态文件
│   │   ├── css/
│   │   └── js/
│   ├── templates/        # 模板文件
│   └── data/             # 数据目录
├── config.py             # 配置文件
├── run.py                # 运行入口
├── crawl_and_index.py    # 爬取和索引脚本
└── requirements.txt      # 项目依赖
```

## 安装与配置

1. 安装依赖：
```
pip install -r requirements.txt
```

2. 安装并运行Elasticsearch (7.x版本)：
   - 下载：https://www.elastic.co/downloads/past-releases/elasticsearch-7-17-7
   - 运行：./bin/elasticsearch (Linux/Mac) 或 .\bin\elasticsearch.bat (Windows)
   - 确保Elasticsearch在http://localhost:9200可访问

3. 安装IK分词器 (用于中文分词)：
```
./bin/elasticsearch-plugin install https://github.com/medcl/elasticsearch-analysis-ik/releases/download/v7.17.7/elasticsearch-analysis-ik-7.17.7.zip
```

4. 配置：
   - 修改config.py中的SECRET_KEY
   - 确保ELASTICSEARCH_HOST指向正确的地址

## 爬取与索引

使用crawl_and_index.py脚本爬取网页并索引：

```
python crawl_and_index.py --max-pages 100 --delay 1.0
```

参数说明：
- `--max-pages`: 最大爬取页面数量，默认50
- `--delay`: 爬取延迟(秒)，默认1.0
- `--start-url`: 起始URL，默认南开大学主页
- `--skip-robots`: 是否忽略robots.txt
- `--max-depth`: 最大爬取深度，默认3

## 运行服务

```
python run.py
```

服务将在 http://127.0.0.1:5000 启动。

## 使用说明

### 基本搜索语法
- 多关键词搜索：`南开大学 计算机`（默认为AND）
- OR运算：`南开大学 OR 天津大学`
- NOT运算：`南开大学 NOT 天津大学`
- 短语搜索：`"南开大学计算机学院"`

### 高级搜索
通过高级搜索页面可以：
- 指定必须包含的词
- 指定必须包含的短语
- 指定包含任意一个词
- 指定不包含的词
- 限制搜索范围到特定子域名
- 选择结果排序方式

## 关于评分系统

本项目使用Elasticsearch的默认相关性评分机制，基于BM25算法，与向量空间模型中的TF-IDF评分相关。系统**不使用PageRank**算法进行评分。

## 许可证

[MIT License](LICENSE)
