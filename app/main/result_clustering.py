"""
搜索结果聚类模块
根据搜索结果的标题和内容，对结果进行简单的分组
"""

import re
from collections import Counter
import jieba

def extract_keywords(text, top_n=5):
    """
    从文本中提取关键词
    """
    if not text or not isinstance(text, str):
        return []
        
    # 去除HTML标签
    text = re.sub(r'<[^>]+>', '', text)
    
    # 分词
    words = jieba.cut(text)
    
    # 过滤停用词（简单版本）
    stop_words = {'的', '了', '是', '在', '我', '有', '和', '就', '不', '人', '都', '一', '一个', '上', '也', '很', '到', '说', '要', '去', '你', '会', '着', '没有', '看', '好', '自己', '这', '那', '啊', '一样', '中', '大', '来', '我们', '为', '吧', '把', '被', '多', '想', '等', '什么', '这个', '那个', '怎么', '还有', '还是', '得', '着', '过', '吗', '哪', '哪里', '只', '这些', '那些', '他们', '她们', '它们', '如果', '因为', '因此'}
    filtered_words = [word for word in words if len(word) > 1 and word not in stop_words]
    
    # 统计词频
    word_count = Counter(filtered_words)
    
    # 取最常见的N个词
    common_words = word_count.most_common(top_n)
    
    return [word for word, count in common_words]

def cluster_search_results(results, max_clusters=5):
    """
    对搜索结果进行简单聚类
    
    参数:
    - results: 搜索结果列表，每项应有title和content属性
    - max_clusters: 最大聚类数量
    
    返回:
    - 聚类结果列表，每项包含cluster_name和items
    """
    if not results or len(results) <= 1:
        return []
    
    # 从所有结果中提取关键词
    all_text = ' '.join([f"{result.get('title', '')} {result.get('snippet', '')}" for result in results])
    common_keywords = extract_keywords(all_text, top_n=10)
    
    # 为每个结果打标签（使用最匹配的关键词）
    clusters = {}
    for result in results:
        result_text = f"{result.get('title', '')} {result.get('snippet', '')}"
        # 选择最匹配的关键词作为聚类标签
        best_keyword = None
        highest_count = 0
        
        for keyword in common_keywords:
            count = result_text.count(keyword)
            if count > highest_count:
                highest_count = count
                best_keyword = keyword
        
        # 如果没有找到合适的关键词，使用"其他"
        if not best_keyword or highest_count == 0:
            best_keyword = "其他"
        
        # 添加到相应的聚类
        if best_keyword not in clusters:
            clusters[best_keyword] = []
        clusters[best_keyword].append(result)
    
    # 格式化聚类结果，按照每类的结果数量排序
    clusters_list = [
        {"name": keyword, "count": len(items), "items": items}
        for keyword, items in clusters.items()
    ]
    clusters_list.sort(key=lambda x: x["count"], reverse=True)
    
    # 如果聚类数量过多，合并较小的聚类到"其他"类别
    if len(clusters_list) > max_clusters:
        main_clusters = clusters_list[:max_clusters-1]
        other_items = []
        for cluster in clusters_list[max_clusters-1:]:
            other_items.extend(cluster["items"])
        
        if other_items:
            main_clusters.append({
                "name": "其他",
                "count": len(other_items),
                "items": other_items
            })
        
        return main_clusters
    
    return clusters_list

def get_smart_snippet(content, query, max_length=200):
    """
    智能生成搜索结果摘要
    尝试找到包含查询词的最相关段落
    
    参数:
    - content: 全文内容
    - query: 查询词
    - max_length: 摘要最大长度
    
    返回:
    - 摘要文本
    """
    if not content:
        return ""
    
    # 将内容分成句子
    sentences = re.split(r'[。！？.!?]', content)
    sentences = [s.strip() for s in sentences if s.strip()]
    
    if not sentences:
        return content[:max_length] + '...' if len(content) > max_length else content
    
    # 匹配包含查询词的句子
    query_terms = query.split()
    matching_sentences = []
    
    for sentence in sentences:
        # 计算句子与查询的匹配度
        match_score = 0
        for term in query_terms:
            if term in sentence:
                match_score += 1
        
        if match_score > 0:
            matching_sentences.append((sentence, match_score))
    
    # 按匹配度排序
    matching_sentences.sort(key=lambda x: x[1], reverse=True)
    
    # 如果有匹配的句子，使用最佳匹配
    if matching_sentences:
        best_sentence = matching_sentences[0][0]
        if len(best_sentence) <= max_length:
            return best_sentence
        else:
            # 如果句子太长，截取包含查询词的片段
            # 找出第一个包含查询词的位置
            first_term_pos = -1
            for term in query_terms:
                pos = best_sentence.find(term)
                if pos != -1:
                    if first_term_pos == -1 or pos < first_term_pos:
                        first_term_pos = pos
            
            if first_term_pos != -1:
                # 计算摘要起始位置，尽量使查询词在中间
                start_pos = max(0, first_term_pos - max_length // 2)
                end_pos = min(len(best_sentence), start_pos + max_length)
                
                snippet = best_sentence[start_pos:end_pos]
                if start_pos > 0:
                    snippet = '...' + snippet
                if end_pos < len(best_sentence):
                    snippet = snippet + '...'
                
                return snippet
    
    # 如果没有匹配句子，返回开头一段
    return content[:max_length] + '...' if len(content) > max_length else content
