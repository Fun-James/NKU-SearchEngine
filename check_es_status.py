#!/usr/bin/env python3
"""
检查 Elasticsearch 服务状态和索引信息
"""

from elasticsearch import Elasticsearch
import sys
import time

def check_es_status():
    """检查ES服务状态"""
    try:
        es = Elasticsearch(
            ['http://localhost:9200'],
            request_timeout=10,
            max_retries=1,
            retry_on_timeout=False
        )
        
        # 检查服务是否可用
        if not es.ping():
            print("❌ Elasticsearch 服务不可用")
            return False
            
        print("✅ Elasticsearch 服务正常")
        
        # 获取集群健康状态
        health = es.cluster.health()
        print(f"📊 集群状态: {health['status']}")
        print(f"📊 节点数: {health['number_of_nodes']}")
        print(f"📊 数据节点数: {health['number_of_data_nodes']}")
        
        # 检查索引信息
        try:
            indices = es.indices.get_alias(index="*")
            print(f"\n📂 现有索引:")
            for index_name in indices.keys():
                if not index_name.startswith('.'):  # 忽略系统索引
                    try:
                        stats = es.indices.stats(index=index_name)
                        doc_count = stats['indices'][index_name]['total']['docs']['count']
                        size_mb = stats['indices'][index_name]['total']['store']['size_in_bytes'] / 1024 / 1024
                        print(f"  • {index_name}: {doc_count} 文档, {size_mb:.2f} MB")
                    except:
                        print(f"  • {index_name}: 无法获取统计信息")
        except Exception as e:
            print(f"⚠️ 获取索引信息失败: {e}")
        
        # 检查内存使用情况
        try:
            nodes_stats = es.nodes.stats()
            for node_id, node_info in nodes_stats['nodes'].items():
                jvm = node_info.get('jvm', {})
                mem = jvm.get('mem', {})
                heap_used_percent = mem.get('heap_used_percent', 0)
                print(f"\n💾 节点 {node_id[:8]}...")
                print(f"  • 堆内存使用率: {heap_used_percent}%")
                
                if heap_used_percent > 85:
                    print("  ⚠️ 内存使用率过高，可能影响性能")
                elif heap_used_percent > 70:
                    print("  🟡 内存使用率较高")
                else:
                    print("  ✅ 内存使用率正常")
        except Exception as e:
            print(f"⚠️ 获取内存信息失败: {e}")
            
        return True
        
    except Exception as e:
        print(f"❌ 连接 Elasticsearch 失败: {e}")
        return False

def wait_for_es_ready(max_wait=60):
    """等待ES服务准备就绪"""
    print("🕐 等待 Elasticsearch 服务准备就绪...")
    
    for i in range(max_wait):
        if check_es_status():
            print("✅ Elasticsearch 服务已准备就绪")
            return True
        
        if i < max_wait - 1:
            print(f"⏳ 等待中... ({i+1}/{max_wait})")
            time.sleep(1)
    
    print("❌ 等待超时，Elasticsearch 服务未准备就绪")
    return False

if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == "--wait":
        success = wait_for_es_ready()
        sys.exit(0 if success else 1)
    else:
        success = check_es_status()
        sys.exit(0 if success else 1)
