from flask import render_template, request, current_app, redirect, url_for, flash, jsonify, session
from . import main
from .query_parser_new import QueryParser  # Changed from query_parser to query_parser_new
from .result_clustering import cluster_search_results, get_smart_snippet
from .intelligent_search_suggestion import IntelligentSearchSuggestion  # 使用新的智能建议系统
from .personalized_ranking import PersonalizedRanking  # 新增：个性化排序
from app.main.search_suggestion import SearchSuggestion
from app.indexer.search_history_indexer import SearchHistoryIndexer

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
history_indexer = None
personalized_ranker = None  # 新增：个性化排序器

def init_search_suggester():
    """初始化搜索建议工具"""
    global suggester, search_suggestion, history_indexer, personalized_ranker
    suggester = IntelligentSearchSuggestion()
    search_suggestion = SearchSuggestion()
    history_indexer = SearchHistoryIndexer()
    personalized_ranker = PersonalizedRanking()  # 新增：初始化个性化排序器
    
    # 确保搜索历史索引存在
    if current_app.elasticsearch:
        history_indexer.ensure_index_exists(current_app.elasticsearch)
    
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
        
    return suggester, search_suggestion, history_indexer

@main.before_app_request
def before_request():
    """在每个请求之前检查搜索建议器是否已初始化"""
    global suggester, personalized_ranker
    if suggester is None or personalized_ranker is None:
        init_search_suggester()

def log_search_query(query, search_type='webpage'):
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
        global suggester, history_indexer
        if suggester:
            suggester.record_search(query)
            
        # 索引到 Elasticsearch 搜索历史
        if history_indexer and current_app.elasticsearch:
            from flask import session
            user_session = session.get('user_id', 'anonymous')
            history_indexer.index_search_query(
                current_app.elasticsearch, 
                query, 
                search_type, 
                user_session
            )
            
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
              # 首先尝试获取 ES Completion Suggester 建议
            try:
                es = current_app.elasticsearch
                if es:
                    es_suggestions = []
                    
                    # 获取搜索历史建议
                    if history_indexer:
                        history_suggestions = history_indexer.get_query_suggestions(es, query, size=3)
                        for hs in history_suggestions:
                            suggestions.append(hs['text'])
                    
                    # 获取标题建议
                    title_suggest = es.search(
                        index=current_app.config['INDEX_NAME'],
                        body={
                            "suggest": {
                                "title_completion": {
                                    "prefix": query,
                                    "completion": {
                                        "field": "title_suggest",
                                        "size": 5,
                                        "skip_duplicates": True
                                    }
                                }
                            }
                        }
                    )
                    title_options = title_suggest.get('suggest', {}).get('title_completion', [])
                    if title_options:
                        for option in title_options[0].get('options', []):
                            es_suggestions.append(option['text'])
                    
                    # 获取内容建议
                    content_suggest = es.search(
                        index=current_app.config['INDEX_NAME'],
                        body={
                            "suggest": {
                                "content_completion": {
                                    "prefix": query,
                                    "completion": {
                                        "field": "content_suggest",
                                        "size": 5,
                                        "skip_duplicates": True
                                    }
                                }
                            }
                        }                    )
                    content_options = content_suggest.get('suggest', {}).get('content_completion', [])
                    if content_options:
                        for option in content_options[0].get('options', []):
                            es_suggestions.append(option['text'])
                    
                    # 将 ES 建议添加到总建议列表
                    suggestions.extend(es_suggestions)
            except Exception as e:
                current_app.logger.error(f"ES completion suggester error: {e}")
            
            if is_pinyin:
                # 如果是拼音输入，优先使用拼音建议
                pinyin_suggestions = search_suggestion.get_pinyin_suggestions(query)
                suggestions.extend(pinyin_suggestions)
            else:
                # 获取普通建议
                autocomplete = suggester.get_autocomplete_suggestions(query, max_suggestions=5)
                suggestions.extend(autocomplete)
                
                # 检查是否需要纠错 - 只有在查询较短且可能有错误时才检查
                if len(query) <= 10:  # 只对较短的查询进行纠错检查
                    potential_correction = search_suggestion.get_query_suggestion(query)
                    # 确保纠正建议确实不同且有意义
                    if potential_correction and potential_correction.lower() != query.lower():
                        correction = potential_correction
            
            # 去重
            seen = set()
            unique_suggestions = []
            for s in suggestions:
                if s and s.strip() and s not in seen:
                    seen.add(s)
                    unique_suggestions.append(s)
            
            response = {
                'suggestions': unique_suggestions[:8],
                'type': 'intelligent'
            }
            
            # 只有在确实有有意义的纠正时才添加
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

@main.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        college = request.form.get('college')
        role = request.form.get('role')
        if college and role:
            session['college'] = college
            session['role'] = role
            return redirect(url_for('main.index'))
        else:
            flash('请填写完整信息！')
    return render_template('login.html')

# 修改index和search_results，未登录时重定向到login
@main.route('/', methods=['GET', 'POST'])
def index():
    if not session.get('college') or not session.get('role'):
        return redirect(url_for('main.login'))
    if request.method == 'POST':
        query = request.form.get('query')
        if query:
            return redirect(url_for('main.search_results', query=query))
    return render_template('index.html')

