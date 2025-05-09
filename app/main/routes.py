from flask import render_template, request, current_app, redirect, url_for, flash, jsonify
from . import main
from .query_parser_new import QueryParser  # Changed from query_parser to query_parser_new
from .result_clustering import cluster_search_results, get_smart_snippet
from .search_suggestion import SearchSuggestion
import json
import os
from collections import Counter
import urllib.parse

# 搜索历史记录文件
SEARCH_HISTORY_FILE = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'data', 'search_history.json')

# 初始化搜索建议工具
suggester = None

def init_search_suggester():
    """初始化搜索建议工具"""
    global suggester
    suggester = SearchSuggestion()
    
    # 从历史记录加载词典
    history = []
    if os.path.exists(SEARCH_HISTORY_FILE):
        try:
            with open(SEARCH_HISTORY_FILE, 'r', encoding='utf-8') as f:
                history = json.load(f)
        except Exception as e:
            current_app.logger.error(f"Error loading search history: {e}")
    
    if history:
        suggester.load_search_history(history)
        
    return suggester

@main.before_app_request
def before_request():
    """在每个请求之前检查搜索建议器是否已初始化"""
    global suggester
    if suggester is None:
        init_search_suggester()

def log_search_query(query):
    """记录搜索查询，用于生成搜索建议"""
    # 确保data目录存在
    os.makedirs(os.path.dirname(SEARCH_HISTORY_FILE), exist_ok=True)
    
    # 读取现有历史记录
    history = []
    if os.path.exists(SEARCH_HISTORY_FILE):
        try:
            with open(SEARCH_HISTORY_FILE, 'r', encoding='utf-8') as f:
                history = json.load(f)
        except:
            history = []
    
    # 添加新查询并保存（限制大小为最近1000条）
    history.append(query)
    history = history[-1000:]
    
    with open(SEARCH_HISTORY_FILE, 'w', encoding='utf-8') as f:
        json.dump(history, f, ensure_ascii=False)

@main.route('/api/suggestions')
def get_suggestions():
    """API接口：根据用户输入获取搜索建议或历史记录"""
    query = request.args.get('query', '').lower()
    show_history = request.args.get('history', 'false').lower() == 'true'
    
    if show_history:
        # 返回最近的搜索历史
        history = []
        if os.path.exists(SEARCH_HISTORY_FILE):
            try:
                with open(SEARCH_HISTORY_FILE, 'r', encoding='utf-8') as f:
                    history = json.load(f)
                # 获取最近的20个不重复记录
                seen = set()
                unique_history = []
                for query in reversed(history):
                    if query not in seen:
                        seen.add(query)
                        unique_history.append(query)
                        if len(unique_history) >= 20:
                            break
                return jsonify({'suggestions': unique_history})
            except Exception as e:
                current_app.logger.error(f"Error loading search history: {e}")
                return jsonify({'suggestions': []})
    
    # 原有的搜索建议逻辑
    if not query or len(query) < 2:
        return jsonify({'suggestions': []})
    
    suggestions = []
    if os.path.exists(SEARCH_HISTORY_FILE):
        try:
            with open(SEARCH_HISTORY_FILE, 'r', encoding='utf-8') as f:
                history = json.load(f)
                
            # 过滤出包含当前输入的查询
            matching_queries = [q for q in history if query in q.lower()]
            
            # 统计频率并获取最常见的前10个
            counter = Counter(matching_queries)
            suggestions = [item[0] for item in counter.most_common(10)]
        except Exception as e:
            current_app.logger.error(f"Error generating suggestions: {e}")
    
    return jsonify({'suggestions': suggestions})

@main.route('/api/clear_history', methods=['POST'])
def clear_history():
    """清空搜索历史"""
    try:
        if os.path.exists(SEARCH_HISTORY_FILE):
            os.remove(SEARCH_HISTORY_FILE)
        return jsonify({'success': True})
    except Exception as e:
        current_app.logger.error(f"Error clearing search history: {e}")
        return jsonify({'success': False}), 500

@main.route('/api/remove_history', methods=['POST'])
def remove_history_item():
    """删除单个搜索历史记录"""
    try:
        data = request.get_json()
        query = data.get('query')
        if not query:
            return jsonify({'success': False, 'message': 'Query is required'}), 400
        
        if os.path.exists(SEARCH_HISTORY_FILE):
            with open(SEARCH_HISTORY_FILE, 'r', encoding='utf-8') as f:
                history = json.load(f)
            
            # 移除所有匹配的记录
            history = [q for q in history if q != query]
            
            with open(SEARCH_HISTORY_FILE, 'w', encoding='utf-8') as f:
                json.dump(history, f, ensure_ascii=False)
        
        return jsonify({'success': True})
    except Exception as e:
        current_app.logger.error(f"Error removing history item: {e}")
        return jsonify({'success': False}), 500

@main.route('/', methods=['GET', 'POST'])
def index():
    if request.method == 'POST':
        query = request.form.get('query')
        if query:
            return redirect(url_for('main.search_results', query=query))
    return render_template('index.html')

