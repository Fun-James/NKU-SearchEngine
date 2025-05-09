from elasticsearch import Elasticsearch, helpers
from datetime import datetime
from flask import current_app
import json

def get_es_client():
    """获取 Elasticsearch 客户端实例"""
    if not current_app or not hasattr(current_app, 'elasticsearch'):
        try:
            from config import Config
            es_host = Config.ELASTICSEARCH_HOST
            return Elasticsearch(es_host)
        except ImportError:
            print("Error: Cannot import Config for Elasticsearch outside Flask app context.")
            return None
    return current_app.elasticsearch

def create_index_if_not_exists(es, index_name):
    """如果索引不存在，则创建它"""
    if not es.indices.exists(index=index_name):
        # 使用IK分词器的索引映射
        body = {
            "settings": {
                "index": {
                    "number_of_shards": 1,
                    "number_of_replicas": 0,
                    "max_ngram_diff": 3,
                    "analysis": {
                        "analyzer": {
                            "nku_analyzer": {
                                "type": "custom",
                                "tokenizer": "ik_max_word",
                                "filter": ["lowercase", "trim", "unique"]
                            }
                        }
                    }
                }
            },
            "mappings": {
                "properties": {
                    "url": {"type": "keyword"},
                    "title": {
                        "type": "text",
                        "analyzer": "nku_analyzer",
                        "search_analyzer": "ik_smart",
                        "fields": {
                            "raw": {
                                "type": "keyword"
                            }
                        }
                    },
                    "content": {
                        "type": "text",
                        "analyzer": "nku_analyzer",
                        "search_analyzer": "ik_smart",
                        "term_vector": "with_positions_offsets"
                    },
                    "file_type": {
                        "type": "keyword"
                    },
                    "mime_type": {
                        "type": "keyword"
                    },
                    "is_document": {
                        "type": "boolean"
                    },
                    "anchor_texts": {
                        "type": "nested",
                        "properties": {
                            "text": {
                                "type": "text",
                                "analyzer": "nku_analyzer",
                                "search_analyzer": "ik_smart"
                            },
                            "href": {
                                "type": "keyword"
                            }
                        }
                    },
                    "crawled_at": {
                        "type": "date",
                        "format": "yyyy-MM-dd HH:mm:ss||yyyy-MM-dd||epoch_millis"
                    }
                }
            }
        }
        try:
            es.indices.create(index=index_name, body=body)
            print(f"Index '{index_name}' created successfully.")
        except Exception as e:
            print(f"Failed to create index '{index_name}': {e}")
            return False
    return True

def index_document(es, index_name, doc_id, document_body):
    """将单个文档存入 Elasticsearch"""
    try:
        es.index(index=index_name, id=doc_id, document=document_body)
        print(f"Document {doc_id} indexed successfully.")
    except Exception as e:
        print(f"Failed to index document {doc_id}: {e}")

def bulk_index_documents(es, index_name, documents):
    """批量索引文档"""
    actions = []
    for doc in documents:
        action = {
            "_index": index_name,
            "_id": doc.get('url'),
            "_source": {
                "url": doc.get('url'),
                "title": doc.get('title', ''),
                "content": doc.get('content', ''),
                "anchor_texts": [
                    {
                        "text": a.get('text', ''),
                        "href": a.get('href', '')
                    } for a in doc.get('anchor_texts', []) if a.get('text') and a.get('href')
                ],
                "crawled_at": doc.get('crawled_at')
            }
        }
        actions.append(action)

    if not actions:
        print("No documents to index.")
        return

    try:
        success, failed = helpers.bulk(es, actions, stats_only=True)
        print(f"Bulk indexing completed: {success} succeeded, {len(failed) if failed else 0} failed.")
    except Exception as e:
        print(f"Bulk indexing failed: {e}")
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

# 示例：如何使用这个模块
if __name__ == '__main__':
    try:
        # 连接到Elasticsearch
        es = Elasticsearch('http://localhost:9200')
        
        # 检查连接
        if es.ping():
            print("Connected to Elasticsearch")
            
            # 创建索引
            index_name = "nku_web"
            if create_index_if_not_exists(es, index_name):
                # 测试分词器
                test_text = "南开大学计算机学院"
                tokens = test_analyzer(es, test_text)
                print(f"\nAnalyzer test for '{test_text}':")
                print("Tokens:", tokens)
                
                # 测试数据
                test_doc = {
                    "url": "https://cc.nankai.edu.cn",
                    "title": "南开大学计算机学院",
                    "content": "南开大学计算机学院创建于1978年...",
                    "anchor_texts": [
                        {"text": "学院简介", "href": "/about"}
                    ]
                }
                
                # 索引测试文档
                index_document(es, index_name, test_doc["url"], test_doc)
                print("\nTest document indexed.")
                
        else:
            print("Could not connect to Elasticsearch!")
            
    except Exception as e:
        print(f"Error: {e}")

