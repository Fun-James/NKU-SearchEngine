from elasticsearch import Elasticsearch
import json

# 连接到Elasticsearch
es = Elasticsearch('http://localhost:9200')

# 检查索引状态
if es.ping():
    print("成功连接到Elasticsearch！")
    
    # 步骤1：获取所有索引
    try:
        indices_info = es.cat.indices(format="json")
        index_names = [index['index'] for index in indices_info]
        print(f"\n所有索引: {', '.join(index_names)}")
        
        # 步骤2：检查特定索引
        index_name = "nku_web"
        if index_name in index_names:
            # 获取索引信息
            index_stats = es.cat.indices(index=index_name, format="json")[0]
            print(f"\n索引 {index_name} 统计信息:")
            print(f"文档总数: {index_stats.get('docs.count', '0')}")
            print(f"索引大小: {index_stats.get('store.size', '0')}")
            
            # 步骤3：获取示例文档
            print("\n尝试获取前3个文档...")
            try:
                query = {"match_all": {}}
                result = es.search(
                    index=index_name,
                    body={"query": query, "size": 3}
                )
                
                # 检查是否有hits
                hits = result.get('hits', {}).get('hits', [])
                if hits:
                    print(f"找到 {len(hits)} 个文档:")
                    for hit in hits:
                        doc = hit['_source']
                        print(f"标题: {doc.get('title', '无标题')}")
                        print(f"URL: {doc.get('url', '无URL')}")
                        content = doc.get('content', '无内容')
                        content_preview = f"{content[:100]}..." if len(content) > 100 else content
                        print(f"内容预览: {content_preview}")
                        print("-" * 50)
                else:
                    print("索引中没有文档！")
            except Exception as e:
                print(f"获取文档时出错: {str(e)}")
        else:
            print(f"索引 {index_name} 不存在!")
    except Exception as e:
        print(f"查询ES时出错: {str(e)}")
else:
    print("无法连接到Elasticsearch，请检查服务是否启动。")