@main.route('/search')
def search_results():
    query = request.args.get('query', '')
    page = request.args.get('page', 1, type=int)
    sort_by = request.args.get('sort', 'relevance')
    search_type = request.args.get('search_type', 'webpage')
    
    if query:
        log_search_query(query)
    
    results = []
    total_hits = 0
    
    if current_app.elasticsearch:
        try:
            # 根据搜索类型选择不同的查询构建方式
            if search_type == 'document':
                # 使用文档专用搜索
                from app.main.document_search import build_document_search_query
                search_body = build_document_search_query(query)
                # 添加分页
                search_body["from"] = (page - 1) * 10
                # 添加高亮配置
                search_body["highlight"] = {
                    "fields": {
                        "title": {"pre_tags": ["<strong>"], "post_tags": ["</strong>"]},
                        "content": {"pre_tags": ["<strong>"], "post_tags": ["</strong>"], "fragment_size": 200, "number_of_fragments": 1}
                    }
                }
                
                # 添加排序
                if sort_by != 'relevance':
                    search_body["sort"] = [{"crawled_at": {"order": "desc" if sort_by == 'newest' else "asc"}}]
            else:
                # 网页搜索继续使用原来的查询解析逻辑
                # 解析查询字符串
                parsed_query = QueryParser.parse_query(query) if query else {"match_all": {}}
                
                # 构建ES查询
                search_body = {
                    "query": {
                        "bool": {
                            "must": [parsed_query]
                        }
                    },
                    "highlight": {
                        "fields": {
                            "title": {"pre_tags": ["<strong>"], "post_tags": ["</strong>"]},
                            "content": {"pre_tags": ["<strong>"], "post_tags": ["</strong>"], "fragment_size": 200, "number_of_fragments": 1}
                        }
                    },
                    "from": (page - 1) * 10,
                    "size": 10
                }
                
                # 排除文档类型
                doc_extensions = [".pdf", ".doc", ".docx", ".xls", ".xlsx", ".ppt", ".pptx"]
                search_body["query"]["bool"]["must_not"] = [
                    {"bool": {
                        "should": [
                            {"wildcard": {"url": f"*{ext}"}} for ext in doc_extensions
                        ]
                    }}
                ]
            
            # 添加排序选项
            if sort_by == 'date':
                search_body["sort"] = [{"crawled_at": {"order": "desc"}}]
            
            # 执行搜索
            resp = current_app.elasticsearch.search(
                index=current_app.config['INDEX_NAME'],
                body=search_body
            )
            
            # 解析结果
            total_hits = resp['hits']['total']['value']
              # 搜索统计
            search_time = resp.get('took', 0) / 1000  # 毫秒转为秒
            
            # 获取聚合数据和其他统计信息
            search_stats = {
                'time': search_time,
                'total_hits': total_hits,
                'max_score': resp['hits'].get('max_score', 0)
            }
            
            # 处理搜索结果
            results = []
            for hit in resp['hits']['hits']:
                source = hit['_source']
                url = source.get('url', '#')
                
                # 解码URL和提取文件名
                try:
                    decoded_url = urllib.parse.unquote(url)
                    filename = decoded_url.split('/')[-1]
                except:
                    decoded_url = url
                    filename = url.split('/')[-1]
                
                # 准备标题：优先使用高亮的标题，如果没有就使用文件名
                if 'title' in hit.get('highlight', {}):
                    title = ''.join(hit['highlight']['title'])
                else:
                    title = filename
                
                # 准备摘要
                if 'content' in hit.get('highlight', {}):
                    snippet = '...'.join(hit['highlight']['content'])
                else:
                    content = source.get('content', '')
                    snippet = get_smart_snippet(content, query)
                
                results.append({
                    'title': title,
                    'url': decoded_url,
                    'filename': filename,  # 添加文件名字段
                    'snippet': snippet,
                    'score': hit['_score']
                })
                
        except Exception as e:
            current_app.logger.error(f"Elasticsearch query failed: {e}")
            # 可以添加错误提示信息给用户
            pass
            
    # 搜索耗时默认为0
    search_time = locals().get('search_time', 0)
    search_stats = locals().get('search_stats', {'time': search_time, 'total_hits': total_hits, 'max_score': 0})
    # 对搜索结果进行聚类（如果需要的话）
    clusters = []
    if results and len(results) > 5:  # 只有当结果足够多时才进行聚类
        try:
            clusters = cluster_search_results(results)
        except Exception as e:
            current_app.logger.error(f"Error clustering results: {e}")
    
    # 检查是否有拼写建议
    query_suggestion = None
    if query and len(results) < 5 and suggester:  # 结果较少时提供拼写建议
        try:
            query_suggestion = suggester.get_query_suggestion(query)
        except Exception as e:            current_app.logger.error(f"Error generating query suggestion: {e}")
    
    return render_template('search_results.html',
                                  query=query,
                                  results=results,
                                  total_hits=total_hits,
                                  max=max,
                                  min=min,
                          page=page, 
                          sort_by=sort_by,
                          search_time=search_time,
                          search_stats=search_stats,
                          clusters=clusters,
                          query_suggestion=query_suggestion)

@main.route('/search/history')
def search_history():
    """显示搜索历史记录"""
    history = []
    if os.path.exists(SEARCH_HISTORY_FILE):
        try:
            with open(SEARCH_HISTORY_FILE, 'r', encoding='utf-8') as f:
                history = json.load(f)
                
            # 获取最近的50个不重复查询
            unique_history = []
            seen = set()
            for query in reversed(history):
                if query not in seen:
                    seen.add(query)
                    unique_history.append(query)
                    if len(unique_history) >= 50:
                        break
            
            history = unique_history
        except Exception as e:
            current_app.logger.error(f"Error loading search history: {e}")
            
    return render_template('search_history.html', history=history)
