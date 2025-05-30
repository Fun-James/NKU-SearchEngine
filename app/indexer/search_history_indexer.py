"""
搜索历史索引管理器
用于将用户搜索历史索引到 Elasticsearch，支持智能建议
"""

import json
from datetime import datetime
from flask import current_app
import jieba


class SearchHistoryIndexer:
    def __init__(self):
        self.index_name = "nku_search_history"
        
    def ensure_index_exists(self, es):
        """确保搜索历史索引存在"""
        try:
            if not es.indices.exists(index=self.index_name):
                mapping = {
                    "mappings": {
                        "properties": {
                            "query": {
                                "type": "text",
                                "analyzer": "ik_smart",
                                "fields": {
                                    "keyword": {
                                        "type": "keyword"
                                    }
                                }
                            },
                            "query_suggest": {
                                "type": "completion",
                                "analyzer": "ik_smart",
                                "search_analyzer": "ik_smart",
                                "preserve_separators": True,
                                "preserve_position_increments": True,
                                "max_input_length": 50
                            },
                            "search_count": {
                                "type": "integer"
                            },
                            "last_searched": {
                                "type": "date"
                            },
                            "user_session": {
                                "type": "keyword"
                            },
                            "search_type": {
                                "type": "keyword"
                            }
                        }
                    },
                    "settings": {
                        "number_of_shards": 1,
                        "number_of_replicas": 0,
                        "analysis": {
                            "analyzer": {
                                "ik_smart": {
                                    "type": "ik_smart"
                                }
                            }
                        }
                    }
                }
                
                es.indices.create(index=self.index_name, body=mapping)
                current_app.logger.info(f"Created search history index: {self.index_name}")
        
        except Exception as e:
            current_app.logger.error(f"Error creating search history index: {e}")
            
    def generate_query_suggestions(self, query):
        """生成查询建议输入"""
        suggestions = []
        
        # 完整查询
        suggestions.append({
            "input": query,
            "weight": 10
        })
        
        # 中文分词
        try:
            tokens = list(jieba.cut(query))
            if len(tokens) > 1:
                # 添加每个词作为建议
                for token in tokens:
                    if len(token.strip()) > 1:  # 只添加长度大于1的词
                        suggestions.append({
                            "input": token.strip(),
                            "weight": 5
                        })
                
                # 添加词组合
                for i in range(len(tokens) - 1):
                    combined = "".join(tokens[i:i+2])
                    if len(combined) > 2:
                        suggestions.append({
                            "input": combined,
                            "weight": 7
                        })
        except Exception as e:
            current_app.logger.warning(f"Error tokenizing query for suggestions: {e}")
        
        return suggestions
    
    def index_search_query(self, es, query, search_type="webpage", user_session=None):
        """索引搜索查询"""
        try:
            if not query or len(query.strip()) < 1:
                return
                
            query = query.strip()
            
            # 检查是否已存在该查询
            search_response = es.search(
                index=self.index_name,
                body={
                    "query": {
                        "term": {
                            "query.keyword": query
                        }
                    }
                }
            )
            
            now = datetime.now()
            
            if search_response['hits']['total']['value'] > 0:
                # 更新现有记录
                doc_id = search_response['hits']['hits'][0]['_id']
                current_count = search_response['hits']['hits'][0]['_source']['search_count']
                
                es.update(
                    index=self.index_name,
                    id=doc_id,
                    body={
                        "doc": {
                            "search_count": current_count + 1,
                            "last_searched": now,
                            "user_session": user_session,
                            "search_type": search_type
                        }
                    }
                )
            else:
                # 创建新记录
                doc = {
                    "query": query,
                    "query_suggest": self.generate_query_suggestions(query),
                    "search_count": 1,
                    "last_searched": now,
                    "user_session": user_session,
                    "search_type": search_type
                }
                
                es.index(
                    index=self.index_name,
                    body=doc
                )
            
            current_app.logger.info(f"Indexed search query: {query}")
            
        except Exception as e:
            current_app.logger.error(f"Error indexing search query: {e}")
    
    def get_query_suggestions(self, es, prefix, size=5):
        """获取查询建议"""
        try:
            response = es.search(
                index=self.index_name,
                body={
                    "suggest": {
                        "query_completion": {
                            "prefix": prefix,
                            "completion": {
                                "field": "query_suggest",
                                "size": size,
                                "skip_duplicates": True
                            }
                        }
                    }
                }
            )
            
            suggestions = []
            options = response.get('suggest', {}).get('query_completion', [])
            if options:
                for option in options[0].get('options', []):
                    suggestions.append({
                        'text': option['text'],
                        'score': option.get('_score', 0),
                        'source': 'search_history'
                    })
            
            return suggestions
            
        except Exception as e:
            current_app.logger.error(f"Error getting query suggestions: {e}")
            return []
    
    def get_popular_queries(self, es, size=10, days=30):
        """获取热门搜索查询"""
        try:
            from datetime import timedelta
            
            since_date = datetime.now() - timedelta(days=days)
            
            response = es.search(
                index=self.index_name,
                body={
                    "query": {
                        "range": {
                            "last_searched": {
                                "gte": since_date
                            }
                        }
                    },
                    "sort": [
                        {"search_count": {"order": "desc"}},
                        {"last_searched": {"order": "desc"}}
                    ],
                    "size": size
                }
            )
            
            queries = []
            for hit in response['hits']['hits']:
                queries.append({
                    'query': hit['_source']['query'],
                    'count': hit['_source']['search_count'],
                    'last_searched': hit['_source']['last_searched']
                })
            
            return queries
            
        except Exception as e:
            current_app.logger.error(f"Error getting popular queries: {e}")
            return []
