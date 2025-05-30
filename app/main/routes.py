from flask import render_template, request, current_app, redirect, url_for, flash, jsonify
from . import main
from .query_parser_new import QueryParser  # Changed from query_parser to query_parser_new
from .result_clustering import cluster_search_results, get_smart_snippet
from .intelligent_search_suggestion import IntelligentSearchSuggestion  # 使用新的智能建议系统
from app.main.search_suggestion import SearchSuggestion

import json
import os
import re
import time
from collections import Counter
import urllib.parse

# 搜索历史记录文件
SEARCH_HISTORY_FILE = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'data', 'search_history.json')

# 初始化搜索建议工具
suggester = None
search_suggestion = None

def init_search_suggester():
    """初始化搜索建议工具"""
    global suggester, search_suggestion
    suggester = IntelligentSearchSuggestion()
    search_suggestion = SearchSuggestion()
    
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
        search_suggestion.load_search_history(history)
        
    return suggester, search_suggestion

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
                if not isinstance(history, list):
                    history = []
        except Exception as e:
            current_app.logger.error(f"Error reading search history: {e}")
            history = []
    
    # 添加新查询并保存（限制大小为最近1000条）
    if query not in history:  # 避免重复添加相同的查询
        history.append(query)
    history = history[-1000:]
    
    try:
        with open(SEARCH_HISTORY_FILE, 'w', encoding='utf-8') as f:
            json.dump(history, f, ensure_ascii=False)
        
        # 同时更新智能搜索建议器
        global suggester
        if suggester:
            suggester.record_search(query)
    except Exception as e:
        current_app.logger.error(f"Error saving search history: {e}")

@main.route('/api/suggestions')
def get_suggestions():
    """API接口：根据用户输入获取智能搜索建议"""
    query = request.args.get('query', '').strip()
    suggestion_type = request.args.get('type', 'all')
    show_history = request.args.get('history', 'false').lower() == 'true'
    simple = request.args.get('simple', 'false').lower() == 'true'
    is_pinyin = request.args.get('pinyin', 'false').lower() == 'true'
    
    global suggester, search_suggestion
    
    # 只保留历史和基础建议
    if show_history:
        history = []
        if os.path.exists(SEARCH_HISTORY_FILE):
            try:
                with open(SEARCH_HISTORY_FILE, 'r', encoding='utf-8') as f:
                    history = json.load(f)
                    if not isinstance(history, list):
                        history = []
                seen = set()
                unique_history = []
                for item in reversed(history):
                    if item not in seen:
                        seen.add(item)
                        unique_history.append(item)
                        if len(unique_history) >= 20:
                            break
                return jsonify({'suggestions': unique_history, 'type': 'history'})
            except Exception as e:
                return jsonify({'suggestions': [], 'type': 'history'})
    
    # 智能搜索建议和纠错
    if suggester and search_suggestion and query and len(query) >= 1:
        try:
            # 获取各种建议
            suggestions = []
            correction = None
            
            if is_pinyin:
                # 如果是拼音输入，优先使用拼音建议
                pinyin_suggestions = search_suggestion.get_pinyin_suggestions(query)
                suggestions.extend(pinyin_suggestions)
            else:
                # 获取普通建议
                autocomplete = suggester.get_autocomplete_suggestions(query, max_suggestions=5)
                suggestions.extend(autocomplete)
                
                # 检查是否需要纠错
                correction = search_suggestion.get_query_suggestion(query)
            
            # 去重
            seen = set()
            unique_suggestions = []
            for s in suggestions:
                if s not in seen:
                    seen.add(s)
                    unique_suggestions.append(s)
            
            response = {
                'suggestions': unique_suggestions[:8],
                'type': 'intelligent'
            }
            
            if correction:
                response['correction'] = correction
            
            return jsonify(response)
        except Exception as e:
            current_app.logger.error(f"Error generating suggestions: {e}")
            return jsonify({'suggestions': [], 'type': 'simple'})
    
    # 回退到基础建议逻辑
    suggestions = []
    if os.path.exists(SEARCH_HISTORY_FILE):
        try:
            with open(SEARCH_HISTORY_FILE, 'r', encoding='utf-8') as f:
                history = json.load(f)
                if not isinstance(history, list):
                    history = []
            matching_queries = [q for q in history if q and query.lower() in q.lower()]
            counter = Counter(matching_queries)
            suggestions = [item[0] for item in counter.most_common(8)]
        except Exception as e:
            suggestions = []
    return jsonify({'suggestions': suggestions, 'type': 'basic'})

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

