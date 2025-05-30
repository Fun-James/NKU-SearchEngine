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
        
        # 获取拼音列表，用于更精确的匹配
        pinyin_list = lazy_pinyin(word)
        
        # 为每个拼音音节建立索引
        for i, py in enumerate(pinyin_list):
            if py:
                # 单个拼音音节
                self.pinyin_dict[py].add(word)
                
                # 从这个位置开始的拼音组合
                for j in range(i + 1, min(i + 3, len(pinyin_list) + 1)):  # 最多组合2个音节
                    combined = ''.join(pinyin_list[i:j])
                    if len(combined) > 1:  # 避免单字符索引
                        self.pinyin_dict[combined].add(word)
        
        # 获取首字母（仅用于长词的快速匹配）
        initials = ''.join([p[0] if p else '' for p in pinyin_list])
        if len(initials) > 2:  # 只为3个字符以上的首字母建立索引
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
        
        # 1. 完全匹配（最高优先级）
        if pinyin in self.pinyin_dict:
            suggestions.update(self.pinyin_dict[pinyin])
        
        # 2. 前缀匹配（仅对较长的输入进行前缀匹配）
        if len(pinyin) >= 2:
            for py in self.pinyin_dict:
                # 只匹配以输入拼音开头，且长度相近的拼音
                if py.startswith(pinyin) and len(py) <= len(pinyin) + 3:
                    suggestions.update(self.pinyin_dict[py])
        
        # 3. 模糊匹配（仅对2字符以上的输入，且编辑距离=1）
        if len(pinyin) >= 2:
            for py in self.pinyin_dict:
                # 只对长度相近的拼音进行模糊匹配
                if abs(len(py) - len(pinyin)) <= 1 and distance(pinyin, py) == 1:
                    suggestions.update(self.pinyin_dict[py])
        
        # 按词频排序
        return sorted(suggestions, key=lambda x: self.word_freq.get(x, 0), reverse=True)[:max_suggestions]
    
    def get_word_suggestions(self, word, max_suggestions=3, threshold=0.8):
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
        
        # 如果词已经在词典中且频率较高，不需要纠正
        if word in self.word_dict and self.word_freq.get(word, 0) >= 2:
            return []
            
        suggestions = set()
        word_lower = word.lower()
        
        # 1. 如果输入是拼音，尝试转换为中文
        if all(c.isalpha() for c in word):
            pinyin_suggestions = self.get_pinyin_suggestions(word)
            suggestions.update(pinyin_suggestions)
        else:
            # 2. 基于编辑距离的错别字纠正（更严格的条件）
            for dict_word in self.word_dict:
                # 跳过相同的词
                if dict_word == word or dict_word == word_lower:
                    continue
                
                edit_dist = distance(word_lower, dict_word.lower())
                
                # 根据词长度调整编辑距离阈值
                max_edit_distance = 1 if len(word) <= 3 else 2
                
                if edit_dist <= max_edit_distance:
                    # 计算相似度
                    similarity = difflib.SequenceMatcher(None, word_lower, dict_word.lower()).ratio()
                    
                    # 提高相似度阈值，确保只有真正相似的词才被建议
                    if similarity >= threshold:
                        suggestions.add(dict_word)
        
        # 如果没有找到足够相似的建议，返回空列表
        if not suggestions:
            return []
          # 按频率和相似度排序
        scored_suggestions = []
        for sugg in suggestions:
            # 计算综合得分（结合编辑距离和字频）
            edit_dist = distance(word_lower, sugg.lower())
            freq_score = self.word_freq.get(sugg, 0)
            similarity = difflib.SequenceMatcher(None, word_lower, sugg.lower()).ratio()
            
            # 调整评分权重，优先考虑相似度
            score = (similarity * 0.6 + (freq_score / 10.0) * 0.3 + (1 / (edit_dist + 1)) * 0.1)
            scored_suggestions.append((sugg, score))
        
        # 排序并返回结果，只返回得分较高的建议
        scored_suggestions.sort(key=lambda x: x[1], reverse=True)
        filtered_suggestions = [(sugg, score) for sugg, score in scored_suggestions if score > 0.8]
        
        return [sugg for sugg, _ in filtered_suggestions[:max_suggestions]]
    
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
                if suggestions and len(suggestions) > 0:
                    # 只有当建议词与原词确实不同时才进行替换
                    best_suggestion = suggestions[0]
                    if best_suggestion.lower() != word.lower():
                        suggested_words.append(best_suggestion)
                        has_corrections = True
                    else:
                        suggested_words.append(word)
                else:
                    suggested_words.append(word)
            else:
                suggested_words.append(word)
        
        # 只有在确实有有意义的纠正时才返回建议
        if has_corrections:
            suggested_query = ''.join(suggested_words)
            # 确保建议查询与原查询确实不同
            if suggested_query.lower() != query.lower():
                return suggested_query
        
        return None
