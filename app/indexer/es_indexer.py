from elasticsearch import Elasticsearch, helpers
from datetime import datetime
from flask import current_app
import json
import re
import jieba
import jieba.analyse

def get_es_client():
    """获取 Elasticsearch 客户端实例，配置超时参数"""
    if not current_app or not hasattr(current_app, 'elasticsearch'):
        try:
            from config import Config
            es_host = Config.ELASTICSEARCH_HOST
            # 创建带超时配置的ES客户端
            return Elasticsearch(
                es_host,
                timeout=60,  # 60秒连接超时
                max_retries=3,  # 最大重试次数
                retry_on_timeout=True,  # 超时时重试
                http_compress=True,  # 启用HTTP压缩
                request_timeout=300  # 5分钟请求超时
            )
        except ImportError:
            print("Error: Cannot import Config for Elasticsearch outside Flask app context.")
            return None
    return current_app.elasticsearch

def create_index_if_not_exists(es, index_name):
    """如果索引不存在，则创建索引"""
    try:
        if not es.indices.exists(index=index_name):
            # 定义索引的设置，包括自定义分析器
            settings = {
                "analysis": {
                    "analyzer": {
                        "nku_analyzer": {
                            "type": "custom",
                            "tokenizer": "ik_max_word",
                            "filter": [
                                "lowercase",
                                "trim",
                                "nku_shingle_filter",  # 添加 shingle 过滤器
                                "unique"
                            ]
                        }
                    },
                    "filter": {
                        "nku_shingle_filter": {    # 定义 shingle 过滤器
                            "type": "shingle",
                            "min_shingle_size": 2,
                            "max_shingle_size": 2,
                            "output_unigrams": True
                        }
                    }
                }
            }
              # 定义索引的映射
            mappings = {
                "properties": {
                    "url": {"type": "keyword"},
                    "title": {"type": "text", "analyzer": "nku_analyzer", "search_analyzer": "ik_smart"},
                    "content": {"type": "text", "analyzer": "nku_analyzer", "search_analyzer": "ik_smart"},
                    "anchor_text": {"type": "text", "analyzer": "nku_analyzer", "search_analyzer": "ik_smart"},
                    "pagerank": {"type": "rank_feature"},
                    "last_modified": {"type": "date"},
                    "file_type": {"type": "keyword"},  # 新增字段，用于存储文件类型
                    "mime_type": {"type": "keyword"},  # 新增字段，用于存储MIME类型
                    "is_document": {"type": "boolean"}, # 新增字段，标记是否为文档
                    
                    # Completion Suggester 字段
                    "title_suggest": {
                        "type": "completion",
                        "analyzer": "ik_smart",
                        "preserve_separators": True,
                        "preserve_position_increments": True,
                        "max_input_length": 50
                    },
                    "content_suggest": {
                        "type": "completion", 
                        "analyzer": "ik_smart",
                        "preserve_separators": True,
                        "preserve_position_increments": True,
                        "max_input_length": 50
                    }
                }
            }
            
            es.indices.create(index=index_name, settings=settings, mappings=mappings)
            print(f"索引 \'{index_name}\' 创建成功，并应用了自定义分析器和映射。")
            return True
        else:
            # print(f"索引 \'{index_name}\' 已存在。")
            return True
    except Exception as e:
        print(f"创建或检查索引 \'{index_name}\' 失败: {e}")
        return False

def index_document(es, index_name, doc_id, document_body):
    """将单个文档存入 Elasticsearch"""
    try:
        es.index(index=index_name, id=doc_id, document=document_body)
        print(f"Document {doc_id} indexed successfully.")
    except Exception as e:
        print(f"Failed to index document {doc_id}: {e}")