@main.route('/api/hot_searches')
def get_hot_searches():
    """获取热门搜索"""
    try:
        limit = request.args.get('limit', 10, type=int)
        time_window = request.args.get('hours', 24, type=int)
        
        if suggester:
            hot_searches = suggester.get_hot_searches(max_results=limit, time_window_hours=time_window)
            return jsonify({
                'success': True,
                'hot_searches': hot_searches
            })
        else:
            return jsonify({
                'success': False,
                'hot_searches': [],
                'message': 'Search suggester not initialized'
            })
    except Exception as e:
        current_app.logger.error(f"Error getting hot searches: {e}")
        return jsonify({
            'success': False,
            'hot_searches': [],
            'message': str(e)
        }), 500

@main.route('/api/remove_history', methods=['POST'])
def remove_history_item():
    """删除单个搜索历史记录"""
    try:
        data = request.get_json()
        query = data.get('query')
        if not query:
            return jsonify({'success': False, 'message': 'Query is required'}), 400
        
        if os.path.exists(SEARCH_HISTORY_FILE):
            try:
                with open(SEARCH_HISTORY_FILE, 'r', encoding='utf-8') as f:
                    history = json.load(f)
                    if not isinstance(history, list):
                        history = []
                  # 移除所有匹配的记录
                history = [q for q in history if q != query]
                
                with open(SEARCH_HISTORY_FILE, 'w', encoding='utf-8') as f:
                    json.dump(history, f, ensure_ascii=False)
            except Exception as e:
                current_app.logger.error(f"Error processing history file during removal: {e}")
                return jsonify({'success': False, 'message': 'Error processing history'}), 500
        
        return jsonify({'success': True})
    except Exception as e:
        current_app.logger.error(f"Error removing history item: {e}")
        return jsonify({'success': False}), 500

@main.route('/api/content_suggestions')
def get_content_suggestions():
    """API接口：获取基于内容的智能搜索建议"""
    query = request.args.get('query', '').strip()
    suggestion_type = request.args.get('type', 'all')  # all, semantic, domain, contextual, trending
    max_suggestions = request.args.get('max', 10, type=int)
    
    if not query:
        return jsonify({
            'success': False,
            'message': 'Query parameter is required',
            'suggestions': []
        }), 400
    
    global suggester
    if not suggester:
        return jsonify({
            'success': False,
            'message': 'Search suggester not initialized',
            'suggestions': []
        }), 500
    
    try:
        # 更新搜索上下文
        suggester.update_search_context(query)
        
        if suggestion_type == 'semantic':
            # 语义相关建议
            suggestions = suggester._get_semantic_suggestions(query, max_suggestions)
            return jsonify({
                'success': True,
                'type': 'semantic',
                'suggestions': suggestions,
                'description': '基于语义相似度的搜索建议'
            })
        elif suggestion_type == 'domain':
            # 领域知识建议
            suggestions = suggester._get_domain_suggestions(query, max_suggestions)
            return jsonify({
                'success': True,
                'type': 'domain',
                'suggestions': suggestions,
                'description': '基于领域知识图谱的搜索建议'
            })
        elif suggestion_type == 'contextual':
            # 上下文相关建议
            suggestions = suggester._get_contextual_suggestions(query, max_suggestions)
            return jsonify({
                'success': True,
                'type': 'contextual',
                'suggestions': suggestions,
                'description': '基于搜索上下文的个性化建议'
            })
        elif suggestion_type == 'trending':
            # 趋势相关建议
            suggestions = suggester._get_trending_suggestions(query, max_suggestions)
            return jsonify({
                'success': True,
                'type': 'trending',
                'suggestions': suggestions,
                'description': '基于当前热门趋势的搜索建议'
            })
        else:
            # 综合内容建议
            all_suggestions = suggester.get_content_suggestions(query, max_suggestions)
            return jsonify({
                'success': True,
                'type': 'comprehensive',
                'suggestions': all_suggestions,
                'description': '综合内容关联搜索建议'
            })
            
    except Exception as e:
        current_app.logger.error(f"Error getting content suggestions: {e}")
        return jsonify({
            'success': False,
            'message': f'Error generating suggestions: {str(e)}',
            'suggestions': []
        }), 500

