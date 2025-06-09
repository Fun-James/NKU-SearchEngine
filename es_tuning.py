#!/usr/bin/env python3
"""
Elasticsearch 性能调优脚本
"""

from elasticsearch import Elasticsearch
import json

def optimize_es_settings():
    """优化ES设置以处理大量索引操作"""
    
    try:
        es = Elasticsearch('http://localhost:9200', timeout=30)
        
        if not es.ping():
            print("❌ 无法连接到 Elasticsearch")
            return False
        
        print("🔧 开始优化 Elasticsearch 设置...")
        
        # 1. 调整索引设置以提高批量索引性能
        index_settings = {
            "index": {
                "refresh_interval": "30s",  # 减少刷新频率
                "number_of_replicas": 0,    # 暂时关闭副本
                "translog": {
                    "durability": "async",   # 异步事务日志
                    "sync_interval": "30s"
                },
                "merge": {
                    "scheduler": {
                        "max_thread_count": 1  # 限制合并线程
                    }
                }
            }
        }
        
        try:
            es.indices.put_settings(index="nku_search", body=index_settings)
            print("✅ 索引设置已优化")
        except Exception as e:
            print(f"⚠️ 索引设置优化失败: {e}")
        
        # 2. 调整集群设置
        cluster_settings = {
            "persistent": {
                "indices.store.throttle.max_bytes_per_sec": "200mb",  # 限制存储吞吐量
                "cluster.routing.allocation.disk.threshold.enabled": False  # 暂时禁用磁盘阈值
            }
        }
        
        try:
            es.cluster.put_settings(body=cluster_settings)
            print("✅ 集群设置已优化")
        except Exception as e:
            print(f"⚠️ 集群设置优化失败: {e}")
        
        # 3. 显示当前设置
        print("\n📊 当前优化设置:")
        try:
            current_settings = es.indices.get_settings(index="nku_search")
            nku_settings = current_settings.get("nku_search", {}).get("settings", {}).get("index", {})
            
            print(f"  • 刷新间隔: {nku_settings.get('refresh_interval', '1s')}")
            print(f"  • 副本数量: {nku_settings.get('number_of_replicas', '1')}")
            print(f"  • 事务日志持久性: {nku_settings.get('translog', {}).get('durability', 'request')}")
            
        except Exception as e:
            print(f"⚠️ 获取设置信息失败: {e}")
        
        return True
        
    except Exception as e:
        print(f"❌ 优化失败: {e}")
        return False

def restore_es_settings():
    """恢复ES设置到生产环境配置"""
    
    try:
        es = Elasticsearch('http://localhost:9200', timeout=30)
        
        if not es.ping():
            print("❌ 无法连接到 Elasticsearch")
            return False
        
        print("🔄 恢复 Elasticsearch 生产设置...")
        
        # 恢复索引设置
        index_settings = {
            "index": {
                "refresh_interval": "1s",   # 恢复默认刷新频率
                "number_of_replicas": 1,    # 恢复副本
                "translog": {
                    "durability": "request"  # 恢复同步事务日志
                }
            }
        }
        
        try:
            es.indices.put_settings(index="nku_search", body=index_settings)
            print("✅ 索引设置已恢复")
        except Exception as e:
            print(f"⚠️ 索引设置恢复失败: {e}")
        
        # 恢复集群设置
        cluster_settings = {
            "persistent": {
                "indices.store.throttle.max_bytes_per_sec": None,
                "cluster.routing.allocation.disk.threshold.enabled": None
            }
        }
        
        try:
            es.cluster.put_settings(body=cluster_settings)
            print("✅ 集群设置已恢复")
        except Exception as e:
            print(f"⚠️ 集群设置恢复失败: {e}")
        
        # 强制刷新索引
        try:
            es.indices.refresh(index="nku_search")
            print("✅ 索引已刷新")
        except Exception as e:
            print(f"⚠️ 索引刷新失败: {e}")
        
        return True
        
    except Exception as e:
        print(f"❌ 恢复失败: {e}")
        return False

def force_merge_index():
    """强制合并索引以优化性能"""
    
    try:
        es = Elasticsearch('http://localhost:9200', timeout=300)  # 5分钟超时
        
        if not es.ping():
            print("❌ 无法连接到 Elasticsearch")
            return False
        
        print("🔄 开始强制合并索引（这可能需要几分钟）...")
        
        # 强制合并到1个段以优化搜索性能
        es.indices.forcemerge(
            index="nku_search",
            max_num_segments=1,
            wait_for_completion=True
        )
        
        print("✅ 索引合并完成")
        return True
        
    except Exception as e:
        print(f"❌ 索引合并失败: {e}")
        return False

if __name__ == "__main__":
    import sys
    
    if len(sys.argv) > 1:
        command = sys.argv[1]
        
        if command == "optimize":
            optimize_es_settings()
        elif command == "restore":
            restore_es_settings()
        elif command == "merge":
            force_merge_index()
        else:
            print("用法:")
            print("  python es_tuning.py optimize  # 优化设置以提高索引性能")
            print("  python es_tuning.py restore   # 恢复生产环境设置")
            print("  python es_tuning.py merge     # 强制合并索引优化搜索")
    else:
        print("🔧 Elasticsearch 性能调优工具")
        print("=" * 40)
        print("用法:")
        print("  python es_tuning.py optimize  # 优化设置以提高索引性能")
        print("  python es_tuning.py restore   # 恢复生产环境设置")
        print("  python es_tuning.py merge     # 强制合并索引优化搜索")