def bulk_index_documents(es, index_name, documents, max_retries=3):
    """批量索引文档，带重试机制"""
    import time
    
    actions = []
    for doc in documents:
        # 获取标题，并进行处理
        title = doc.get('title', '')        # 如果标题为空或太短，尝试从URL中提取一个有意义的标题
        if not title or len(title.strip()) < 3:
            url = doc.get('url', '')
            try:
                import re  # 确保在此作用域中可以使用 re 模块
                from urllib.parse import unquote, urlparse
                
                # 解析URL
                parsed_url = urlparse(url)
                path = parsed_url.path
                
                # 尝试从路径中提取有意义的部分作为标题
                if path and len(path) > 1:
                    path_parts = path.split('/')
                    # 获取最后一个非空的部分
                    for part in reversed(path_parts):
                        if part.strip():
                            # 移除扩展名和特殊字符
                            title_candidate = re.sub(r'\.(html?|php|asp|aspx|jsp)$', '', part)
                            title_candidate = re.sub(r'[_\-]', ' ', title_candidate)
                            if title_candidate and len(title_candidate) > 3:
                                title = title_candidate
                                break
                    
                # 如果仍然没有合适的标题，使用域名作为标题
                if not title or len(title.strip()) < 3:
                    title = f"来自 {parsed_url.netloc} 的网页"
            except Exception as e:
                print(f"从URL提取标题时出错: {e}")
                if url:
                    # 如果所有提取失败，至少提供URL域名作为标题
                    title = url.split('/')[2] if len(url.split('/')) > 2 else url
        
        # 检查是否是附件，并设置文件类型
        is_attachment = doc.get('is_attachment', False)
        file_info = doc.get('file_info', {})
        file_type = file_info.get('file_type', '未知文档')
        mime_type = file_info.get('mime_type', 'text/html')
          # 检查标题中是否已经包含文件类型标记，如果已经包含则不再添加
        if is_attachment and file_type and '[' not in title:
            # 南开大学特殊处理 - 检查是否是特定文件
            if '附件1-2025年度天津市教育工作重点调研课题指南' in title:
                title = '附件1-2025年度天津市教育工作重点调研课题指南'
                file_type = 'Word文档'
            elif '附件2-天津市教育工作重点调研课题申报表' in title:
                title = '附件2-天津市教育工作重点调研课题申报表'
                file_type = 'Word文档'
            elif '附件3-2025年度天津市教育工作重点调研课题申报汇总表' in title:
                title = '附件3-2025年度天津市教育工作重点调研课题申报汇总表'
                file_type = 'Excel表格'
          # 如果标题中已包含文件类型标记，从中提取正确的文件类型
        if '[' in title and ']' in title:
            try:
                import re  # 确保在此作用域中可以使用 re 模块
                type_match = re.search(r'\[(.*?)\]', title)
                if type_match:
                    extracted_type = type_match.group(1)
                    if extracted_type in ['PDF文档', 'Word文档', 'Excel表格', 'PowerPoint演示文稿']:
                        # 使用标题中的文件类型
                        file_type = extracted_type
                        # 可选：移除标题中的文件类型标记，避免重复显示
                        # title = re.sub(r'\s*\[.*?\]', '', title)
            except Exception as re_error:
                print(f"处理标题中的文件类型标记时出错: {re_error}")
                # 继续执行，不影响整个索引过程
          # 生成 Completion Suggester 所需的建议输入
        title_suggestions = generate_suggest_input(title, None)
        content_suggestions = generate_suggest_input(None, doc.get('content', ''))
        
        action = {
            "_index": index_name,
            "_id": doc.get('url'),
            "_source": {
                "url": doc.get('url'),
                "title": title,
                "content": doc.get('content', ''),
                "is_attachment": is_attachment,
                "file_type": file_type,
                "mime_type": mime_type,
                "anchor_texts": [
                    {
                        "text": a.get('text', ''),
                        "href": a.get('href', '')
                    } for a in doc.get('anchor_texts', []) if a.get('text') and a.get('href')
                ],
                "crawled_at": doc.get('crawled_at'),
                "title_suggest": {
                    "input": title_suggestions,
                    "weight": 10  # 标题权重较高
                },
                "content_suggest": {
                    "input": content_suggestions,
                    "weight": 5   # 内容权重较低
                }
            }        }
        actions.append(action)

    if not actions:
        print("No documents to index.")
        return    # 根据文档数量动态调整批处理参数
    doc_count = len(actions)
    if doc_count <= 10:
        chunk_size = doc_count
        max_chunk_bytes = 3 * 1024 * 1024  # 3MB
    elif doc_count <= 30:
        chunk_size = 15
        max_chunk_bytes = 5 * 1024 * 1024  # 5MB
    else:
        chunk_size = 25
        max_chunk_bytes = 8 * 1024 * 1024  # 8MB

    print(f"📊 准备索引 {doc_count} 个文档，使用批处理大小: {chunk_size}")

    # 重试机制
    for attempt in range(max_retries):
        try:
            # 检查ES服务器状态
            if not es.ping():
                raise Exception("ES服务器不可用")
                  # 设置优化的超时时间和参数
            success, failed = helpers.bulk(
                es, 
                actions, 
                stats_only=True,
                timeout='10m',  # 10分钟超时
                request_timeout=600,  # 10分钟请求超时
                chunk_size=chunk_size,  # 动态调整的块大小
                max_chunk_bytes=max_chunk_bytes,  # 动态调整的最大块字节数
                refresh=False  # 不立即刷新，提高性能
            )
            
            # 成功后手动刷新索引
            es.indices.refresh(index=index_name)
            
            print(f"✅ 批量索引完成: {success} 成功, {len(failed) if failed else 0} 失败")
            
            # 清理内存
            del actions
            import gc
            gc.collect()
            
            return  # 成功后退出
            
        except Exception as e:
            print(f"❌ 批量索引尝试 {attempt + 1}/{max_retries} 失败: {e}")
            if attempt < max_retries - 1:
                wait_time = (attempt + 1) * 15  # 递增等待时间：15s, 30s, 45s
                print(f"⏳ 等待 {wait_time} 秒后重试...")
                time.sleep(wait_time)
                
                # 减小批处理大小进行重试
                chunk_size = max(5, chunk_size // 2)
                max_chunk_bytes = max_chunk_bytes // 2
                print(f"🔻 调整批处理参数 - 块大小: {chunk_size}, 最大字节数: {max_chunk_bytes // 1024 // 1024}MB")
            else:
                print("💥 所有重试尝试都失败了")
                # 清理内存
                del actions
                import gc
                gc.collect()
                raise

def test_analyzer(es, text):
    """测试IK分词器的分词效果"""
    try:
        result = es.indices.analyze(
            body={
                "analyzer": "ik_max_word",
                "text": text
            }
        )
        return [token["token"] for token in result["tokens"]]
    except Exception as e:
        print(f"Analyzer test failed: {e}")
        return []

def generate_suggest_input(title, content):
    """生成用于 completion suggester 的输入数据"""
    suggestions = []
    
    # 从标题生成建议
    if title and len(title.strip()) > 0:
        # 完整标题
        title_clean = title.strip()
        if len(title_clean) >= 2:
            suggestions.append(title_clean)
        
        # 分词后的重要词汇
        try:
            title_words = list(jieba.cut(title_clean))
            for word in title_words:
                word_clean = word.strip()
                if len(word_clean) >= 2 and word_clean not in ['的', '和', '与', '或', '在', '是', '有', '了', '都']:
                    suggestions.append(word_clean)
        except:
            pass
    
    # 从内容中提取关键词
    if content and len(content.strip()) > 0:
        try:
            # 提取关键词，限制数量避免过多
            keywords = jieba.analyse.extract_tags(content, topK=5, withWeight=False)
            for keyword in keywords:
                keyword_clean = keyword.strip()
                if len(keyword_clean) >= 2:
                    suggestions.append(keyword_clean)
        except:
            pass
    
    # 去重并过滤，限制长度
    unique_suggestions = []
    seen = set()
    for s in suggestions:
        s_clean = s.strip()
        if (len(s_clean) >= 2 and len(s_clean) <= 50 and 
            s_clean not in seen and 
            not s_clean.isdigit()):  # 排除纯数字
            seen.add(s_clean)
            unique_suggestions.append(s_clean)
    
    return unique_suggestions[:10]  # 限制每个文档最多10个建议
