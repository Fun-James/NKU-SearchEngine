#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
测试通配符搜索功能
"""
from app.main.query_parser_new import QueryParser
import json

def test_wildcard_query():
    """测试通配符查询解析"""
    test_query = '?津大学'
    print(f'查询: {test_query}')
    print(f'是否包含通配符: {QueryParser.has_wildcards(test_query)}')
    
    # 测试查询解析
    parsed_query = QueryParser.parse_query(test_query)
    print(f'解析结果:')
    print(json.dumps(parsed_query, indent=2, ensure_ascii=False))
    
    # 测试其他通配符示例
    test_cases = [
        "北*大学",
        "*津大学", 
        "清华?学",
        "正常搜索"
    ]
    
    print("\n其他测试用例:")
    for case in test_cases:
        has_wildcard = QueryParser.has_wildcards(case)
        parsed = QueryParser.parse_query(case)
        print(f"\n查询: {case}")
        print(f"包含通配符: {has_wildcard}")
        print(f"查询类型: {'wildcard' if has_wildcard else 'multi_match'}")

if __name__ == "__main__":
    test_wildcard_query()
