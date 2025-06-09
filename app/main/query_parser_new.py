"""
查询解析模块 - 支持基本搜索功能和通配符搜索
"""
import re

class QueryParser:
    """搜索查询解析器"""
    
    @staticmethod
    def has_wildcards(term):
        """检查词项是否包含通配符"""
        return '*' in term or '?' in term
    
    @staticmethod
    def parse_query(query_string):
        if not query_string or not query_string.strip():
            return {"match_all": {}}
        
        # 初始化布尔查询
        bool_query = {
            "bool": {
                "must": [],
                "should": [],
                "must_not": []
            }
        }
        
        # 提取短语（引号内的内容）
        phrases = []
        for match in re.finditer(r'"([^"]*)"', query_string):
            phrase = match.group(1).strip()
            if phrase:
                phrases.append(phrase)
                query_string = query_string.replace(f'"{phrase}"', '')
        
        # 处理短语查询
        for phrase in phrases:
            bool_query["bool"]["must"].append({
                "bool": {
                    "should": [
                        {"match_phrase": {"title": {"query": phrase, "boost": 2}}},
                        {"match_phrase": {"content": {"query": phrase}}}
                    ]
                }
            })
        
        # 处理剩余关键词
        terms = [t for t in query_string.split() if t.strip()]
          # 构建关键词查询
        for term in terms:
            if term.upper() != 'AND' and term.upper() != 'OR' and term.upper() != 'NOT':
                # 检查是否包含通配符
                if QueryParser.has_wildcards(term):
                    # 使用通配符查询
                    bool_query["bool"]["must"].append({
                        "bool": {
                            "should": [
                                {"wildcard": {"title": {"value": term, "boost": 2}}},
                                {"wildcard": {"content": {"value": term}}}
                            ]
                        }
                    })
                else:
                    # 使用普通模糊匹配查询
                    bool_query["bool"]["must"].append({
                        "multi_match": {
                            "query": term,
                            "fields": ["title^2", "content"],
                            "type": "most_fields",
                            "operator": "or",
                            "minimum_should_match": "70%",
                            "fuzziness": "AUTO"
                        }
                    })
        
        # 清理空的布尔子句
        for key in list(bool_query["bool"].keys()):
            if not bool_query["bool"][key]:
                del bool_query["bool"][key]
        
        return bool_query if bool_query["bool"] else {"match_all": {}}