@main.route('/search')
def search_results():
    if not session.get('college') or not session.get('role'):
        return redirect(url_for('main.login'))
    query = request.args.get('query', '')
    page = request.args.get('page', 1, type=int)
    search_type = request.args.get('search_type', 'webpage')
    if query:
        log_search_query(query, search_type)
    
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
                        'filename': source.get('filename', ''),
                        'snapshot_path': source.get('snapshot_path')  # 添加快照路径
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
                
                # 个性化排序 (新增)
                user_college = session.get('college')
                user_role = session.get('role')
                personalization_stats = {}
                
                if personalized_ranker and user_college and user_role:
                    # 应用个性化排序
                    results = personalized_ranker.rerank_results(results, user_college, user_role)
                    # 获取个性化统计信息
                    personalization_stats = personalized_ranker.get_personalization_stats(results, user_college, user_role)
                    current_app.logger.info(f"Applied personalized ranking for {user_college}-{user_role}, avg score: {personalization_stats.get('avg_personalized_score', 0):.3f}")
                
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
                    personalization_stats=personalization_stats,  # 新增：个性化统计信息
                    user_college=user_college,  # 新增：用户学院
                    user_role=user_role,  # 新增：用户身份
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
        try:            # 使用相关查询作为建议
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
                          personalization_stats=locals().get('personalization_stats', {}),  # 新增：个性化统计信息
                          user_college=session.get('college'),  # 新增：用户学院
                          user_role=session.get('role'),  # 新增：用户身份
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

@main.route('/api/es_suggestions', methods=['GET', 'POST'])
def get_es_suggestions():
    """使用 Elasticsearch Completion Suggester 获取建议"""
    if request.method == 'POST':
        data = request.get_json()
        query = data.get('query', '').strip() if data else ''
        suggestion_type = data.get('type', 'all') if data else 'all'
        size = data.get('size', 8) if data else 8
    else:
        query = request.args.get('query', '').strip()
        suggestion_type = request.args.get('type', 'all')
        size = request.args.get('size', 8, type=int)
    
    if not query or len(query) < 1:
        return jsonify({'suggestions': [], 'type': 'elasticsearch_completion'})
    
    try:
        es = current_app.elasticsearch
        if not es:
            return jsonify({'suggestions': [], 'error': 'Elasticsearch not available'})
        suggestions = []
        
        # 检测是否为拼音输入
        is_pinyin = all(c.isalpha() or c.isspace() for c in query) and any(c.isalpha() for c in query)
        
        # 如果是拼音输入，先获取拼音对应的中文建议
        if is_pinyin and search_suggestion:
            try:
                pinyin_suggestions = search_suggestion.get_pinyin_suggestions(query, max_suggestions=5)
                for chinese_word in pinyin_suggestions:
                    suggestions.append({
                        'text': chinese_word,
                        'score': 1.0,
                        'source': 'pinyin_conversion',
                        'original_pinyin': query
                    })
            except Exception as e:
                current_app.logger.error(f"Pinyin conversion error: {e}")
          # 首先获取搜索历史建议
        if suggestion_type in ['history', 'all'] and history_indexer:
            try:
                history_suggestions = history_indexer.get_query_suggestions(es, query, size=3)
                suggestions.extend(history_suggestions)
            except Exception as e:
                current_app.logger.error(f"Search history suggestion error: {e}")
        
        if suggestion_type in ['title', 'all']:
            # 从文档标题获取建议
            try:
                # 对于拼音输入，同时搜索拼音转换后的中文词汇
                search_queries = [query]
                if is_pinyin and search_suggestion:
                    pinyin_chinese = search_suggestion.get_pinyin_suggestions(query, max_suggestions=3)
                    search_queries.extend(pinyin_chinese)
                
                for search_query in search_queries:
                    title_suggest = es.search(
                        index=current_app.config['INDEX_NAME'],
                        body={
                            "suggest": {
                                "title_completion": {
                                    "prefix": search_query,
                                    "completion": {
                                        "field": "title_suggest",
                                        "size": size,
                                        "skip_duplicates": True
                                    }
                                }
                            }
                        }
                    )
                    title_options = title_suggest.get('suggest', {}).get('title_completion', [])
                    if title_options:
                        for option in title_options[0].get('options', []):
                            suggestions.append({
                                'text': option['text'],
                                'score': option.get('_score', 0),
                                'source': 'title'
                            })
            except Exception as e:
                current_app.logger.error(f"Title suggestion error: {e}")
        
        if suggestion_type in ['content', 'all']:
            # 从文档内容获取建议
            try:
                # 对于拼音输入，同时搜索拼音转换后的中文词汇
                search_queries = [query]
                if is_pinyin and search_suggestion:
                    pinyin_chinese = search_suggestion.get_pinyin_suggestions(query, max_suggestions=3)
                    search_queries.extend(pinyin_chinese)
                
                for search_query in search_queries:
                    content_suggest = es.search(
                        index=current_app.config['INDEX_NAME'],
                        body={
                            "suggest": {
                                "content_completion": {
                                    "prefix": search_query,
                                    "completion": {
                                        "field": "content_suggest",
                                        "size": size,
                                        "skip_duplicates": True
                                    }
                                }
                            }
                        }
                    )
                    content_options = content_suggest.get('suggest', {}).get('content_completion', [])
                    if content_options:
                        for option in content_options[0].get('options', []):
                            suggestions.append({
                                'text': option['text'],
                                'score': option.get('_score', 0),
                                'source': 'content'
                            })
            except Exception as e:
                current_app.logger.error(f"Content suggestion error: {e}")
        
        # 按分数排序并去重
        seen = set()
        unique_suggestions = []
        for suggestion in sorted(suggestions, key=lambda x: x.get('score', 0), reverse=True):
            if suggestion['text'] not in seen:
                seen.add(suggestion['text'])
                unique_suggestions.append(suggestion)
                if len(unique_suggestions) >= size:
                    break
        
        return jsonify({
            'suggestions': unique_suggestions,
            'type': 'elasticsearch_completion',
            'total': len(unique_suggestions)
        })
        
    except Exception as e:
        current_app.logger.error(f"Elasticsearch completion suggestion error: {e}")
        return jsonify({'suggestions': [], 'error': str(e)})

