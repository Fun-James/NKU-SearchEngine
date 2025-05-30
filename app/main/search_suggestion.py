"""
搜索建议和拼写纠正模块 - 商用级智能推荐系统
"""
import difflib
import re
import json
import time
from collections import Counter, defaultdict
from datetime import datetime, timedelta
import jieba
import jieba.analyse

class SearchSuggestion:
    """
    提供搜索建议和拼写纠正功能 - 商用级智能推荐系统
    """
    
    def __init__(self, dictionary_path=None):
        """
        初始化搜索建议系统
        
        参数:
        - dictionary_path: 可选，字典文件的路径
        """
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
        
        # 热门搜索缓存
        self.hot_searches_cache = None
        self.hot_searches_cache_time = 0
        self.cache_duration = 300  # 5分钟缓存
        
        # 初始化jieba分词
        jieba.initialize()
        
        # 加载字典 (如果提供)
        if dictionary_path:
            try:
                with open(dictionary_path, 'r', encoding='utf-8') as f:
                    for line in f:
                        word = line.strip().lower()
                        if word:
                            self.word_dict.add(word)
                            self._build_prefix_index(word)
            except Exception as e:
                print(f"Error loading dictionary: {e}")
                
    def load_search_history(self, history):
        """
        从搜索历史中加载单词
        
        参数:
        - history: 搜索历史字符串列表
        """
        for query in history:
            # 简单的中文分词 (按空格和标点符号分割)
            words = re.findall(r'[\w\u4e00-\u9fff]+', query.lower())
            for word in words:
                if len(word) > 1:  # 忽略单字词
                    self.word_dict.add(word)
                    self.word_freq[word] += 1
    
    def get_word_suggestions(self, word, max_suggestions=3, threshold=0.7):
        """
        为给定词找到最相似的词
        
        参数:
        - word: 目标词
        - max_suggestions: 返回建议的最大数量
        - threshold: 相似度阈值 (0-1)
        
        返回:
        - 建议词列表，按相似度排序
        """
        if not word or len(word) < 2:
            return []
            
        # 找到所有相似词
        matches = []
        for dict_word in self.word_dict:
            # 计算两个词的相似度
            similarity = difflib.SequenceMatcher(None, word, dict_word).ratio()
            if similarity > threshold:
                matches.append((dict_word, similarity, self.word_freq.get(dict_word, 0)))
        
        # 按相似度和频率排序
        matches.sort(key=lambda x: (x[1], x[2]), reverse=True)
        
        # 返回前N个建议
        return [match[0] for match in matches[:max_suggestions]]
            
    def get_query_suggestion(self, query):
        """
        为整个查询提供建议
        
        参数:
        - query: 原始查询字符串
        
        返回:
        - 修正后的查询或None (如果不需要修正)
        """
        if not query:
            return None
            
        # 分词处理查询
        original_words = re.findall(r'[\w\u4e00-\u9fff]+', query.lower())
        suggested_query = query
        
        has_corrections = False
        for word in original_words:
            if len(word) > 1:  # 忽略单字词
                suggestions = self.get_word_suggestions(word)
                if suggestions and suggestions[0] != word:
                    # 替换词
                    suggested_query = re.sub(r'\b' + re.escape(word) + r'\b', suggestions[0], suggested_query, flags=re.IGNORECASE)
                    has_corrections = True
        
        return suggested_query if has_corrections else None

# 测试代码
if __name__ == "__main__":
    suggester = SearchSuggestion()
    
    # 模拟搜索历史
    test_history = [
        "南开大学计算机学院",
        "南开大学招生",
        "南开大学软件学院",
        "计算机科学",
        "人工智能专业",
        "数据科学"
    ]
    
    suggester.load_search_history(test_history)
    
    # 测试词建议
    test_words = ["计算机", "计算及", "南凯大学", "数据"]
    for word in test_words:
        suggestions = suggester.get_word_suggestions(word)
        print(f"'{word}' 的建议词: {suggestions}")
    
    # 测试查询建议
    test_queries = ["南凯大学计算及", "人工智力"]
    for query in test_queries:
        suggestion = suggester.get_query_suggestion(query)
        if suggestion:
            print(f"原始查询: '{query}' -> 建议查询: '{suggestion}'")
        else:
            print(f"查询 '{query}' 无需更正")
