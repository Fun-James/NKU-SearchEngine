"""
个性化查询排序模块
根据用户的学院和身份信息对搜索结果进行个性化排序
"""

import re
from collections import defaultdict
from urllib.parse import urlparse


class PersonalizedRanking:
    """个性化排序器"""
    
    def __init__(self):        # 学院关键词映射
        self.college_keywords = {
            # 人文社科类院系
            '文学院': ['文学', '语言', '文字', '诗歌', '小说', '散文', '古典文学', '现代文学', '中文', '汉语'],
            '历史学院': ['历史', '史学', '古代史', '近代史', '现代史', '世界史', '中国史'],
            '哲学院': ['哲学', '思想', '伦理', '逻辑', '美学', '中国哲学', '西方哲学'],
            '外国语学院': ['外语', '英语', '日语', '法语', '德语', '俄语', '翻译', '口译', '外语教学'],
            '法学院': ['法学', '法律', '民法', '刑法', '宪法', '国际法', '法理学', '司法'],
            '周恩来政府管理学院': ['政治', '行政', '公共管理', '政府', '政策', '社会治理', '政治学'],
            '马克思主义学院': ['马克思主义', '政治理论', '思想政治', '党史', '毛概', '马原'],
            '汉语言文化学院': ['汉语', '中文', '汉字', '中国文化', '对外汉语', '语言文化'],
            '新闻与传播学院': ['新闻', '传播', '媒体', '广告', '公关', '新媒体', 'journalism', '传媒'],
            '社会学院': ['社会学', '社会', '社会工作', '人类学', '社会调查', '社会科学'],
            '旅游与服务学院': ['旅游', '酒店', '服务', '旅游管理', '休闲', '旅游业'],
            
            # 经济管理类院系
            '经济学院': ['经济', '宏观经济', '微观经济', '经济学', '产业经济', '国际经济'],
            '商学院': ['商业', '管理', '企业管理', '市场营销', '工商管理', 'MBA', '商务'],
            '金融学院': ['金融', '银行', '投资', '证券', '保险', '财务', '会计', '金融学'],
            
            # 理工类院系
            '数学科学学院': ['数学', '统计', '概率', '线性代数', '微积分', '数论', '几何', '数学分析'],
            '物理科学学院': ['物理', '力学', '热学', '电磁学', '光学', '量子', '原子物理', '物理学'],
            '化学学院': ['化学', '有机化学', '无机化学', '物理化学', '分析化学', '化工', '化学工程'],
            '生命科学学院': ['生物', '生命科学', '遗传学', '生态学', '分子生物学', '细胞生物学', '生物技术'],
            '环境科学与工程学院': ['环境', '环保', '生态', '污染', '环境工程', '环境科学', '可持续发展'],
            '材料科学与工程学院': ['材料', '材料工程', '材料科学', '高分子', '金属材料', '复合材料'],
            '电子信息与光学工程学院': ['电子', '光学', '通信', '信号处理', '电路', '光电', '微电子', '信息工程'],
            '计算机学院': ['计算机', '软件', 'AI', '人工智能', '算法', '编程', '程序', '代码', '系统', '网络', '数据库'],
            '网络空间安全学院': ['网络安全', '信息安全', '密码学', '防火墙', '入侵检测', '安全协议', '网络安全'],
            '人工智能学院': ['人工智能', 'AI', '机器学习', '深度学习', '神经网络', '智能系统', '数据挖掘'],
            '软件学院': ['软件', '编程', '开发', '程序设计', '系统开发', '应用开发', '软件工程'],
            '统计与数据科学学院': ['统计', '数据科学', '大数据', '数据分析', '统计学', '数据挖掘', '数据处理'],
            
            # 医学类院系
            '医学院': ['医学', '临床', '病理', '解剖', '生理', '药理', '医疗', '健康', '疾病', '临床医学'],
            '药学院': ['药学', '药物', '制药', '药理', '药剂', '临床药学', '药物研发']
        }
        
        # 身份关键词映射
        self.role_keywords = {
            '本科生': ['本科', '学士', '本科生', '大学生', '本科教育', '基础课程', '通识教育'],
            '研究生': ['研究生', '硕士', '研究', '学术', '论文', '导师', '研究方向'],
            '博士生': ['博士', 'PhD', '博士生', '博士论文', '学术研究', '科研', '博士后'],
            '教师': ['教师', '教授', '副教授', '讲师', '师资', '教学', '科研', '学术', '课程'],
            '行政': ['行政', '管理', '办公', '服务', '通知', '公告', '规定', '制度', '流程']
        }
          # URL域名权重映射（基于学院相关性）
        self.domain_weights = {
            # 人文社科类
            'wxy.nankai.edu.cn': {'文学院': 2.0},
            'history.nankai.edu.cn': {'历史学院': 2.0},
            'phil.nankai.edu.cn': {'哲学院': 2.0},
            'sfs.nankai.edu.cn': {'外国语学院': 2.0},
            'law.nankai.edu.cn': {'法学院': 2.0},
            'zfxy.nankai.edu.cn': {'周恩来政府管理学院': 2.0},
            'cz.nankai.edu.cn': {'马克思主义学院': 2.0},
            'hyxy.nankai.edu.cn': {'汉语言文化学院': 2.0},
            'jc.nankai.edu.cn': {'新闻与传播学院': 2.0},
            'shxy.nankai.edu.cn': {'社会学院': 2.0},
            'tas.nankai.edu.cn': {'旅游与服务学院': 2.0},
            
            # 经济管理类
            'economics.nankai.edu.cn': {'经济学院': 2.0},
            'bs.nankai.edu.cn': {'商学院': 2.0},
            'finance.nankai.edu.cn': {'金融学院': 2.0},
            
            # 理工类
            'math.nankai.edu.cn': {'数学科学学院': 2.0, '统计与数据科学学院': 1.3},
            'physics.nankai.edu.cn': {'物理科学学院': 2.0},
            'chem.nankai.edu.cn': {'化学学院': 2.0},
            'sky.nankai.edu.cn': {'生命科学学院': 2.0},
            'env.nankai.edu.cn': {'环境科学与工程学院': 2.0},
            'mse.nankai.edu.cn': {'材料科学与工程学院': 2.0},
            'ceo.nankai.edu.cn': {'电子信息与光学工程学院': 2.0},
            'cc.nankai.edu.cn': {'计算机学院': 2.0, '软件学院': 2.0},
            'cyber.nankai.edu.cn': {'网络空间安全学院': 2.0},
            'ai.nankai.edu.cn': {'人工智能学院': 2.0, '计算机学院': 1.5},
            'stat.nankai.edu.cn': {'统计与数据科学学院': 2.0, '数学科学学院': 1.3},
            
            # 医学类
            'medical.nankai.edu.cn': {'医学院': 2.0},
            'pharmacy.nankai.edu.cn': {'药学院': 2.0}
        }
        
        # 身份相关的URL路径权重
        self.path_weights = {
            '/undergraduate/': {'本科生': 1.5},
            '/graduate/': {'研究生': 1.5, '博士生': 1.5},
            '/phd/': {'博士生': 2.0},
            '/faculty/': {'教师': 2.0},
            '/admin/': {'行政': 2.0},
            '/notice/': {'行政': 1.3, '教师': 1.2},
            '/course/': {'本科生': 1.3, '研究生': 1.2, '教师': 1.5},
            '/research/': {'研究生': 1.5, '博士生': 2.0, '教师': 1.8},
            '/academic/': {'研究生': 1.3, '博士生': 1.5, '教师': 1.5}
        }
    
    def calculate_personalized_score(self, result, user_college, user_role):
        """
        计算个性化分数
        
        参数:
        - result: 搜索结果字典 (包含title, snippet, url, score等字段)
        - user_college: 用户学院
        - user_role: 用户身份
        
        返回:
        - 个性化分数 (0-1之间的浮点数)
        """
        base_score = 0.0
        
        # 1. 基于内容的匹配分数
        content_score = self._calculate_content_score(result, user_college, user_role)
        
        # 2. 基于URL的匹配分数
        url_score = self._calculate_url_score(result.get('url', ''), user_college, user_role)
        
        # 3. 基于文档类型的匹配分数
        doc_type_score = self._calculate_doc_type_score(result, user_role)
        
        # 加权组合
        personalized_score = (
            content_score * 0.5 +
            url_score * 0.3 +
            doc_type_score * 0.2
        )
        
        return min(1.0, max(0.0, personalized_score))
    
    def _calculate_content_score(self, result, user_college, user_role):
        """基于内容的匹配分数"""
        score = 0.0
        
        # 获取文本内容
        title = result.get('title', '').lower()
        snippet = result.get('snippet', '').lower()
        content = f"{title} {snippet}"
        
        # 学院关键词匹配
        if user_college in self.college_keywords:
            college_keywords = self.college_keywords[user_college]
            for keyword in college_keywords:
                if keyword.lower() in content:
                    score += 0.1  # 每个匹配的关键词增加0.1分
        
        # 身份关键词匹配
        if user_role in self.role_keywords:
            role_keywords = self.role_keywords[user_role]
            for keyword in role_keywords:
                if keyword.lower() in content:
                    score += 0.05  # 每个匹配的身份关键词增加0.05分
        
        return min(1.0, score)
    
    def _calculate_url_score(self, url, user_college, user_role):
        """基于URL的匹配分数"""
        if not url:
            return 0.0
        
        score = 0.0
        
        try:
            parsed_url = urlparse(url)
            domain = parsed_url.netloc.lower()
            path = parsed_url.path.lower()
            
            # 域名权重匹配
            if domain in self.domain_weights:
                domain_weights = self.domain_weights[domain]
                if user_college in domain_weights:
                    score += domain_weights[user_college] * 0.3
            
            # 路径权重匹配
            for path_pattern, weights in self.path_weights.items():
                if path_pattern in path:
                    if user_role in weights:
                        score += weights[user_role] * 0.2
                        
        except Exception:
            pass
        
        return min(1.0, score)
    
    def _calculate_doc_type_score(self, result, user_role):
        """基于文档类型的匹配分数"""
        score = 0.0
        
        # 获取文件类型
        file_type = result.get('file_type', '').lower()
        is_attachment = result.get('is_attachment', False)
        
        # 不同身份对不同文档类型的偏好
        doc_type_preferences = {
            '本科生': {
                'pdf': 0.1,  # 课件、教材
                'ppt': 0.15,  # 课堂演示
                'doc': 0.05,  # 作业要求
                'webpage': 0.1  # 一般网页内容
            },
            '研究生': {
                'pdf': 0.2,  # 论文、研究资料
                'doc': 0.1,  # 研究计划
                'ppt': 0.1,  # 学术演示
                'webpage': 0.15  # 学术网页
            },
            '博士生': {
                'pdf': 0.25,  # 高级研究资料
                'doc': 0.15,  # 研究文档
                'webpage': 0.2  # 学术资源
            },
            '教师': {
                'pdf': 0.2,  # 教学资料、研究论文
                'ppt': 0.2,  # 教学课件
                'doc': 0.15,  # 教学文档
                'webpage': 0.15  # 学术网页
            },
            '行政': {
                'doc': 0.2,  # 公文、通知
                'pdf': 0.15,  # 正式文件
                'webpage': 0.1  # 网页通知
            }
        }
        
        if user_role in doc_type_preferences:
            preferences = doc_type_preferences[user_role]
            
            if is_attachment and file_type:
                # 提取文件扩展名
                if 'pdf' in file_type.lower():
                    score += preferences.get('pdf', 0)
                elif any(x in file_type.lower() for x in ['ppt', 'powerpoint']):
                    score += preferences.get('ppt', 0)
                elif any(x in file_type.lower() for x in ['doc', 'word']):
                    score += preferences.get('doc', 0)
            else:
                score += preferences.get('webpage', 0)
        
        return score
    
    def rerank_results(self, results, user_college, user_role):
        """
        对搜索结果进行个性化重排序
        
        参数:
        - results: 原始搜索结果列表
        - user_college: 用户学院
        - user_role: 用户身份
        
        返回:
        - 重排序后的结果列表
        """
        if not results or not user_college or not user_role:
            return results
        
        # 为每个结果计算个性化分数
        scored_results = []
        for result in results:
            personalized_score = self.calculate_personalized_score(result, user_college, user_role)
            
            # 结合原始ES分数和个性化分数
            original_score = result.get('score', 0)
            
            # 归一化原始分数 (假设最高分为20，根据实际情况调整)
            normalized_original = min(1.0, original_score / 20.0)
            
            # 综合分数：70%原始分数 + 30%个性化分数
            final_score = normalized_original * 0.7 + personalized_score * 0.3
            
            scored_results.append({
                'result': result,
                'final_score': final_score,
                'original_score': original_score,
                'personalized_score': personalized_score
            })
        
        # 按综合分数排序
        scored_results.sort(key=lambda x: x['final_score'], reverse=True)
        
        # 返回重排序后的结果，并添加个性化信息
        reranked_results = []
        for scored_result in scored_results:
            result = scored_result['result'].copy()
            result['personalized_score'] = scored_result['personalized_score']
            result['final_score'] = scored_result['final_score']
            reranked_results.append(result)
        
        return reranked_results
    
    def get_personalization_stats(self, results, user_college, user_role):
        """
        获取个性化统计信息
        
        返回:
        - 包含个性化统计信息的字典
        """
        if not results:
            return {}
        
        stats = {
            'total_results': len(results),
            'college_matched': 0,
            'role_matched': 0,
            'domain_matched': 0,
            'avg_personalized_score': 0.0
        }
        
        total_personalized_score = 0.0
        
        for result in results:
            p_score = self.calculate_personalized_score(result, user_college, user_role)
            total_personalized_score += p_score
            
            # 统计匹配情况
            content = f"{result.get('title', '')} {result.get('snippet', '')}".lower()
            
            # 学院匹配
            if user_college in self.college_keywords:
                for keyword in self.college_keywords[user_college]:
                    if keyword.lower() in content:
                        stats['college_matched'] += 1
                        break
            
            # 身份匹配
            if user_role in self.role_keywords:
                for keyword in self.role_keywords[user_role]:
                    if keyword.lower() in content:
                        stats['role_matched'] += 1
                        break
            
            # 域名匹配
            url = result.get('url', '')
            if url:
                try:
                    domain = urlparse(url).netloc.lower()
                    if domain in self.domain_weights and user_college in self.domain_weights[domain]:
                        stats['domain_matched'] += 1
                except Exception:
                    pass
        
        stats['avg_personalized_score'] = total_personalized_score / len(results)
        
        return stats
