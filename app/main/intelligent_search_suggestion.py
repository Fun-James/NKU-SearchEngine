"""
智能搜索建议系统 - 精简版
"""
import difflib
import re
import json
import time
import logging
from collections import Counter, defaultdict
from datetime import datetime, timedelta
import jieba
import jieba.analyse

class IntelligentSearchSuggestion:
    """
    智能搜索建议系统，精简版：
    1. 实时自动补全
    2. 相关查询推荐
    """
    def __init__(self, dictionary_path=None):
        """
        初始化智能搜索建议系统
        """
        # 设置日志
        self.logger = logging.getLogger(__name__)
        
        # 基础词典和频率统计
        self.word_dict = set()
        self.word_freq = Counter()
        self.query_freq = Counter()
        
        # 前缀匹配字典：用于快速自动补全
        self.prefix_dict = defaultdict(set)
        
        # 相关查询映射：基于共现的相关查询
        self.related_queries = defaultdict(set)
        
        # 搜索时间戳：用于趋势分析
        self.search_timestamps = defaultdict(list)
        
        # 初始化jieba分词
        jieba.initialize()
        
        # 加载字典 (如果提供)
        if dictionary_path:
            self._load_dictionary(dictionary_path)
    
    def _load_dictionary(self, dictionary_path):
        """加载外部词典"""
        try:
            with open(dictionary_path, 'r', encoding='utf-8') as f:
                for line in f:
                    word = line.strip().lower()
                    if word:
                        self.word_dict.add(word)
                        self._build_prefix_index(word)
        except Exception as e:
            print(f"Error loading dictionary: {e}")
    
    def _build_prefix_index(self, word):
        """构建前缀索引，用于快速自动补全"""
        for i in range(1, len(word) + 1):
            prefix = word[:i]
            self.prefix_dict[prefix].add(word)
    
    def load_search_history(self, history):
        """
        从搜索历史中学习和构建词典
        """
        current_time = time.time()
        
        for query in history:
            if not query or len(query.strip()) == 0:
                continue
                
            # 记录查询频率和时间戳
            query_lower = query.lower().strip()
            self.query_freq[query_lower] += 1
            self.search_timestamps[query_lower].append(current_time)
            
            # 使用jieba进行中文分词
            words = list(jieba.cut(query_lower))
            # 同时使用正则表达式分词作为补充
            regex_words = re.findall(r'[\w\u4e00-\u9fff]+', query_lower)
            all_words = words + regex_words
            
            for word in all_words:
                if len(word) > 1:  # 忽略单字词
                    self.word_dict.add(word)
                    self.word_freq[word] += 1
                    self._build_prefix_index(word)
            
            # 构建相关查询关系
            self._build_related_queries(query_lower, all_words)
    
    def _build_related_queries(self, query, words):
        """构建查询之间的相关关系"""
        # 基于共同词汇建立查询相关性
        for other_query in self.query_freq.keys():
            if other_query != query:
                other_words = list(jieba.cut(other_query)) + re.findall(r'[\w\u4e00-\u9fff]+', other_query)
                # 计算词汇重叠度
                common_words = set(words) & set(other_words)
                if len(common_words) >= 1:  # 至少有一个共同词
                    self.related_queries[query].add(other_query)
                    self.related_queries[other_query].add(query)
    
    def get_autocomplete_suggestions(self, prefix, max_suggestions=8):
        """
        获取自动补全建议（前缀匹配）
        """
        if not prefix or len(prefix) < 1:
            return []
        
        prefix_lower = prefix.lower()
        suggestions = []
        
        # 1. 精确前缀匹配
        if prefix_lower in self.prefix_dict:
            candidates = list(self.prefix_dict[prefix_lower])
            # 按频率排序
            candidates.sort(key=lambda x: self.word_freq.get(x, 0), reverse=True)
            suggestions.extend(candidates[:max_suggestions])
        
        # 2. 查询历史中的前缀匹配
        for query in self.query_freq.keys():
            if query.startswith(prefix_lower) and query not in suggestions:
                suggestions.append(query)
        
        # 3. 模糊前缀匹配
        if len(suggestions) < max_suggestions:
            for word in self.word_dict:
                if word.startswith(prefix_lower) and word not in suggestions:
                    suggestions.append(word)
                if len(suggestions) >= max_suggestions:
                    break
        
        # 按频率和相关性排序
        suggestions.sort(key=lambda x: (
            self.query_freq.get(x, 0) + self.word_freq.get(x, 0),
            -len(x)  # 长度较短的优先
        ), reverse=True)
        
        return suggestions[:max_suggestions]
    
    def get_related_queries(self, query, max_suggestions=5):
        """
        获取相关查询推荐
        """
        if not query:
            return []
        
        query_lower = query.lower().strip()
        related = []
        
        # 1. 直接相关查询
        if query_lower in self.related_queries:
            related.extend(list(self.related_queries[query_lower]))
        
        # 2. 基于关键词的相关查询
        query_words = set(jieba.cut(query_lower))
        for other_query in self.query_freq.keys():
            if other_query != query_lower and other_query not in related:
                other_words = set(jieba.cut(other_query))
                # 计算词汇相似度
                intersection = query_words & other_words
                if len(intersection) > 0:
                    similarity = len(intersection) / len(query_words | other_words)
                    if similarity > 0.3:  # 相似度阈值
                        related.append(other_query)
        
        # 按查询频率排序
        related.sort(key=lambda x: self.query_freq.get(x, 0), reverse=True)
        
        return related[:max_suggestions]
    
    def get_comprehensive_suggestions(self, query, max_autocomplete=5, max_related=3):
        """
        获取综合建议（包括自动补全、相关查询）
        """
        result = {
            "autocomplete": [],
            "related": []
        }
        
        if query and len(query.strip()) > 0:
            # 自动补全
            result["autocomplete"] = self.get_autocomplete_suggestions(query, max_autocomplete)
            
            # 相关查询
            result["related"] = self.get_related_queries(query, max_related)
        
        return result
    
    def record_search(self, query):
        """
        记录一次搜索，用于学习和改进建议
        """
        if not query:
            return
        
        query_lower = query.lower().strip()
        current_time = time.time()
        
        # 更新查询频率和时间戳
        self.query_freq[query_lower] += 1
        self.search_timestamps[query_lower].append(current_time)
        
        # 限制时间戳数量，避免内存过度使用
        if len(self.search_timestamps[query_lower]) > 100:
            self.search_timestamps[query_lower] = self.search_timestamps[query_lower][-50:]
        
        # 更新词汇
        words = list(jieba.cut(query_lower)) + re.findall(r'[\w\u4e00-\u9fff]+', query_lower)
        for word in words:
            if len(word) > 1:
                self.word_dict.add(word)
                self.word_freq[word] += 1
                self._build_prefix_index(word)
        
        # 清除热门搜索缓存
        self.hot_searches_cache = None
    
    def get_search_trends(self, days=7):
        """
        获取搜索趋势分析
        """
        current_time = time.time()
        time_threshold = current_time - (days * 24 * 3600)
        
        # 按天统计搜索量
        daily_stats = defaultdict(lambda: defaultdict(int))
        
        for query, timestamps in self.search_timestamps.items():
            for ts in timestamps:
                if ts > time_threshold:
                    day = datetime.fromtimestamp(ts).strftime('%Y-%m-%d')
                    daily_stats[day][query] += 1
        
        # 计算趋势
        trends = []
        for day, queries in daily_stats.items():
            total_searches = sum(queries.values())
            top_queries = sorted(queries.items(), key=lambda x: x[1], reverse=True)[:5]
            trends.append({
                "date": day,
                "total_searches": total_searches,
                "top_queries": top_queries
            })
        
        return sorted(trends, key=lambda x: x["date"])
    
    def extract_semantic_keywords(self, text):
        """使用jieba提取语义关键词"""
        if not text:
            return []
        
        # 使用TF-IDF提取关键词
        keywords = jieba.analyse.extract_tags(text, topK=10, withWeight=True)
        return [(word, weight) for word, weight in keywords if len(word) > 1]
    
    def build_semantic_relations(self, documents):
        """
        基于文档内容构建语义关系图
        
        参数:
        - documents: 文档列表，每个文档包含 'title' 和 'content'
        """
        print("构建语义关系图...")
        
        for doc in documents:
            if not isinstance(doc, dict) or 'title' not in doc:
                continue
                
            title = doc.get('title', '')
            content = doc.get('content', '')
            full_text = f"{title} {content}"
            
            # 提取关键词
            keywords = self.extract_semantic_keywords(full_text)
            keyword_list = [word for word, weight in keywords]
            
            # 构建关键词之间的共现关系
            for i, word1 in enumerate(keyword_list):
                for word2 in keyword_list[i+1:]:
                    self.semantic_relations[word1].add(word2)
                    self.semantic_relations[word2].add(word1)
                    
                # 添加到词典
                self.word_dict.add(word1)
                self._build_prefix_index(word1)
        
        print(f"构建了 {len(self.semantic_relations)} 个语义关系")
    
    def _get_semantic_suggestions(self, query):
        """获取语义相关建议"""
        suggestions = []
        
        # 对查询进行分词
        words = list(jieba.cut(query))
        
        for word in words:
            if word in self.semantic_relations:
                related_words = list(self.semantic_relations[word])
                # 按共现频率排序（这里简化为随机，实际可以统计共现次数）
                suggestions.extend(related_words[:3])
        
        return list(set(suggestions))[:5]
    
    def _get_domain_suggestions(self, query):
        """获取领域知识建议"""
        suggestions = []
        
        # 对查询进行分词
        words = list(jieba.cut(query))
        
        for word in words:
            if word in self.domain_knowledge:
                related_concepts = list(self.domain_knowledge[word])
                suggestions.extend(related_concepts[:3])
        
        # 模糊匹配领域概念
        for concept in self.domain_knowledge.keys():
            if concept in query or query in concept:
                suggestions.extend(list(self.domain_knowledge[concept])[:2])
        
        return list(set(suggestions))[:5]
    
    def _get_contextual_suggestions(self, query):
        """基于用户搜索上下文的建议"""
        suggestions = []
        
        if len(self.context_history) > 0:
            # 获取最近的搜索历史
            recent_queries = self.context_history[-5:]
            
            # 提取最近搜索的关键词
            recent_keywords = set()
            for recent_query in recent_queries:
                words = list(jieba.cut(recent_query.lower()))
                recent_keywords.update(words)
            
            # 基于最近关键词推荐相关概念
            for keyword in recent_keywords:
                if keyword in self.domain_knowledge:
                    suggestions.extend(list(self.domain_knowledge[keyword])[:2])
                if keyword in self.semantic_relations:
                    suggestions.extend(list(self.semantic_relations[keyword])[:2])
        
        return list(set(suggestions))[:3]
    
    def _get_trending_suggestions(self, query):
        """获取趋势相关建议"""
        suggestions = []
        
        # 获取热门搜索中与当前查询相关的项目
        hot_searches = self.get_hot_searches(max_results=20)
        
        query_words = set(jieba.cut(query))
        
        for hot_item in hot_searches:
            hot_query = hot_item['query']
            hot_words = set(jieba.cut(hot_query))
            
            # 如果有共同词汇，则推荐
            if query_words & hot_words:
                suggestions.append(hot_query)
        
        return suggestions[:3]
    
    def _calculate_relevance(self, query, suggestion):
        """计算查询与建议的相关性分数"""
        query_words = set(jieba.cut(query))
        suggestion_words = set(jieba.cut(suggestion))
        
        if not query_words or not suggestion_words:
            return 0.0
        
        # 计算词汇重叠度
        intersection = query_words & suggestion_words
        union = query_words | suggestion_words
        jaccard_similarity = len(intersection) / len(union) if union else 0
        
        # 考虑查询和建议的频率
        query_freq = self.query_freq.get(query, 1)
        suggestion_freq = self.query_freq.get(suggestion, 1)
        freq_boost = min(query_freq, suggestion_freq) / max(query_freq, suggestion_freq)
        
        # 综合相关性分数
        relevance = jaccard_similarity * 0.7 + freq_boost * 0.3
        
        return relevance
    
    def update_search_context(self, query):
        """更新用户搜索上下文"""
        if query and query.strip():
            self.context_history.append(query.lower().strip())
            # 保持上下文历史不超过10条
            if len(self.context_history) > 10:
                self.context_history.pop(0)
    
    # 性能优化方法 (新增)
    def optimize_performance(self):
        """性能优化方法"""
        try:
            # 清理过期的时间戳数据
            current_time = time.time()
            cutoff_time = current_time - 30 * 24 * 3600  # 30天前
            
            for query in list(self.search_timestamps.keys()):
                timestamps = self.search_timestamps[query]
                self.search_timestamps[query] = [
                    ts for ts in timestamps if ts > cutoff_time
                ]
                if not self.search_timestamps[query]:
                    del self.search_timestamps[query]
            
            # 清理低频词汇
            min_freq = 2
            low_freq_words = [
                word for word, freq in self.word_freq.items()
                if freq < min_freq
            ]
            
            for word in low_freq_words:
                if word in self.word_dict:
                    self.word_dict.remove(word)
                del self.word_freq[word]
                
                # 从前缀索引中移除
                for prefix_len in range(1, len(word) + 1):
                    prefix = word[:prefix_len]
                    if prefix in self.prefix_dict:
                        self.prefix_dict[prefix].discard(word)
                        if not self.prefix_dict[prefix]:
                            del self.prefix_dict[prefix]
            
            self.logger.info(f"性能优化完成：清理了 {len(low_freq_words)} 个低频词")
            
        except Exception as e:
            self.logger.error(f"性能优化失败: {str(e)}")
    
    def get_performance_stats(self):
        """获取性能统计信息"""
        stats = {
            'word_dict_size': len(self.word_dict),
            'query_freq_size': len(self.query_freq),
            'prefix_dict_size': len(self.prefix_dict),
            'related_queries_size': len(self.related_queries),
            'semantic_relations_size': len(self.semantic_relations),
            'context_history_size': len(self.context_history)
        }
        
        if self.performance_monitor:
            monitor_stats = self.performance_monitor.get_stats()
            stats.update(monitor_stats)
        
        if self.cache_manager:
            cache_stats = self.cache_manager.get_stats()
            stats.update({'cache': cache_stats})
        
        return stats
    
    # 错误恢复方法 (新增)
    def handle_error_gracefully(self, operation, *args, **kwargs):
        """优雅地处理错误"""
        try:
            if hasattr(self, operation):
                method = getattr(self, operation)
                return method(*args, **kwargs)
            else:
                raise AttributeError(f"未找到方法: {operation}")
        except Exception as e:
            if self.error_handler:
                return self.error_handler.handle_suggestion_error(e, 
                    kwargs.get('query', ''), 
                    kwargs.get('fallback_suggestions', []))
            else:
                self.logger.error(f"操作 {operation} 失败: {str(e)}")
                return []
    
    # 批量操作优化 (新增)
    def batch_update_suggestions(self, queries_batch):
        """批量更新建议以提高性能"""
        if not queries_batch:
            return
        
        try:
            start_time = time.time()
            
            # 批量处理查询
            for query in queries_batch:
                if query and query.strip():
                    self.update_search_context(query)
                    # 预构建相关数据
                    words = list(jieba.cut(query.lower()))
                    for word in words:
                        if len(word) > 1:
                            self.word_dict.add(word)
                            self.word_freq[word] += 1
                            self._build_prefix_index(word)
            
            # 定期优化性能
            if len(queries_batch) > 100:
                self.optimize_performance()
            
            duration = time.time() - start_time
            self.logger.info(f"批量更新 {len(queries_batch)} 个查询，耗时 {duration:.2f} 秒")
            
        except Exception as e:
            self.logger.error(f"批量更新失败: {str(e)}")


# 测试代码
if __name__ == "__main__":
    suggester = IntelligentSearchSuggestion()
    
    # 模拟搜索历史
    test_history = [
        "南开大学计算机学院",
        "南开大学招生",
        "南开大学软件学院", 
        "计算机科学",
        "人工智能专业",
        "数据科学",
        "机器学习算法",
        "深度学习课程",
        "Python编程",
        "Java开发"
    ]
    
    suggester.load_search_history(test_history)
    
    # 测试自动补全
    print("=== 自动补全测试 ===")
    test_prefixes = ["南开", "计算", "人工"]
    for prefix in test_prefixes:
        suggestions = suggester.get_autocomplete_suggestions(prefix)
        print(f"'{prefix}' 的自动补全: {suggestions}")
    
    # 测试相关查询
    print("\n=== 相关查询测试 ===")
    test_queries = ["南开大学", "计算机"]
    for query in test_queries:
        related = suggester.get_related_queries(query)
        print(f"'{query}' 的相关查询: {related}")
