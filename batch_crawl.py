#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
批量爬取脚本 - 用于爬取10万+网页，支持断点续爬和去重
"""

import subprocess
import sys
import time
import os
import json
import signal
from datetime import datetime
from elasticsearch import Elasticsearch

class CrawlManager:
    """爬取管理器，支持批次管理和断点续爬"""
    
    def __init__(self):
        self.progress_file = "crawl_progress.json"
        self.es = None
        self.connect_es()
    
    def connect_es(self):
        """连接到Elasticsearch"""
        try:
            self.es = Elasticsearch('http://localhost:9200')
            if self.es.ping():
                print("✅ 已连接到Elasticsearch")
                return True
            else:
                print("⚠️  无法连接到Elasticsearch，将无法进行去重")
                return False
        except Exception as e:
            print(f"⚠️  连接Elasticsearch失败: {e}")
            return False
    
    def get_crawled_urls_count(self):
        """获取已爬取的URL数量"""
        if not self.es:
            return 0
        try:
            result = self.es.count(index="nku_web")
            return result['count']
        except:
            return 0
    
    def save_progress(self, batch_num, total_batches, completed_pages):
        """保存爬取进度"""
        progress = {
            "current_batch": batch_num,
            "total_batches": total_batches,
            "completed_pages": completed_pages,
            "last_update": datetime.now().isoformat(),
            "crawled_urls_count": self.get_crawled_urls_count()
        }
        
        try:
            with open(self.progress_file, 'w', encoding='utf-8') as f:
                json.dump(progress, f, ensure_ascii=False, indent=2)
            print(f"📝 已保存进度: 批次 {batch_num}/{total_batches}")
        except Exception as e:
            print(f"⚠️  保存进度失败: {e}")
    
    def load_progress(self):
        """加载之前的进度"""
        if os.path.exists(self.progress_file):
            try:
                with open(self.progress_file, 'r', encoding='utf-8') as f:
                    return json.load(f)
            except Exception as e:
                print(f"⚠️  加载进度失败: {e}")
        return None
    
    def clear_progress(self):
        """清理进度文件"""
        if os.path.exists(self.progress_file):
            try:
                os.remove(self.progress_file)
                print("🗑️  已清理进度文件")
            except:
                pass

def run_crawl_command_with_timeout(args_list, timeout_minutes=30):
    """执行爬取命令，带超时控制"""
    cmd = [sys.executable, "crawl_and_index.py"] + args_list
    print(f"执行命令: {' '.join(cmd)}")
    print(f"超时设置: {timeout_minutes} 分钟")
    
    try:
        # 使用超时控制
        result = subprocess.run(
            cmd, 
            capture_output=True, 
            text=True, 
            encoding='utf-8',
            timeout=timeout_minutes * 60  # 转换为秒
        )
        
        if result.returncode == 0:
            print("✅ 爬取成功完成")
            # 只显示最后几行输出，避免输出过多
            output_lines = result.stdout.strip().split('\n')
            if len(output_lines) > 10:
                print("..." + '\n'.join(output_lines[-10:]))
            else:
                print(result.stdout)
        else:
            print("❌ 爬取出现错误")
            print(result.stderr)
        return result.returncode == 0
        
    except subprocess.TimeoutExpired:
        print(f"⏰ 爬取超时 ({timeout_minutes} 分钟)，强制结束")
        return False
    except KeyboardInterrupt:
        print("🛑 用户中断爬取")
        return False
    except Exception as e:
        print(f"❌ 执行命令出错: {e}")
        return False

def main():
    """主要的批量爬取策略"""
    print("🚀 开始批量爬取南开大学网站群")
    print("=" * 60)    # 策略1: 爬取10万页面 (推荐)
    strategy_1 = {
        "name": "完整爬取策略",
        "description": "爬取南开主站9%，各学院平均分配91%",
        "args": [
            "--total-pages", "100000",
            "--main-ratio", "0.09",
            "--delay", "0.3",
            "--max-depth", "6",
            "--skip-robots"
        ]
    }
    
    # 策略2: 仅爬取学院网站 (用于补充)
    strategy_2 = {
        "name": "学院专项爬取",
        "description": "仅爬取各学院网站，每个学院3000页",
        "args": [
            "--total-pages", "75000",
            "--colleges-only",
            "--delay", "0.2",
            "--max-depth", "7",
            "--skip-robots"
        ]
    }
    
    # 策略3: 主站深度爬取 (用于补充)
    strategy_3 = {
        "name": "主站深度爬取",
        "description": "仅爬取南开主站，深度挖掘",
        "args": [
            "--total-pages", "50000",
            "--main-only",
            "--delay", "0.2",
            "--max-depth", "8",
            "--skip-robots"
        ]    }
    
    # 选择策略
    strategies = [strategy_1, strategy_2, strategy_3]
    
    print("请选择爬取策略:")
    for i, strategy in enumerate(strategies, 1):
        print(f"{i}. {strategy['name']}: {strategy['description']}")
    
    print("4. 自定义策略")
    print("5. 传统分批次爬取")
    print("6. 智能分批次爬取 (推荐)")
    
    choice = input("\n请输入选择 (1-6): ").strip()
    
    if choice in ["1", "2", "3"]:
        strategy = strategies[int(choice) - 1]
        print(f"\n选择了: {strategy['name']}")
        print(f"描述: {strategy['description']}")
        
        timeout_minutes = int(input("超时时间(分钟, 默认30): ").strip() or "30")
        confirm = input("确认开始爬取? (y/N): ").strip().lower()
        if confirm == 'y':
            start_time = datetime.now()
            print(f"\n开始时间: {start_time}")
            
            success = run_crawl_command_with_timeout(strategy['args'], timeout_minutes)
            
            end_time = datetime.now()
            duration = end_time - start_time
            print(f"\n结束时间: {end_time}")
            print(f"总耗时: {duration}")
            
            if success:
                print("🎉 批量爬取任务完成！")
            else:
                print("❌ 批量爬取任务失败")
    
    elif choice == "4":
        custom_crawl()
    
    elif choice == "5":
        batch_crawl()
    
    elif choice == "6":
        smart_batch_crawl()
    
    else:
        print("无效选择")

def custom_crawl():
    """自定义爬取参数"""
    print("\n=== 自定义爬取配置 ===")
    
    total_pages = input("总页面数 (默认100000): ").strip() or "100000"
    main_ratio = input("主站比例 0.0-1.0 (默认0.09): ").strip() or "0.09"
    delay = input("爬取延迟秒数 (默认0.2): ").strip() or "0.2"
    max_depth = input("最大深度 (默认6): ").strip() or "6"
    timeout_minutes = int(input("超时时间(分钟, 默认30): ").strip() or "30")
    
    args = [
        "--total-pages", total_pages,
        "--main-ratio", main_ratio,
        "--delay", delay,
        "--max-depth", max_depth,
        "--skip-robots"
    ]
    
    print(f"\n配置参数: {' '.join(args)}")
    print(f"超时设置: {timeout_minutes} 分钟")
    confirm = input("确认开始爬取? (y/N): ").strip().lower()
    
    if confirm == 'y':
        start_time = datetime.now()
        print(f"\n开始时间: {start_time}")
        
        success = run_crawl_command_with_timeout(args, timeout_minutes)
        
        end_time = datetime.now()
        duration = end_time - start_time
        print(f"\n结束时间: {end_time}")
        print(f"总耗时: {duration}")
        
        if success:
            print("🎉 自定义爬取任务完成！")
        else:
            print("❌ 自定义爬取任务失败")

def smart_batch_crawl():
    """智能分批次爬取，支持断点续爬和超时控制"""
    print("\n=== 智能分批次爬取策略 ===")
    print("✨ 特性：断点续爬、超时控制、进度保存、自动重试")
    print("策略：主站9%，各学院91%（平均分配）")
    
    manager = CrawlManager()
    
    # 检查之前的进度
    previous_progress = manager.load_progress()
    if previous_progress:
        print(f"\n📋 发现之前的爬取进度:")
        print(f"   上次完成批次: {previous_progress['current_batch']}")
        print(f"   已完成页面: {previous_progress['completed_pages']}")
        print(f"   ES中URL数: {previous_progress.get('crawled_urls_count', 0)}")
        print(f"   上次更新: {previous_progress['last_update']}")
        
        continue_choice = input("是否从上次进度继续? (y/N): ").strip().lower()
        if continue_choice == 'y':
            batch_size = previous_progress['completed_pages'] // previous_progress['current_batch']
            total_batches = previous_progress['total_batches']
            start_batch = previous_progress['current_batch'] + 1
            print(f"将从第 {start_batch} 批次继续")
        else:
            manager.clear_progress()
            batch_size = int(input("每批次页面数 (推荐8000-15000): ").strip() or "10000")
            total_batches = int(input("总批次数 (推荐5-10批): ").strip() or "8")
            start_batch = 1
    else:
        batch_size = int(input("每批次页面数 (推荐8000-15000): ").strip() or "10000")
        total_batches = int(input("总批次数 (推荐5-10批): ").strip() or "8")
        start_batch = 1
    
    timeout_minutes = int(input("单批次超时时间(分钟) (推荐20-30): ").strip() or "25")
    rest_minutes = int(input("批次间休息时间(分钟) (推荐3-8): ").strip() or "5")
    
    total_pages = batch_size * total_batches
    print(f"\n📊 爬取计划:")
    print(f"   每批次: {batch_size} 页")
    print(f"   总批次: {total_batches} 批")
    print(f"   预计总页面: {total_pages}")
    print(f"   单批次超时: {timeout_minutes} 分钟")
    print(f"   批次间休息: {rest_minutes} 分钟")
    
    if manager.es:
        current_count = manager.get_crawled_urls_count()
        print(f"   当前ES中已有: {current_count} 个URL")
    
    confirm = input("\n确认开始智能批次爬取? (y/N): ").strip().lower()
    if confirm != 'y':
        return
    
    overall_start = datetime.now()
    completed_pages = (start_batch - 1) * batch_size
    
    for batch_num in range(start_batch, total_batches + 1):
        print(f"\n{'='*60}")
        print(f"🔄 第 {batch_num}/{total_batches} 批次")
        print(f"{'='*60}")
        
        # 使用一致的9%:91%策略
        args = [
            "--total-pages", str(batch_size),
            "--main-ratio", "0.09",
            "--delay", "0.2",  # 稍微快一点
            "--max-depth", "5",  # 适中的深度
            "--skip-robots"
        ]
        
        batch_start = datetime.now()
        print(f"🕐 批次开始时间: {batch_start}")
        print(f"📝 目标页面数: {batch_size}")
        
        # 使用带超时的爬取函数
        success = run_crawl_command_with_timeout(args, timeout_minutes)
        
        batch_end = datetime.now()
        batch_duration = batch_end - batch_start
        
        print(f"🕐 批次结束时间: {batch_end}")
        print(f"⏱️  批次耗时: {batch_duration}")
        
        if success:
            print(f"✅ 第 {batch_num} 批次完成")
            completed_pages += batch_size
            manager.save_progress(batch_num, total_batches, completed_pages)
        else:
            print(f"❌ 第 {batch_num} 批次失败")
            
            # 提供重试选项
            retry_choice = input("选择操作 - (r)重试/(s)跳过/(q)退出: ").strip().lower()
            if retry_choice == 'r':
                continue  # 重试当前批次
            elif retry_choice == 'q':
                print("🛑 用户选择退出")
                break
            else:
                print("⏭️  跳过此批次")
                completed_pages += batch_size  # 仍然记录为已处理
                manager.save_progress(batch_num, total_batches, completed_pages)
        
        # 显示总体进度
        if manager.es:
            current_total = manager.get_crawled_urls_count()
            print(f"📊 ES中当前总计: {current_total} 个URL")
        
        # 除了最后一批次，都要休息
        if batch_num < total_batches:
            print(f"😴 休息 {rest_minutes} 分钟后继续下一批次...")
            try:
                time.sleep(rest_minutes * 60)
            except KeyboardInterrupt:
                print("\n🛑 用户中断休息，是否继续下一批次?")
                continue_choice = input("继续下一批次? (y/N): ").strip().lower()
                if continue_choice != 'y':
                    break
    
    overall_end = datetime.now()
    overall_duration = overall_end - overall_start
    
    print(f"\n🎉 智能批次爬取完成！")
    print(f"📅 总开始时间: {overall_start}")
    print(f"📅 总结束时间: {overall_end}")
    print(f"⏱️  总耗时: {overall_duration}")
    print(f"📄 计划页面数: {total_pages}")
    print(f"📄 已处理页面: {completed_pages}")
    
    if manager.es:
        final_count = manager.get_crawled_urls_count()
        print(f"📊 ES中最终计数: {final_count} 个URL")
    
    # 清理进度文件
    manager.clear_progress()

def batch_crawl():
    """传统分批次爬取（保持兼容性）"""
    print("\n=== 传统分批次爬取策略 ===")
    print("⚠️  建议使用选项6的智能批次爬取，功能更完善")
    print("策略：主站9%，各学院91%（平均分配）")
    
    batch_size = int(input("每批次页面数 (推荐10000-20000): ").strip() or "15000")
    total_batches = int(input("总批次数 (推荐5-8批): ").strip() or "7")
    rest_minutes = int(input("批次间休息时间(分钟) (推荐5-10): ").strip() or "5")
    timeout_minutes = int(input("单批次超时时间(分钟) (推荐25-35): ").strip() or "30")
    
    total_pages = batch_size * total_batches
    print(f"\n计划爬取总页面数: {total_pages}")
    
    confirm = input("确认开始分批次爬取? (y/N): ").strip().lower()
    if confirm != 'y':
        return
    
    overall_start = datetime.now()
    
    for batch_num in range(1, total_batches + 1):
        print(f"\n{'='*50}")
        print(f"🔄 第 {batch_num}/{total_batches} 批次")
        print(f"{'='*50}")
        
        # 统一使用9%主站，91%学院的策略
        args = [
            "--total-pages", str(batch_size),
            "--main-ratio", "0.09",
            "--delay", "0.2",
            "--max-depth", "6",
            "--skip-robots"
        ]
        
        batch_start = datetime.now()
        print(f"批次开始时间: {batch_start}")
        
        # 使用带超时的爬取函数
        success = run_crawl_command_with_timeout(args, timeout_minutes)
        
        batch_end = datetime.now()
        batch_duration = batch_end - batch_start
        
        print(f"批次结束时间: {batch_end}")
        print(f"批次耗时: {batch_duration}")
        
        if not success:
            print(f"❌ 第 {batch_num} 批次失败")
            retry = input("是否重试此批次? (y/N): ").strip().lower()
            if retry == 'y':
                continue  # 重试当前批次
        else:
            print(f"✅ 第 {batch_num} 批次完成")
        
        # 除了最后一批次，都要休息
        if batch_num < total_batches:
            print(f"😴 休息 {rest_minutes} 分钟后继续下一批次...")
            try:
                time.sleep(rest_minutes * 60)
            except KeyboardInterrupt:
                print("\n🛑 用户中断，是否继续?")
                continue_choice = input("继续下一批次? (y/N): ").strip().lower()
                if continue_choice != 'y':
                    break
    
    overall_end = datetime.now()
    overall_duration = overall_end - overall_start
    
    print(f"\n🎉 所有批次完成！")
    print(f"总开始时间: {overall_start}")
    print(f"总结束时间: {overall_end}")
    print(f"总耗时: {overall_duration}")
    print(f"预计爬取页面数: {total_pages}")

if __name__ == "__main__":
    main()
