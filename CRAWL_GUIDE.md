# 大规模网站爬取指南

## 概述

本工具支持爬取南开大学主站及所有学院网站，目标是爬取不少于10万个网页。

## 新增功能

### 1. 多网站批量爬取
- 支持同时爬取南开大学主站和27个学院网站
- 智能分配每个网站的爬取页面数量
- 自动处理不同网站的特殊情况

### 2. 灵活的参数配置
```bash
# 完整参数列表
python crawl_and_index.py --total-pages 100000 --main-ratio 0.3 --delay 0.3 --max-depth 6 --skip-robots

# 仅爬取学院网站
python crawl_and_index.py --total-pages 50000 --colleges-only --delay 0.2

# 仅爬取主站
python crawl_and_index.py --total-pages 30000 --main-only --delay 0.2
```

### 3. 分批次爬取策略
使用 `batch_crawl.py` 进行分批次爬取，避免长时间运行的风险。

## 快速开始

### 方法1: 使用批处理脚本 (推荐)
```bash
# Windows用户
start_crawl.bat

# 然后按提示选择爬取规模
```

### 方法2: 使用Python脚本
```bash
# 启动分批次爬取工具
python batch_crawl.py

# 或直接爬取
python crawl_and_index.py --total-pages 100000 --main-ratio 0.09 --delay 0.3
```

### 方法3: 监控爬取进度
```bash
# 在另一个终端窗口运行监控
python monitor_crawl.py --target 100000 --interval 30
```

## 爬取策略说明

### 页面分配策略
- **南开主站**: 9% (约9,000页)
- **各学院网站**: 91% (约91,000页，平均每个学院约3,370页)

### 学院网站列表 (27个)
#### 人文社科类 (11个)
- 文学院、历史学院、哲学院、外国语学院、法学院
- 周恩来政府管理学院、马克思主义学院、汉语言文化学院
- 新闻与传播学院、社会学院、旅游与服务学院

#### 经济管理类 (3个)
- 经济学院、商学院、金融学院

#### 理工类 (11个)
- 数学科学学院、物理科学学院、化学学院、生命科学学院
- 环境科学与工程学院、材料科学与工程学院、电子信息与光学工程学院
- 计算机学院、网络空间安全学院、人工智能学院、统计与数据科学学院

#### 医学类 (2个)
- 医学院、药学院

## 推荐的爬取方案

### 方案A: 一次性完整爬取
适合网络稳定、时间充裕的情况
```bash
python crawl_and_index.py --total-pages 100000 --main-ratio 0.09 --delay 0.3 --max-depth 6 --skip-robots
```

### 方案B: 分批次爬取 (推荐)
适合大多数情况，降低风险
```bash
python batch_crawl.py
# 选择 "5. 分批次爬取"
# 建议配置: 7批次，每批次15000页，间隔5分钟
```

### 方案C: 分类别爬取
先爬取重要内容，再补充其他内容
```bash
# 第一阶段: 爬取主站
python crawl_and_index.py --total-pages 40000 --main-only --delay 0.2

# 第二阶段: 爬取理工类学院
python crawl_and_index.py --total-pages 35000 --colleges-only --delay 0.2

# 第三阶段: 爬取其他学院
# ... 继续爬取
```

## 监控和管理

### 实时监控
```bash
# 监控爬取进度
python monitor_crawl.py --target 100000 --interval 30

# 查看当前统计
python monitor_crawl.py --stats-only
```

### 检查索引状态
```bash
# 检查索引内容
python check_index_new.py

# 删除索引重新开始
python delete_indices.py
```

## 性能优化建议

### 1. 爬取参数调优
- **延迟时间**: 0.2-0.5秒 (根据网络情况调整)
- **最大深度**: 6-8层 (平衡覆盖度和效率)
- **并发数**: 通过调整延迟间接控制

### 2. 系统资源
- **内存**: 建议8GB以上
- **磁盘**: 确保有10GB以上可用空间
- **网络**: 稳定的互联网连接

### 3. Elasticsearch优化
```bash
# 增加堆内存 (在elasticsearch.yml中)
-Xms2g
-Xmx4g

# 调整刷新间隔
PUT /nku_web/_settings
{
  "refresh_interval": "30s"
}
```

## 故障处理

### 常见问题
1. **连接超时**: 增加延迟时间，检查网络连接
2. **内存不足**: 使用分批次爬取，减少单次爬取量
3. **索引失败**: 检查Elasticsearch服务状态和磁盘空间

### 恢复策略
```bash
# 查看当前已爬取数量
python monitor_crawl.py --stats-only

# 继续爬取剩余部分
python crawl_and_index.py --total-pages [剩余数量] --colleges-only
```

## 验证结果

### 检查爬取质量
```bash
# 查看索引统计
curl -X GET "localhost:9200/nku_web/_stats?pretty"

# 查看样本文档
curl -X GET "localhost:9200/nku_web/_search?size=5&pretty"

# 检查各个域名的分布
curl -X GET "localhost:9200/nku_web/_search?pretty" -H 'Content-Type: application/json' -d'
{
  "size": 0,
  "aggs": {
    "domains": {
      "terms": {
        "field": "domain.keyword",
        "size": 30
      }
    }
  }
}'
```

### 预期结果
- 总文档数: ≥ 100,000
- 覆盖域名: 28个 (主站 + 27个学院)
- 索引大小: 约1-3GB
- 平均文档大小: 10-30KB

## 注意事项

1. **尊重robots.txt**: 虽然可以跳过，但建议在合理范围内遵守
2. **网络礼貌**: 设置适当的延迟，避免对服务器造成压力
3. **监控进度**: 长时间爬取时要定期检查进度和系统状态
4. **备份数据**: 重要的爬取结果应该及时备份

## 技术支持

如遇到问题，可以:
1. 查看终端输出的错误信息
2. 检查Elasticsearch日志
3. 使用监控工具查看当前状态
4. 尝试分批次爬取降低单次任务复杂度
