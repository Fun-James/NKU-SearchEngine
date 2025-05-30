"""
测试个性化排序功能
"""

import sys
import os
sys.path.insert(0, '.')

from app.main.personalized_ranking import PersonalizedRanking

def test_personalized_ranking():
    """测试个性化排序功能"""
    print("=== 个性化排序功能测试 ===\n")
    
    # 初始化排序器
    ranker = PersonalizedRanking()
    
    # 模拟搜索结果
    mock_results = [
        {
            'title': '南开大学计算机学院人工智能研究中心',
            'snippet': '计算机学院致力于人工智能、机器学习、深度学习等前沿技术研究，为博士生和研究生提供优质的科研环境。',
            'url': 'https://cc.nankai.edu.cn/research/ai',
            'score': 15.2,
            'is_attachment': False
        },
        {
            'title': '南开大学本科生教学管理系统',
            'snippet': '为本科生提供课程选择、成绩查询、学分管理等服务，支持在线选课和成绩查询。',
            'url': 'https://www.nankai.edu.cn/undergraduate/system',
            'score': 12.8,
            'is_attachment': False
        },
        {
            'title': '南开大学历史学院学术论文要求[PDF文档]',
            'snippet': '历史学院研究生学术论文写作规范，包含格式要求、引用标准等详细说明。',
            'url': 'https://history.nankai.edu.cn/documents/thesis_requirements.pdf',
            'score': 11.5,
            'is_attachment': True,
            'file_type': 'PDF文档'
        },
        {
            'title': '南开大学教师职业发展规划',
            'snippet': '为教师提供职业发展指导，包含教学、科研、学术交流等方面的发展建议。',
            'url': 'https://www.nankai.edu.cn/faculty/development',
            'score': 10.3,
            'is_attachment': False
        },
        {
            'title': '南开大学行政管理制度汇编',
            'snippet': '包含各类行政管理制度、办事流程、服务指南等内容，为行政人员提供工作参考。',
            'url': 'https://www.nankai.edu.cn/admin/regulations',
            'score': 9.7,
            'is_attachment': False
        }
    ]
    
    # 测试不同用户的个性化排序
    test_cases = [
        ('计算机学院', '博士生'),
        ('计算机学院', '本科生'),
        ('历史学院', '研究生'),
        ('政府管理学院', '教师'),
        ('文学院', '行政')
    ]
    
    for college, role in test_cases:
        print(f"\n--- 测试用户: {college} - {role} ---")
        
        # 进行个性化排序
        ranked_results = ranker.rerank_results(mock_results.copy(), college, role)
        
        # 获取统计信息
        stats = ranker.get_personalization_stats(ranked_results, college, role)
        
        print(f"个性化统计:")
        print(f"  学院匹配: {stats['college_matched']} 个结果")
        print(f"  身份匹配: {stats['role_matched']} 个结果")
        print(f"  域名匹配: {stats['domain_matched']} 个结果")
        print(f"  平均个性化分数: {stats['avg_personalized_score']:.3f}")
        
        print(f"\n排序后的结果:")
        for i, result in enumerate(ranked_results[:3], 1):  # 只显示前3个
            print(f"  {i}. {result['title'][:50]}...")
            print(f"     原始分数: {result['score']:.1f} | 个性化分数: {result.get('personalized_score', 0):.3f} | 综合分数: {result.get('final_score', 0):.3f}")
    
    print("\n=== 个性化关键词测试 ===")
    
    # 测试关键词匹配
    print("\n计算机学院的关键词:", ranker.college_keywords.get('计算机学院', [])[:10])
    print("博士生的关键词:", ranker.role_keywords.get('博士生', []))
    
    # 测试域名权重
    print("\n相关域名权重:")
    for domain, weights in ranker.domain_weights.items():
        if '计算机学院' in weights:
            print(f"  {domain}: {weights['计算机学院']}")

def test_content_scoring():
    """测试内容评分功能"""
    print("\n=== 内容评分测试 ===")
    
    ranker = PersonalizedRanking()
    
    test_result = {
        'title': '南开大学计算机学院机器学习课程',
        'snippet': '面向研究生的高级机器学习课程，涵盖深度学习、神经网络等前沿算法。',
        'url': 'https://cc.nankai.edu.cn/courses/ml',
        'score': 12.0
    }
    
    # 测试不同用户的内容评分
    users = [
        ('计算机学院', '研究生'),
        ('数学科学学院', '研究生'),
        ('计算机学院', '本科生'),
        ('文学院', '本科生')
    ]
    
    for college, role in users:
        score = ranker.calculate_personalized_score(test_result, college, role)
        print(f"{college}-{role}: 个性化分数 = {score:.3f}")

if __name__ == "__main__":
    test_personalized_ranking()
    test_content_scoring()