@main.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('main.login'))

@main.route('/api/personalization_info')
def get_personalization_info():
    """API接口：获取当前用户的个性化信息"""
    user_college = session.get('college')
    user_role = session.get('role')
    
    if not user_college or not user_role:
        return jsonify({
            'success': False,
            'message': '用户未登录或信息不完整'
        }), 401
    
    global personalized_ranker
    if not personalized_ranker:
        return jsonify({
            'success': False,
            'message': '个性化排序器未初始化'
        }), 500
    
    # 获取用户相关的关键词
    college_keywords = personalized_ranker.college_keywords.get(user_college, [])
    role_keywords = personalized_ranker.role_keywords.get(user_role, [])
    
    # 获取相关域名权重
    relevant_domains = {}
    for domain, weights in personalized_ranker.domain_weights.items():
        if user_college in weights:
            relevant_domains[domain] = weights[user_college]
    
    return jsonify({
        'success': True,
        'user_info': {
            'college': user_college,
            'role': user_role
        },
        'personalization_config': {
            'college_keywords': college_keywords[:10],  # 只显示前10个
            'role_keywords': role_keywords,
            'relevant_domains': relevant_domains,
            'total_college_keywords': len(college_keywords),
            'total_role_keywords': len(role_keywords)
        }
    })

@main.route('/snapshot/<path:snapshot_id>')
def view_snapshot(snapshot_id):
    """展示网页快照"""
    import os
    from flask import send_from_directory, abort, render_template_string
    
    # 获取快照文件夹路径
    snapshot_folder = current_app.config.get('SNAPSHOT_FOLDER')
    if not snapshot_folder:
        abort(404)
    
    # 确保快照ID是安全的文件名（防止路径遍历攻击）
    if '..' in snapshot_id or '/' in snapshot_id or '\\' in snapshot_id:
        abort(404)
    
    # 构建快照文件路径
    snapshot_file = f"{snapshot_id}.html"
    snapshot_path = os.path.join(snapshot_folder, snapshot_file)
    
    # 检查文件是否存在
    if not os.path.exists(snapshot_path):
        abort(404)
    
    try:
        # 读取快照文件内容
        with open(snapshot_path, 'r', encoding='utf-8') as f:
            snapshot_content = f.read()
        
        # 添加快照页面的头部信息
        snapshot_header = '''
        <div style="background-color: #f0f0f0; padding: 10px; border-bottom: 2px solid #ccc; font-family: Arial, sans-serif;">
            <div style="max-width: 1200px; margin: 0 auto;">
                <h3 style="margin: 0; color: #333;">🔍 网页快照</h3>
                <p style="margin: 5px 0; color: #666;">
                    这是该网页在被爬虫抓取时的备份版本。当前页面可能已经发生变化。
                    <a href="javascript:history.back()" style="color: #1a73e8; text-decoration: none; margin-left: 20px;">
                        ← 返回搜索结果
                    </a>
                </p>
            </div>
        </div>
        '''
        
        # 如果快照内容包含<body>标签，在其后插入头部信息
        if '<body>' in snapshot_content.lower():
            snapshot_content = snapshot_content.replace('<body>', f'<body>{snapshot_header}', 1)
        elif '<html>' in snapshot_content.lower():
            # 如果没有body标签但有html标签，在html标签后插入
            snapshot_content = snapshot_content.replace('<html>', f'<html>{snapshot_header}', 1)
        else:
            # 如果都没有，在内容开头插入
            snapshot_content = snapshot_header + snapshot_content
        
        # 返回快照内容
        from flask import Response
        return Response(snapshot_content, mimetype='text/html')
        
    except Exception as e:
        current_app.logger.error(f"Error reading snapshot file {snapshot_path}: {e}")
        abort(500)