@main.route('/api/semantic_relations')
def get_semantic_relations():
    """API接口：获取查询词的语义关联关系"""
    query = request.args.get('query', '').strip()
    
    if not query:
        return jsonify({
            'success': False,
            'message': 'Query parameter is required',
            'relations': {}
        }), 400
    
    global suggester
    if not suggester:
                return jsonify({
            'success': False,
            'message': 'Search suggester not initialized',
            'relations': {}
        }), 500
    
    try:
        # 获取语义关键词
        keywords_with_weights = suggester.extract_semantic_keywords(query)
        keywords = [word for word, weight in keywords_with_weights]
        
        # 获取相关的语义关系
        relations = {}
        for keyword in keywords:
            if keyword in suggester.semantic_relations:
                relations[keyword] = list(suggester.semantic_relations[keyword].keys())[:5]
        
        # 获取领域知识关联
        domain_relations = {}
        for keyword in keywords:
            if keyword in suggester.domain_knowledge:
                domain_relations[keyword] = suggester.domain_knowledge[keyword][:5]
        
        return jsonify({
            'success': True,
            'query': query,
            'keywords': keywords,
            'semantic_relations': relations,
            'domain_relations': domain_relations,
            'total_relations': len(suggester.semantic_relations)
        })
        
    except Exception as e:
        current_app.logger.error(f"Error getting semantic relations: {e}")
        return jsonify({
            'success': False,
            'message': f'Error getting relations: {str(e)}',
            'relations': {}
        }), 500

