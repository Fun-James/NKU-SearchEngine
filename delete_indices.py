from elasticsearch import Elasticsearch

# 连接到Elasticsearch
es = Elasticsearch('http://localhost:9200')

# 检查连接
if es.ping():
    print("成功连接到Elasticsearch！")
    
    # 删除索引
    index_name = "nku_web"
    
    if es.indices.exists(index=index_name):
        es.indices.delete(index=index_name)
        print(f"成功删除索引 {index_name}")
    else:
        print(f"索引 {index_name} 不存在")
        
    # 同样删除测试索引
    test_index = "test_index"
    if es.indices.exists(index=test_index):
        es.indices.delete(index=test_index)
        print(f"成功删除索引 {test_index}")
else:
    print("无法连接到Elasticsearch，请检查服务是否启动。")
