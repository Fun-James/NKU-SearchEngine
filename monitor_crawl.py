#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
爬取进度监控工具
"""

import time
import json
from datetime import datetime
from elasticsearch import Elasticsearch
import argparse

def get_index_stats(es, index_name):
    """获取索引统计信息"""
    try:
        if not es.indices.exists(index=index_name):
            return None
            
        stats = es.indices.stats(index=index_name)
        index_stats = stats['indices'][index_name]['total']
        
        return {
            'doc_count': index_stats['docs']['count'],
            'store_size_mb': index_stats['store']['size_in_bytes'] / 1024 / 1024,
            'indexing_rate': index_stats.get('indexing', {}).get('index_total', 0),
            'search_rate': index_stats.get('search', {}).get('query_total', 0)
        }
    except Exception as e:
        print(f"获取索引统计失败: {e}")
        return None

def format_size(size_mb):
    """格式化大小显示"""
    if size_mb < 1024:
        return f"{size_mb:.2f} MB"
    else:
        return f"{size_mb/1024:.2f} GB"

def calculate_eta(current_docs, target_docs, docs_per_second):
    """计算预估完成时间"""
    if docs_per_second <= 0:
        return "未知"
    
    remaining_docs = max(0, target_docs - current_docs)
    remaining_seconds = remaining_docs / docs_per_second
    
    if remaining_seconds < 60:
        return f"{remaining_seconds:.0f}秒"
    elif remaining_seconds < 3600:
        return f"{remaining_seconds/60:.1f}分钟"
    else:
        return f"{remaining_seconds/3600:.1f}小时"

def monitor_progress(es, index_name, target_docs=100000, refresh_interval=30):
    """监控爬取进度"""
    print(f"🔍 开始监控索引: {index_name}")
    print(f"📊 目标文档数: {target_docs:,}")
    print(f"⏱️  刷新间隔: {refresh_interval}秒")
    print("=" * 80)
    
    start_time = datetime.now()
    last_doc_count = 0
    last_check_time = start_time
    
    try:
        while True:
            current_time = datetime.now()
            stats = get_index_stats(es, index_name)
            
            if stats is None:
                print(f"[{current_time.strftime('%H:%M:%S')}] 索引不存在或无法访问")
                time.sleep(refresh_interval)
                continue
            
            current_docs = stats['doc_count']
            size_mb = stats['store_size_mb']
            
            # 计算速率
            time_diff = (current_time - last_check_time).total_seconds()
            docs_added = current_docs - last_doc_count
            docs_per_second = docs_added / time_diff if time_diff > 0 else 0
            
            # 计算进度
            progress_percent = (current_docs / target_docs) * 100 if target_docs > 0 else 0
            
            # 计算ETA
            eta = calculate_eta(current_docs, target_docs, docs_per_second)
            
            # 显示进度条
            bar_length = 40
            filled_length = int(bar_length * progress_percent / 100)
            bar = '█' * filled_length + '-' * (bar_length - filled_length)
            
            # 运行时间
            elapsed = current_time - start_time
            elapsed_str = str(elapsed).split('.')[0]  # 去掉微秒
            
            print(f"\r[{current_time.strftime('%H:%M:%S')}] "
                  f"|{bar}| "
                  f"{progress_percent:5.1f}% "
                  f"({current_docs:,}/{target_docs:,}) "
                  f"| {format_size(size_mb)} "
                  f"| {docs_per_second:.1f} docs/s "
                  f"| ETA: {eta} "
                  f"| 运行: {elapsed_str}", end='')
            
            # 更新记录
            last_doc_count = current_docs
            last_check_time = current_time
            
            # 检查是否完成
            if current_docs >= target_docs:
                print(f"\n\n🎉 目标完成！共索引 {current_docs:,} 个文档")
                break
            
            time.sleep(refresh_interval)
            
    except KeyboardInterrupt:
        print(f"\n\n⏹️  监控已停止")
        final_stats = get_index_stats(es, index_name)
        if final_stats:
            print(f"最终统计: {final_stats['doc_count']:,} 文档, {format_size(final_stats['store_size_mb'])}")

def show_detailed_stats(es, index_name):
    """显示详细统计信息"""
    stats = get_index_stats(es, index_name)
    if stats is None:
        print("索引不存在或无法访问")
        return
    
    print(f"\n📈 索引 {index_name} 详细统计:")
    print("-" * 50)
    print(f"文档数量: {stats['doc_count']:,}")
    print(f"存储大小: {format_size(stats['store_size_mb'])}")
    print(f"平均文档大小: {stats['store_size_mb']*1024/stats['doc_count']:.2f} KB" if stats['doc_count'] > 0 else "N/A")
    
    # 获取更多详细信息
    try:
        # 获取字段映射信息
        mapping = es.indices.get_mapping(index=index_name)
        fields = mapping[index_name]['mappings']['properties'].keys()
        print(f"字段数量: {len(fields)}")
        print(f"主要字段: {', '.join(list(fields)[:5])}")
        
        # 获取一些样本数据
        sample = es.search(index=index_name, size=1)
        if sample['hits']['hits']:
            sample_doc = sample['hits']['hits'][0]['_source']
            print(f"样本文档字段: {list(sample_doc.keys())}")
        
    except Exception as e:
        print(f"获取详细信息时出错: {e}")

def main():
    parser = argparse.ArgumentParser(description='监控爬取进度')
    parser.add_argument('--index', default='nku_web', help='要监控的索引名称')
    parser.add_argument('--target', type=int, default=100000, help='目标文档数量')
    parser.add_argument('--interval', type=int, default=30, help='刷新间隔(秒)')
    parser.add_argument('--stats-only', action='store_true', help='仅显示统计信息')
    args = parser.parse_args()
    
    # 连接Elasticsearch
    es = Elasticsearch('http://localhost:9200')
    if not es.ping():
        print("❌ 无法连接到Elasticsearch，请确保服务已启动")
        return
    
    print("✅ Elasticsearch 连接成功")
    
    if args.stats_only:
        show_detailed_stats(es, args.index)
    else:
        monitor_progress(es, args.index, args.target, args.interval)

if __name__ == "__main__":
    main()