@main.route('/api/build_content_index', methods=['POST'])
def build_content_index():
    """API接口：构建内容索引以支持语义关联"""
    try:
        data = request.get_json()
        documents = data.get('documents', [])
        
        if not documents:
            return jsonify({
                'success': False,
                'message': 'No documents provided'
            }), 400
        
        global suggester
        if not suggester:
            return jsonify({
                'success': False,
                'message': 'Search suggester not initialized'
            }), 500
        
        # 构建语义关系
        suggester.build_semantic_relations(documents)
        
        return jsonify({
            'success': True,
            'message': f'Successfully built content index from {len(documents)} documents',
            'relations_count': len(suggester.semantic_relations)
        })
        
    except Exception as e:
        current_app.logger.error(f"Error building content index: {e}")
        return jsonify({
            'success': False,
            'message': f'Error building index: {str(e)}'
        }), 500

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
            else:                # 网页搜索继续使用原来的查询解析逻辑
                # 解析查询字符串
                parsed_query = QueryParser.parse_query(query) if query else {"match_all": {}}

                # 修改：如果parsed_query是bool/must结构，直接用must，否则包装成must，实现所有term都必须命中
                if isinstance(parsed_query, dict) and "bool" in parsed_query and "must" in parsed_query["bool"]:
                    must_clauses = parsed_query["bool"]["must"]
                else:
                    must_clauses = [parsed_query]

                search_body = {
                    "query": {
                        "bool": {
                            "must": must_clauses
                        }
                    },
                    "highlight": {
                        "fields": {
                            "title": {"pre_tags": ["<strong>"], "post_tags": ["</strong>"]},
                            "content": {
                                "pre_tags": ["<strong>"], 
                                "post_tags": ["</strong>"], 
                                "fragment_size": 300,  # 可适当调大
                                "number_of_fragments": 1
                            }
                        },
                        "require_field_match": False  # 新增：允许所有命中词高亮
                    },
                    "from": (page - 1) * 10,
                    "size": 10
                }

                # 网页搜索模式下严格排除所有文档类型
                doc_extensions = [".pdf", ".doc", ".docx", ".xls", ".xlsx", ".ppt", ".pptx"]
                must_not_clauses = [
                    # 排除URL包含文件扩展名的结果
                    {"bool": {
                        "should": [
                            {"wildcard": {"url": f"*{ext}"}} for ext in doc_extensions
                        ]
                    }},
                    # 排除已标记为文档的结果
                    {"term": {"is_document": True}},
                    # 排除URL中含有常见文档下载参数的结果
                    {"wildcard": {"url": "*download*"}},
                    {"wildcard": {"url": "*attachment*"}},
                    {"wildcard": {"url": "*file=*"}}
                ]
                search_body["query"]["bool"]["must_not"] = must_not_clauses
            
            # 执行搜索
            resp = current_app.elasticsearch.search(
                index=current_app.config['INDEX_NAME'],
                body=search_body
            )
            
            # 解析搜索结果
            if resp['hits']['total']['value'] > 0:
                search_time = resp.get('took', 0) / 1000.0  # 转换为秒
                
                # 获取结果集
                hit_list = resp['hits']['hits']
                processed_results = []
                
                for hit in hit_list:
                    source = hit['_source']
                    result = {
                        'url': source['url'],
                        'title': source.get('title', ''),
                        'snippet': '',
                        'score': hit['_score'],
                        'is_attachment': source.get('is_attachment', False),
                        'file_type': source.get('file_type', '') if source.get('is_attachment', False) else '',
                        'mime_type': source.get('mime_type', 'text/html'),
                        'filename': source.get('filename', '')
                    }
                    
                    # 处理标题高亮
                    if 'highlight' in hit and 'title' in hit['highlight']:
                        result['title'] = hit['highlight']['title'][0]
                        
                    # 处理内容高亮/摘要
                    if 'highlight' in hit and 'content' in hit['highlight']:
                        result['snippet'] = hit['highlight']['content'][0]
                    else:
                        # 如果没有高亮内容，则从原始内容中提取一小段
                        content = source.get('content', '')
                        if content:
                            # 显示内容的前200个字符
                            result['snippet'] = content[:200] + "..."
                    
                    # 特殊处理文档类型
                    if search_type == 'document' or result['is_attachment']:
                        # 如果URL结尾是常见的文档扩展名，则显示文件类型
                        file_ext_match = re.search(r'\.(pdf|doc|docx|xls|xlsx|ppt|pptx)$', source['url'], re.IGNORECASE)
                        if file_ext_match:
                            ext = file_ext_match.group(1).lower()
                            if not result.get('file_type'):
                                if ext in ['pdf']:
                                    result['file_type'] = 'PDF文档'
                                elif ext in ['doc', 'docx']:
                                    result['file_type'] = 'Word文档'
                                elif ext in ['xls', 'xlsx']:
                                    result['file_type'] = 'Excel表格'
                                elif ext in ['ppt', 'pptx']:
                                    result['file_type'] = 'PowerPoint演示文稿'
                        
                        # 提取文件名                        
                        if not result.get('filename'):
                            filename = os.path.basename(urllib.parse.unquote(source['url']))
                            result['filename'] = filename
                        
                        # 特殊处理"feb482194347a6fa415f145d8178"之类的附件
                        if 'feb482194347a6fa415f145d8178' in source['url']:
                            if 'docx' in source['url']:
                                # 检查标题中是否已经包含文件类型标记
                                if '[PDF文档]' not in result['title'] and '[Word文档]' not in result['title']:
                                    result['title'] = '附件1-2025年度天津市教育工作重点调研课题指南'
                                result['file_type'] = 'Word文档'
                                result['filename'] = '附件1-2025年度天津市教育工作重点调研课题指南.docx'
                            elif '.doc' in source['url']:
                                if '[PDF文档]' not in result['title'] and '[Word文档]' not in result['title']:
                                    result['title'] = '附件2-天津市教育工作重点调研课题申报表'
                                result['file_type'] = 'Word文档'
                                result['filename'] = '附件2-天津市教育工作重点调研课题申报表.doc'
                            elif '.xls' in source['url']:
                                if '[PDF文档]' not in result['title'] and '[Excel表格]' not in result['title']:
                                    result['title'] = '附件3-2025年度天津市教育工作重点调研课题申报汇总表'
                                result['file_type'] = 'Excel表格'
                                result['filename'] = '附件3-2025年度天津市教育工作重点调研课题申报汇总表.xls'
                                
                        # 移除标题中可能已存在的文件类型标记，避免重复
                        if '[PDF文档]' in result['title'] or '[Word文档]' in result['title'] or '[Excel表格]' in result['title'] or '[PowerPoint演示文稿]' in result['title']:
                            # 标题中已经包含文件类型标记，不再重复添加
                            # 从文件类型中提取实际的文件类型
                            file_type_match = re.search(r'\[(.*?)\]', result['title'])
                            if file_type_match:
                                extracted_type = file_type_match.group(1)
                                # 使用提取的类型更新文件类型
                                result['file_type'] = extracted_type
                    
                    processed_results.append(result)
                
                # 将搜索结果传递给模板
                results = processed_results
                total_hits = resp['hits']['total']['value']
                search_stats = {
                    'max_score': resp['hits']['max_score'] or 0
                }
                
                # 增加智能摘要生成
                if len(processed_results) > 3:
                    # 聚类搜索结果
                    clusters = cluster_search_results(processed_results)
                else:
                    clusters = None
                
                # 分析是否提供搜索建议
                if int(total_hits) == 0 and total_hits < 5 and len(query) > 2:
                    # 尝试生成查询建议
                    if suggester:
                        query_suggestion = suggester.get_suggestion(query)
                    else:
                        query_suggestion = None
                else:
                    query_suggestion = None
                
                return render_template('search_results.html', 
                    query=query, 
                    results=results, 
                    total_hits=total_hits, 
                    search_time=search_time, 
                    search_stats=search_stats,
                    clusters=clusters,
                    page=page,
                    search_type=search_type,
                    query_suggestion=query_suggestion,
                    max=max,
                    min=min)
            else:
                total_hits = 0
            
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
            # 使用相关查询作为建议
            related_queries = suggester.get_related_queries(query, max_suggestions=3)
            if related_queries:
                query_suggestion = related_queries[0]  # 使用第一个相关查询作为建议
        except Exception as e:
            current_app.logger.error(f"Error generating query suggestion: {e}")
    
    return render_template('search_results.html',
                          query=query,
                          results=results,
                          total_hits=total_hits,
                          page=page,
                          search_type=search_type,
                          search_time=search_time,
                          search_stats=search_stats,
                          clusters=clusters,
                          query_suggestion=query_suggestion,
                          max=max,
                          min=min)

@main.route('/search/history')
def search_history():
    """显示搜索历史记录"""
    history = []
    if os.path.exists(SEARCH_HISTORY_FILE):
        try:
            with open(SEARCH_HISTORY_FILE, 'r', encoding='utf-8') as f:
                history = json.load(f)
                if not isinstance(history, list):
                    current_app.logger.error("Search history is not a list")
                    history = []
                
            # 获取最近的50个不重复查询
            unique_history = []
            seen = set()
            for query in reversed(history):
                if query and query not in seen:  # 确保查询不为空
                    seen.add(query)
                    unique_history.append(query)
                    if len(unique_history) >= 50:
                        break
            
            history = unique_history
        except Exception as e:
            current_app.logger.error(f"Error loading search history: {e}")
            
    return render_template('search_history.html', history=history)
