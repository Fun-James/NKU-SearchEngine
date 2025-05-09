from elasticsearch import Elasticsearch

# 连接到Elasticsearch
es = Elasticsearch('http://localhost:9200')

# 测试连接
if es.ping():
    print("成功连接到Elasticsearch！")
    
    # 创建测试索引
    index_settings = {
        "settings": {
            "index": {
                "number_of_shards": 1,
                "number_of_replicas": 0
            }
        },
        "mappings": {
            "properties": {
                "content": {
                    "type": "text",
                    "analyzer": "ik_max_word",
                    "search_analyzer": "ik_smart"
                }
            }
        }
    }
    
    # 创建或重新创建测试索引
    index_name = "test_index"
    if es.indices.exists(index=index_name):
        es.indices.delete(index=index_name)
    es.indices.create(index=index_name, body=index_settings)
    print(f"创建索引 {index_name} 成功！")
    
    # 测试IK分词器
    analyze_body = {
        "analyzer": "ik_max_word",
        "text": "南开大学计算机学院"
    }
    
    result = es.indices.analyze(body=analyze_body)
    print("\nIK分词器测试结果：")
    tokens = [token["token"] for token in result["tokens"]]
    print(f"输入文本：{analyze_body['text']}")
    print(f"分词结果：{', '.join(tokens)}")
    
else:
    print("无法连接到Elasticsearch，请检查服务是否启动。")