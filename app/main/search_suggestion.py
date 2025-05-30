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
from pypinyin import lazy_pinyin, Style
from Levenshtein import distance

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
        
        # 拼音索引字典
        self.pinyin_dict = defaultdict(set)
        
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
            self._load_dictionary(dictionary_path)
    
    def build_pinyin_index(self, word):
        """
        构建拼音索引
        """
        if not word:
            return
            
        # 获取完整拼音
        full_pinyin = ''.join(lazy_pinyin(word))
        self.pinyin_dict[full_pinyin].add(word)
        
        # 获取首字母
        initials = ''.join([p[0] if p else '' for p in lazy_pinyin(word)])
        if len(initials) > 1:
            self.pinyin_dict[initials].add(word)
    
    def load_search_history(self, history):
        """
        从搜索历史中加载单词
        
        参数:
        - history: 搜索历史字符串列表
        """
        for query in history:
            # 分词并建立索引
            words = list(jieba.cut(query.lower()))
            for word in words:
                if len(word) > 1:  # 忽略单字词
                    self.word_dict.add(word)
                    self.word_freq[word] += 1
                    self.build_pinyin_index(word)  # 构建拼音索引
    
    def get_pinyin_suggestions(self, pinyin, max_suggestions=5):
        """
        获取拼音对应的中文建议
        
        参数:
        - pinyin: 拼音字符串
        - max_suggestions: 返回建议的最大数量
        
        返回:
        - 建议词列表，按词频排序
        """
        if not pinyin:
            return []
            
        pinyin = pinyin.lower()
        suggestions = set()
        
        # 1. 完全匹配
        if pinyin in self.pinyin_dict:
            suggestions.update(self.pinyin_dict[pinyin])
        
        # 2. 前缀匹配
        for py in self.pinyin_dict:
            if py.startswith(pinyin):
                suggestions.update(self.pinyin_dict[py])
        
        # 3. 模糊匹配（编辑距离<=2的拼音）
        for py in self.pinyin_dict:
            if distance(pinyin, py) <= 2:
                suggestions.update(self.pinyin_dict[py])
        
        # 按词频排序
        return sorted(suggestions, key=lambda x: self.word_freq.get(x, 0), reverse=True)[:max_suggestions]
    
    def get_word_suggestions(self, word, max_suggestions=3, threshold=0.7):
        """
        为给定词找到最相似的词，支持拼音和错别字纠正
        
        参数:
        - word: 目标词
        - max_suggestions: 返回建议的最大数量
        - threshold: 相似度阈值 (0-1)
        
        返回:
        - 建议词列表，按相似度排序
        """
        if not word or len(word) < 2:
            return []
            
        suggestions = set()
        
        # 1. 如果输入是拼音，尝试转换为中文
        if all(c.isalpha() for c in word):
            pinyin_suggestions = self.get_pinyin_suggestions(word)
            suggestions.update(pinyin_suggestions)
        
        # 2. 基于编辑距离的错别字纠正
        for dict_word in self.word_dict:
            # 计算编辑距离
            if distance(word, dict_word) <= 2:
                suggestions.add(dict_word)
            
            # 计算相似度
            similarity = difflib.SequenceMatcher(None, word, dict_word).ratio()
            if similarity > threshold:
                suggestions.add(dict_word)
        
        # 按频率和相似度排序
        scored_suggestions = []
        for sugg in suggestions:
            # 计算综合得分（结合编辑距离和字频）
            edit_dist = distance(word, sugg)
            freq_score = self.word_freq.get(sugg, 0)
            similarity = difflib.SequenceMatcher(None, word, sugg).ratio()
            score = (similarity * 0.4 + freq_score * 0.4 + (1 / (edit_dist + 1)) * 0.2)
            scored_suggestions.append((sugg, score))
        
        # 排序并返回结果
        scored_suggestions.sort(key=lambda x: x[1], reverse=True)
        return [sugg for sugg, _ in scored_suggestions[:max_suggestions]]
    
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
        original_words = list(jieba.cut(query))
        has_corrections = False
        suggested_words = []
        
        for word in original_words:
            if len(word) > 1:  # 对多字词进行纠正
                suggestions = self.get_word_suggestions(word)
                if suggestions and suggestions[0] != word:
                    suggested_words.append(suggestions[0])
                    has_corrections = True
                else:
                    suggested_words.append(word)
            else:
                suggested_words.append(word)
        
        if has_corrections:
            return ''.join(suggested_words)
        return None

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
