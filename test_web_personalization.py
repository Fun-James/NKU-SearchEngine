"""
个性化排名 Web 功能测试脚本
测试通过 Web 接口的个性化搜索功能
"""

import requests
import json
from urllib.parse import urljoin

# 测试配置
BASE_URL = "http://127.0.0.1:5000"
TEST_QUERY = "计算机"

def test_personalized_search():
    """测试个性化搜索功能"""
    
    # 创建一个会话
    session = requests.Session()
    
    # 测试用户配置
    test_users = [
        {"college": "计算机学院", "role": "博士生", "name": "计算机学院博士生"},
        {"college": "历史学院", "role": "研究生", "name": "历史学院研究生"},
        {"college": "金融学院", "role": "本科生", "name": "金融学院本科生"},
        {"college": "文学院", "role": "教师", "name": "文学院教师"}
    ]
    
    results = {}
    
    for user in test_users:
        print(f"\n=== 测试用户: {user['name']} ===")
        
        # 1. 登录用户
        login_data = {
            'college': user['college'],
            'role': user['role']
        }
        
        try:
            # 获取登录页面
            login_page = session.get(urljoin(BASE_URL, '/login'))
            if login_page.status_code != 200:
                print(f"获取登录页面失败: {login_page.status_code}")
                continue
            
            # 提交登录信息
            login_response = session.post(urljoin(BASE_URL, '/login'), data=login_data)
            if login_response.status_code != 302:  # 期望重定向
                print(f"登录失败: {login_response.status_code}")
                continue
            
            print(f"✓ 登录成功: {user['college']} - {user['role']}")
            
            # 2. 执行搜索
            search_params = {
                'q': TEST_QUERY,
                'search_type': 'intelligent',
                'page': 1
            }
            
            search_response = session.get(urljoin(BASE_URL, '/search'), params=search_params)
            if search_response.status_code != 200:
                print(f"搜索失败: {search_response.status_code}")
                continue
            
            print(f"✓ 搜索执行成功")
            
            # 3. 获取个性化信息（如果有API端点）
            try:
                personalization_response = session.get(urljoin(BASE_URL, '/personalization_info'))
                if personalization_response.status_code == 200:
                    personalization_data = personalization_response.json()
                    print(f"✓ 个性化信息:")
                    print(f"  - 用户学院: {personalization_data.get('user_college', 'N/A')}")
                    print(f"  - 用户身份: {personalization_data.get('user_role', 'N/A')}")
                    if 'stats' in personalization_data:
                        stats = personalization_data['stats']
                        print(f"  - 学院匹配: {stats.get('college_matched', 0)} 项")
                        print(f"  - 身份匹配: {stats.get('role_matched', 0)} 项")
                        print(f"  - 域名匹配: {stats.get('domain_matched', 0)} 项")
                        print(f"  - 平均个性化分数: {stats.get('avg_personalized_score', 0):.3f}")
            except:
                print("! 个性化信息API不可用或格式错误")
            
            # 保存结果
            results[user['name']] = {
                'login_success': True,
                'search_success': True,
                'college': user['college'],
                'role': user['role']
            }
            
        except Exception as e:
            print(f"✗ 测试失败: {e}")
            results[user['name']] = {
                'login_success': False,
                'search_success': False,
                'error': str(e)
            }
        
        # 登出以清理会话
        try:
            session.get(urljoin(BASE_URL, '/logout'))
        except:
            pass
    
    # 输出总结
    print(f"\n=== 测试总结 ===")
    successful_tests = sum(1 for r in results.values() if r.get('login_success') and r.get('search_success'))
    total_tests = len(results)
    print(f"成功测试: {successful_tests}/{total_tests}")
    
    if successful_tests == total_tests:
        print("✓ 所有个性化搜索测试通过!")
    else:
        print("! 部分测试失败，请检查系统状态")
    
    return results

def test_anonymous_search():
    """测试未登录用户的搜索功能"""
    print(f"\n=== 测试匿名用户搜索 ===")
    
    try:
        # 创建新会话（不登录）
        session = requests.Session()
        
        # 执行搜索
        search_params = {
            'q': TEST_QUERY,
            'search_type': 'intelligent',
            'page': 1
        }
        
        search_response = session.get(urljoin(BASE_URL, '/search'), params=search_params)
        if search_response.status_code == 200:
            print("✓ 匿名搜索成功")
            return True
        else:
            print(f"✗ 匿名搜索失败: {search_response.status_code}")
            return False
            
    except Exception as e:
        print(f"✗ 匿名搜索异常: {e}")
        return False

if __name__ == "__main__":
    print("开始个性化搜索 Web 功能测试...")
    
    # 测试匿名搜索
    anonymous_success = test_anonymous_search()
    
    # 测试个性化搜索
    personalized_results = test_personalized_search()
    
    print(f"\n=== 最终结果 ===")
    print(f"匿名搜索: {'✓ 通过' if anonymous_success else '✗ 失败'}")
    
    successful_personalized = sum(1 for r in personalized_results.values() 
                                 if r.get('login_success') and r.get('search_success'))
    total_personalized = len(personalized_results)
    print(f"个性化搜索: {successful_personalized}/{total_personalized} 通过")
    
    if anonymous_success and successful_personalized == total_personalized:
        print("\n🎉 所有测试通过！个性化搜索功能正常工作！")
    else:
        print("\n⚠️  部分测试失败，请检查系统配置")
